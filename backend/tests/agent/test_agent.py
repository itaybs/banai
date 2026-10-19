"""Agent turn + proposal protocol with a mocked OpenAI client (no network)."""

from __future__ import annotations

import copy
import logging
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.language import FALLBACK_REPLY, OFF_TOPIC_REPLY, detect, reply_language
from app.agent.orchestrator import MAX_REPAIRS, fill_ids
from app.agent.prompts import build_system_prompt, derived_facts
from app.agent.tools import ANSWER, CLARIFY, DECLINE, PRODUCTION_CLAIM, PROPOSE, ProposeArgs
from app.api.agent import MESSAGE_TEXT_PATTERN, get_llm_client
from app.config import get_settings, get_signing_key
from app.domain.apply import apply_ops
from app.domain.catalog import load_catalog
from app.domain.defaults import basic_wardrobe
from app.domain.schema import SAFE_TEXT_PATTERN
from app.main import create_app
from app.services import signing
from tests.agent.fakes import FakeClient, completion, propose, tool_call

ADD_SHELF = {"op": "add_shelf", "compartmentId": "cmp_left", "y": 1000}
OVERLAPPING_SHELF = {"op": "add_shelf", "compartmentId": "cmp_left", "y": 405}  # overlaps shf_l1 at 400


@pytest.fixture
def make_client(monkeypatch):
    """A TestClient whose agent uses the given fake OpenAI client."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("PROPOSAL_SIGNING_KEY", "test-signing-key")
    get_settings.cache_clear()
    get_signing_key.cache_clear()

    def build(fake):
        app = create_app()
        app.dependency_overrides[get_llm_client] = lambda: fake
        return TestClient(app)

    yield build
    get_settings.cache_clear()
    get_signing_key.cache_clear()


def chat_body(text="Add a shelf at 100 cm on the left", design=None, revision=1):
    return {"messages": [{"role": "user", "text": text}], "design": design or basic_wardrobe(), "revision": revision}


def test_every_turn_must_use_a_tool_and_free_text_is_never_shown(make_client):
    fake = FakeClient(completion(content="The weather today is sunny!"))
    data = make_client(fake).post("/api/chat", json=chat_body("מה מזג האוויר היום?")).json()["data"]
    assert data == {"reply": OFF_TOPIC_REPLY["he"], "replySignature": signing.sign_reply(get_signing_key(), data["reply"]), "proposal": None}
    request = fake.requests[0]
    assert request["model"]
    assert request["tool_choice"] == "required"
    assert {tool["function"]["name"] for tool in request["tools"]} == {PROPOSE, CLARIFY, ANSWER, DECLINE}
    assert request["messages"][0]["role"] == "system"
    assert "Scope (strict)" in request["messages"][0]["content"]
    assert '"cmp_left"' in request["messages"][0]["content"]  # the current design is in context
    assert request["messages"][-1] == {"role": "user", "content": "מה מזג האוויר היום?"}


def test_system_prompt_carries_the_review_rules():
    prompt = build_system_prompt(basic_wardrobe(), load_catalog(), "he")
    assert '"[app] applied: <summary>"' in prompt and "only source of truth" in prompt  # R3
    assert "## Customer-dictated wording" in prompt  # R1
    assert "less than 90 cm of free height" in prompt and "at least 150 cm" in prompt  # R4
    assert "offer 2-3 concrete options" in prompt  # R5
    assert "state the allowed range" in prompt  # R6
    assert "real change made by `ops`" in prompt  # R7
    assert "never past tense" in prompt  # R8
    assert "gender-neutral" in prompt and "gender-neutral" not in build_system_prompt(basic_wardrobe(), load_catalog(), "en")  # R9
    # Static rules first, per-turn data last (keeps the provider's prompt cache effective).
    assert prompt.index("## Practical layout checks") < prompt.index("## Current design")


def test_derived_facts_give_clear_heights_below_rails_and_between_shelves():
    # R4: the model got only free spans and never worked out the gap under a rail itself.
    design = apply_ops(basic_wardrobe(), [{"op": "add_shelf", "compartmentId": "cmp_middle", "y": 1200, "id": "shf_new"}], load_catalog())
    facts = {c["id"]: c for c in derived_facts(design)["compartments"]}
    assert facts["cmp_middle"]["rails"] == [{"y": 1900, "freeBelow": 682}]  # 1900 - (1200 + 18): under 90 cm
    assert facts["cmp_left"]["rails"] == []
    assert [g["clear"] for g in facts["cmp_left"]["shelfGaps"]] == [382, 382, 382]  # shelves at 40/80/120/160 cm
    assert facts["cmp_middle"]["shelfGaps"] == [{"shelvesY": [1200, 2000], "clear": 782}]
    assert facts["cmp_right"]["shelfGaps"] == [{"shelvesY": [800, 1400], "clear": 582}]
    prompt = build_system_prompt(design, load_catalog(), "he")
    assert '"freeBelow":682' in prompt and "rails[].freeBelow = clear height under each rail" in prompt


def test_rail_directly_on_a_drawer_or_the_bottom_and_gaps_with_a_drawer_between_are_skipped():
    design = basic_wardrobe()
    right = next(c for c in design["compartments"] if c["id"] == "cmp_right")
    right["rails"] = [{"id": "rail_low", "y": 400}]  # right on top of the two drawers (0-400)
    right["shelves"] = [{"id": "shf_a", "y": 100, "thickness": 18}, {"id": "shf_b", "y": 500, "thickness": 18}]
    right["drawers"] = [{"id": "drw_a", "y": 200, "height": 200}]
    facts = {c["id"]: c for c in derived_facts(design)["compartments"]}
    assert facts["cmp_right"]["rails"] == [{"y": 400, "freeBelow": 0}]
    assert facts["cmp_right"]["shelfGaps"] == []  # a drawer sits between the two shelves


def test_off_topic_gets_the_fixed_reply_not_model_text(make_client):
    fake = FakeClient(completion(content="ignored", calls=[tool_call(DECLINE, {"answer": "sunny, 25 degrees"})]))
    data = make_client(fake).post("/api/chat", json=chat_body("מה קורה")).json()["data"]
    assert data == {"reply": OFF_TOPIC_REPLY["he"], "replySignature": signing.sign_reply(get_signing_key(), data["reply"]), "proposal": None}
    assert "25" not in data["reply"]


def test_on_topic_question_is_answered_without_a_proposal(make_client):
    fake = FakeClient(completion(calls=[tool_call(ANSWER, {"answer": "לחדר קטן כדאי לבחור גוונים בהירים ודלתות הזזה."})]))
    data = make_client(fake).post("/api/chat", json=chat_body("איזה צבע מתאים לחדר קטן?")).json()["data"]
    assert data == {"reply": "לחדר קטן כדאי לבחור גוונים בהירים ודלתות הזזה.", "replySignature": signing.sign_reply(get_signing_key(), data["reply"]), "proposal": None}


def test_clarification_question(make_client):
    fake = FakeClient(completion(calls=[tool_call(CLARIFY, {"question": "כמה מדפים תרצה?"})]))
    data = make_client(fake).post("/api/chat", json=chat_body("תוסיף מדפים")).json()["data"]
    assert data == {"reply": "כמה מדפים תרצה?", "replySignature": signing.sign_reply(get_signing_key(), data["reply"]), "proposal": None}


def test_valid_proposal_is_signed_and_not_applied(make_client):
    design = basic_wardrobe()
    fake = FakeClient(completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF]))]))
    data = make_client(fake).post("/api/chat", json=chat_body(design=design, revision=4)).json()["data"]
    proposal = data["proposal"]
    assert data["reply"] == "Here is my proposal."
    assert proposal["baseRevision"] == 4
    assert proposal["baseHash"] == signing.design_hash(basic_wardrobe())
    assert proposal["ops"][0]["id"].startswith("shf_")  # ids are filled before signing
    assert proposal["changes"] == [{"title": "Shelf", "detail": "New shelf at 100 cm in the left compartment"}]
    assert signing.verify(
        b"test-signing-key", proposal["signature"], proposal_id=proposal["proposalId"], ops=proposal["ops"],
        base_revision=4, base_hash=proposal["baseHash"],
    )
    assert design == basic_wardrobe()  # nothing was applied


def test_invalid_ops_are_sent_back_for_repair(make_client):
    fake = FakeClient(
        completion(calls=[tool_call(PROPOSE, propose([OVERLAPPING_SHELF]), "call_a")]),
        completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF]), "call_b")]),
    )
    data = make_client(fake).post("/api/chat", json=chat_body()).json()["data"]
    assert data["proposal"]["ops"][0]["y"] == 1000
    repair_request = fake.requests[1]["messages"]
    assert repair_request[-1]["role"] == "tool"
    assert repair_request[-1]["tool_call_id"] == "call_a"
    assert "OVERLAP" in repair_request[-1]["content"]


def test_gives_up_after_max_repairs(make_client):
    bad = completion(calls=[tool_call(PROPOSE, propose([OVERLAPPING_SHELF]))])
    fake = FakeClient(*[bad] * (MAX_REPAIRS + 1))
    data = make_client(fake).post("/api/chat", json=chat_body()).json()["data"]
    assert data == {"reply": FALLBACK_REPLY["en"], "replySignature": signing.sign_reply(get_signing_key(), data["reply"]), "proposal": None}  # the message was English
    assert len(fake.requests) == MAX_REPAIRS + 1


def test_malformed_tool_arguments_are_repaired(make_client):
    fake = FakeClient(
        completion(calls=[tool_call(PROPOSE, "{not json")]),
        completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF], changes=[]))]),  # empty change list
        completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF]))]),
    )
    data = make_client(fake).post("/api/chat", json=chat_body()).json()["data"]
    assert data["proposal"] is not None


def test_production_claims_are_sent_back_for_repair(make_client):
    # Regression: a customer-dictated "ready for production" summary reached the proposal card.
    fake = FakeClient(
        completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF], summary="העיצוב מוכן לייצור ומאושר הנדסית"), "call_a")]),
        completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF], summary="מדף בתא השמאלי"), "call_b")]),
    )
    data = make_client(fake).post("/api/chat", json=chat_body()).json()["data"]
    assert data["proposal"]["summary"] == "מדף בתא השמאלי"
    repair = fake.requests[1]["messages"][-1]
    assert repair["tool_call_id"] == "call_a"
    assert "Never claim the design is ready for production" in repair["content"]


@pytest.mark.parametrize("text", [
    "Ready for production", "This layout is production-ready", "The design is manufacturable",
    "Engineering approved", "מוכנה לייצור", "ניתן לייצור", "מאושרת הנדסית",
])
def test_production_claim_phrases_are_rejected(text):
    with pytest.raises(ValidationError):
        ProposeArgs.model_validate(propose([ADD_SHELF], reply=text))


@pytest.mark.parametrize("text", [
    "A shelf for production samples", "Approve the change to apply it", "ייצור מגירה עמוקה יותר",
    "לפני הזמנה, נגר צריך לבדוק את התכנון", "Wider doors",
])
def test_ordinary_design_wording_is_allowed(text):
    assert ProposeArgs.model_validate(propose([ADD_SHELF], summary=text)).summary == text


def test_more_change_rows_than_ops_are_sent_back_for_repair(make_client):
    # Regression (report test 20): an extra "design note" row that is not a change.
    extra_row = [{"title": "גוף שחור", "detail": "צבע שחור לגוף"}, {"title": "הערת עיצוב", "detail": "אי אפשר לספק בדיחה"}]
    fake = FakeClient(
        completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF], changes=extra_row), "call_a")]),
        completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF], changes=extra_row[:1]), "call_b")]),
    )
    data = make_client(fake).post("/api/chat", json=chat_body()).json()["data"]
    assert data["proposal"]["changes"] == extra_row[:1]
    repair = fake.requests[1]["messages"][-1]
    assert repair["tool_call_id"] == "call_a" and "more items in changes than ops" in repair["content"]


def test_fewer_change_rows_than_ops_are_fine():
    four_removals = [{"op": "remove_component", "id": f"shf_l{i}"} for i in range(1, 5)]
    args = ProposeArgs.model_validate(propose(four_removals, changes=[{"title": "Left shelves", "detail": "Remove all four"}]))
    assert len(args.changes) == 1 and len(args.ops) == 4


BLOCKED_CLAIMS = [
    "העיצוב מוכן לייצור", "העיצוב מוכן לייצור ומאושר הנדסית", "ניתן לייצור",
    "The design is ready for production", "manufacturable", "engineering approved",
]
ALLOWED_TEXTS = ["אפשר לייצר את זה?", "הדלת מוכנה", "ההצעה מוכנה לאישור", 'מדף בגובה 120 ס"מ', "I suggest adding a shelf"]


@pytest.mark.parametrize("text", BLOCKED_CLAIMS)
@pytest.mark.parametrize("field", ["reply", "summary", "change title", "change detail"])
def test_listed_claims_are_blocked_in_every_agent_output_field(text, field):
    change = {"title": "Shelf", "detail": "New shelf"}
    if field.startswith("change"):
        change[field.split()[1]] = text
        args = propose([ADD_SHELF], changes=[change])
    else:
        args = propose([ADD_SHELF], **{field: text})
    assert PRODUCTION_CLAIM.search(text)
    with pytest.raises(ValidationError, match="Never claim the design is ready for production"):
        ProposeArgs.model_validate(args)


@pytest.mark.parametrize("text", ALLOWED_TEXTS)
def test_listed_texts_are_allowed(text):
    assert not PRODUCTION_CLAIM.search(text)
    args = propose([ADD_SHELF], reply=text, summary=text, changes=[{"title": text, "detail": text}])
    assert ProposeArgs.model_validate(args).summary == text


@pytest.mark.parametrize("text", BLOCKED_CLAIMS)
def test_the_customer_message_is_never_checked_for_claims(make_client, text):
    # Only the agent's output is checked: the customer may write (or ask about) anything.
    fake = FakeClient(completion(calls=[tool_call(ANSWER, {"answer": "BanAI designs are visual drafts."})]))
    response = make_client(fake).post("/api/chat", json=chat_body(text))
    assert response.status_code == 200
    assert fake.requests[0]["messages"][-1]["content"] == text


def test_a_question_about_manufacturing_is_not_blocked(make_client):
    fake = FakeClient(completion(calls=[tool_call(ANSWER, {"answer": "BanAI designs are visual drafts; a carpenter should check them."})]))
    response = make_client(fake).post("/api/chat", json=chat_body("Is this design ready for production?"))
    assert response.status_code == 200
    assert response.json()["data"]["reply"].startswith("BanAI designs are visual drafts")


def test_provider_errors_become_a_generic_502(make_client):
    fake = FakeClient(error=RuntimeError("secret provider detail sk-123"))
    response = make_client(fake).post("/api/chat", json=chat_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AGENT_ERROR"
    assert "sk-123" not in response.text


class ProviderError(Exception):
    """Shaped like openai.APIStatusError: the message may echo provider text, even key fragments."""

    def __init__(self, message, status_code=None, code=None, type=None):
        super().__init__(message)
        self.status_code, self.code, self.type = status_code, code, type


@pytest.mark.parametrize("error", [
    ProviderError("You have no credits remaining. key sk-abc123", status_code=429, code="credit_balance_exhausted", type="insufficient_quota"),
    ProviderError("Incorrect API key provided: sk-abc123", status_code=401, code="invalid_api_key"),
])
def test_account_problems_get_their_own_friendly_message(make_client, caplog, error):
    fake = FakeClient(error=error)
    with caplog.at_level(logging.WARNING, logger="app.api.agent"):
        response = make_client(fake).post("/api/chat", json=chat_body("תוסיף מדף"))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AGENT_ACCOUNT"
    assert "בעיה בחשבון השירות" in response.json()["error"]["message"]
    assert "sk-abc123" not in response.text


def test_agent_failures_log_class_status_and_code_only(make_client, caplog):
    fake = FakeClient(error=ProviderError("Rate limited for key sk-abc123, retry later", status_code=429, code="rate_limit_exceeded"))
    with caplog.at_level(logging.WARNING, logger="app.api.agent"):
        response = make_client(fake).post("/api/chat", json=chat_body())
    assert response.status_code == 502 and response.json()["error"]["code"] == "AGENT_ERROR"  # not an account problem
    logged = [r.getMessage() for r in caplog.records if r.name == "app.api.agent"]
    assert logged == ["agent call failed: ProviderError status=429 code=rate_limit_exceeded"]
    assert "sk-abc123" not in caplog.text and "retry later" not in caplog.text


def test_chat_without_api_key_is_503(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        response = TestClient(create_app()).post("/api/chat", json=chat_body())
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AGENT_UNAVAILABLE"
    finally:
        get_settings.cache_clear()


def test_chat_rejects_invalid_design_and_bad_history(make_client):
    client = make_client(FakeClient())
    broken = basic_wardrobe()
    broken["dimensions"]["width"] = 10
    assert client.post("/api/chat", json=chat_body(design=broken)).status_code == 422
    body = chat_body()
    body["messages"].append({"role": "assistant", "text": "ok"})
    assert client.post("/api/chat", json=body).status_code == 422
    body = chat_body("hi‮")
    assert client.post("/api/chat", json=body).status_code == 422


def test_emoji_joined_with_zwj_is_a_valid_chat_message(make_client):
    # Regression: a family emoji (joined by U+200D) was rejected with 422.
    fake = FakeClient(completion(calls=[tool_call(CLARIFY, {"question": "לאיזה תא?"})]))
    response = make_client(fake).post("/api/chat", json=chat_body("👨‍👩‍👧 ארון משפחתי 😊 תוסיף מדף"))
    assert response.status_code == 200
    assert fake.requests[0]["messages"][-1]["content"] == "👨‍👩‍👧 ארון משפחתי 😊 תוסיף מדף"


def test_app_outcome_notes_reach_the_model_in_order(make_client):
    fake = FakeClient(completion(calls=[tool_call(ANSWER, {"answer": "Both shelves were applied."})]))
    body = chat_body()
    body["messages"] = [
        {"role": "user", "text": "Add a shelf at 100 cm"}, {"role": "assistant", "text": "I suggest a shelf."},
        {"role": "user", "text": "[app] applied: Shelf at 100 cm"}, {"role": "user", "text": "What did I confirm?"},
    ]
    assert make_client(fake).post("/api/chat", json=body).status_code == 200
    sent = [(m["role"], m["content"]) for m in fake.requests[0]["messages"][1:]]
    assert sent[2] == ("user", "[app] applied: Shelf at 100 cm")


def test_message_pattern_differs_from_safe_text_only_by_newline_and_zwj():
    blocked_by_safe = [chr(c) for c in range(0x30000) if not re.fullmatch(SAFE_TEXT_PATTERN, chr(c))]
    allowed_in_messages = {c for c in blocked_by_safe if re.fullmatch(MESSAGE_TEXT_PATTERN, c)}
    assert allowed_in_messages == {"\n", "‍"}
    assert re.fullmatch(MESSAGE_TEXT_PATTERN, "first line\nsecond line")


# ---- applying proposals ----

def _proposal_for(client, revision=1):
    fake_client = client
    return fake_client.post("/api/chat", json=chat_body(revision=revision)).json()["data"]["proposal"]


def test_confirm_applies_the_signed_ops(make_client):
    client = make_client(FakeClient(completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF]))])))
    proposal = _proposal_for(client, revision=3)
    response = client.post("/api/proposals/apply", json={"design": basic_wardrobe(), "revision": 3, "proposal": proposal})
    data = response.json()["data"]
    assert data["revision"] == 4
    shelves = data["design"]["compartments"][0]["shelves"]
    assert any(s["id"] == proposal["ops"][0]["id"] and s["y"] == 1000 for s in shelves)


def test_stale_revision_or_design_is_409(make_client):
    client = make_client(FakeClient(completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF]))])))
    proposal = _proposal_for(client, revision=3)
    newer = client.post("/api/proposals/apply", json={"design": basic_wardrobe(), "revision": 4, "proposal": proposal})
    assert newer.status_code == 409
    assert newer.json()["error"]["code"] == "STALE"
    edited = basic_wardrobe()
    edited["dimensions"]["depth"] = 550
    changed = client.post("/api/proposals/apply", json={"design": edited, "revision": 3, "proposal": proposal})
    assert changed.status_code == 409


def test_tampered_proposal_is_rejected(make_client):
    client = make_client(FakeClient(completion(calls=[tool_call(PROPOSE, propose([ADD_SHELF]))])))
    proposal = _proposal_for(client)
    tampered = copy.deepcopy(proposal)
    tampered["ops"][0]["y"] = 1500
    response = client.post("/api/proposals/apply", json={"design": basic_wardrobe(), "revision": 1, "proposal": tampered})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_SIGNATURE"


def test_fill_ids_covers_new_components_without_touching_input():
    ops = [
        {"op": "add_drawer", "compartmentId": "cmp_left", "y": 0, "height": 200},
        {"op": "add_partition", "compartmentId": "cmp_left", "offset": 300},
        {"op": "create_wardrobe", "width": 2000, "height": 2400, "depth": 600, "compartmentCount": 3},
        {"op": "add_shelf", "compartmentId": "cmp_left", "y": 0, "id": "shf_keep"},
    ]
    original = copy.deepcopy(ops)
    filled = fill_ids(ops)
    assert ops == original
    assert filled[0]["id"].startswith("drw_")
    assert filled[1]["id"].startswith("prt_") and filled[1]["newCompartmentId"].startswith("cmp_")
    assert len(filled[2]["compartmentIds"]) == 3 and len(filled[2]["partitionIds"]) == 2
    assert filled[3]["id"] == "shf_keep"


def test_health_reports_whether_the_agent_is_configured(monkeypatch):
    for value, expected in (("", False), ("k", True)):
        monkeypatch.setenv("OPENAI_API_KEY", value)
        get_settings.cache_clear()
        assert TestClient(create_app()).get("/api/health").json()["data"]["agent"] is expected
    get_settings.cache_clear()


# ---- reply language: the agent answers in the language the message is written in ----

def test_detect_and_reply_language():
    assert detect("תוסיף מדף") == "he"
    assert detect("Add a shelf") == "en"
    assert detect("תצבע ב-Walnut") == "he"  # Hebrew wins in mixed text
    assert detect("240?") is None
    history = [{"role": "user", "text": "שלום"}, {"role": "assistant", "text": "היי"}, {"role": "user", "text": "Add a shelf"}]
    assert reply_language(history, "he") == "en"  # follows the latest customer message
    assert reply_language([{"role": "user", "text": "240?"}], "en") == "en"  # no letters: the chat's choice
    assert reply_language([{"role": "user", "text": "240?"}], "he") == "he"


def test_hebrew_message_gets_hebrew_only(make_client):
    fake = FakeClient(completion(calls=[tool_call(DECLINE, {})]))
    data = make_client(fake).post("/api/chat", json={**chat_body("מה קורה"), "language": "en"}).json()["data"]
    assert data["reply"] == OFF_TOPIC_REPLY["he"]
    assert "in HEBREW" in fake.requests[0]["messages"][0]["content"].split("## RESPONSE LANGUAGE")[-1]


def test_english_message_gets_english_only(make_client):
    fake = FakeClient(completion(calls=[tool_call(DECLINE, {})]))
    data = make_client(fake).post("/api/chat", json={**chat_body("What's the weather today?"), "language": "he"}).json()["data"]
    assert data["reply"] == OFF_TOPIC_REPLY["en"]
    assert "in ENGLISH" in fake.requests[0]["messages"][0]["content"].split("## RESPONSE LANGUAGE")[-1]


def test_message_without_letters_uses_the_chat_language(make_client):
    fake = FakeClient(completion(calls=[tool_call(DECLINE, {})]))
    data = make_client(fake).post("/api/chat", json={**chat_body("240?"), "language": "en"}).json()["data"]
    assert data["reply"] == OFF_TOPIC_REPLY["en"]


def test_api_errors_follow_the_ui_language(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        en = client.post("/api/chat", json={**chat_body(), "language": "en"}).json()["error"]["message"]
        he = client.post("/api/chat", json=chat_body()).json()["error"]["message"]
        assert en.startswith("The AI designer") and "המעצב" in he
        assert client.post("/api/chat", json={**chat_body(), "language": "fr"}).status_code == 422
    finally:
        get_settings.cache_clear()
