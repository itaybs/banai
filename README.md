# BanAI — AI Wardrobe Designer

An MVP for designing standard straight wardrobes with three synchronized parts:
- a conversational AI agent
- a manual properties editor
- a dimensionally accurate Three.js viewer

All three edit **one canonical design state** through the same typed operations.

## My contributions to this fork

Features built in this fork ([itaybs/banai](https://github.com/itaybs/banai)) and proposed upstream as pull requests to `dev`.

### Latest: a room around the wardrobe ([#94](https://github.com/JonathanZouari/banai/pull/94))

A wardrobe is hard to judge floating on a grey grid. **View in a room** places it inside a furnished room in the 3D viewer, so you can see it against a wall, next to a bed, from the doorway, in morning or evening light. The room is decoration only: it never changes the wardrobe and is never saved with the design.

| | |
|---|---|
| <img src="docs/features/room-scene/images/doorway-view-morning.png" alt="The doorway view in the morning: a white three-door wardrobe on a warm wall, sun through the window and the Room panel on the left"> | <img src="docs/features/room-scene/images/doorway-view-evening.png" alt="The same doorway view in the evening: a low warm sun in the window and the lamps glowing"> |
| *From the doorway, in the morning.* | *The same view in the evening.* |

<img src="docs/features/room-scene/images/floor-plan-door-swing-amber.png" width="560" alt="A floor plan from above: the wide wardrobe door's swing arc reaches the bed, whose outline is amber">

*Floor plan with the door swing on: the wide right door of the wardrobe swings into the bed, so the bed is outlined in amber.*

[Full feature page](docs/features/room-scene/README.md) · [PR #94](https://github.com/JonathanZouari/banai/pull/94)

### Earlier features

- <img src="docs/features/start-templates/images/start-screen-english.png" width="120" alt="The template gallery"> **[Template gallery with real 3D thumbnails](docs/features/start-templates/README.md)**: three new starting templates with real 3D thumbnails and an inside view. [#86](https://github.com/JonathanZouari/banai/pull/86)
- <img src="docs/features/proposal-diff/images/change-row-hover-3d-highlight.png" width="120" alt="A change row highlighting its part in 3D"> **[What will change, in the proposal card](docs/features/proposal-diff/README.md)**: the AI proposal lists the exact changes and highlights each part in 3D. [#70](https://github.com/JonathanZouari/banai/pull/70)
- <img src="docs/features/design-summary/images/design-summary-card.png" width="120" alt="The design summary card"> **[Design summary card](docs/features/design-summary/README.md)**: counts, interior volume and hanging length at the top of the Properties panel. [#53](https://github.com/JonathanZouari/banai/pull/53)
- <img src="docs/features/agent-review/images/chat-language-selector-hebrew.png" width="120" alt="The language selector above the chat"> **[Agent review and a language selector](docs/features/agent-review/README.md)**: fixes from 30 UI tests of the AI designer, and an explicit reply language. [#18](https://github.com/JonathanZouari/banai/pull/18)

All features, with status, commits and screenshots: [docs/features/README.md](docs/features/README.md)

![BanAI workspace](docs/screenshots/02-workspace.png)

## Table of contents

- [My contributions to this fork](#my-contributions-to-this-fork)
- [Features](#features)
- [Screenshots](#screenshots)
- [How it works](#how-it-works)
- [Repository layout](#repository-layout)
- [Local development](#local-development)
- [Configuration](#configuration)
- [Testing](#testing)
- [Environments](#environments)
- [Project status](#project-status)
- [Documentation](#documentation)

## Features

- **3D viewer:**
  - Orbit and zoom around the wardrobe, and click any component to select it.
  - Live dimension labels in cm.
  - A "Show interior" toggle hides the doors.
- **Properties editor:**
  - Overall size, doors (hinged, sliding or none), materials, colours and finishes.
  - Compartments, shelves, drawers and hanging rails.
  - Every edit is validated, and an invalid value never changes the design.
- **AI Designer chat:**
  - Describe the wardrobe in Hebrew or English, and the agent replies with a **proposal**.
  - Nothing changes until you press **Confirm**.
  - Proposals are HMAC-signed, re-validated on the server, and rejected if the design changed in the meantime.
- **Voice:**
  - Press the mic, speak in Hebrew or English, and press it again. Your words are transcribed and sent as a chat message, and the result is still a proposal you confirm.
  - Optionally, have replies **read aloud** in an AI-generated voice.
- **Design-only scope:** the agent declines anything that isn't about wardrobe design.

## Screenshots

| | |
|---|---|
| **Start screen.** Choose how to begin. ![Start screen](docs/screenshots/01-start-screen.png) | **Workspace.** Chat, 3D view and properties. ![Workspace](docs/screenshots/02-workspace.png) |
| **Interior and selection.** Doors hidden, a shelf selected and editable. ![Interior and selection](docs/screenshots/03-interior-and-selection.png) | **AI proposal.** The agent proposes; you confirm. ![AI proposal](docs/screenshots/04-ai-proposal.png) |
| **Proposal applied.** The design updates to 240 cm wide. ![Proposal applied](docs/screenshots/05-proposal-applied.png) | |

## How it works

```
 chat (OpenAI) ──► signed proposal ──► Confirm ──┐
 properties editor ──► ops ──────────────────────┼──► ops engine ──► canonical design ──► Three.js viewer
                                                 │    (validated)
```

- **One op protocol.** Every change is a list of pure, typed ops such as `update_dimensions`, `configure_doors`, `add_shelf` or `set_material`.
  - The Python engine in `backend/app/domain/` is authoritative.
  - The JS mirror in `frontend/src/domain/` gives instant manual edits.
  - Shared golden fixtures keep the two engines in sync.
- **Units.** All lengths are integer millimetres. The UI shows cm.
- **Stateless AI proposals.**
  - `POST /api/chat` returns `{reply, proposal}`. The proposal is signed over `{ops, baseRevision, baseHash}`.
  - `POST /api/proposals/apply` verifies the signature and returns **409** if the proposal is stale.
- **Rendering.** The viewer renders from state only; it never owns data.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI + Pydantic API and AI agent (Python 3.13, managed by `uv`) |
| `frontend/` | Vanilla JS + Three.js, bundled with Vite |
| `shared/fixtures/` | Golden fixtures used by both test suites |
| `supabase/` | Supabase CLI config and SQL migrations |
| `docs/` | Architecture, schema, frontend and infra docs, plus screenshots |
| `.claude/` | Claude Code project settings and the Obsidian work-log Stop hook |

## Local development

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/), Node 22+.

```bash
# Backend (http://localhost:8000)
cd backend
cp .env.example .env        # add OPENAI_API_KEY to enable the AI Designer
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:5173)
cd frontend
cp .env.example .env
npm ci
npm run dev
```

## Configuration

**Backend** (`backend/.env`):

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Enables the AI Designer. Without it, the chat says the agent isn't connected. |
| `OPENAI_CHAT_MODEL` | Model to use, for example `gpt-4.1`. It has a configurable default. |
| `OPENAI_TRANSCRIBE_MODEL` / `OPENAI_TTS_MODEL` / `OPENAI_TTS_VOICE` | Voice models and voice. Optional; the defaults are `gpt-4o-mini-transcribe`, `gpt-4o-mini-tts` and `marin`. |
| `PROPOSAL_SIGNING_KEY` | HMAC key for proposals. Required outside `APP_ENV=local`. |
| `CORS_ORIGINS` | Allowed frontend origins, comma-separated. |
| `APP_ENV` | Set to `local`, `dev` or `production`. API docs are disabled in production. |

**Frontend** (`frontend/.env`):

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend URL, read at build time. |

Never commit `.env` files. The repository is public.

## Testing

```bash
cd backend  && uv run pytest              # backend unit + API tests
cd frontend && npm test                   # frontend unit tests (vitest)
cd frontend && npx playwright test        # end-to-end tests (starts its own servers)
```

Playwright E2E tests never call OpenAI; the agent flows mock the `/api` edge.

## Environments

| Railway environment | Git branch | Services (root dir) |
|---|---|---|
| `production` | `main` | `frontend` (`/frontend`), `backend` (`/backend`) |
| `dev` | `dev` | `frontend` (`/frontend`), `backend` (`/backend`) |

- All work lands on `dev`.
- Merging to `main` deploys production, and only happens with explicit approval.
- See `docs/railway.md`.

## Project status

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundations and infrastructure | Done |
| 2 | Design model and ops engine | Done |
| 3 | 3D viewer | Done |
| 4 | UI and manual editing | Done |
| 5 | AI designer agent | Merged |
| 5+ | Voice (speech in, read-aloud out) | Done |
| 6+ | Persistence and share links, AI photoreal render, deployment hardening | Planned |

Save and Render in the top bar open dialogs that say those features aren't available yet.

## Documentation

- [`docs/architecture.md`](docs/architecture.md): architecture and phase plan
- [`docs/schema.md`](docs/schema.md): design schema and op protocol
- [`docs/frontend.md`](docs/frontend.md): store, viewer and editor
- [`docs/railway.md`](docs/railway.md) and [`docs/supabase.md`](docs/supabase.md): infrastructure
- [`docs/features/`](docs/features/README.md): features built in this fork and proposed upstream, with screenshots
