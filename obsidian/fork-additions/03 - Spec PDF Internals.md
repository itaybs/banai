---
project: BanAI
type: architecture
tags: [banai, fork, spec-pdf, architecture]
---

# Spec PDF Internals

Back to [[00 - Fork Additions]]. What the feature does: [[02 - Spec PDF Feature]].

## Backend: `backend/app/spec/` and `POST /api/spec/pdf`
- `app/api/spec.py`: the endpoint.
  - Body: `design`, `revision` (≥ 1), `language` (`he` | `en`, required), `preferences` (all optional), `frontImage` (PNG data URL), `includeSummary` (default true).
  - Preference limits: location 200, timeline 100, requests 500, name 80 characters. Intended use is one of `clothes`, `kids`, `linen`, `mixed`.
  - Image limits: PNG only, at most 1.5 MB and 4096 px per side.
  - Response: `application/pdf`, `Content-Disposition: attachment; filename="banai-design-r<revision>.pdf"`, `Cache-Control: no-store`.
- `app/spec/content.py`: design → titled sections of text lines, in Hebrew or English. Pure logic, no PDF code. The tests check this layer.
  - `CATALOG_HE` holds the Hebrew names for the catalog (the catalog itself is English only).
- `app/spec/pdf.py`: renders the content with fpdf2. See [[04 - Hebrew RTL and Font]].
- `app/spec/summary.py`: the AI summary (tool `write_design_summary`), with the production-claim guard.
- `app/agent/clearances.py`: `design_issues()` and `free_below()` are shared with the chat's warnings.

## Frontend dialog
- `src/spec/specDialog.js`: the dialog. It is rebuilt on every open, in the chat's language and direction.
- `src/spec/specRequest.js`: builds the request (trims answers, drops empty ones, applies the limits). Pure, unit tested.
- `src/api/client.js`: `fetchSpecPdf()` returns a Blob; errors arrive as the usual JSON envelope.
- `src/chat/chatPanel.js`: the button, and its disabled state.
- `src/main.js`: passes the store's **committed** design and revision, the chat language and the viewer capture.

## Front image capture
- `viewer.captureFront()` in `src/viewer/viewer.js`, with the framing math in `src/viewer/capture.js` (`frontView()`, unit tested).
- It renders a straight front view at 900 × 1000 px, hides the `dimensions` and `highlight` layers, then restores the user's camera.
- If the capture fails, the PDF is still made without an image.

## Share on touch devices, download on desktop
- `src/spec/share.js`: `shareOrDownload()`.
- **Touch devices** (`matchMedia('(pointer: coarse)')`): the share sheet (`navigator.share` with the file) when `canShare` allows it.
- **Desktop**: always a plain download. Desktop Chrome on Windows can share files, but it opens the Windows share window, which people do not expect there.
- Closing the share sheet counts as cancelled (nothing is downloaded). Any other share error falls back to a download.
- The app itself never sends the PDF anywhere.
