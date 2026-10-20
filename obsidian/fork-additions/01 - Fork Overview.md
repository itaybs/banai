---
project: BanAI
type: overview
tags: [banai, fork]
---

# Fork Overview

Back to [[00 - Fork Additions]].

## Where the work lives
- Fork: `itaybs/banai`, forked from `JonathanZouari/banai`. The upstream repo was not changed.
- **PR #1** (`feature/voice-agent`, merged into the fork's `main`): agent review and fixes.
- **PR #2** (`feature/spec-pdf`, open): the design summary PDF for the carpenter.

## PR #1: agent review and fixes
- 30 behaviour tests of the AI designer through the real UI in Chrome, re-run after each round of fixes. Report: `reports/voice-agent-test-report.html` (Hebrew, RTL).
- Result on the original 30 tests: **23 / 4 / 3 → 30 / 0 / 0** (pass / partial / fail).
- Main fixes:
  - **Emoji with a zero-width joiner** no longer break the chat (a refused message is dropped from the history).
  - **The agent knows what was confirmed**: `[app] applied: …` / `[app] cancelled: …` notes in the history.
  - **No "ready for production" claims**: a narrow phrase check in code, through the existing repair loop.
  - **Change rows must match ops** (no invented rows).
  - **Clearance warnings are written by code** (under 90 cm below a rail, under 20 cm between shelves, under 150 cm for long items).
  - **A number without a unit always means cm** (a proposal that reads it as mm goes back for repair).
  - **Language selector** above the chat (עברית / English): the selected language is the only reply language.
  - **Read-aloud starts off on every visit** (a saved "on" kept it on after one stray click).
  - Safer failures: speech fails fast, logs keep only the error class and code, and account problems get their own message.

## PR #2: design summary PDF
- A "סיכום לנגר" button produces a PDF the customer sends to a carpenter. See [[02 - Spec PDF Feature]].
- Why: once the design is done, the customer needs one organized document for the carpenter.
- It is an **approved exception** (2026-10-20) to the "manufacturing exports" exclusion: a visual design draft, not a manufacturing file. Recorded in `CLAUDE.md`, `docs/architecture.md` §5b and [[06 - Product Specification]] §22.
