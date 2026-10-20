---
project: BanAI
type: feature
tags: [banai, fork, spec-pdf]
---

# Spec PDF Feature

Back to [[00 - Fork Additions]]. How it is built: [[03 - Spec PDF Internals]].

## The "סיכום לנגר" button
- Above the chat, next to the language selector ("Summary for the carpenter" in English).
- **Disabled** while the agent is answering or a proposal waits for Confirm. A proposal counts only once it is confirmed.
- Opens a dialog in the chat language. The **disclaimer comes first**, then optional questions:
  - intended use (clothes / kids' room / linen and towels / mixed)
  - installation location
  - timeline
  - special requests
  - a name to show on the PDF
- There is **no budget question**: pricing is excluded from the product.

## What the PDF contains
- Title, date, design revision, and "prepared for" (only if a name was typed).
- A **disclaimer box** on page 1, and a short disclaimer in the footer of every page: a visual design draft, not a manufacturing drawing; the carpenter must verify all measurements on site.
- A **front view image** from the 3D model, labelled as illustrative and not to scale.
- Overall dimensions, interior dimensions, panel thickness, number of compartments and partitions.
- Each compartment from left to right, with its items from bottom to top (drawers, shelves, rails with the free height below them). Heights are measured from the top of the bottom panel.
- Doors (type, count, hinge sides), materials, colours and finishes (catalog names in Hebrew when the PDF is in Hebrew).
- **Clearance notes**: less than 90 cm below a rail, or less than 20 cm between shelves.
- The customer's preferences, and the **AI summary** (labelled "written by AI").
- The language follows the chat's selected language.

## Where the numbers come from
- **Every number comes from the design**, never from model text. The backend re-validates the confirmed design with the domain engine, then builds the content.
- Clearances come from the same code that writes the chat's clearance warnings (`app/agent/clearances.py`).

## The AI summary and its guard
- One short paragraph (at most about 60 words). The model gets the exact PDF lines as data.
- Its text must pass the safe-text pattern and the **production-claim guard** (no "ready for production", "manufacturable", "engineering approved", "מוכן לייצור", "מאושר הנדסית", …).
- If the call fails or the text is rejected, the PDF is made **without** the summary.
- It costs one model call per PDF.

## What is refused
- Customer text that claims production readiness or approval → **422 `TEXT_CLAIM`**.
- Unknown fields (for example a budget) → 422.
- An image that is not a small, valid PNG → **422 `IMAGE_INVALID`**.
- An invalid design or a missing/unknown language → 422.
- As a final check, nothing in the document may match the production-claim guard.

## Privacy
- **Nothing is stored**: the PDF is built per request and sent back with `Cache-Control: no-store`.
- No phone, email, chat transcript or design link (a link would carry the secret share token).
- The only personal detail is the optional name, and only if the customer typed it.
- Logs keep only error classes and codes, never text or keys.
