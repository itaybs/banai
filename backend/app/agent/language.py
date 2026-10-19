"""Reply language: the agent answers only in the language the customer's latest message is
written in (Hebrew or English). The language chosen in the chat is used when a message has no
letters to go by (e.g. "240?"). The chat UI switches its language to match what was written."""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["he", "en"]
LANGUAGES: tuple[Language, ...] = ("he", "en")

_HEBREW = re.compile(r"[א-ת]")
_LATIN = re.compile(r"[A-Za-z]")

# Fixed texts (never model-written).
OFF_TOPIC_REPLY: dict[Language, str] = {
    "he": "אני כאן כדי לעזור רק בעיצוב ותכנון הארון שלך: מידות, חלוקה פנימית, מדפים ומגירות, "
          "דלתות, חומרים, צבעים וגימורים. במה אפשר לעזור בעיצוב?",
    "en": "I'm here to help only with designing and planning your wardrobe: dimensions, interior "
          "layout, shelves and drawers, doors, materials, colours and finishes. How can I help with your design?",
}
FALLBACK_REPLY: dict[Language, str] = {
    "he": "לא הצלחתי להפוך את הבקשה לשינוי תקין בארון. אפשר לנסח אותה אחרת, או לספר לי קצת יותר מה תרצה?",
    "en": "I couldn't turn that into a valid change to your wardrobe. Could you rephrase it, or tell me a bit more?",
}

# The instruction appended at the very end of the system prompt (after the per-turn data).
# It overrides the language of earlier messages in the conversation.
INSTRUCTION: dict[Language, str] = {
    "he": "Write EVERYTHING customer-facing in HEBREW (reply, summary, change titles and details, "
          "questions, answers), even if earlier messages were in English. Write centimetres as ס\"מ. Translate catalog names (Walnut -> אגוז, White -> לבן). "
          "Use correct Hebrew grammatical gender (\"איזו מידה\", \"באיזה גובה\", \"באיזה תא\"). Address the customer in a "
          "gender-neutral way and avoid slash forms like \"גובה/גובהים\".",
    "en": "Write EVERYTHING customer-facing in ENGLISH (reply, summary, change titles and details, "
          "questions, answers), even if earlier messages were in Hebrew. Write centimetres as cm.",
}


def detect(text: str) -> Language | None:
    """The language a message is written in, or None when it has no Hebrew or Latin letters.
    Hebrew wins when a message mixes both (e.g. Hebrew with an English brand name). Mirrored in
    frontend/src/chat/i18n.js (detectLanguage)."""
    if _HEBREW.search(text):
        return "he"
    if _LATIN.search(text):
        return "en"
    return None


def reply_language(messages: list[dict], chosen: Language) -> Language:
    latest = next((m["text"] for m in reversed(messages) if m["role"] == "user"), "")
    return detect(latest) or chosen
