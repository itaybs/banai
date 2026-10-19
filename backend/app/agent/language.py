"""Reply language: the customer picks Hebrew or English in the chat, and that choice is the ONLY
language the agent answers in, whatever language a message is written or spoken in. The chat sends
it with every request; nothing is detected from the message text."""

from __future__ import annotations

from typing import Literal

Language = Literal["he", "en"]
LANGUAGES: tuple[Language, ...] = ("he", "en")

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
# It overrides the language of the customer's messages and of earlier replies.
INSTRUCTION: dict[Language, str] = {
    "he": "Write EVERYTHING customer-facing in HEBREW (reply, summary, change titles and details, "
          "questions, answers): the customer chose Hebrew, so answer in Hebrew even when they write in English "
          "or another language, and even if earlier replies were in English. Write centimetres as ס\"מ. Translate catalog names (Walnut -> אגוז, White -> לבן). "
          "Use correct Hebrew grammatical gender (\"איזו מידה\", \"באיזה גובה\", \"באיזה תא\"). Address the customer in a "
          "gender-neutral way and avoid slash forms like \"גובה/גובהים\".",
    "en": "Write EVERYTHING customer-facing in ENGLISH (reply, summary, change titles and details, "
          "questions, answers): the customer chose English, so answer in English even when they write in Hebrew "
          "or another language, and even if earlier replies were in Hebrew. Write centimetres as cm.",
}
