"""Deterministic clearance notes the backend appends to the agent's reply (the model ignores the
numbers, so code states them): too little hanging space under a rail, too little room between
shelves, and a long-items check for questions about hanging dresses or coats.

ASSUMPTION: the thresholds are configurable design defaults, not manufacturing rules."""

from __future__ import annotations

import re

from app.agent.language import Language

RAIL_MIN_FREE_BELOW = 900  # mm of hanging space under a rail
SHELF_MIN_GAP = 200  # mm between neighbouring shelves
LONG_ITEMS_MIN_FREE_BELOW = 1500  # mm under a rail for long dresses and coats

# Questions about hanging long items (customer text, either language).
LONG_ITEMS = re.compile(
    r"שמל\S*\s+ארוכ|מעיל|פריטים ארוכים|בגדים ארוכים|long (?:dress|coat|item|cloth|garment)|\bcoats?\b|\bmaxi",
    re.IGNORECASE,
)

RAIL_OPS = {"add_rail", "modify_rail"}
SHELF_OPS = {"add_shelf", "modify_shelf"}


def cm(mm: int) -> str:
    """Millimetres as centimetres with one decimal at most: 182 -> "18.2", 1800 -> "180"."""
    return f"{mm / 10:.1f}".removesuffix(".0")


def _free_below(compartment: dict, y: int) -> int:
    """Clear height under height y, down to the nearest shelf or drawer top (or the bottom)."""
    tops = [s["y"] + s["thickness"] for s in compartment["shelves"]] + [d["y"] + d["height"] for d in compartment["drawers"]]
    return y - max((top for top in tops if top <= y), default=0)


def _rail_clearances(design: dict) -> dict[str, tuple[int, int, int]]:
    """rail id -> (compartment index from the left, rail y, free height below it)."""
    return {
        rail["id"]: (index, rail["y"], _free_below(compartment, rail["y"]))
        for index, compartment in enumerate(design["compartments"])
        for rail in compartment["rails"]
    }


def _shelf_gaps(compartment: dict) -> list[tuple[dict, dict, int]]:
    """(lower shelf, upper shelf, clear height) for neighbouring shelves with no drawer between them."""
    shelves = sorted(compartment["shelves"], key=lambda shelf: shelf["y"])
    gaps = []
    for lower, upper in zip(shelves, shelves[1:]):
        bottom, top = lower["y"] + lower["thickness"], upper["y"]
        if not any(d["y"] < top and d["y"] + d["height"] > bottom for d in compartment["drawers"]):
            gaps.append((lower, upper, top - bottom))
    return gaps


RAIL_WARNING: dict[Language, str] = {
    "he": 'לתשומת הלב: מתחת למוט בגובה {y} ס"מ יישארו רק {free} ס"מ פנויים לתלייה.',
    "en": "Note: only {free} cm will be left for hanging below the rail at {y} cm.",
}
SHELF_WARNING: dict[Language, str] = {
    "he": 'לתשומת הלב: בין המדפים בגובה {low} ו-{high} ס"מ יישארו רק {gap} ס"מ.',
    "en": "Note: only {gap} cm will be left between the shelves at {low} and {high} cm.",
}
LONG_ITEMS_RAIL: dict[Language, str] = {
    "he": 'מתחת למוט בגובה {y} ס"מ (תא {n} משמאל) יש רק {free} ס"מ פנויים',
    "en": "the rail at {y} cm (compartment {n} from the left) has only {free} cm free below it",
}
LONG_ITEMS_NOTE: dict[Language, str] = {
    "he": 'לידיעה: בעיצוב הנוכחי {rails}, פחות מ-150 ס"מ שפריטים ארוכים צריכים.',
    "en": "For reference: in the current design {rails}, less than the 150 cm long items need.",
}
LIST_JOIN: dict[Language, str] = {"he": ", ו", "en": ", and "}


def proposal_warning(before: dict, after: dict, ops: list[dict], language: Language) -> str | None:
    """One warning sentence when a proposal that adds or moves a rail or shelf leaves too little room.

    `ops` must already have ids for new components (orchestrator.fill_ids). A rail is checked when it
    is added or moved, or when a shelf in its compartment is, and only if its space got smaller."""
    rails_touched = {op["id"] for op in ops if op.get("op") in RAIL_OPS and op.get("id")}
    shelves_touched = {op["id"] for op in ops if op.get("op") in SHELF_OPS and op.get("id")}
    if not rails_touched and not shelves_touched:
        return None
    rails_before = _rail_clearances(before)
    for index, compartment in enumerate(after["compartments"]):
        shelf_moved = any(shelf["id"] in shelves_touched for shelf in compartment["shelves"])
        for rail in sorted(compartment["rails"], key=lambda r: r["y"]):
            if rail["id"] not in rails_touched and not shelf_moved:
                continue
            free = _free_below(compartment, rail["y"])
            previous = rails_before.get(rail["id"], (index, rail["y"], None))[2]
            if free < RAIL_MIN_FREE_BELOW and (previous is None or rail["id"] in rails_touched or free < previous):
                return RAIL_WARNING[language].format(y=cm(rail["y"]), free=cm(free))
        for lower, upper, gap in _shelf_gaps(compartment):
            if gap < SHELF_MIN_GAP and (lower["id"] in shelves_touched or upper["id"] in shelves_touched):
                return SHELF_WARNING[language].format(low=cm(lower["y"]), high=cm(upper["y"]), gap=cm(gap))
    return None


def long_items_note(question: str, design: dict, language: Language) -> str | None:
    """For a question about hanging long items: the existing rails with under 150 cm below them."""
    if not LONG_ITEMS.search(question):
        return None
    short = sorted(
        (value for value in _rail_clearances(design).values() if value[2] < LONG_ITEMS_MIN_FREE_BELOW),
        key=lambda value: (value[0], value[1]),
    )
    if not short:
        return None
    rails = LIST_JOIN[language].join(
        LONG_ITEMS_RAIL[language].format(y=cm(y), n=index + 1, free=cm(free)) for index, y, free in short
    )
    return LONG_ITEMS_NOTE[language].format(rails=rails)


def with_note(text: str, note: str | None) -> str:
    return f"{text} {note}" if note else text
