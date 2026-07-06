# Session Hardening Register — 2026-07-02
## Source: Epicor / RF Fager round-1 edit + export (live-loop Edit Agent session)
## Purpose: memorialize every issue raised this session and its fix, so the multi-agent
## skill set + quote viewer don't repeat the same mistakes or hit the same hurdles.

Status key: ✅ done (committed) · 🔄 in progress (running task) · 🆕 newly flagged (task chip) · 📝 doc/behavior

---

## A. Data / pipeline correctness

### A1 — Collapsed timecodes at the Transcript stage  ✅ (symptom) + 🔄 (root cause)
**What:** `startTC == endTC` (block-start value repeated at quote AND segment level). Doug
Duvall 86/87, Bryce Fager 14/46; Tim clean. Present in the per-speaker
`doug-duvall-tagged-quotes-v1.json`, so it originates at Transcript/Transcription, not the
Synthesis merge. Undetected for 5 stages; only the FCPXML export caught it.
**Impact:** editorial cut unaffected (viewer is text-based); FCPXML clip windows for Doug were
wrong (12/29 tight entries, 5 hard-truncated).
**Fixes:**
- ✅ **Symptom gate** — `scripts/validate_timecodes.py` (+ `test_validate_timecodes.py`, fixtures),
  commit `aea4c7f`. Per-speaker deterministic checks: `startTC==endTC` runs, non-monotonic
  starts, segment TCs outside quote window, unparseable/inverted. WARN on isolated; FAIL on
  run(≥3)/fraction(≥25%). Wired into SKILL-orchestrator (hard pre-handoff FAIL),
  SKILL-transcript (`--strict` self-check before emit), SKILL-edit (Phase 1 `--warn-only`).
  Would have caught this at the Transcript stage.
- ✅ **Round-1 unblock** — re-derived correct TCs by aligning verbatim text to the FCPXML caption
  offsets → `tagged-quotes-v2.json` (quote text untouched; Rule 1 intact). Rebuild verify PASS.
  Reusable aligner: session scratchpad `repair_doug_tc.py`.
- 🔄 **Root cause (still open):** WHY does Transcript/Transcription emit collapsed TCs? The gate
  catches the symptom; the source still produces bad data. Tracked in the running fix task.
  Owner: root-cause TC task (separate session).

### A2 — Caption-derived TC recovery is a reusable capability  📝
The alignment trick (parse `<caption>` offsets from the extracted per-speaker FCPXML, token-match
each quote/segment near its old block-start anchor) recovered correct TCs cleanly. Worth
promoting from scratchpad into a real `scripts/` tool as the standard TC-repair/backfill path
(and a fallback the Transcript Agent could use when its own TCs are degenerate).
→ folded into the root-cause TC task.

---

## B. Tooling / export robustness

### B1 — Edit→FCPXML `_editCuts` ↔ `segments[]` seam (2nd occurrence)  ✅
**What:** the viewer exports char-range `_editCuts`; `build_fcpxml.py` needs v5 `segments[]` +
word-trims. Hand-converted on h-s-ibew (1st) and again here (2nd).
**Fix:** ✅ canonical converter `scripts/editcuts_to_segments.py` (+ test), commit `88743d8`.
SKILL-edit "Fulfilling an export request" should reference it as the required step (verify the
doc landed; if not, fold into B-doc task).
**Note:** the converter must keep the mid-segment-cut approximation behavior (see B2) and emit a
per-entry fidelity note.

### B2 — Mid-segment interior cuts can't be represented  ✅ (warn) + 📝 (schema)
**What:** the viewer lets an editor cut the *interior* of a segment (#68, #130 this round);
segments+word-trims can only approximate with the widest contiguous span, so the FCPXML plays
slightly wider. Documented v5.7 limitation; the editor tightens in FCP.
**Prevention:**
- ✅ **Viewer warns on interior cuts.** `scripts/quotes_viewer_template.jsx` detects when an
  entry's `_editCuts` leave a fully-cut word *between* two kept words in one source segment
  (`interiorCutSegments`, a JS mirror of `editcuts_to_segments.editcuts_to_segments` — cross-
  validated byte-for-byte against the Python converter). Surfaces three ways: a live amber notice
  in the trim editor as the cut is made (names the retained words), a persistent notice on the
  revealed card, and a compact "⚠ interior cut" badge on the collapsed timeline card.
- ✅ **Flag carried through export.** `exportToFCPXML` stamps affected entries with `_fidelity`
  and adds a top-level `fidelity_warnings[]` to `trimmed-quotes-v*-tight.json`, plus a
  `fidelity_warning_count` on `export-request.json` and a note in the export-confirm modal — so
  the FCPXML handoff/verify can list them automatically instead of the Edit Agent doing it by
  hand. Additive keys; `editcuts_to_segments.py` and `build_fcpxml.py` ignore/preserve them and
  still convert from `_editCuts` (verified). SKILL-edit/SKILL-fcpxml should read
  `fidelity_warnings` on handoff — cross-scope, flagged.
- 📝 **Longer-term (not built):** extend the schema to allow disjoint kept-ranges per segment
  (`kept_ranges: [[start,end],...]`) so interior cuts are *represented*, not approximated. Touches
  Transcript/Synthesis/FCPXML — a dedicated schema pass.

### B3 — Filler one-word segments hard-FAIL the FCPXML verify  🆕
**What:** bare one-word "sentences" ("Right.", "Yeah.", the name "Bryce Fager.") don't exist as
standalone captions (the captioner fuses them), so the matcher can't place them and verify
FAILs — on zero-content filler. This round it forced an extra rebuild after trimming #1/#6/#9/#15.
**Prevention:** the FCPXML verify should **downgrade** a dropped single filler/stopword segment to
a WARNING, not a hard FAIL; and/or the Edit Agent should trim leading filler by default. → task chip.

### B4 — Reference FCPXML named but not present  🆕
**What:** `fcpxml-params-v1.md` named `Sample_narrative.fcpxml` as the reference skeleton, but it
wasn't in the project `xml/` — only in the shared `design-samples/`. The FCPXML Agent had to copy
it in.
**Prevention:** `build_fcpxml.py` should **fall back** to the shared design-sample automatically
(esp. for all-multicam projects where the reference is structural only), instead of erroring.
→ task chip (bundled with B3 as FCPXML build/verify robustness).

---

## C. Agent editorial behavior (so a fresh Edit Agent doesn't repeat the mistakes)

These are captured in project memory + `handoffs/epicor-rf-fager/edit-agent-lessons-v1.md`, but
must be **promoted into SKILL-edit** so ANY agent behaves right, not just this project's memory.

### C1 — No spoken self-IDs (names/titles ride on lower-thirds)  📝 3rd+ sighting → PROMOTE
Cut every "My name is X, I'm the Y" beat; cold-open on story. 3rd+ sighting across projects →
ready to promote into SKILL-edit Selection Principles. (memory `feedback_no_spoken_self_ids`)

### C2 — Decide editorial choices IN the edit, not as abstract chat menus  📝 1st sighting
Put a candidate beat in the Timeline so Jeff reads it in sequence (Review) and keeps/cuts it;
reserve chat questions for non-textual forks (client-sensitivity, scope). (memory
`feedback_decide_in_edit_context`)

### C3 — Winnow bias toward the problem→relief spine  📝 calibration
Build over-inclusive, but recommend the *tight* set leaner on establishing/ambition/credibility
beats (Act 1: 13→6; Jeff cuts these first). Calibration note for the Editing Coach.

→ task chip: promote C1 now (ready), stage C2/C3 for confirmation, into SKILL-edit + the coach.

---

## D. Process / live-loop friction (minor)

- **D1 — Kickoff claimed "viewer already built and served"; it wasn't.** I built + served it (Phase
  1/2). Session-setup should always verify the server responds and (re)build if not, and the
  kickoff template shouldn't assert a running server. 📝 (fold into SKILL-edit Phase 2 note.)
- **D2 — Stale viewer tab / rebuild-refresh.** After an agent rebuild, Jeff must refresh; and the
  viewer's autosave can clobber an agent-written round if the open tab is stale. The Edit Agent's
  "read `viewer-state.json` first, reconcile with the round file on disk" discipline handled it,
  but the viewer could detect a newer round on disk and prompt a reload. 📝 (viewer UX backlog.)

---

## Rollup — what remains after this doc
- 🔄 **A1 root cause** — why Transcript emits collapsed TCs (running task).
- ✅ **B2** mid-segment-cut viewer warning + export flag DONE; 📝 disjoint-kept-ranges schema deferred.
- 🆕 **B3/B4** FCPXML build/verify robustness (filler→warning; reference-file fallback).
- 📝 **C1–C3** promote this session's editorial lessons into SKILL-edit + Editing Coach (C1 ready).
- 📝 **D1/D2** minor session-setup + viewer-reload polish.

The two headline hurdles (A1 gate, B1 conversion) are ✅ committed on `viewer-edit-redesign`
(`aea4c7f`, `88743d8`) — not yet pushed/merged to `main`.
