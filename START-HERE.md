# START HERE

**This is the re-entry point.** Coming back after a break and not sure where things stand? Read this (2 min). Or just open a Claude session in this repo and say **"where are we?"** — I keep my own memory of this project and will reconstruct it for you.

**Last updated:** 2026-07-02 — by Claude, at the close of the **Epicor / RF Fager** round-1 session (export delivered; viewer/Edit redesign + hardening fixes merged to `main`).

---

## The vision (one line)
Turn the `documentary-junior-editor` pipeline into a **SaaS app inside the Storyboard Ops platform.** Jeff owns product + editorial; the tooling does the heavy lifting.

## Where we are right now
- The full pipeline works. The **Edit** step was redesigned into an act-by-act "live partner" with a persistent quote-viewer app.
- ✅ **Validated on real projects:** H+S IBEW 2026 (2026-06-30, edit → verified FCPXML export). The live loop is real, not theoretical.
- 🎬 **Epicor / RF Fager — round-1 export DONE (2026-07-02).** Full four-act cut assembled + winnowed to a 29-entry tight cut; FCPXML built and **verify PASS**: `XML/imports/epicor-rf-fager_tight_cut_v1.fcpxml` (56 clips, 6:32), import-ready. Hit an upstream **collapsed-timecode bug** (Doug Duvall 86/87, Bryce 14/46, from the Transcript stage) — patched inline by re-deriving TCs from the FCPXML captions into `tagged-quotes-v2.json`; text untouched (Rule 1 intact). Prevention guardrail **now built (2026-07-02):** a deterministic upstream **timecode-sanity gate** (`scripts/validate_timecodes.py` + `test_validate_timecodes.py`) catches collapsed/non-monotonic/out-of-window TCs at the source — wired into the Orchestrator (hard pre-handoff fail), Transcript (self-check before emit), and Edit (session-start warning) skills. The durable `_editCuts↔segments` export-conversion fix also landed (`88743d8`). Entries #68/#130 need a manual in/out tighten in FCP (mid-segment limitation). Handoffs at `handoffs/epicor-rf-fager/`.
- ✅ **MERGED to `main` (2026-07-02, PR #1, merge `637e109`).** The whole viewer/Edit redesign plus the two hardening fixes — the **timecode-sanity gate** (`aea4c7f`) and the durable **`_editCuts→segments` export converter** (`88743d8`) — are now on `main`. Remaining hardening items are follow-up tasks (Transcript TC root cause; promote editorial lessons into SKILL-edit; FCPXML verify robustness; mid-segment viewer warning) — see `session-hardening-2026-07-02.md`. New work branches from `main`.
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
- `session-hardening-2026-07-02.md` — the issues-and-fixes register from the Epicor edit session (TC gate + export-conversion fixes done; remaining items tasked).
- `memory/` — Claude's persistent project memory (auto-loads each session).

## How to get un-lost in 30 seconds
Open a Claude session in this repo and say **"where are we?"** I'll read my memory + this file and hand you the current state and the single next step. **This file is refreshed at the end of every working session, so it's never stale.**
