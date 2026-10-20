---
project: BanAI
type: open-items
tags: [banai, fork, todo]
---

# Fork Known Limitations

Back to [[00 - Fork Additions]]. Original open items: [[05 - Open Items]].

## The PDF
- **No design id until saving exists (Phase 7).** The PDF uses the confirmed design in the app, and the revision is the in-session revision. Once Phase 7 is built, the endpoint should load the saved design by id.
- **Not a manufacturing file, by design**: no cut lists, board sizes, hardware, prices or budget.
- **The front image is illustrative**: a straight view of the 3D model, not a scaled drawing.
- **Desktop never uses the share sheet**: it always downloads. Phones and tablets use the share sheet when the browser can share files.
- **New catalog items need a Hebrew name** in `CATALOG_HE` (`backend/app/spec/content.py`); otherwise the Hebrew PDF shows the English name.
- **The AI summary costs one model call** per PDF, and is left out when the agent is unavailable.

## Still untested
- The real mobile share path, and voice input. See [[05 - Fork Testing]].
