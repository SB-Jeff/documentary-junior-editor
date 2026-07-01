# START HERE

**This is the re-entry point.** Coming back after a break and not sure where things stand? Read this (2 min). Or just open a Claude session in this repo and say **"where are we?"** — I keep my own memory of this project and will reconstruct it for you.

**Last updated:** 2026-06-30 — by Claude, at the close of the H+S IBEW 2026 edit session.

---

## The vision (one line)
Turn the `documentary-junior-editor` pipeline into a **SaaS app inside the Storyboard Ops platform.** Jeff owns product + editorial; the tooling does the heavy lifting.

## Where we are right now
- The full pipeline works. The **Edit** step was redesigned into an act-by-act "live partner" with a persistent quote-viewer app.
- ✅ **Just validated on a real project** (H+S IBEW 2026, 2026-06-30): a complete edit → a verified FCPXML export. The live loop is real, not theoretical.
- Code lives on branch **`viewer-edit-redesign`** (draft PR #1). **Not merged to `main` yet.**
- Strategically: we're at the decision of **whether/when to take the viewer to the cloud** (see the migration path — the viewer goes first).

## 👉 THE NEXT ACTION (the one thing)
Decide the immediate next move — pick one:
- **(a)** Claude drafts the **target-architecture + migration doc** (the concrete plan for Phase A: cloud viewer), **or**
- **(b)** Jeff lines up an **engineering owner** for the cloud build first.

Everything else waits behind this choice.

## Settled — don't re-litigate these
- **Edit = act-by-act, agent-goes-first, live-partner model.** (`SKILL-edit.md`)
- **Viewer = persistent local app** — served in Chrome by `viewer_save_server.py` reading the project SSD; three tiers: Quote Library / Timeline / Cuts. (`SPEC-viewer-edit-redesign.md`)
- **Cloud plan is phased:** the **viewer goes to the cloud first (Phase A)**; the **pipeline stays local/hybrid longer (Phase B)** because it's entangled with local media + Final Cut Pro.
- **Dev discipline:** freeze a known-good version; make changes on a branch; small named increments with a clear "done."

## Open / waiting on Jeff
- Cloud go/no-go, and **who owns the engineering.**
- The (a) vs (b) choice above.

## Where the details live
- `SPEC-viewer-edit-redesign.md` — the viewer/edit design spec.
- `quotes-viewer-roadmap.md` — the viewer roadmap.
- `cowork-session-guide.md` — how to run a full editing session start to finish.
- `CHANGELOG.md` — version history.
- `memory/` — Claude's persistent project memory (auto-loads each session).

## How to get un-lost in 30 seconds
Open a Claude session in this repo and say **"where are we?"** I'll read my memory + this file and hand you the current state and the single next step. **This file is refreshed at the end of every working session, so it's never stale.**
