---
project: BanAI
type: testing
tags: [banai, fork, testing]
---

# Fork Testing

Back to [[00 - Fork Additions]].

## Unit tests
- **Backend** (from `backend/`): `uv run pytest`. 303 tests at the time of PR #2.
  - The PDF: `tests/spec/test_spec.py` (content in both languages, the disclaimer, no production claims, the endpoint, image and text validation, privacy).
  - The agent fixes: `tests/agent/` (`test_agent.py`, `test_clearances.py`, `test_units.py`, `test_voice.py`).
- **Frontend** (from `frontend/`): `npm test`. 211 tests at the time of PR #2.
  - The PDF: `tests/unit/spec/spec.test.js` (request building, share vs. download, front-view framing, strings in both languages).

## Playwright (end to end)
- The PDF dialog spec, alone and with one worker (the machine is low on memory):
  - from `frontend/`: `npx playwright test tests/e2e/spec.spec.js --workers=1`
  - It starts its own servers on ports 8010 and 5183, with no OpenAI key (the API calls are mocked).
  - `uv` must be on the `PATH`.
  - Result for PR #2: **2 / 2 passed**.
- The rest of the E2E suite was **not run locally** because of memory.

## Live checks done in Chrome
- The dialog with real typing → a 46 KB PDF, opened in Chrome's PDF viewer. The 3D front capture, the clearance note, the preferences and the AI summary were all correct.
- The button is disabled while a proposal waits, and the dialog follows the English chat language.

## Still untested
- **The real mobile share path** (the share sheet on a phone). Only the desktop download path was checked live.
- **Voice input**: real speech cannot be tested through Chrome automation.
