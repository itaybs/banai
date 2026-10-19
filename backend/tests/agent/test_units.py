"""Bare numbers mean centimetres (report test #9: "200?" became a shelf at 20 cm)."""

from __future__ import annotations

import pytest

from app.agent.prompts import build_system_prompt
from app.agent.tools import CLARIFY, PROPOSE
from app.agent.units import bare_numbers, millimetre_mistake
from app.domain.catalog import load_catalog
from app.domain.defaults import basic_wardrobe
from tests.agent.fakes import FakeClient, completion, propose, tool_call
from tests.agent.test_agent import chat_body, make_client  # noqa: F401 (fixture)


@pytest.mark.parametrize(("text", "expected"), [
    ("200?", [200]),
    ("200", [200]),
    ("תוסיף מדף ב-120", [120]),
    ("Add a shelf at 100 please", [100]),
    ('תוסיף מדף בגובה 150 ס"מ', []),  # has a unit
    ("תוסיף מדף בגובה 150 ס״מ", []),  # gershayim
    ("make it 240 cm wide", []),
    ("depth 600 mm", []),
    ("2.4 m tall", []),  # a decimal with a unit
    ("ב-50% מהגובה", []),
    ("64.5", []),  # decimals are not checked
    ("3 drawers at 40 cm", [3]),
    ('רוחב 240 ס"מ וגובה 260', [260]),
])
def test_bare_numbers(text, expected):
    assert bare_numbers(text) == expected


SHELF_AT_20_CM = {"op": "add_shelf", "compartmentId": "cmp_middle", "y": 200}  # "200" read as mm


def test_a_bare_number_read_as_millimetres_is_a_mistake():
    message = millimetre_mistake([SHELF_AT_20_CM], "200?")
    assert message and "200 is 200 cm = 2000 mm, never 200 mm" in message and "add_shelf.y = 200" in message


@pytest.mark.parametrize(("ops", "text"), [
    ([{"op": "add_shelf", "compartmentId": "cmp_middle", "y": 2000}], "200?"),  # 200 cm: right
    ([SHELF_AT_20_CM], 'תוסיף מדף בגובה 20 ס"מ'),  # the customer said 20 cm: 200 mm is right
    ([{"op": "add_drawer", "compartmentId": "cmp_middle", "y": 0, "height": 200}], "תוסיף 3 מגירות"),  # 3 is a count
    ([{"op": "configure_doors", "type": "sliding", "count": 2}], "2 sliding doors"),  # not a length field
])
def test_no_mistake_when_the_number_is_used_as_centimetres_or_is_not_a_length(ops, text):
    assert millimetre_mistake(ops, text) is None


def test_the_proposal_goes_back_for_repair_and_the_fixed_one_is_kept(make_client):  # noqa: F811
    fake = FakeClient(
        completion(calls=[tool_call(PROPOSE, propose([SHELF_AT_20_CM]), "call_a")]),
        completion(calls=[tool_call(CLARIFY, {"question": 'למה מתייחסים ה-200 ס"מ: רוחב, גובה או מיקום של מדף?'}, "call_b")]),
    )
    data = make_client(fake).post("/api/chat", json=chat_body("200?", language="he")).json()["data"]
    assert data["proposal"] is None
    assert data["reply"] == 'למה מתייחסים ה-200 ס"מ: רוחב, גובה או מיקום של מדף?'
    repair = fake.requests[1]["messages"][-1]
    assert repair["tool_call_id"] == "call_a" and "never 200 mm" in repair["content"]


def test_a_correct_centimetre_proposal_passes(make_client):  # noqa: F811
    fake = FakeClient(completion(calls=[tool_call(PROPOSE, propose([{"op": "update_dimensions", "height": 2600}]))]))
    data = make_client(fake).post("/api/chat", json=chat_body("Make it 260 tall", language="en")).json()["data"]
    assert data["proposal"]["ops"] == [{"op": "update_dimensions", "height": 2600}]
    assert len(fake.requests) == 1  # no repair round


def test_the_prompt_states_the_bare_number_rule():
    prompt = build_system_prompt(basic_wardrobe(), load_catalog(), "he")
    assert "WITHOUT a unit always means centimetres (200 -> 2000), never millimetres" in prompt
    assert "gender-neutral question" in prompt
