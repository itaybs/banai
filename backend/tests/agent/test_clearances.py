"""Code-added clearance warnings (report tests #5, #6 and #8: the model ignored the numbers)."""

from __future__ import annotations

import pytest

from app.agent.clearances import cm, long_items_note, proposal_warning
from app.agent.orchestrator import fill_ids
from app.agent.tools import ANSWER, PROPOSE
from app.domain.apply import apply_ops
from app.domain.catalog import load_catalog
from app.domain.defaults import basic_wardrobe
from tests.agent.fakes import FakeClient, completion, propose, tool_call
from tests.agent.test_agent import chat_body, make_client  # noqa: F401 (fixture)

RAIL_AT_180_LEFT = {"op": "add_rail", "compartmentId": "cmp_left", "y": 1800}  # left shelf at 160 cm below it


def warning_for(ops, language="he", design=None):
    before = design or apply_ops(basic_wardrobe(), [], load_catalog())
    ops = fill_ids(ops)
    return proposal_warning(before, apply_ops(before, ops, load_catalog()), ops, language)


def test_cm_formatting():
    assert (cm(182), cm(1800), cm(682), cm(0)) == ("18.2", "180", "68.2", "0")


def test_a_new_rail_with_little_room_below_gets_a_warning_in_the_selected_language():
    assert warning_for([RAIL_AT_180_LEFT], "he") == 'לתשומת הלב: מתחת למוט בגובה 180 ס"מ יישארו רק 18.2 ס"מ פנויים לתלייה.'
    assert warning_for([RAIL_AT_180_LEFT], "en") == "Note: only 18.2 cm will be left for hanging below the rail at 180 cm."


def test_a_new_shelf_under_an_existing_rail_gets_a_warning():
    # Report test #8: a shelf at 120 cm under the middle rail at 190 cm leaves 68.2 cm.
    shelf = {"op": "add_shelf", "compartmentId": "cmp_middle", "y": 1200}
    assert warning_for([shelf]) == 'לתשומת הלב: מתחת למוט בגובה 190 ס"מ יישארו רק 68.2 ס"מ פנויים לתלייה.'


def test_moving_a_rail_down_is_checked_too():
    assert warning_for([{"op": "modify_rail", "id": "rail_m1", "y": 500}], "en") == (
        "Note: only 50 cm will be left for hanging below the rail at 50 cm."
    )


def test_shelves_too_close_together_get_a_warning():
    # A shelf at 100 cm sits 18.2 cm above the shelf at 80 cm.
    assert warning_for([{"op": "add_shelf", "compartmentId": "cmp_left", "y": 1000}]) == (
        'לתשומת הלב: בין המדפים בגובה 80 ו-100 ס"מ יישארו רק 18.2 ס"מ.'
    )


@pytest.mark.parametrize("ops", [
    [{"op": "add_shelf", "compartmentId": "cmp_left", "y": 2000}],  # 38.2 cm above the top shelf, no rail
    [{"op": "add_rail", "compartmentId": "cmp_right", "y": 2364}],  # 94.6 cm above the shelf at 140 cm
    [{"op": "set_material", "target": "doors", "color": {"catalogId": "walnut"}}],  # no rail or shelf
])
def test_no_warning_when_there_is_enough_room(ops):
    assert warning_for(ops) is None


def test_an_existing_short_rail_is_not_warned_again_by_an_unrelated_shelf():
    design = apply_ops(basic_wardrobe(), fill_ids([RAIL_AT_180_LEFT]), load_catalog())
    assert warning_for([{"op": "add_shelf", "compartmentId": "cmp_left", "y": 2000}], design=design) is None


def test_the_reply_gets_the_warning_and_hebrew_stays_gender_neutral(make_client):  # noqa: F811
    fake = FakeClient(completion(calls=[tool_call(PROPOSE, propose([RAIL_AT_180_LEFT], reply="אציע מוט בגובה 180 ס\"מ."))]))
    data = make_client(fake).post("/api/chat", json=chat_body("תוסיף מוט", language="he")).json()["data"]
    assert data["reply"] == 'אציע מוט בגובה 180 ס"מ. לתשומת הלב: מתחת למוט בגובה 180 ס"מ יישארו רק 18.2 ס"מ פנויים לתלייה.'
    assert "שים לב" not in data["reply"] and "תשים" not in data["reply"]


def test_english_selected_gets_the_english_warning(make_client):  # noqa: F811
    fake = FakeClient(completion(calls=[tool_call(PROPOSE, propose([RAIL_AT_180_LEFT], reply="I suggest a rail at 180 cm."))]))
    data = make_client(fake).post("/api/chat", json=chat_body("תוסיף מוט", language="en")).json()["data"]
    assert data["reply"].endswith("Note: only 18.2 cm will be left for hanging below the rail at 180 cm.")


# ---- questions about hanging long items ----

def with_left_rail():
    return apply_ops(basic_wardrobe(), fill_ids([RAIL_AT_180_LEFT]), load_catalog())


def test_long_items_question_gets_the_real_number_for_short_rails():
    note = long_items_note("באיזה גובה מומלץ לשים מוט תלייה לשמלות ארוכות?", with_left_rail(), "he")
    assert note == 'לידיעה: בעיצוב הנוכחי מתחת למוט בגובה 180 ס"מ (תא 1 משמאל) יש רק 18.2 ס"מ פנויים, פחות מ-150 ס"מ שפריטים ארוכים צריכים.'
    assert "190" not in note  # the middle rail has 190 cm below it: enough
    assert long_items_note("Where should I hang long coats?", with_left_rail(), "en") == (
        "For reference: in the current design the rail at 180 cm (compartment 1 from the left) has only "
        "18.2 cm free below it, less than the 150 cm long items need."
    )


@pytest.mark.parametrize("question", ["איזה צבע מתאים לחדר קטן?", "How deep should drawers be?"])
def test_other_questions_get_no_long_items_note(question):
    assert long_items_note(question, with_left_rail(), "he") is None


def test_no_note_when_every_rail_has_room():
    assert long_items_note("Where do long dresses go?", apply_ops(basic_wardrobe(), [], load_catalog()), "en") is None


def test_the_answer_gets_the_long_items_note(make_client):  # noqa: F811
    # Report test #6: the model called an 18 cm clearance suitable; the code now states the number.
    fake = FakeClient(completion(calls=[tool_call(ANSWER, {"answer": 'לשמלות ארוכות מומלץ מוט בגובה 180 ס"מ ומעלה.'})]))
    data = make_client(fake).post("/api/chat", json=chat_body("באיזה גובה לשים מוט לשמלות ארוכות?", design=with_left_rail(), language="he")).json()["data"]
    assert data["reply"].startswith('לשמלות ארוכות מומלץ מוט בגובה 180 ס"מ ומעלה. לידיעה:')
    assert '18.2 ס"מ' in data["reply"]
