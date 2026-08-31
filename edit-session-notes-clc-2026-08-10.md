# Edit-session notes — CLC 2026, Round 1 (2026-08-10)

Skill/tooling adjustments proposed from the first Edit Agent session on
childrens-law-center-2026 (Fable 5 as Edit Agent, live local viewer, full
Rough Cut → Reduction → editor's own "Tighter Cut" → FCPXML export in one day).
Input for the Editing Coach / Skill Review promotion loop. Occurrence counts
follow the three-occurrence discipline.

---

## A. Mechanical fixes found this session (commit/port; some already patched in place on the SSD copy)

1. **Orphan parser duplication + fragmentation** (`build_quotes_viewer.py`).
   The build unioned per-speaker `*-orphans-v1.md` AND the Synthesis combined
   `orphan-quotes-v1.md` → 28 duplicate orphan cards; the line-based heuristic
   also split multi-paragraph orphans and dropped speaker attribution.
   **Patched in-session**: structured parser for the combined file (canonical
   `### #NNN` numbering, speaker sections, merged blockquotes, rationale
   capture) with combined-file precedence. Durable fix stays open: Synthesis
   should emit `is_orphan` entries inside tagged-quotes (the build already
   consumes them).
2. **editing-versions dual-location shadowing** — the agent wrote proposals to
   flat `handoffs/editing-versions/` while the viewer saves to
   `handoffs/<slug>/editing-versions/`; the slug copy wins on stem collision,
   so Jeff's viewer kept baking a stale cut ("I don't see any quotes in Act
   2"). **Skill fix (promote):** on flat projects the agent writes cut
   proposals to the viewer's save location (or keeps both locations
   byte-identical, which is what the session fell back to). Alternative code
   fix: union by newest mtime instead of location precedence.
3. **`build_fcpxml.py` null-id routing crash** — viewer-saved title cards carry
   `"source_quote_id": null` (key present), which `"source_quote_id" in entry`
   mis-routed. **Patched in-session** (`is not None`); needs a regression test
   and a note in SKILL-fcpxml's entry-shape examples.
4. **fcpxml-params speaker keys must match tagged-quotes speaker names.**
   Params v1 used short names ("Anne"); the timeline carries full names —
   every entry would have speaker-missed. The FCPXML agent created
   `fcpxml-params-v2.md` mid-build. **Skill fix (promote):** SKILL-fcpxml-params
   gains a validation step — keys must equal the `speaker` values in the
   latest tagged-quotes before emit.
5. **`parse_act_structure()` heading fragility** — act labels in
   `act-structure-v1.md` live as bold text under `### Structure`, so the
   parser found none and the build worked only because entry `part` strings
   happened to match. Fix the parser to read the "Act Labels" section, or make
   SKILL-creative-context emit labels as headings.
6. **Title cards / interstitials still don't render in FCPXML** (known
   limitation §2.4). It bit hard this session: 4 cards hand-added in FCP, in
   the same session where Jeff explicitly promoted interstitial-in-place-of-
   quote as a Reduction tool (see B2). **Promote from "known limitation" to
   the next scripted build priority.**

## B. Skill-text adjustments (promote now — Jeff-stated or directly instructed this session)

1. **Jeff's two-pass standard, near-verbatim** (belongs at the top of Phase 3
   and Phase 5): *the first timeline pass is judged on "everything makes
   sense" — coherence, not brevity. Going from initial to next "is not about
   making sense, it's about what can I cut and still have it work."*
2. **Interstitial-in-place-of-quote is an explicit Reduction tool** (Jeff:
   "an interstitial can sometimes be used in place of actual quotes if the
   quotes are long or are not well worded"). Session proof: #18's stumbly 13s
   → one 6s card that also repaired two facts the cuts had orphaned.
3. **Convert brief Challenges into build constraints before assembling.** The
   14:30 block-structured first Act 1 violated Challenge #3's literal
   instruction ("tight trims interleaved with attorney material rather than
   long Jacoby runs") even though the agent had read it. Phase 3 should
   require an explicit Challenge-compliance check pre-critic.
4. **Blocks vs braid, named.** Source/interview order is not narrative order;
   the transcript-summary cross-reference map is the act's interleave
   architecture, not an appendix. (CLC 2026 is the first occurrence of the
   failure *and* the validated fix — call-and-response braiding, e.g. a chorus
   enumeration serving as the antecedent that lets a trimmed protagonist
   fragment stand.)
5. **Why Beat-3 re-runs the critic:** cuts orphan setups. Cutting #12/#18/#16-
   context silently stranded "third shelter placement" and "emancipation
   papers" — caught only by the fresh-eyes pass on the *reduced* sequence.
   Add this example to the cadence text so the reduction critic never gets
   skipped as "already read it."

## C. First-occurrence patterns (memory/lessons only — do NOT promote yet)

1. **Split-don't-cut.** Jeff's Tighter Cut split #90→90a/90b, #27→27a/27b,
   #30→30a/30b rather than keeping or killing whole entries. The agent's
   Reduction proposals should offer splits, not just keep/cut binaries.
2. **Restrained ask runway.** Jeff cut the entire ask stack — #133, #132,
   #88, #76, even Jim's #105 money line — ending on Anne's "star in their
   future." Directly counter to the brief's "crescendo into the fund-a-need."
   Watch where the FINAL lands before generalizing; may be a
   let-the-emcee-do-the-ask pattern for gala films.
3. **Named-cut correction workflow.** Jeff corrected the agent's Reduction by
   Save-As ("Tighter Cut"), not by Cuts-bin restores — so the correction
   signal lives in *diffs between saved cuts*, not the tweak log. The Coach
   should diff `rough-cut.json` ↔ `v1.json` ↔ `tighter-cut.json`.

## D. Viewer / tooling roadmap items

1. **`scripts/diff_cuts.py`** — membership/order/trim/split diff between two
   editing-versions files. Needed for C3, and the agent hand-rolled exactly
   this twice in-session.
2. **Per-act runtime tallies in the viewer's act nav.** Reduction is steered
   by per-act numbers; the agent recomputed them by script all session. Show
   them live where Jeff cuts.
3. **Document the viewer-save entry shape in SKILL-edit's data model:**
   viewer-saved cuts are `_editCuts`-only (`type: "spoken"`, no `segments[]`).
   Any programmatic re-trim must replace `segments[]` AND strip `_editCuts`
   (they're display-authoritative), or go through `editcuts_to_segments.py`.
4. **Edit-handoff template note:** when a cut never introduces the attorney
   chorus in dialogue (every cold-read pass flagged it), the handoff must
   state that lower-thirds carry roles — supers are load-bearing, not
   decoration.

## What worked — keep, no changes

- The **cold-read critic** earned its place: real catches on all five passes
  (both directions — assembly gaps and reduction-orphaned facts), and the
  bounded loop (1 re-sequence + 1 re-critique → seam-flags) prevented
  polish-chasing.
- **`editcuts_to_segments.py` + fidelity report** — clean conversion of an
  editor-authored cut with splits; the mid-segment fidelity notes went
  verbatim into the handoff to Jeff.
- **Timecode gate at session start** — clean pass, zero cost.
- **Why/why-not notes everywhere** — Jeff audited selection in the Library
  and never had to ask "where did X go."

*Status: session notes only. Skill edits in B await Jeff's sign-off; C items
are 1st sightings; A items need commits (viewer + fcpxml patches currently
live only on the CLC SSD copy of the scripts).*
