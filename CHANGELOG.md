# Documentary Junior Editor — Changelog

## v5.9 — 2026-06-09 (quote viewer — kickoff-brief P1–P5 batch)

Viewer release. Works the 2026-06-09 kickoff brief (`Downloads/quote-viewer-kickoff-brief.md`,
from the TC Pain Clinic 2026 organic session + Skill Review) — the data-contract hardening and
browser-first persistence punch list. See the `2026-06-09 kickoff brief` section in
`quotes-viewer-roadmap.md`. Five commits, one per item; P1 + P5 verified in a real browser via
the Claude Preview MCP, P2/P4 via the new committed QA gate. Commits local — **not pushed**.

### Quote viewer (`scripts/quotes_viewer_template.jsx`, `scripts/build_quotes_viewer.py`, `scripts/viewer_save_server.py`)

- **Browser-first persistence (P1, `622e95b`).** New `scripts/viewer_save_server.py` — a tiny
  localhost helper (sandboxed to `<root>/handoffs/**.json`, 127.0.0.1-only, CORS) the viewer
  POSTs `{path, content}` to. New `persistFile()` tries the most robust available tier in order:
  **Cowork `callMcpTool` → local helper → browser download** (never-lose-data fallback).
  `saveAsNewRound` (a no-op outside Cowork before) now persists; export gains the helper tier;
  the tweak log writes via Cowork-or-helper but never forces a download. Run
  `python3 scripts/viewer_save_server.py` from the project/SSD root while editing.
- **Fail the build loud (P2, `387a1f4`).** Dropped the silent `["Act 1","Act 2","Act 3"]`
  fallback. `validate_project_metadata()` now aborts the build (non-zero exit) on empty/missing
  `act_labels` or non-`{name,slug}` `speakers`, on both the `--data` and `--slug` paths — naming
  what's wrong and where. A bad input stops the build instead of shipping a blank viewer.
- **Orphan-pool empty-state (P5, `b266437`).** The Quote Library's Orphans section is now always
  rendered, with three states: list / "none match the current filters" / an amber warning that
  orphans were likely not merged upstream (`is_orphan:true` in `tagged-quotes-v*.json`). A silent
  upstream merge gap is now visible at review time.
- **Speaker-color guard (P3).** Already shipped in the 2026-06-01 blank-page batch (`67b1082`):
  every color lookup degrades to a default via `speakerColors[slug] || {bg,fg}`, so a bad
  `speakerSlug` can't throw. P2 now also blocks string-form speakers at build. (Brief's optional
  "visible warning on degrade" left out per simplicity bias — flagged in the roadmap.)

### QA / build tooling (`scripts/test_viewer_build.py`, `scripts/test-fixtures/`)

- **Pre-handoff QA gate (P4, `08dbb19`).** Committed `scripts/test_viewer_build.py` — a runnable
  gate (6 checks, exits non-zero on any regression) plus one fixture per historical failure mode
  (`negative_missing_act_labels`, `negative_string_speakers`, `negative_empty_orphans`,
  `negative_string_source_quote_id`). Pins every blank-page bug as a regression test. Built as a
  zero-dependency build-level gate (this repo is deliberately npm-install-free); runtime render
  smoke-tests run via the Claude Preview MCP.

### Cross-scope flags (not edited here — see `quotes-viewer-roadmap.md`)

- `SKILL-editing-coach.md` should point at `quotes-viewer-roadmap.md` as the single feedback sink (§4).
- Synthesis should emit orphans as `is_orphan:true` inside `tagged-quotes-v*.json` (durable fix for P5).
- Standardize `source_quote_id` as an integer in the documented schema (the build coerces; now regression-tested).

## v5.8 — 2026-05-31 (quote viewer — Tight/Loose/Library rework)

Viewer release. Implements the approved hammer-ner-2026 membership redesign (see the
`hammer-ner-2026` batch in `quotes-viewer-roadmap.md` and the approved mockup
`scripts/mockups/approved-membership-design-v4.html`). Replaces the conviction-tier +
Rough/Tight-view model with an authoritative two-window membership model, unifies the
Edit + Review surfaces, makes the agent handoff iterative, fixes the split bug, and turns
Export into an FCPXML-Agent handoff. All changes are in `scripts/quotes_viewer_template.jsx`
and `scripts/build_quotes_viewer.py`. Verified per entry with a node transpile of the built
component + unit tests of the pure helpers (browser preview was unavailable this session).

### Quote viewer (`scripts/quotes_viewer_template.jsx`, `scripts/build_quotes_viewer.py`)

- **Membership model + verbs + Window toggle (P0).** Every timeline entry now carries
  `membership: "tight" | "loose"`. `membershipOf(entry)` migrates legacy data on load
  (must-keep + tight-candidate → tight; probable-keep → loose; non-spoken structural
  entries → tight) and the build script's `migrate_membership` does the same for the
  raw-handoffs path, dropping `runtime_recommendation`. A **Window** toggle (Tight default
  / Loose) replaces Rough/Tight via `inActiveWindow`, rewired through the timeline filter,
  Library hide-in-cut, runtime totals, and export. Per-card verbs: **Cut → Loose**,
  **Add Back → Tight**, **Drop → Library**; Library **Add** lands straight in Tight; each
  move logs a `set_membership` tweak. Interstitials get the verbs too. Retired
  `runtime_recommendation`, `REC_CYCLE`, the clickable rec badge, `cutFilter`, `inTightCut`,
  and the must-keep/tight-candidate/probable-keep tiers.
- **Unified Edit + Review page with per-card reveal (P1).** The Edit and Review tabs collapse
  into one **Edit** surface (Quote Library stays separate). Default is a clean read
  (`renderCleanCard`); each card exposes only ✎ Edit, which flips it to edit-in-place
  (Cut/Add Back/Drop/Trim/Split live inside), with ✕ Done to collapse. Neighbors stay clean,
  multiple open at once, and a global **Reveal all / Collapse all** acts on the active window.
  Membership chip + colored edge show only in the Loose window. Retired `renderReview`.
- **Iterative "Talk to agent" (P1).** The panel is now per-batch: each op is tagged with its
  batch; **Send batch** copies that batch to the clipboard, appends it to the cumulative
  `handoffs/[slug]/tweak-log-v[N].json` (**schema_version 2**: per-op `batch` field + a
  top-level `batches[]` of `{batch, note, sent_at}`), advances the counter, and clears the
  panel — send-and-keep-working, no rebuild. A per-batch **"Why this batch?"** intent note
  replaces the old free-text commentary. Retired the per-op "Comment on this" button.
- **Split bugfix (P1).** `executeSplit` cloned the full quote onto both halves
  (`_editCuts: []`). It now keeps each half's character span by setting `_editCuts` to the
  complement of `[boundaries[i], boundaries[i+1]]` — verbatim text untouched, only per-half
  trim ranges differ (Cardinal Rule 1). Unit-tested 2-way and 3-way against `buildKeptText`.
- **Export → "Send to FCPXML Agent" (design tie-in).** The button is renamed and export is now
  a handoff: it writes `trimmed-quotes-v[N].json` for the selected window (degrades to a
  browser download outside Cowork via `hasCallMcpTool()`) and shows a modal with a
  ready-to-paste FCPXML Agent launch prompt. The viewer no longer builds the XML itself
  (`build_fcpxml.py` call removed).

### Cross-scope flags (route to the editorial side — not edited from the viewer project)

- `SKILL-editing-coach.md` — the per-op "Comment on this" annotation category is retired, and
  the tweak log is now schema_version 2 (batch markers + per-batch intent notes). Coach's
  documented input changes.
- `cowork-session-guide.md` — stale rough/tight vocabulary and the old direct-build export are
  superseded by the Tight/Loose windows + the FCPXML-Agent handoff.
- `SKILL-edit.md` — the earlier `tight-candidate` dependency is obsolete; the membership model
  supersedes it.

## v5.7 — 2026-05-31 (feedback capture + Hammer NER 2026 review pass)

Skill Review pass on the Hammer NER 2026 project. The headline change is to
**how editorial feedback is captured**: the tweak-log → Editing Coach → Skill
Review chain proved brittle (it silently no-ops when viewer tweak-log
persistence is absent, and hard-stopped Skill Review when Coach hadn't run).
On Hammer NER 2026 it didn't fire at all — the Edit Agent instead wrote a
self-authored lessons doc, which worked better. That pattern is now the
documented default.

Source: `edit-agent-lessons-v1.md` (Hammer NER 2026 Round 1, Edit Agent on
opus-4.7) plus the system-level review of the pipeline state.

### Feedback capture (SKILL-edit.md, SKILL-review.md, cowork-session-guide.md)

- **Edit Agent emits `edit-agent-lessons-v[N].md` at project close**
  (SKILL-edit.md Phase 7, item 5). Primary capture path; reviewer-actionable;
  honors three-occurrence promotion discipline.
- **Editing Coach is now optional.** SKILL-review.md drops the hard Coach
  prerequisite — when Coach didn't run, Skill Review reads the Edit Agent's
  lessons doc directly. `cowork-session-guide.md` reflects the optional step.

### SKILL-edit.md editorial promotions (from Hammer NER 2026)

- **Reference examples are not runtime templates** (Phase 3). Runtime is a
  downstream property of story organization, not a budget; brief "~X% of
  runtime" hints are advisory and do not gate the Rough Cut.
- **Segment selection is structural** (Phase 3). New subsection naming three
  failure modes cut firmly even in the Rough Cut — forward-references,
  tangents, material-covered-better-elsewhere — plus the broad-at-entry-level
  vs. light-hand-at-fat-trim reconciliation.
- **Wrapper-body-wrapper ordering pattern** (Phase 3). The five-point
  single-protagonist + institutional-thesis structure, validated across Pacer
  Center, International Institute, Hammer NER 2026.
- **Cardinal Rule 2 relocated to proposal time** (Phase 3 step 5 / Phase 7).
  Coherence is verified in-session before Jeff sees a sequence; emit does a
  confirmation pass over changed regions only. Rule 1 stays at emit. Rule text
  unchanged — only the verification moment moved.
- **Mid-segment cuts documented as an accepted limitation** (data model).
  `_editCuts` is authoritative for the viewer; FCPXML approximates and the
  editor refines in FCP. Disjoint-`kept_ranges` schema extension parked as
  forward-looking.

### FCPXML doc fixes (from the FCPXML Agent's Round 1 review notes)

- **#4 Reference FCPXML required for all projects** (SKILL-fcpxml-params.md).
  The reference file (`Project Sample.fcpxmld`) drives the project skeleton
  regardless of clip type; it is not single-clip-only. Params Agent must
  always set it. (Left blank on Hammer NER's all-multicam project; stalled
  `build_fcpxml.py`.)
- **#5 Speaker-name authority** (SKILL-fcpxml-params.md). Params speaker keys
  must exactly match the Synthesis `speaker` field in `tagged-quotes-v[N].json`,
  not the FCPXML `<media name=...>` metadata. `build_spine()` does an exact
  dict lookup and silently skips non-matches — a mismatch can yield a 0-clip
  FCPXML. (Hammer NER: `Isiah` / `Mike & Janna Stern` metadata vs. canonical
  transcript names.) Root cause shared with the slug-vs-display-label issues
  below — a cross-agent shared-vocabulary problem.
- **#6 Cut-selection confirmation** (SKILL-fcpxml.md Phase 1, new step 1.6).
  Before generating, state must-keep vs. probable-keep counts and ask which
  cut(s) to emit — rough, tight, or both. (Agent emitted rough when Jeff
  wanted tight; had to regenerate.)

### SKILL.md drift cleanup

- Version header (was "5.0"), "Current version" → 5.7, "eight agents"
  wording, folder tree (added SKILL-orchestrator.md, SKILL-editing-coach.md,
  cowork-session-guide.md, quotes-viewer-roadmap.md, and the current script
  set), handoffs listing (added edit-agent-lessons + lessons-learned).

### Still open / parked

- **FCPXML script bugs (code follow-ups, `build_fcpxml.py` / `generate_fcpxml.py`
  — OPEN, high priority):**
  - #1 Act-boundary title cards all stack at the sequence-start offset
    (~3600.01s) instead of their actual act positions — section-divider offset
    must track cumulative spine duration.
  - #2 `parse_act_structure` regex `(?:Act|Part|Section)` misses "Intro" and
    other non-Act-prefixed headings — extend to Intro/Epilogue/Prologue, or
    match all `##` headings under `## Structure`.
  - #3 Slug `part` fields (`act-1-addie`) don't canonicalize to display labels
    ("Act 1 — Addie") in `_canonicalize_section` — add slug↔label
    normalization, or have the Edit Agent emit display labels in `part`.
- Disjoint `kept_ranges` schema extension for mid-segment cuts (forward-looking).
- `scripts/build_quotes_viewer.py` and `scripts/quotes_viewer_template.jsx`
  carry uncommitted Hammer NER 2026 patches (act-chip labels, data-shape
  normalization, authoritative `_editCuts` round-trip) — commit with this pass.
- Hammer NER 2026 reference-example folder (Final_Edit.txt + lessons-learned.md
  + transcripts) not yet built — next step.


## v5.6 — 2026-05-21 (quote viewer batch)

Viewer release. Clears the open `quotes-viewer-roadmap.md` queue — three P0 items
(two regressions + the Editing Coach's blocking dependency) and five P1 items —
ahead of the next editing session. All changes are in `scripts/quotes_viewer_template.jsx`
and `scripts/build_quotes_viewer.py`; no agent-facing skill semantics changed. Two
items ship their viewer/build halves with the SKILL-edit.md half flagged for the
Editing Coach (see "Cross-scope dependencies" in the roadmap).

### Quote viewer (`scripts/quotes_viewer_template.jsx`, `scripts/build_quotes_viewer.py`)

- **Tweak-log persistence (P0).** `applyLocalEdit` now records structured ops
  (`seq`, `entry_id`, `change_type`, `before`, `after`, `timestamp`, `note`,
  `description`). On Send and Export the viewer writes
  `handoffs/[slug]/tweak-log-v[N].json` via `callMcpTool` (no-op outside Cowork),
  matching the input `SKILL-editing-coach.md` documents. Coach no longer runs in
  degraded fallback mode.
- **Drag-to-reorder fixed (P0 regression).** Root cause: native HTML5 drag-and-drop
  is unreliable inside Cowork's sandboxed artifact iframe. Reimplemented with pointer
  events (`setPointerCapture` + `pointermove`/`pointerup`), robust in every context.
  The **whole card** is the drag source (excluding buttons + trim/text editors), with
  a 5px click-vs-drag threshold and mid-drag selection suppression — the left-edge grip
  alone was undiscoverable. Within-act reorder; cross-act moves use the act-reassign
  dropdown.
- **Interstitials restored (P0 regression).** "+ interstitial" insertion controls
  between every Edit-view entry and at each act head, with an inline editor
  (interstitial / title_card / context_beat, text, duration). Non-spoken entries get
  a dedicated amber card with editable text/intent + duration; Review view renders
  them inline (attributed as their type, e.g. "— TITLE CARD", with italic text).
  Verbatim quote text stays untouched (Cardinal
  Rule 1). Restores the viewer as a complete surface for Cardinal Rule 2.
- **Quote Library: hide-in-cut filter (P1).** Toggle hides source quotes already in
  the active cut (respects Rough/Tight via a shared `inTightCut` predicate);
  persisted per project in localStorage.
- **Quote Library: search (P1).** Real-time, case-insensitive match on verbatim quote
  text + rationale, composed after speaker/act and hide-in-cut filters; transient.
- **Quote Library: act-reassign dropdown (P1).** Re-tag a source quote's act from the
  Library; held in viewer state (`sourceActOverrides`) and logged as a
  `reassign_source_act` tweak for the Edit Agent to persist canonically. The viewer
  never overwrites the upstream `tagged-quotes` file.
- **Tight-candidate state (P1, viewer + build halves).** Rec badge cycles three states
  (must-keep → tight-candidate → probable-keep); Tight cut = must-keep +
  tight-candidate. `build_quotes_viewer.py` no longer collapses `tight-candidate`.
- **tight_priority ranking — built then reverted.** The badge + view-only "priority
  sort" was implemented, then removed on Jeff's call: sorting probable-keeps by
  confidence pulls quotes out of their intended playback order, which fights the
  narrative read-through (Cardinal Rule 2). Re-filed to the roadmap with a
  non-reordering constraint for any future attempt.
- **Test harness.** Added `scripts/test-fixtures/sample_viewer_data.json` — a committed
  fixture (2 speakers, 3 acts, must/tight-candidate/probable mix, orphan, interstitial)
  for a repeatable `build_quotes_viewer.py --data` manual-test loop.

### Cross-scope dependencies flagged (not changed here)

- The Edit Agent populating **`tight-candidate`** during the rough cut requires a
  `SKILL-edit.md` change owned by the Editing Coach. The viewer + build-script halves
  shipped; the skill-side half is flagged in the roadmap entry for coordination —
  `SKILL-edit.md` was not edited.
- `SKILL-edit.md:1080` says drag reorders "within or across acts," but the
  implementation constrains drag to within an act (cross-act via the dropdown).
  Doc/behavior discrepancy flagged in the roadmap for the skill owners.

## v5.5 — 2026-05-21

Minor release. New **Orchestrator Agent** formalizes the parallel sub-agent fan-out
pattern that ran organically on the 2026 Nanos Boston project. Step 2 of the
pipeline now collapses from N+1 separate Cowork sessions (one FCPXML Params + one
Transcript Agent per speaker) into a single Orchestrator session that launches
all of them as parallel sub-agents.

For a 10-speaker project this is a 10× reduction in session-launch overhead.

### Orchestrator Agent (new — `SKILL-orchestrator.md`)

- **Tenth agent in the pipeline.** Inserted at Step 2, between Creative Context
  and Synthesis. Model: sonnet-4.6 (coordination work, not creative judgment).
- **Single coordination session.** One Cowork session launches all sub-agents in
  parallel via a single Task-tool message with multiple invocations. Sub-agents
  return when complete; Orchestrator validates outputs exist on disk.
- **Plan-then-confirm pause point.** Orchestrator surfaces the planned fan-out
  (which sub-agents, expected file count) for Jeff's one-click confirmation
  before launching anything. This is the only human-in-the-loop moment.
- **Re-run patterns documented.** Targeted re-runs work — Creative Context updated
  to v2 triggers re-run of all Transcript Agents at v2; targeted speaker re-runs
  scope to only those speakers; FCPXML Params re-extraction explicit-only.
- **Standalone manual launches still valid.** Both `SKILL-transcript.md` and
  `SKILL-fcpxml-params.md` retain their standalone Cowork session pattern for
  surgical one-off work. Orchestrator is the default for first runs and bulk
  re-runs.
- **Failure handling: no auto-retry.** If any sub-agent fails or returns
  incomplete output, Orchestrator reports and waits for Jeff's direction.
  Failures usually indicate a deeper issue that auto-retry would just repeat.
- **Pilot reference.** 2026 Nanos Boston brand-video (May 14, 2026) ran this
  pattern organically before it was codified; all 41 expected output files
  materialized on disk on first attempt.

### `SKILL.md` (master)

- Pipeline diagram updated: ten agents, Orchestrator inserted at Step 2.
- Agent count updated from nine to ten throughout.
- v5.5 highlights section added.

### `SKILL-creative-context.md`

- "Next step" section rewritten to hand off to Orchestrator instead of telling
  Jeff to launch N+1 sessions manually.
- Launch prompt for Orchestrator provided as the single handoff prompt (replaces
  the prior multiple launch prompts for Transcript and FCPXML Params).
- Note added: standalone manual launches of Transcript or FCPXML Params Agents
  remain valid for surgical re-runs; Orchestrator is the recommended default.

### `SKILL-transcript.md` and `SKILL-fcpxml-params.md`

- Brief sub-agent invocation pattern section added under "Your Role" (Transcript)
  and "Cardinal Rules" (FCPXML Params). Notes that the recommended invocation
  path is via Orchestrator, but standalone manual launches remain valid.
- Instructions themselves unchanged — both skills function identically whether
  launched by the Orchestrator or by Jeff manually.

### `cowork-session-guide.md`

- Title version bumped to v5.5.
- Step 2 collapsed from "Step 2a (FCPXML Params solo) + Step 2b (one Transcript
  Agent per speaker)" to single "Step 2: Orchestrator Agent." Includes starter
  prompt, how-it-runs walkthrough, expected output count, re-run patterns, and
  fall-back-to-manual guidance.
- Step 5 split into Step 5a (Editing Coach at-close, v5.4) and Step 5b (Skill
  Review). The prior guide didn't reflect the v5.4 Coach split — folded in here.
- Quick Reference table updated to show Orchestrator at Step 2 and the 5a/5b
  split. Also adds the optional between-rounds Coach invocation in Step 4.
- Overview text updated: pipeline now described as ten agents.

### Version footers bumped

- `SKILL.md` → v5.5 (current version line)
- `SKILL-orchestrator.md` → v5.5 (new file)
- `SKILL-creative-context.md` → v5.5
- `SKILL-transcript.md` → v5.5
- `SKILL-fcpxml-params.md` → v5.5 (was v5.4.1; this release supersedes)
- `cowork-session-guide.md` → v5.5

`SKILL-edit.md`, `SKILL-fcpxml.md`, `SKILL-synthesis.md`, `SKILL-transcription.md`,
`SKILL-editing-coach.md`, `SKILL-review.md` unchanged in v5.5 — they remain at
v5.4 or v5.4.1.

## v5.4.1 — 2026-05-21

Patch release. Three Nanos technical findings landed into the FCPXML Params and
FCPXML Agent skill files so the next project doesn't re-discover them. Driven by
the 2026 Nanos Boston brand-video FCPXML Params Agent session (May 14, 2026)
which surfaced the failure modes during first-run execution.

### `SKILL-fcpxml-params.md`

- **New "Project UID — intentionally omitted" section.** Documents the
  `generate_fcpxml.py` fix that removed the block copying `uid`/`modDate` from
  the reference project (`Project Sample.fcpxmld`). Explains the duplicate-
  multicam-on-second-import bug it prevents. Exists to ensure the Params Agent
  doesn't re-introduce project UID extraction in a future revision.
- **Known pattern: camera file code angle naming.** When `<mc-angle>` `name`
  attributes carry camera file codes instead of human-readable "tight"/"wide"
  labels, the convention observed on Nanos (8 of 10 speakers) is `P1008xxx` =
  tele/zoom, `P1SBxxx` = wide. Documented in the "Identifying tele vs wide"
  section. Future projects assign by this pattern but still flag for Jeff's
  eyeball confirmation; not a blocker since angle toggling works in FCP.
- **Source path detection.** Source FCPXMLs may live at `XML/exports/`
  (canonical per `SKILL.md`) or `xml/outputs/` (observed on Nanos). Params Agent
  must auto-detect. Future projects should standardize on `XML/exports/`.
- **`.fcpxmld` package flag for FCPXML Agent.** If source FCPXMLs are
  `.fcpxmld` packages (directories with `Info.fcpxml` inside), the handoff must
  include an explicit flag alerting the FCPXML Agent to run Phase 0
  (`extract_fcpxml.py`) before reading source files. Params Agent itself parses
  `Info.fcpxml` directly from packages so its own work is unaffected, but
  `build_fcpxml.py` downstream can't find any source files because it matches
  only `*.fcpxml`, not `*.fcpxmld`.

### `SKILL-fcpxml.md`

- **Phase 0 upgraded from "suggested" to "REQUIRED".** Added auto-detection
  between `XML/exports/` and `xml/outputs/` paths. Added a precondition check
  that distinguishes (a) packages-need-extraction, (b) already-extracted, (c)
  files-only-no-packages, (d) no-source-files-found-stop-the-agent. The last
  case is a hard fail; the prior version of Phase 0 would silently proceed and
  fail in confusing ways downstream when `find_speaker_fcpxml()` returned
  empty.
- Added a "Why this phase is required" section citing the Nanos failure mode
  so the requirement isn't dropped in a future cleanup pass.

### Code work referenced

`scripts/generate_fcpxml.py` — block copying `uid`/`modDate` from reference
project removed. SHIPPED (in the same Nanos session work).

`scripts/build_fcpxml.py` — no changes required for the Nanos fixes. The
`find_speaker_fcpxml()` function still only matches `*.fcpxml`; the fix is
upstream (Phase 0 must run first). Adding `.fcpxmld` package handling directly
in `build_fcpxml.py` could be a future enhancement, but extraction-as-required-
precondition is the cleaner pattern.

### Version footers bumped

- `SKILL-fcpxml-params.md` → v5.4.1
- `SKILL-fcpxml.md` → v5.4.1

Other v5.4 files unchanged. `SKILL.md` (master) stays at v5.4 — this is a
patch to two agent files, not a release-level update.

## v5.4 — 2026-05-21

Pipeline learning-loop release. Two foundational changes: narrative coherence formally
promoted to Cardinal Rule status alongside the verbatim rule, and a new Editing Coach
Agent introduced to systematically improve Edit Agent performance from session feedback.
Skill Review Agent narrowed in scope to pipeline-wide concerns now that Edit-Agent-
specific analysis lives in Coach.

Driven by the 2026 Nanos Boston brand-video project review (May 2026). Nanos surfaced
two recurring issues: (1) the Edit Agent didn't proactively check narrative coherence
unless Jeff explicitly asked, and routinely produced cuts that didn't read as continuous
narrative when Jeff probed them, and (2) Jeff was using `must-keep` as a workspace
toggle to inflate the Tight view rather than as a conviction signal, contaminating the
override log and pointing at both a SKILL-edit.md gap (no ranking inside probable-keeps)
and a quote viewer gap (no tight-candidate state distinct from must-keep).

### Cardinal Rule 2 — Narrative Coherence (new)

- **Promoted from feedback rule to Cardinal Rule status.** Previously documented as a
  "Narrative Coherence Rule" subsection in `SKILL-edit.md` only and as a feedback
  memory in Jeff's conversational memory. Now formal Cardinal Rule 2, repeated in every
  agent skill file alongside Cardinal Rule 1 (verbatim quotes).
- **Operationalized in `SKILL-edit.md` Phase 7.** Phase 7 renamed from "Cardinal Rule
  Verification" to "Cardinal Rules Verification" and split into two required checks:
  Rule 1 verification (per-entry verbatim integrity, unchanged) and Rule 2 verification
  (whole-timeline narrative coherence — orphan pronouns, back-reference openers,
  subject anchoring, logical jumps, redundancy, tonal whiplash, act transitions). A
  cut is not "ready to present" until both pass. Required after every change, every
  round, applies equally to rough and tight.
- **Master `SKILL.md` updated.** "The Cardinal Rule" section renamed to "The Cardinal
  Rules" with both rules side-by-side. Pipeline diagram updated to show nine agents.

### Editing Coach Agent (new — `SKILL-editing-coach.md`)

- **Companion to the Edit Agent.** Reads the quote viewer's override log + Jeff's
  reasoning, identifies patterns where the Edit Agent's defaults diverged from Jeff's
  judgment, turns those patterns into targeted SKILL-edit.md updates and viewer
  roadmap entries.
- **Two modes.** Between-rounds (course-correct mid-project, briefs the next Edit
  Agent invocation) and at-close (consolidate across all rounds, codify into skill
  files, hand off to Skill Review).
- **Co-equal primary inputs.** Edit Agent performance AND quote viewer design. Coach
  routes each finding to Agent / Viewer / Both during clustering.
- **Three-occurrence rule for rule promotion.** Observations promote to SKILL-edit.md
  rules only after appearing in 3+ projects (or with Jeff's explicit blessing).
  Prevents premature codification of project-shaped insights.
- **No separate coaching corpus file.** The collection of past projects'
  `reference-examples/[project-name]/lessons-learned.md` files IS the corpus. Coach
  reads them filtered by project type.
- **Known pattern seeded from Nanos:** must-keep-as-workspace toggle. Two-pronged
  fix: SKILL-edit.md ranks within probable-keeps, viewer exposes a tight-candidate
  state distinct from must-keep. Both flagged for future work.

### Skill Review Agent redesign (`SKILL-review.md`)

- **Narrower scope.** Pipeline-wide only: technical issues, system design observations,
  capability/state-of-the-art audit, Jeff's forward-looking ideas, reference-example
  contribution. Edit-Agent-specific analysis (override patterns, editorial corrections,
  rule promotion) moves to the Editing Coach Agent.
- **New phase: Capability audit.** Web-search for new Claude capabilities, new MCPs,
  new orchestration patterns since the last project; surface candidates for pipeline
  redesign. Nanos already flagged one (sub-agent parallelism for Transcript + FCPXML
  Params); this phase ensures future projects systematically look for similar wins
  rather than discovering them by accident.
- **Removed:** much of the diff-mining ceremony, the dense per-agent question
  checklist, and the multi-step sync-and-push wrap-up (sync stays; ceremony shrinks).

### Shared `lessons-learned.md` structure

Coach and Skill Review write to one file per project under these headers:

- `## Session Feedback: Editing` (Coach)
- `## Session Feedback: Quote Viewer` (Coach)
- `## Session Feedback: System` with sub-sections `### Technical Issues`,
  `### Architecture & Design`, `### Capability Audit` (Skill Review)
- `## Forward-Looking — Jeff's Ideas` (Skill Review)
- `## Reference Value` (Skill Review)

Authorship implicit by section. Future Coach invocations read the Editing + Quote Viewer
sections of past projects' files as their corpus; future Skill Review invocations read
the System + Forward-Looking sections similarly.

### Quote viewer roadmap (`quotes-viewer-roadmap.md`)

New file at the master skill folder root. Single source of truth for viewer change
requests, consumed by the separate Claude Code project that owns viewer development.
Coach files per-project entries from Cowork sessions; entries migrate to master at
project close so the canonical viewer code and its roadmap travel together.

### Skill version footers bumped

- `SKILL.md` → v5.4
- `SKILL-edit.md` → v5.4
- `SKILL-editing-coach.md` → v5.4 (new file)
- `SKILL-review.md` → v5.4 (redesigned)

Other agent skill files (`SKILL-transcription.md`, `SKILL-creative-context.md`,
`SKILL-transcript.md`, `SKILL-fcpxml-params.md`, `SKILL-synthesis.md`,
`SKILL-fcpxml.md`) remain on their prior versions; Cardinal Rule 2 still applies to
them via the master `SKILL.md` header. They should be updated to include both rules
in their own headers on the next Skill Review pass that touches each.

### Known carry-forward items

- **Tweak-log persistence.** Editing Coach assumes `tweak-log-v[N].json` is saved to
  disk at session end. The viewer template doesn't currently do this. Tracked as a
  parallel code track for the Claude Code viewer project. Coach has documented
  fallback inputs (visible viewer state, Jeff's memory, rough/tight diff) for
  projects without persistence — including the Nanos brand-video project itself,
  which will be the first run under v5.4.

## v5.3 — 2026-05-13

Viewer template rewrite + supporting SKILL changes, all landing as a single
release. Major user-facing change: the quote viewer is now React-rewritten
against the v5.0 data model with v4.0.1-style editorial affordances restored
(whole-quote cards, drag-to-reorder, scissors split, character-range trim
editor), plus several new capabilities (Rough/Tight sub-toggle, round
dropdown with Save-as-new, unified Send-to-agent panel, direct-write Export).

### Viewer rewrite (`scripts/quotes_viewer_template.jsx`)

Replaces the v4.0.1 canonical template entirely. Universal component, same
across all projects. Three top-level views — **Edit** (default), **Review**,
**Quote Library** — driven by a tab-style mode toggle in the header. Header
is two-tone (gray identity/nav row, white filter/cut row) with content
centered to match the main pane.

- **Edit view** uses v4.0.1-style quote-block cards: whole-quote display
  (no segment breakdown in UI), drag-and-drop reorder via the left-edge
  drag handle (not the whole card — fixes the text-selection-hijack
  failure mode), ↑/↓ move buttons within an act, scissors split into
  sub-quotes with `#5a`/`#5b`-style IDs (entry IDs are derived from
  source num; the legacy `e_NNN` namespace is retired), character-range
  trim editor (highlight + Delete, snaps to word boundaries, supports
  middle drops), clickable recommendation badge that toggles
  must-keep ↔ probable-keep, act-reassign dropdown, per-card
  Comment-on-this button.
- **Two-tier recommendation system.** Collapses the v5.0 four-tier
  (`must-keep` / `probable-keep` / `probable-cut` / `optional`) to
  two-tier (`must-keep` / `probable-keep` only). Reduction is now about
  demoting recommendations to land Tight Cut at target runtime, not
  about dropping entries. The build script auto-migrates legacy
  four-tier data on first build.
- **Rough/Tight sub-toggle** in the Edit view header. Rough = must-keep
  + probable-keep (the agent's wider selection). Tight = must-keep only.
  The Cut block shows the active cut's entry count + runtime, with the
  Export button folded in.
- **Round dropdown** in the header. Loads versions baked at build time
  from `editing-versions/v[N].json`. Includes "+ Save current as new
  round" which writes a new round file directly to disk via
  `window.cowork.callMcpTool('mcp__workspace__bash', ...)` — no paste,
  no chat round-trip. Switching rounds with unsynced tweaks prompts to
  confirm; pending tweaks are scoped per-round.
- **Send-to-agent panel** (bottom-right docked, collapsible) unifies
  the prior dual Sync + Discuss surfaces into one: pending tweaks list,
  editorial commentary textarea, single Send button. Send composes a
  chat message that includes ops + optional commentary + full timeline
  JSON + version stamp, copied to clipboard for paste. The panel's
  collapsed state shows a yellow warning border when there are pending
  tweaks (replaces the prior header pill).
- **Export is self-contained.** Click Export and the viewer writes the
  current working state to the round's JSON file via `callMcpTool`,
  then invokes `build_fcpxml.py` directly. **Does not require Sync
  first** — state alignment happens as part of Export. Sync stays as a
  separate, intentional act of "here's my reasoning, learn from it."
- **Quote Library view** (formerly "Source Pool" — renamed for
  clarity) shows every catalogued quote with whole-quote text,
  rationale, and act tag. Segments are not exposed in the UI (backend
  data only). Orphans appear in a dedicated section at the bottom of
  the list, not as an Act filter chip (orphan is an editorial verdict,
  not an act).
- **Graceful degradation outside Cowork.** Save, Export, and other
  `callMcpTool` actions show clear "only available inside Cowork"
  messages when the viewer is opened as a static HTML file in a regular
  browser. The viewer remains read-only-functional for review purposes.

### New `scripts/build_quotes_viewer.py`

Companion build script that wraps the canonical .jsx template into a
self-contained HTML artifact (React 18 + Babel-standalone + inline CSS).
Replaces the previous ad-hoc wrapping that the Edit Agent did at session
time. Auto-discovers project data from the handoffs folder, migrates v5.0
segment-based trims to character-range trims for the new viewer, collapses
four-tier recommendations to two-tier, and emits a ready-to-load HTML file.

Invocation:

```
python3 scripts/build_quotes_viewer.py \
    --slug <project-slug> \
    --ssd-root <project-ssd-root> \
    --output <handoffs/[slug]/[slug]_quotes_view.html>
```

The Edit Agent runs this once at Phase 2 session start, then calls
`mcp__cowork__create_artifact` with the output.

### SKILL-edit.md changes

- **Phase 2 rewritten.** Documents the new build-script invocation,
  enumerates the v5.0 viewer's capabilities, removes the obsolete
  "Viewer template — Phase 3 follow-up" section (gap closed).
- **Phase 3 (Rough Cut) updated.** Two-tier recommendation system
  documented; Rough/Tight semantics explained; removed `probable-cut`
  and `optional` tier descriptions.
- **Phase 5 (Reduction) reframed.** Reduction is now about demoting
  recommendations to land the Tight Cut at target runtime, not about
  dropping entries. Drop-entry retained only for "shouldn't have been
  pulled in at all" cases. Segment-level trim/drop guidance replaced
  with the viewer's character-range editor + split workflow.
- **Data model section** updated to document `_editCuts`, `_subLabel`,
  the entry_id namespace migration (`e_NNN` retired in favor of
  source-num-derived IDs with letter suffixes for splits), and the
  two-tier recommendation values.

### Out of scope, parked for separate review

- **`build_fcpxml.py` v5.0-awareness update.** The script still expects
  v4.0.1-shape JSON. The viewer's Export button calls it but the script
  fails at the load step against v5.0 entries. Highest-priority parked
  work; blocks actual FCPXML round-trip testing of the new viewer.
- **Editing Coach Agent.** New SKILL for evaluating post-project
  feedback and proposing SKILL updates. Designed during this review but
  deferred to a separate ship. Scope: read `editorial-feedback-v[N].md`
  + Final_Edit comparison across reference examples, propose
  `skill-update-proposal-v[N].md` for human review. Per-project cadence
  initially; scales back when patterns stabilize.
- **Feedback file persistence layer** (`editorial-feedback-v[N].md`).
  The viewer's Send-to-agent panel can already produce the commentary;
  the agent-side handling that appends it to a per-project feedback
  file at session end, and reads it at next session start, is the
  follow-up work.
- **FCPXML Agent elimination.** Pipeline simplification flagged during
  review; deferred until `build_fcpxml.py` is hardened enough that the
  viewer's direct-invoke path can replace the agent's orchestration
  layer.
- **Cowork session guide updates** for the new viewer interactions
  (Save-as-new-round, Comment-on-this, Export semantics). Pending.

### Reference artifacts produced during this session

- `handoffs/tccs-dr-pan-testimonials/viewer_and_refinement_punch_list.md`
  — the design-review punch list used to drive the rewrite.
- `handoffs/tccs-dr-pan-testimonials/tccs-dr-pan-testimonials_v4_viewer.html`
  — v4.0.1 comparison viewer rendered with TCCS data, used to validate
  the trim-and-split workflow before committing to the rewrite.
- `handoffs/tccs-dr-pan-testimonials/tccs-dr-pan-testimonials_mockup_v1.html`
  — full integrated mockup of the rewritten viewer.
- `handoffs/tccs-dr-pan-testimonials/tccs-dr-pan-testimonials_header_redesign.html`
  — header layout exploration with side-by-side variants.
- `handoffs/tccs-dr-pan-testimonials/tccs-dr-pan-testimonials_send_panel_sketch.html`
  — Send-to-agent panel design sketch.

## v5.2 — 2026-05-13

Skill Review pass for the TCCS Dr Pan & Testimonials project. Folds in the
unreleased v5.1 / v5.1.1 working-tree changes that addressed the
Transcription Agent's host-side launcher pattern, and adds new lessons from
the FCPXML stage and the editor's actual finishing-pass behavior.

### Rolled-up v5.1 / v5.1.1 content (previously uncommitted on this SSD)

- **Full Disk Access documented as a one-time per-machine setup** in
  cowork-session-guide.md. Without it, the Cowork sandbox can't bind-mount
  external SSDs and every transcription session falls back to host-side
  Terminal.
- **`.env` replaces git-crypt** for the AssemblyAI key. Key lives at
  `documentary-junior-editor/.env`, gitignored, read by python-dotenv. The
  legacy `secrets/assembly_ai.key` git-crypt path is deprecated and slated
  for deletion.
- **`start-editing` host-side launcher** added. Single bash command, no
  file extension (avoids chat auto-linking of `.py` / `.sh`), self-resolves
  project root, preflights folder layout / API key / Python deps, runs
  transcription, reports outcome. Replaces multi-line copy-paste sequences
  that had been failing in chat.
- **`commit-skill-changes` helper** added for syncing SSD-side SKILL edits
  to the Desktop clone with a `.commit-message` file.
- **SKILL-transcription.md rewritten** around the launcher pattern. Phase 4
  is now "present the single bash command to Jeff"; the agent waits, then
  validates results and writes the handoff doc.
- **SKILL.md and cowork-session-guide.md** updated to document the new
  setup and reference the launcher.
- **Opus 4.6 → Opus 4.7** across all SKILL files where Opus is the model.
  Sonnet stays at 4.6.

### New for v5.2 — from the TCCS Dr Pan & Testimonials review

- **Act title cards: every export must include them; the editor strips at
  finishing.** Rule promoted in SKILL-fcpxml.md. The FCPXML Agent must
  auto-generate one title card per act boundary on every emission,
  regardless of whether the Edit Agent emitted explicit `title_card`
  entries. Title cards are the editor's structural editing aid and are
  removed as the last polish step.
- **Cross-reference pair flag is a suggestion, not a constraint.** When
  the Edit Agent or FCPXML Agent flags a quote pair as "keep both; do not
  merge or reorder," that's a recommendation. The editor may reorder
  around the pair in finishing. SKILL-edit.md language softened.
- **Edit Agent blind spot: outcome / visual-result material.** SKILL-edit.md
  now instructs the agent to scan the full tagged-quotes pool for any
  outcome-description quote that didn't make the initial selection,
  particularly for Act 3. The pool contains fully-tagged quotes the
  agent's selection can miss.
- **Segment-level pruning guidance.** SKILL-edit.md notes that the editor
  consistently drops more segments inside kept entries than the agent's
  plan suggests. When in doubt, the agent should err toward fewer segments
  per entry, especially when the entry already lands its core idea in
  segs 0-1.
- **Restore tail-beat codas under suspicion of redundancy.** SKILL-edit.md
  notes that tail segments the agent calls redundant often earn their
  place in finishing. When dropping a tail segment, the agent should
  surface the call for explicit confirmation rather than silently dropping.
- **Multi-speaker FCPXML resource-ID remap documented.** SKILL-fcpxml.md
  documents that per-speaker captioned `.fcpxmld` exports all use `r2` as
  their multicam media resource ID. Merge into a single output FCPXML
  requires dynamic remap (detect highest ID in first speaker's XML, shift
  subsequent speakers above that range).
- **Multi-output multicam re-import duplication documented.** SKILL-fcpxml.md
  documents the duplicate-on-reimport problem: emit references to library
  multicams by UID, do not re-declare the full `<media>` block in every
  output FCPXML.
- **`parse_params_md()` basename bug flagged.** Pending fix in
  `build_fcpxml.py` — uses `os.path.basename()` on `.fcpxmld/Info.fcpxml`
  paths, stripping the package name.
- **Mid-quote zero-duration segment verification.** SKILL-fcpxml.md adds a
  pre-lock verification step for any segment flagged with zero-duration
  timecode estimates (the FCPXML Agent should verify against source audio
  rather than silently using the estimate).
- **Slug-consistency rule.** SKILL-transcription.md adds Phase 0.5 — confirm
  project slug with Jeff before writing the handoff doc, so downstream
  agents read the same path.
- **SSD-must-remain-mounted note.** cowork-session-guide.md troubleshooting
  entry: disconnecting / reconnecting the SSD mid-pipeline breaks the
  Cowork session's folder permission grant.
- **Drive-name rule promoted.** cowork-session-guide.md "Project Folder
  Structure" section now states upfront that project SSD names must avoid
  spaces and special characters (`& ; : ' " <space>`). Previously only in
  troubleshooting.
- **SKILL-review.md Phase 3 follow-up tracking refreshed.** Marks
  `transcribe.py` work as shipped (v5.1), `build_fcpxml.py` as the highest
  priority next code work, viewer template as parked for separate review,
  `secrets/assembly_ai.key` as ready for deletion.

### New reference example

- `reference-examples/tccs-dr-pan-testimonials/` — Customer Testimonial,
  single-speaker patient testimonial with supporting practitioner, single
  Edit Agent round with `skip_to_fcpxml`, no v2 emissions. Includes
  `lessons-learned.md`, `Final_Edit.txt`, and the in-scope raw transcripts.

### Out of scope, parked for separate review tasks

- **Quote viewer (`quotes_viewer_template.jsx`) design review.** Multiple
  rounds of drift across recent projects; some prior design was lost,
  some new functionality is good, some needs tweaking. To be addressed
  in its own task.
- **Pipeline architecture review.** The 8-agent pipeline assumes the
  editor wants the agent to do narrative + selection work. The editor's
  actual workflow on TCCS Dr Pan was closer to: agents do mechanical work,
  editor makes all editorial decisions in FCP. Whether the pipeline
  should be simplified for that workflow is a strategic question to
  address in its own task.

## v5.0 — 2026-04-29

Major version — twelve lessons distilled from the International Institute of Minnesota
Fund-a-Need 2026 review, including a fundamental data-model rewrite (segments + timeline
entries), a new Transcription Agent at pipeline position 0, universal pipeline versioning,
the Edit Agent reframed as a multi-round partner, and Phase 0 Discovery on the Creative
Context Agent.

### Quotes are clay; the timeline is the work product (SKILL-edit.md, SKILL-transcript.md, SKILL-synthesis.md, SKILL-fcpxml.md, SKILL.md)

The biggest data-model change since v3.1's Selection+Trim merge into the Edit Agent.
Source quotes are no longer atomic blocks the Edit Agent annotates with trim metadata —
they are decomposed into **segments** at tag time. A segment is a meaningful,
self-contained piece of an idea (a clause or phrase that completes a thought). Smaller
than a sentence. Larger than a word.

The paper cut becomes a **timeline of entries**. Each entry has `segments[]`; each
segment references its source quote, source segment index, and optional per-segment
head/tail trim. A timeline entry is a contiguous-in-source-order play of segments from
one source quote, with arbitrary internal drops allowed (head, middle, tail, any
combination). Two cases produce new entries: playback order ≠ source order, or segments
from different source quotes. Splitting is implicit — the agent decomposes whenever a
manipulation requires it.

**Why:** Jeff's mental model articulated during the v5.0 review: *"The quotes from the
interview subjects are clay. We can mold them any way we want to communicate the story
as long as we use them verbatim and edit on a topic or idea level and not a word level.
Think about it as a collection of segments that you can rearrange — but you can't take
individual words or very short snippets and go about it that way."* The v4.0 model
treated quotes as near-atomic; the v5.0 model treats them as raw material the timeline
is composed from. This collapses intra-quote reorder and cross-quote pairing into one
general primitive.

The Cardinal Rule's existing wording is preserved verbatim. The framing AROUND it
expands: where it says "rearrange sentences," that capability now operates on segments
rather than whole sentences, and segment reuse can cross source-quote boundaries.

**Schema impact:** `tagged-quotes-v[N].json` now has per-quote `segments[]`. The merged
output preserves them. `trimmed-quotes-v[N].json` becomes a timeline of entries, each
with `segments[]` referencing the source pool. The FCPXML Agent generates one clip per
source segment per timeline entry.

**Out of scope, flagged for follow-up:** `scripts/quotes_viewer_template.jsx` v5.0
upgrades (segment-level reorder UI, source attribution per segment, status badges).
`scripts/build_fcpxml.py` segment-aware clip generation. Both flagged as Phase 3 code
changes.

### New Transcription Agent at pipeline position 0 (SKILL-transcription.md, SKILL.md, cowork-session-guide.md)

Replaces the prompt-driven Step 0 script invocation. The Transcription Agent is a
proper SKILL with structured behavior: audio detection (`.mp3`, `.wav`, `.m4a`, `.mov`,
`.mp4`), speaker confirmation (derive name from filename, present list, accept Jeff's
corrections), format conversion (ffmpeg in the Cowork sandbox if a video container),
AssemblyAI calls with retry logic (transient retry, 401/403 hard-fail with clear
message), output validation (non-empty, timecodes, speaker labels, plausible word
count), and `transcription-summary-v[N].md` handoff.

**Runs entirely in the Cowork sandbox.** No Terminal interaction at any point.

**AssemblyAI key location:** `documentary-junior-editor/secrets/assembly_ai.key` —
git-crypt encrypted in `storyboard-ops`. Each Mac needs `git-crypt unlock` once with
the master key; after that, `git pull` retrieves the decrypted file transparently. If
git-crypt isn't unlocked, the agent fails fast with the exact remediation command.

**Trigger:** the Creative Context Agent on launch checks for audio without transcripts.
If found, it pauses and provides the Transcription Agent launch prompt; Jeff runs that
in a separate Cowork session and returns.

**Why:** Jeff observation — "the audio transcription process is still pretty buggy and
seems to be happening differently across projects." Root causes: prompt interpretation
varies; the script lookup of the AssemblyAI key sometimes fails; Terminal pasting is
required when Cowork can't reach the script; format edge cases aren't consistently
handled. Promoting transcription to a proper agent makes behavior predictable and
removes the Terminal dependency.

**Out of scope, flagged for follow-up:** `scripts/transcribe.py` updated to read the
encrypted key path (currently looks at `~/Desktop/storyboard-ops/file-api/.env`).
The new SKILL documents the v5.0 contract; the script catches up in a Phase 3 code
change.

### Universal pipeline versioning + dependency graph (every SKILL file, SKILL.md)

Every handoff document is suffixed `-v[N]`; no agent ever overwrites. Per-file version
trajectory — re-running the Creative Context Agent doesn't force a re-run of every
downstream file, only the ones whose upstream just incremented.

A new file at `handoffs/pipeline-state.json` (or per-project-slug variant on multi-project
SSDs) tracks current versions per agent and dependency edges. Schema documented in
`SKILL.md`. Every agent reads it on launch — surfaces stale-state warnings to Jeff when
an upstream agent has run since this agent last did. Every agent writes to it on emit,
recording the upstream versions it consumed.

**Cascade behavior:** in Cowork today, stale-state warnings surface in chat and Jeff
decides pace. In n8n + Claude API (Phase 4 of the storyboard-ops roadmap), the same
file becomes the orchestrator's work queue — same data, automated cascade. Skill is
identical in both worlds.

**Why:** Jeff observation — when revisiting upstream work (e.g., revising the act
structure), downstream agents currently overwrite their previous outputs, losing the
history of how the project evolved. The Edit Agent already does versioning naturally
(v1, v2, v3); generalizing this across the pipeline gives Jeff lossless history,
diff-able passes, and a single state file the Skill Review Agent can read to reconstruct
the project's full editorial journey.

**Dependency edges:** Creative Context → Transcript Agents → Synthesis → Edit → FCPXML;
FCPXML Params is an independent branch; Transcription is a precondition that emits no
downstream-relevant version. Each agent on launch checks every upstream it depends on
against the version it consumed last time.

### Edit Agent built for multi-round iteration; agents stay separate (SKILL-edit.md, SKILL.md, cowork-session-guide.md)

Reframes the Edit Agent's job from "produce a paper cut once" to "be a partner across
indefinite rounds." The three phases (Rough Cut → Discussion → Reduction) loop. Each
round emits a versioned `trimmed-quotes-v[N].json` and triggers a fresh FCPXML run.
Jeff watches the FCPXML in FCP, optionally appends to `review-notes.md`, and re-launches
the Edit Agent for round N+1. No fixed cap on rounds.

The Edit ↔ FCPXML loop is named explicitly in the pipeline diagram, not just "loop-back
support" as a footnote.

**Edit and FCPXML stay separate Cowork sessions.** The architectural intent is
preserved: separate context windows (Edit's editorial reasoning doesn't bleed into
FCPXML's largely-deterministic XML transformation), and the model split (Opus for
editing, Sonnet for FCPXML) is real cost optimization.

**Friction reduction:** every handoff closes with a "Next agent + model + launch prompt"
footer (see Lesson 9 below) so Jeff copy-pastes between sessions instead of reconstructing
context. n8n + Claude API (Phase 4) automates the cascade entirely.

**Why:** v4.0 introduced the three-phase Rough Cut → Discussion → Reduction structure
but treated it as linear. Jeff's reality across projects is multi-round — react,
revise, react, revise. v5.0 makes this the expected operating mode, not the special case.

### Live HTML artifact as Edit Agent work surface (SKILL-edit.md)

The HTML artifact is no longer an end-of-session deliverable. It's created at session
start from `tagged-quotes-v[N].json`, updated via `update_artifact` after every editorial
decision, and bidirectional via `sendPrompt()` — clicking "drop" or "accept proposed
trim" in the artifact sends the corresponding chat message back to the Edit Agent.

**Auto-scroll to current focus.** When the agent says "let's discuss Alice #6," the
artifact auto-scrolls to and highlights #6. Jeff never has to ask "which one is that
again?"

**Full quote text always inlined in chat on first reference.** Even with the live
viewer, the agent quotes the verbatim text the first time a quote enters discussion in
chat. Subsequent references can use just the ID once the quote's been brought into view.
Solves the "agent abbreviates and Jeff has to ask for the full text" pain Jeff
identified in the v5.0 review.

**End-of-session, final state saved as `[project-slug]_quotes_view.html`** in the
handoffs folder — same as today, so the artifact persists and reloads next session.

**Why:** Jeff observation — *"the editing agent frequently refers to quotes by number
and abbreviates what the quote is. I repeatedly am asking for the full context. The
ideal workflow would be that the editing agent creates the quote viewer so I can
reference what's being discussed and when decisions are made the quote viewer is
automatically updated. Think of it like a word doc where we are editing the work product
together."* Cowork's `mcp__cowork__create_artifact` and `update_artifact` plus the
artifact's `sendPrompt()` capability make this fully achievable today.

**Out of scope, flagged for follow-up:** `scripts/quotes_viewer_template.jsx` rewrite
to support bidirectional buttons, segment-level reorder UI, status badges, source
attribution per segment in composite entries, runtime-recommendation toggle. The
SKILL specifies the contract; the template catches up in a Phase 3 code change.

### Wide rough cut + per-quote runtime recommendation (SKILL-edit.md)

The wide rough cut from v4.0 is preserved — it's the inventory view that lets Jeff see
what was left on the table. Layered on top: the Edit Agent tags each quote with a
`runtime_recommendation` field — `must-keep`, `probable-keep`, `probable-cut`, or
`optional` — toward 2× target runtime. The viewer adds a toggle: "show full inventory"
vs. "show recommended tight cut." Jeff sees both views.

**Why:** v4.0 said *"first pass is a rough cut, not a draft"* and intentionally let it
run long. On International Institute the rough cut landed at 20:47 against a ~5-minute
target — 4× over, not the 25–30% the v4.0 calibration anticipated. Jeff's framing of
the trade-off: a 2× rough cut is the ideal endpoint, but a wide rough cut shows what's
on the table; the runtime recommendation gives the agent room to develop tighter
judgment without taking visibility away.

### Title-card-as-shortener pattern (SKILL-edit.md)

Promoted from incidental to a named editorial move. Trigger: backstory or contextual
material that reads cleaner on screen than spoken — a stat, a date, a piece of context,
a backstory beat that doesn't need a face. The Edit Agent proposes title cards in the
rough cut when this pattern fits, not just as act dividers.

**Why:** International Institute's final edit replaced four spoken backstory beats with
on-screen title cards — including one verbatim from the v3 interstitial the Edit Agent
had drafted. Pattern is general (not specific to non-native English speakers, as Jeff
clarified during the review).

### Suggesting context beats (SKILL-edit.md)

The Edit Agent identifies narrative gaps where external context (a stat, a date, a
piece of framing) would land harder than spoken material. Surfaces them in
`edit-handoff-v[N].md` with location, intent, and `(research needed)` tag. The agent
does NOT do the research — Jeff fills in.

**Why:** International Institute's final used research-sourced title cards
("Fewer than 1% of the world's refugees are resettled," U.S. Refugee Admissions
Program suspension stats) for stakes-raising. Doing the research in-agent would
burn context window. Identifying the opportunity and letting Jeff fill in is the
right division of labor.

### Brief is starting points, not constraints (SKILL-creative-context.md)

Replaced "must stay / immovable / locked in / permanent" language in the
creative-brief-summary output spec with "currently planned to stay / load-bearing in
current structure / tentatively committed / current default."

**Why:** International Institute's brief flagged three beats as "immovable" (Stephen
Miller, the seizure-medication block, the "I was the luckiest" hinge). All three were
dropped in Jeff's final FCP edit. His framing: *"editing is iterative. You make
decisions up front. You look at them in the context of the larger edit. You adjust or
change those decisions based on how the whole is sitting."* The brief carries editorial
intent at session-start time; commitments are starting points, not constraints.

### Creative Context Agent Phase 0 — Discovery (SKILL-creative-context.md)

New Phase 0 step before brief construction. Searches Google Drive for project documents
(by folder path or keyword) and Gmail for relevant threads (by project name + client
domain). Surfaces candidates as a list with one-line summaries; Jeff approves which to
ingest. Falls back to manual upload if Drive/Gmail connectors aren't connected.

**Why:** Jeff observation — *"the creative agent often asks for relevant background
info. I would like for it to automatically look for meeting notes in the google drive
project folder as well as relevant emails."* Cowork's Drive and Gmail MCPs are
available; the Discovery step makes use of them with explicit Jeff-approval before
ingestion.

### FCPXML Agent handles both multicam and single-clip footage (SKILL-fcpxml-params.md, SKILL-fcpxml.md)

Per-interview `clip_type` detection in the Params Agent. Multicam (existing default):
`<media>` containing `<multicam>` with `<mc-angle>` children — generates `<mc-clip>`
references with angle selection. Single-clip: top-level `<asset>` resource — generates
`<asset-clip>` references directly with format, tcFormat, audioRole. Captions match
against direct children of `<asset-clip>` rather than nested under multicam structures.
Mixed projects (some multicam, some single-clip) handled per-interview, not project-wide.

**Validation samples:** `documentary-junior-editor/design-samples/single-clip/` carries
`Ben_captioned_interview.fcpxml` (single-cam captioned interview from Nanos 2026 Boston)
and `Sample_narrative.fcpxml` (sample narrative timeline using single-clip sources) as
authoritative reference.

**Why:** Jeff observation — *"I came across one issue in another project where the
interview files were not a multi-cam but a single clip. The .xml agent definitely
struggled with this. Would be great if handling both scenarios was baked into that
agent's skill."* The Nanos project sample XMLs were uploaded during the v5.0 review
and live in the skill folder for Phase 3 implementation reference.

**Out of scope, flagged for follow-up:** `scripts/build_fcpxml.py` and
`scripts/build_v2_fcpxml.py` clip_type branching. The SKILL specifies the contract;
the scripts catch up in a Phase 3 code change.

### Every agent declares model in frontmatter; every handoff closes with a "Next" footer (every SKILL file)

Audit and fix: every SKILL frontmatter has a correct `model:` field. Every handoff
document closes with a footer naming the next agent, the model to use, and a paste-able
launch prompt for the next Cowork session.

Single source of truth — the same `model:` field consumed by Jeff in Cowork today
(reads it in the SKILL frontmatter; sees the recommendation in the handoff footer)
and by n8n via API call later (reads frontmatter as the API model parameter).

**Why:** Jeff observation — *"I've been trying to select the appropriate model when
launching each task but sometimes use Opus by default when it's not necessary. Is it
possible to have each agent in the system launch the next agent with the right model
selected?"* Cross-session automation isn't possible in Cowork (only Jeff starts sessions),
but making the model recommendation visible at every transition is.

### Reference example: International Institute of Minnesota (Nonprofit Fundraising)

Second `Nonprofit Fundraising` example after Pacer Center. Three speakers
(Alice Mupenzi, Blaine Joseph, Jane Graupman); 2026 Fund-a-Need gala video. Final edit
hand-refined in FCP from a 20:47 rough cut to a 5:12 fund-a-need pitch — 76% reduction,
13 quotes removed, 10 added (all from previously-tagged-but-unselected pool, zero
orphans pulled), 7 narrative title cards (most replacing spoken stats), all three
act-divider titles dropped, 1 sentence-level reorder inside Alice #11, 3 brief-locked
beats overridden in FCP.

Validates: the runtime-recommendation layer (rough cut at 4× target was a survey of
strong material, not a tightening pass), the title-card-as-shortener pattern, the
"brief is starting points" framing, and the segment-level reorder data model.

### Cardinal Rule status

Zero violations across the International Institute pipeline. Verified across all per-speaker
tagged-quotes outputs, the merged synthesis output, all three trimmed-quotes versions
(v1, v2, v3), both rough-cut FCPXMLs (v1, v2), and Jeff's final FCP edit. Alice #11's
sentence-level reorder is permitted by the Cardinal Rule (verbatim words, only order
changed) — not a violation.

### Follow-ups flagged but not done in v5.0

- `scripts/transcribe.py` — read the git-crypt'd key from `secrets/assembly_ai.key`;
  drop legacy `~/Desktop/storyboard-ops/file-api/.env` lookup. Phase 3 code change.
- `scripts/build_fcpxml.py` and `scripts/build_v2_fcpxml.py` — branched clip_type
  generation; segment-aware clip emission per timeline entry. Phase 3 code change.
- `scripts/quotes_viewer_template.jsx` — bidirectional `sendPrompt()` buttons,
  current-focus highlighting, status badges, segment-level reorder UI, source
  attribution per segment in composite entries, runtime-recommendation toggle.
  Phase 3 code change.
- `SPEC-pipeline-v4.md` — n8n spec carries forward from v4.0; should be updated to
  reflect v5.0 changes (eight agents, pipeline-state.json schema, multi-round Edit↔FCPXML
  loop). Pending Jeff's approval before touching n8n deployment surface.
- One-time per-machine setup: `brew install git-crypt`; export master key on primary Mac;
  `git-crypt unlock` on each additional Mac. Documented in cowork-session-guide.md;
  Jeff runs it once per machine.

### Version bumps summary

- `SKILL.md` → v5.0
- `SKILL-transcription.md` → v5.0 (NEW)
- `SKILL-creative-context.md` → v5.0
- `SKILL-transcript.md` → v5.0
- `SKILL-synthesis.md` → v5.0
- `SKILL-edit.md` → v5.0
- `SKILL-edit-pipeline.md` → v5.0
- `SKILL-fcpxml-params.md` → v5.0
- `SKILL-fcpxml.md` → v5.0
- `SKILL-review.md` → v5.0
- `cowork-session-guide.md` → v5.0
- `CHANGELOG.md` → v5.0

Scripts remain at v4.0.x pending the Phase 3 follow-up code changes listed above.

---

## v4.0.1 — 2026-04-17

Template implementation of the v4.0 Review/Edit dual-mode viewer spec.
The spec landed in SKILL-edit.md as part of v4.0 on the same day, but
`scripts/quotes_viewer_template.jsx` itself was not updated — every Edit
Agent session since v4.0 had to construct Review mode from scratch from
the spec. This entry eliminates that per-session work by baking the
toggle into the template's universal React component.

### Review/Edit toggle baked into `scripts/quotes_viewer_template.jsx`

**Behavior.**

- Default landing is Review mode.
- Review is act-scoped by default, not whole-sequence. The initial scope
  is the first act that has selected quotes on mount, matching the
  act-by-act rhythm of the Discussion phase. An `All` tab reads the full
  sequence end-to-end with section dividers.
- Review renders selected quotes only, as continuous narrative. Speaker
  labels appear on speaker change (and reset at each act divider when
  reading `All`). Trimmed text is shown when a trim exists; otherwise
  the full quote. Interstitials render inline at their anchor positions.
  Start-of-sequence interstitials show when the scope is the first act
  or `All`. No editorial controls — this is reading, not editing.
- Edit mode preserves all existing behavior: trim controls, drag
  handles, section-reassign dropdowns, scissors splits, interstitial
  placement, checkboxes, Selected Quotes bottom bar.
- Both modes read from the same state — `quotes`, `editedQuotes`,
  `interstitials`. Selecting/deselecting, applying a trim, placing or
  removing an interstitial in Edit mode reflects immediately in Review
  and vice versa. No data drift between modes.

**UI unification.**

- Review's act scope and Edit's section filter now render with the same
  underline-tab pattern, anchored in the same position directly below
  the Review/Edit mode toggle. Toggling between modes feels like staying
  in one artifact rather than jumping between two screens.
- `Save State` and `Restore State` moved from the editorial toolbar to
  the Review/Edit toggle row (visible only in Edit mode). They're
  file-level utilities, not editorial actions, and now read that way.
- The editorial toolbar is now just the `+ Interstitial` button.
- An `ACTS` caption sits above the scope tabs in Review mode to cue
  that the tabs are story acts.

**Data block contract unchanged.** `initialQuotes`, `initialTrims`,
`initialInterstitials`, `RESTORED_STATE`, and `SECTION_CONFIG`
signatures are identical. Populating the data block is the same
operation as before.

**Template header comment updated.** The instructions block at the top
of the file now mentions the dual-mode nature so future consumers don't
attempt to re-derive Review from the spec.

**Why:** Jeff observed that starting every editing session by
reconstructing Review mode from scratch was wasted work and a drift
vector — two agents could each interpret the spec slightly differently
and produce viewers that behaved differently. Baking the toggle into
the template makes the behavior canonical and instant.

### Follow-ups flagged but not done

- `SKILL-edit-pipeline.md` (n8n variant) still reflects the
  v3.5-pipeline template. The v4.0 toggle spec and this v4.0.1 template
  bake-in should propagate to the pipeline variant in a separate pass,
  pending Jeff's approval before touching the n8n deployment surface.

### Version bumps summary

- `scripts/quotes_viewer_template.jsx` → v4.0.1 (dual-mode bake-in)
- `CHANGELOG.md` → v4.0.1
- All other files unchanged.

### Out of scope

Data block shape changes, SKILL-edit.md (spec already landed in v4.0),
SKILL-edit-pipeline.md, and any fcpxml-related code.

---

## v4.0 — 2026-04-17

Major version — Edit Agent workflow reframe, viewer dual-mode, plus new rules
and the first Nonprofit Testimonial reference example. Originally planned as
v3.5; the workflow reframe tipped it into a major version bump.

### Edit Agent workflow reframe: first pass is a rough cut, not a draft (SKILL-edit.md)

Reframes the Edit Agent's first-pass output from a near-target draft to a
**rough cut** — longer, over-inclusive, not runtime-gated. The goal of the
first pass is the best possible story with logical progression and stand-
alone narrative integrity; whether it lands at 5 minutes or 12 minutes does
not matter for this pass. Reduction happens later, after review.

The Edit Agent now operates in three explicit phases:

1. **Rough Cut** — include every quote that plausibly earns its place. Err
   long. Expect 1.5x–2x the target runtime. A rough cut that lands at
   target means quotes got missed; that is the failure mode this phase is
   designed to prevent.
2. **Discussion** — collaborative review with Jeff. The agent brings a
   proposal (which beats to cut first, which are load-bearing, which are
   uncertain, and why) so Jeff has a reactable surface. Review mode in the
   viewer is the primary surface. Question: "does this tell the story?"
3. **Reduction** — targeted trim against agreed runtime, informed by the
   Discussion. Runtime becomes a real constraint here. Edit mode in the
   viewer is the primary surface. Question: "which words come out?"

**Why:** On Crisis Nursery, the Edit Agent produced what looked like a draft
at 5:50 against the 3–5 minute target — already trimmed toward runtime — and
good Act 3 quotes were missed as a result. Jeff's observation: "the goal
initially is to tell the best possible story... then we look at it again and
see what we can cut without losing any of the integrity of the story."
Previous skill guidance ("consider runtime from the start," "if 2x over
target, tighten before presenting") was actively working against this.
Replaced entirely.

The Act 3 runtime-overrun rule drafted as part of the planned v3.5 entry
has been subsumed by the broader rough-cut principle. It survives in the
skill as the "never pre-truncate the closing act" guidance — one expression
of the general rule, not a standalone Act-3-specific rule.

### Viewer: Review / Edit mode toggle (SKILL-edit.md)

The JSX/HTML viewer now renders with a Review/Edit toggle.

- **Review mode** (default landing): selected quotes rendered as continuous
  narrative — speaker labels, act dividers, trimmed text only, no controls.
  Surface for the Discussion phase.
- **Edit mode**: full interactive interface (trim controls, drag handles,
  section dropdowns, scissors splits, interstitial placement, filters).
  Surface for the Reduction phase.

Both modes read from the same data block — no drift between modes.

**Why:** Jeff raised that the transition from chat discussion to the
interactive viewer was slow and that context was effectively being burned
generating narrative previews in chat separately from the interactive
viewer. A single dual-mode artifact solves both — one render, two ways to
consume, naturally aligned to the Discussion/Reduction rhythm. An earlier
proposal to split viewer generation into a separate Viewer Agent was
considered and rejected in favor of the toggle — the toggle solves the
user-facing problem (reading the story vs. editing the quotes) without
adding pipeline complexity or forcing session-switching.

### New editorial rules (SKILL-edit.md)

**Limited-entry supporting voice pattern.** For projects with a primary
protagonist plus a close-relation second voice (spouse, adult child,
colleague), don't distribute the supporting voice evenly. Pick 2–4
deliberate entry points where the second voice adds something the
protagonist can't. Added to Phase 3 Selection Principles. Reference
example: Crisis Nursery Testimonial (TJ Bryant — three entries across 22
total beats).

**Lead-with-vulnerability, close-with-authority placement.** When a
subject has both personal vulnerability and earned present-day authority
(board seat, staff role, public advocacy, credentialed perspective), open
with the vulnerable material and save the authority for the close rather
than front-loading credentials. Added to Phase 3 Ordering Principles.
Previously lived only in user memory — now encoded in the skill so it
syncs via git to all machines.

**Runtime estimation in two numbers.** Long-form emotional testimonials
run roughly 25–30% longer than word-count math predicts. Estimate the
rough-cut length and the target length as separate numbers so the gap
between "what we have" and "what we need to get to" is explicit. Sets
expectations for the Discussion; constrains the Reduction.

### Reference example: Crisis Nursery Testimonial (Nonprofit Testimonial)

First Nonprofit Testimonial added to the knowledge base — the 2026 Crisis
Nursery annual fundraising video with Tyanna Bryant (protagonist) and her
24-year-old son TJ (supporting / intergenerational witness). 22 quotes
across 3 acts (Stigma / Partner / Every Parent), 1 split (source #7 into
Act 1 closer + Act 2 opener), no interstitials. Approved on first pass —
no loop-back from FCPXML.

Establishes patterns for: single-protagonist with limited-entry supporting
voice (TJ enters exactly three times); paired-perspective emotional center
(mother's memory + adult child's own-voice confirmation of the same
event); off-scope material routed to Orphans rather than Discards when
part of a quote pool future editors might revisit; act labels set directly
to messaging-framework pillars when the Interview Guide already speaks in
those terms.

Reference example's `lessons-learned.md` has been updated in v4.0 to
reframe the 7:29.6 runtime as a rough-cut-treated-as-draft failure mode
rather than a deliberate overrun kept for Act 3 integrity, per Jeff's
observation that good Act 3 quotes were missed.

### Folder-layout variants documented (SKILL-fcpxml.md)

Added Phase 1 guidance acknowledging two layout variants the FCPXML Agent
may encounter:

- **Uppercase `XML/` with `exports/` and `imports/` subfolders.** Source
  `.fcpxmld` packages in `XML/exports/`; generated rough cut written to
  `XML/imports/`. Crisis Nursery used this.
- **Multi-deliverable output naming without `_v<N>` suffix.** When a
  project slug already implies scope
  (`[project-slug]_rough_cut.fcpxml`) and there is only one version, Jeff
  sometimes drops the version suffix. The skill now tells the agent to
  match the naming used in `edit-handoff.md` rather than force the
  canonical `[ProjectName]_rough_cut_v<N>.fcpxml` form.

Neither variant requires a structural change — just an instruction to the
agent to read what's there and not over-correct.

The `handoffs/[project-slug]/` multi-deliverable subfolder convention was
already documented in SKILL.md (Multi-Project Folders section) prior to
this review; v4.0 adds no new convention, just reinforces it.

### Known issues — OPEN, flagged for Jeff

**FCPXML Params parser-format mismatch (SKILL-fcpxml-params.md).** Schema
mismatch between the `fcpxml-params.md` format documented in the skill
(per-speaker `### [Name]` sections with `Media ref ID` / `Tele angleID` /
`Wide angleID` bullets) and the format `scripts/build_fcpxml.py`'s
`parse_params_md` actually parses (flat top-level sections: `## Media Ref
IDs`, `## Angle IDs`, `## Reference FCPXML`, `## Library Location`, `##
Event Name`, `## Format Reference`). The FCPXML Agent on Crisis Nursery
reformatted the file mid-pipeline before `build_fcpxml.py` would run.

*Interim guidance:* skill instructs Params Agent to produce BOTH forms —
parser-expected top-level sections for tool consumption, followed by a
per-speaker details block for human reading.

*Open for Jeff:* which side should be the canonical form long-term —
update `parse_params_md` to accept the per-speaker headings, or keep the
parser format and drop the per-speaker human-readable block? Either
direction eliminates the dual-format obligation.

**FCPXML caption-matcher performance on long interviews (SKILL-fcpxml.md).**
`build_fcpxml.py`'s fuzzy matcher scans `captions × max_span` windows per
sentence with `search_hint` reset to 0 at the start of each quote. On
Tyanna's ~708-caption source this exceeded the 45-second shell timeout
end-to-end. Validated workaround: narrow the caption search window per
quote using each quote's `startTC`/`endTC` (±15-second buffer). Match
scores stayed 0.85–1.00 and total match time dropped to ~2 seconds. The
permanent fix belongs in `generate_fcpxml.py`'s `find_quote_range` — use
the TC window already present in `paper_cuts` to set
`search_start`/`search_end` rather than scanning the whole caption list
per quote.

### Cardinal Rule status

Zero violations on Crisis Nursery. All 22 trims verified as contiguous
verbatim substrings of the source text. Transcription artifacts preserved
per the rule (#1 "Tiana" spelling instead of "Tyanna"; #38 lowercase
"please don't wait" sentence start). Split handling (#7 → #7a + #7)
treated as two independently trimmed subclips from the same source TC
window — clean.

### Follow-ups flagged but not done

- **SKILL-edit-pipeline.md** (n8n variant) holds matching v3.5-pipeline
  content. The v4.0 workflow reframe and dual-mode viewer spec would
  benefit from a matching update, but this agent did not modify the
  pipeline variant — flagged for Jeff's approval before touching the n8n
  deployment surface.

### Version bumps summary

- `SKILL.md` → v4.0
- `SKILL-edit.md` → v4.0
- `SKILL-fcpxml-params.md` → v4.0
- `SKILL-fcpxml.md` → v4.0.1
- `SKILL-review.md` → unchanged (v3.4)
- `SKILL-creative-context.md`, `SKILL-transcript.md`, `SKILL-synthesis.md`
  → unchanged (no v4.0 changes warranted)
- `SKILL-edit-pipeline.md` → unchanged (v3.5-pipeline); flagged for a
  matching v4.0-pipeline pass pending Jeff's approval

---

## v3.4 — 2026-04-09

### Narrative Coherence Rule added to SKILL-edit.md

New rule with the same prominence as the Cardinal Rule. The paper cut must read as a coherent story. After every change to selection or ordering, the Edit Agent must read the assembled sequence for narrative flow. Quote fragments that don't stand alone may work when paired with other fragments — evaluate sequences, not isolated pieces. Thread multiple trimmed quotes together to build narratives. Suggest interstitials when no quote bridges a gap, but first try to solve it with transcript material.

**Why:** On the Pacer Center project, the Edit Agent evaluated quotes in isolation rather than as a flowing sequence. Jeff had to repeatedly ask the agent to check coherence, and it found problems it should have caught on its own.

### Viewer is the single source of truth (SKILL-edit.md)

Every editorial suggestion must be reflected in the interactive viewer before moving on. The agent must not describe changes in chat without applying them to the artifact. If the chat and the viewer disagree, the viewer is wrong and must be fixed. Updates happen after every batch of changes, not accumulated for a single update at the end.

**Why:** On the Pacer Center project, the Edit Agent made suggestions in chat that weren't consistently reflected in the viewer — wrong ordering, quotes in wrong acts, trims not shown. Jeff had to bridge the gap manually and request sync, and the synced output sometimes still didn't match.

### Selection and trimming are simultaneous (SKILL-edit.md)

The first pass should be trimmed selects, not a wide net followed by tightening. When the agent proposes a quote, it should simultaneously propose which portion earns its place. Runtime estimation added to first-pass guidance.

**Why:** The Pacer Center first pass came in at 28 quotes / ~12 minutes against a 3–5 minute target because quotes were selected untrimmed. The tightening pass to 22 quotes / ~6 minutes was avoidable work.

### Narrative roadmaps elevated to editorial instructions (SKILL-edit.md)

Strengthened language: roadmaps from the Creative Context Agent are the editorial plan Jeff approved, not background context. The Edit Agent must check proposals against roadmaps and flag conflicts explicitly rather than silently departing.

**Why:** On the Pacer Center project, the Edit Agent drifted from the roadmaps and Jeff had to redirect it back to the act structure multiple times.

### Version management added (SKILL-edit.md, SKILL-fcpxml.md)

Editing passes saved as versioned files (`trimmed-quotes-v1.json`, `trimmed-quotes-v2.json`). The latest version is always also saved as `trimmed-quotes.json`. Viewer supports version dropdown for comparison. FCPXML filenames match versions (`_rough_cut_v1.fcpxml`, `_rough_cut_v2.fcpxml`). Version history documented in `edit-handoff.md`.

**Why:** On the Pacer Center project, the first FCPXML was too long. Jeff went back for a shorter cut, but the Edit Agent overwrote the original files. There was no way to compare versions or trace which edit produced which FCPXML.

### Long interview handling added to SKILL-transcript.md

Interviews over ~45 minutes should be processed in two halves to maintain cataloguing quality. The Transcript Agent splits the work, processes each half with a fresh context re-read, and combines the outputs.

**Why:** The Pacer Center project had a 57-minute and a 90+ minute interview. Overall cataloguing quality did not feel as strong as previous projects with 15–30 minute interviews.

### Case-setup act assignment guidance added to SKILL-transcript.md

Quotes that establish a case's backstory often belong to the preceding act (where the emotional weight of the setup lands), not the act where the case resolves.

**Why:** On the Pacer Center project, #23 and #24 (Timmy's backstory) were tagged to "PACER in Action" but reassigned to "The Wall" during editing because the setup works better before the vulnerability moment.

### Transcription documented as Step 0 (SKILL.md, cowork-session-guide.md)

SKILL.md's "Setting Up a New Project" now includes a transcription step before confirming files are present. The cowork-session-guide's Step 0 now has a full Cowork starter prompt that handles dependency installation, API key location, script execution, and output verification — no Terminal required.

**Why:** On the Pacer Center project, transcription was a significant friction point. Jeff assumed it was part of the pipeline but it wasn't documented. The script existed on another machine but had to be hunted down and debugged through multiple Terminal round trips.

### Reference example: Pacer Center (Nonprofit Fundraising)

First nonprofit fundraising project in the knowledge base. Two speakers (Norma — surrogate parent, Karen Malka — PACER advocate). 22 quotes + 2 interstitials across 4 acts. Establishes patterns for: protagonist + expert two-voice structure, case stories as narrative engine, interstitials for procedural context, profanity handling for formal audiences, and emotional close structure (extraordinary → universal bridge).

### Version bumped: SKILL.md, SKILL-edit.md, SKILL-transcript.md, SKILL-fcpxml.md → v3.4

---

## v3.3.1 — 2026-03-31

### Skill source of truth moved from Google Drive to GitHub

The storyboard-ops project (including all skills) is now version-controlled in a private GitHub repository and synced across machines via Git. Google Drive is no longer the source of truth for skill files.

**What changed:**
- cowork-session-guide.md: "Before You Start" updated — skill folder source changed from Google Drive to `storyboard-ops/skills/` with `git pull` reminder
- Workflow: before starting a new project, run `git pull` in `storyboard-ops` to ensure the latest skill version, then copy into the project folder as before

**Why:** Jeff works across three machines (Mac mini, Mac Studio, MacBook Pro). Google Drive's streaming mode caused empty/broken files when syncing the codebase. Git provides reliable syncing with full version history for both application code and skills.

---

## v3.3 — 2026-03-30

### Text interstitial support

Added the ability to create, position, edit, and remove text interstitials — factual on-screen text cards (credentials, titles, context) that appear between spoken quotes in the paper cut. Modeled on the Dr. Pan Intro project, which used two text interstitials (items 4 and 6 in the final edit) to cover education and residency that no spoken quote addressed.

**JSX viewer template changes (quotes_viewer_template.jsx):**
- New `initialInterstitials` array in the data block for pre-baked interstitials
- Interstitial state management: add, edit, remove, and position interstitials in the sequence
- "Add text interstitial" button appears after each selected quote in "Selected only" mode
- Interstitial cards render as indigo-bordered dashed cards with "TEXT INTERSTITIAL" badge, visually distinct from spoken quote cards
- Click interstitial text to edit, click ✕ to remove
- Interstitials included in save/restore state
- Summary bar shows interstitials alongside selected quotes
- Stats line includes interstitial count

**SKILL-edit.md changes:**
- Edit Agent now proactively suggests interstitials when it identifies gaps — credentials, factual context, transitions, or missing information that no quote covers
- Guidance for when and how to suggest interstitials, with reference to Dr. Pan Intro as model
- Interstitial viewer features documented in Interactive Viewer Features section
- Phase 5 Final Review updated to include interstitials in the read-through
- Handoff checklist updated to confirm interstitials

### Final-state HTML viewer required as Edit Agent deliverable

The Edit Agent must now save a self-contained HTML viewer to the project handoffs folder before completing. This ensures Jeff can review the paper cut at any time without a Cowork session.

**What changed:**
- SKILL-edit.md: New handoff document #3 — `handoffs/[project-slug]_quotes_view.html`
- File naming convention: `[project-slug]_quotes_view.html`
- Must contain final state: all quotes (selected and unselected), trims, interstitials, section assignments baked into the data block
- Self-contained: React 18 + Babel + Tailwind from CDNs, opens in any browser
- Viewer file path must be documented in `edit-handoff.md` under Key Files
- edit-handoff.md description updated to include viewer path and interstitial summary

### SKILL.md updated
- Pipeline diagram updated to show HTML viewer and interstitials as Edit Agent outputs
- Project folder structure updated with `[project-slug]_quotes_view.html` in handoffs
- Multi-project folder structure updated accordingly

### Version bumped: SKILL.md → v3.3, SKILL-edit.md → v3.3

---

## v3.2.2 — 2026-03-29

### FCPXML timing padding increased from ~2 frames to 2 seconds

The previous ~2 frame padding (~0.08 seconds) produced clips that were too tight — the editor frequently had to extend clips to capture the full line. Increased to 2 seconds on each end. It is always easier to cut excess than to wonder whether something is missing.

**What changed:**
- SKILL-fcpxml.md: Phase 3 Timing Extraction updated from "~2 frames" to "2 seconds"

### Non-contiguous trim handling documented in SKILL-fcpxml.md

When a trim removes middle content from a quote (e.g., "My dad was a plastic surgeon, for 30 years" from an original that includes "he's retired now, but he was in private practice" in between), the sentence-level caption matcher could only find one of the two kept portions. This caused clips to be too short or to start at the wrong position — confirmed on quotes #2 and #10 in the Dr. Pan Intro project.

**What changed:**
- SKILL-fcpxml.md: New "Non-Contiguous Trims" section added to Phase 3 with detection and handling guidance. When detected, the FCPXML Agent should match the full original quote for clip range instead of matching the trimmed text sentence by sentence. Formal splits (`split: true`) remain separate clips.

### Reference example: Dr. Pan Intro (updated)

Replaced the v3.1 reference example with the v3.2.1 pipeline run. Updated Final_Edit.txt (now includes text interstitials T1 and T2, uses merged numbering from Synthesis Agent), updated lessons-learned.md with findings from the full pipeline review including the non-contiguous trim bug and timing padding issue.

### Version bumped: SKILL-fcpxml.md → v3.2.2

---

## v3.2.1 — 2026-03-28

### Transcript Agent: four required outputs, mandatory file verification

Fixed a reliability issue where one of two parallel Transcript Agents completed successfully while the other either asked unnecessary questions or reported completion without saving all required files. Root cause: the skill file said "three outputs" in multiple places but actually requires four (tagged-quotes.json, orphans.md, discards.md, AND summary.md). The summary was produced in Phase 1 but not listed in Phase 3's output requirements, so an agent could consider itself done after three files.

**What changed:**
- SKILL-transcript.md: Description, Phase 3 heading, and completeness check all updated from "three" to "four" outputs. Summary.md added as explicit Output 4 in Phase 3.
- SKILL-transcript.md: New mandatory file verification step — agent must read back all four files from disk and confirm they exist before reporting completion. Presenting in chat is not sufficient.
- SKILL-transcript.md: Completion section now requires listing all four file paths with confirmation. Includes warning that the Synthesis Agent validates all four and will reject incomplete sets.
- SKILL-synthesis.md: Phase 1.3 gap reporting updated with specific remediation guidance — tells Jeff which speaker's Transcript Agent needs to be re-run, and describes the common failure pattern (agent reports completion without saving files).
- SKILL-transcript.md, SKILL-synthesis.md version bumped to v3.2.1

### Multi-project folder support

Documented the scenario where multiple video projects share a single SSD folder (same FCP library, same transcripts, same source FCPXMLs). When this happens, each project's handoffs go in `handoffs/[project-slug]/` subfolders instead of flat `handoffs/`.

**Why:** The TCCS shoot produced both a Dr. Pan Intro and a Facial Rejuvenation Testimonial from the same interviews. Starting the second project in the same folder caused a collision — the Creative Context Agent would have overwritten the first project's handoffs. The fix was project-slug subfolders, but the skill files didn't document this pattern.

**What changed:**
- SKILL.md: New "Multi-Project Folders" section with subfolder structure and guidance on when to use it
- SKILL-creative-context.md: New "Multi-Project Detection" step in Required Inputs — the Creative Context Agent now checks for existing handoff subfolders and asks Jeff to establish a project slug at the start. Handoff save paths updated to reference `[project-slug]/` variant.
- SKILL-creative-context.md version bumped to v3.2.1

### Edit Agent: edit-handoff.md added as standard output

The Edit Agent now produces `handoffs/edit-handoff.md` as a standard handoff document alongside `trimmed-quotes.json`. This structured summary gives the FCPXML Agent clear context about the paper cut state — including notes about skipped trims, splits, and edge cases. Added to SKILL-edit.md output specification, SKILL-fcpxml.md required inputs, and SKILL-review.md required inputs.

**Why:** The Facial Rejuvenation project revealed that the Edit Agent needs a way to communicate context that the data alone doesn't convey — such as "Act 3 has no trims yet" or specific editorial intent behind splits. Without this document, the FCPXML Agent has to infer state from the data.

### Edit Agent: "skip to FCPXML" workflow documented

Added note to SKILL-edit.md that Jeff may choose to skip detailed trimming on some sections and proceed to FCPXML generation. This is a valid workflow — not every act needs full trimming before the rough cut is generated.

### Reference example: Facial Rejuvenation

First multi-speaker B2B testimonial processed through the full v3.0+ pipeline. Two speakers (Erin Harmon — patient, Dr. JD Luck — practitioner). Includes transcripts, Final_Edit.txt, and lessons-learned.md. Notable for the Act 2 call-and-response structure (patient experience interleaved with practitioner philosophy) and clean scope boundary management (body surgery confined to single trust beat).

### Version bumped: SKILL-edit.md, SKILL-fcpxml.md, SKILL-review.md → v3.2.1

---

## v3.2 — 2026-03-28

### Interactive viewer overhaul (quotes_viewer_template.jsx)

Major upgrade to the quote viewer's interactive editing capabilities. All changes are in the REACT COMPONENT section of the template — the data block format is unchanged.

**Character-range text editing** — Replaced sentence-level trim editor with a character-range selection model. Users highlight text and press Delete to toggle words between kept and cut. Cuts snap to word boundaries automatically. The Delete key inverts state: kept text becomes cut, cut text becomes kept. Orphaned spaces between cuts are absorbed automatically.

**Quote splitting UI** — The viewer now supports interactive quote splitting. A scissors button (✂) appears on each selected quote card. Clicking it opens split mode, where clickable markers appear between every word. Place one or more split markers, then confirm. The quote becomes independent sub-quotes (e.g., #82a, #82b) that inherit existing text cuts, section assignment, and selection state. Each sub-quote is a fully independent card with its own editing, drag, and section reassignment.

**Drag-and-drop reordering** — Replaced up/down arrow buttons with drag-and-drop. Selected quotes show a 6-dot grip handle on the left edge. Drag a card onto another card within the same section to reorder. A blue indicator line shows the drop position (above or below target). Cross-section dragging is blocked.

**Color-coded section filters** — Section filter buttons at the top now use each section's assigned color (blue, amber, emerald, etc.) instead of uniform black. Both active and inactive states reflect the section color, making it easy to visually associate filter buttons with their quote cards.

**Checkbox-only selection** — Quote selection now only toggles via the checkbox in the upper right of each card, not by clicking anywhere on the card. This prevents accidental deselection when working in "Selected only" mode.

**String-based quote IDs** — Internal data model changed from integer `num` to string `id` field for all lookups, state management, and React keys. Display still uses `q.num` (integer) plus `q.subLabel` for split quotes. This enables the `"82a"` / `"82b"` identifier pattern for split quotes.

**HTML viewer pattern** — The primary working viewer is now an HTML file wrapping the JSX with React 18 + Babel standalone + Tailwind CSS CDN. This provides full interactivity without a build step. Console warnings from CDN scripts are suppressed.

### SKILL-edit.md updated

Updated to reflect new viewer features: character-range editing workflow, split UI interaction, drag-and-drop reordering, color-coded filters, and the updated split data model (`id`/`num`/`subLabel` fields).

---

## v3.1.1 — 2026-03-27

### Project type renamed: "New Staff Introduction"

"Physician Introduction / Single-Speaker Intro" renamed to "New Staff Introduction" across all skill files, reference examples, and changelog. The category covers any video introducing a new high-level staff member — audience can be internal, external, or both. The goal is always to establish credibility, trust, and rapport.

### Reference example: HDG COO Intro

Second new staff introduction added to the knowledge base. Erin GaN, COO at Health Dimensions Group — internal audience (~3,000 team members). Pre-pipeline reference (edited manually). Includes Final_Edit.txt from VTT captions and lessons-learned.md. Full interview transcript to be added when available.

---

## v3.1 — 2026-03-26

### Selection Agent + Trim Agent merged into Edit Agent (SKILL-edit.md)

The separate Selection Agent (SKILL-selection.md) and Trim Agent (SKILL-trim.md) have been merged into a single Edit Agent (SKILL-edit.md). Pipeline reduced from 8 agents to 7.

**Why:** The Dr. Pan Intro project proved that selection and trimming are too intertwined to separate. During the Trim session, 3 quotes were swapped (deselected and replaced with previously unselected quotes), the sequence was substantially reordered, and a quote was split — all decisions that required access to the full quote pool and couldn't happen in an isolated trim-only context. The artifact viewer already gave Jeff access to all quotes, undermining the isolation rationale.

**What changed:**
- SKILL-selection.md and SKILL-trim.md replaced by SKILL-edit.md
- Edit Agent handles selection, trimming, and subclip splitting in a single collaborative session
- Internal phases preserve focused-task quality: Pre-Selection Review → First Pass Selection → Collaborative Editing → Final Review → Cardinal Rule Verification → Handoff
- selection-state.json eliminated as a cross-agent handoff document
- Edit Agent produces trimmed-quotes.json directly for the FCPXML Agent

### Subclip splitting

Quotes can now be split into independently orderable subclips. Each subclip becomes a first-class entry with its own sequence position, trim, and timecode range.

**Why:** The Dr. Pan edit required interleaving parts of quote #21 with quote #14 to create a single cohesive thought (#21a → #14 → #21b). The previous system could only represent splits as trim annotations, not as independently orderable items.

**Data model:** Split quotes use `num: "21a"`, `parentNum: 21`, `split: true`, `split_part: "a"`. Each subclip can be reordered, trimmed, and placed anywhere in the sequence independently.

**Note:** As of v3.2, the viewer template fully supports interactive splitting UI. See v3.2 changelog above.

### Cardinal Rule protection shifted to active verification

The previous approach relied on context isolation — the Trim Agent received only selected quotes, not the full transcript. In practice, the artifact gave Jeff access to all quotes, undermining the isolation. The Edit Agent now protects the Cardinal Rule through an active verification step (Phase 6) that checks every trimmed quote is a verbatim subset of its original before saving the handoff.

### SKILL-fcpxml.md updated with Phase 0

Added Phase 0: Extract .fcpxml Files from .fcpxmld Packages. The FCPXML Agent now checks for .fcpxmld packages in xml/ and runs scripts/extract_fcpxml.py before proceeding. Also added note about single-interview projects using the subject's file as both caption source and reference.

### New Staff Introduction added as project type

Added "New Staff Introduction" to SKILL-creative-context.md project type examples. Introduces a new high-level staff member — audience can be internal, external, or both. Structure: origin/identity → philosophy/approach → emotional payoff. Based on the Dr. Pan Intro project — first single-speaker intro video in the pipeline.

### Single-speaker project guidance

Added note to SKILL-review.md that cross-interview analysis sections should be adapted to intra-interview analysis for single-speaker projects.

### All skill files updated to v3.1

Version bumped across: SKILL.md, SKILL-creative-context.md, SKILL-edit.md (new), SKILL-synthesis.md, SKILL-fcpxml.md, SKILL-fcpxml-params.md, SKILL-review.md.

### Reference example: Dr. Pan Intro

First new staff introduction added to the knowledge base. Includes transcripts, Final_Edit.txt, and lessons-learned.md.

---

## v3.0 — 2026-03-19

### Multi-agent pipeline expansion: 6 agents to 8 agents

**New agents:**
- **FCPXML Params Agent** (SKILL-fcpxml-params.md) — extracts FCPXML technical parameters from sample narrative XML. Previously embedded in Transcript Agent Phase 0 Step 3. Now runs in parallel with Transcript Agents as a dedicated Haiku 4.5 agent.
- **Synthesis Agent** (SKILL-synthesis.md) — merges per-speaker Transcript Agent outputs into combined handoffs. Produces narrative assessment with speaker coverage map, redundancy report, gap report, recommended speaker weight, and cross-references.

### Transcript Agent scoped to single interview
- Each instance processes one interview transcript (previously handled all interviews)
- Output filenames use speaker slugs: `[speaker-slug]-tagged-quotes.json`, `[speaker-slug]-orphans.md`, `[speaker-slug]-discards.md`, `[speaker-slug]-summary.md`
- Phase 2 (Preliminary Narrative Assessment) removed — moved to Synthesis Agent
- Phase 0 Step 3 (FCPXML param extraction) removed — moved to FCPXML Params Agent
- Phase 0 Steps 1-2 (file validation, extract_fcpxml.py) removed — handled by Project Setup Validator
- Captioned XML no longer a required input for the Transcript Agent
- All "Structure Agent" references removed

### Dynamic act labels (fully implemented)
- All hardcoded section names (Opening, Challenge, Solution, Impact) removed from SKILL files and JSX template
- Act labels are set by Creative Context Agent per project and flow through entire pipeline
- JSX quotes_viewer_template.jsx: sectionColors, sections array, and reassign dropdown now derive dynamically from quote data via `buildSectionColors()` function
- Color palette (6 colors) cycles for any number of sections; Orphan always gets gray
- SECTION_CONFIG data block field added for explicit section configuration

### Narrative roadmaps (new Creative Context Agent output)
- Creative Context Agent Phase 3 added: develops per-section narrative roadmap after act structure approved
- Each roadmap covers: how section opens/closes, emotional arc, speaker assignments, key moments, what it accomplishes
- Roadmaps included in act-structure.md handoff document
- Selection Agent uses roadmaps as editorial direction for sequencing and ordering

### Creative context inputs relaxed
- Creative Launch transcript and interview guide changed from "Essential — must have before starting" to "Soft Requirement — preferred but not blocking"
- Jeff may provide context conversationally; pipeline does not hard-block on file presence

### Project type diversity
- Added Recruiting Video and Brand Film examples to Creative Context Agent
- All project type examples reframed as illustrations, not defaults
- Added explicit note: "let the interviews drive the structure"

### Skill Review Agent updates
- Updated to reflect 8-agent pipeline (sixth to eighth agent)
- Added review sections for FCPXML Params Agent, per-interview Transcript Agents, and Synthesis Agent
- Added dynamic act label consistency check to lessons learned categories
- Added project type tagging guidance for reference examples

### Dropped outputs
- `tagged-quotes.md` (human-readable version) dropped — dashboard quote viewer renders JSON directly

### Cowork compatibility
- All changes are backward-compatible with manual Cowork sessions
- Each agent can still be run as a separate Cowork session pointing at the project folder
- Cowork workflow serves as fallback if n8n has issues

---

## 2026-03-04

### Trimming guidance updated
- Second Pass Editorial Principle #10 rewritten: "Trim for meaning, not brevity." Don't trim quotes just because they're verbose or conversational. Only trim when the content genuinely changes — speaker pivots to a different topic, repeats with a weaker version, or trails into something unrelated. Natural speech patterns are part of documentary authenticity.

### Fuzzy matching bug documented
- Added "Known Issue: Fuzzy Matching with Short Quotes" subsection under FCPXML Generation.
- Short sentences with common words (under ~8 words) can match to the wrong location in the interview when the 0.65 threshold is too permissive.
- Documented five recommended algorithm improvements: proximity constraints, minimum text length for sentence matching, context-aware matching, higher thresholds for short strings, and fallback to whole-quote matching for short quotes.
- Based on BBBS 2026 comparison: ~12 of 49 clips landed on wrong region due to this issue.

## 2026-03-03

### Scope broadened beyond B2B
- Description, intro, and all references updated to treat branding films, client hero stories, nonprofit fundraisers, recruiting videos, and B2B testimonials equally — no single project type given top billing.

### Multi-pass editing workflow added
- V1 (wide selects) and V2+ (tightening passes) workflow documented.
- Versioning & non-destructive editing: dict-based rebuild method for JSX data block updates; warning against regex insertion (caused 18 corrupted trims in testing).

### Second Pass Editorial Principles added
- 10 principles for tightening passes, including quote redistribution (#9) and trimming guidance (#10).

### Narrative structures expanded
- Three-Act / Cold Open structure listed first as primary pattern.
- Problem → Solution structure listed as alternative (previously the only option).
- "Other Structures" section added for thematic, chronological, and parallel structures.

### Speaker Roles generalized
- Replaced B2B-specific roles with universal patterns: Primary Subject, Supporting Voices, Institutional Voice, Independent Validator.

### JSX viewer improvements
- Collapsible Selected Quotes panel (default collapsed, scroll constraint, removed sticky positioning).
- Safe JSX editing method documented (dict-based rebuild).

### FCPXML generation updates
- JSX viewer designated as primary source of truth (over Excel).
- Versioned output naming (_v1, _v2, etc.).
- Reference PDF generation added as standard post-FCPXML step.

### Session Retrospective added
- New end-of-session step for continuous skill improvement.

### Phase 0 updated
- Cowork local-folder-only limitation documented (no portable drive support).

### Editorial Rules
- Added #11: Quote redistribution between sections.
