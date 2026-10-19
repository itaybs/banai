"""Bare numbers: a number the customer writes without a unit always means centimetres, never
millimetres. Report test #9: "200?" became a shelf at 20 cm (200 read as mm). The check below is
deterministic: a proposal whose length equals a bare number taken as millimetres goes back to the
model for repair."""

from __future__ import annotations

import re

# A number, unless a unit (or a percent sign) follows it. Hebrew units may carry a geresh/gershayim.
_NUMBER = re.compile(r"(?<![\d.])(\d+(?:[.,]\d+)?)(?![\d.,])")
_UNIT_AFTER = re.compile(
    r"\s*(?:%|cm\b|mm\b|m\b|meters?\b|metres?\b|centimet(?:er|re)s?\b|millimet(?:er|re)s?\b|"
    r"ס[\"״]?מ|מ[\"״]מ|מ['׳](?![א-ת])|מטר|סנטימטר|מילימטר)",
    re.IGNORECASE,
)

# Op fields that hold a length in millimetres.
LENGTH_FIELDS = ("width", "height", "depth", "y", "offset", "position", "thickness", "panelThickness", "partitionThickness")


def bare_numbers(text: str) -> list[int]:
    """Whole numbers in the customer's text that have no unit after them (decimals are skipped)."""
    numbers = []
    for match in _NUMBER.finditer(text):
        if _UNIT_AFTER.match(text, match.end()):
            continue
        value = match.group(1).replace(",", ".")
        if "." not in value:
            numbers.append(int(value))
    return numbers


def millimetre_mistake(ops: list[dict], customer_text: str) -> str | None:
    """A repair message when an op length equals a bare number read as mm (it should be that many cm)."""
    bare = set(bare_numbers(customer_text))
    if not bare:
        return None
    for op in ops:
        for field in LENGTH_FIELDS:
            value = op.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value in bare:
                return (
                    f"The customer wrote {value} without a unit: a number without a unit always means centimetres, "
                    f"so {value} is {value} cm = {value * 10} mm, never {value} mm. {op.get('op')}.{field} = {value} "
                    "reads it as millimetres. Fix the ops, or call ask_clarification if it is unclear what the number refers to."
                )
    return None
