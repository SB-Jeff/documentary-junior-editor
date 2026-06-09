# Lessons Learned — TC Pain Clinic 2026 (Organic Variant)
## Completed: 2026-06-08
## Project Type: OTT/CTV Ad Campaign (:30 spot) — Healthcare
## Subjects: 3 (Dr. Will — Founder/Medical Director; Dr. Haas — Assistant Medical Director; Sheila — Clinic Administrator)
## Variant: organic-only (no scripted/safety lines) — sibling to the parent `tc-pain-clinic-2026` run

> The Project Type tag is used by future agents to filter for relevant reference examples.
> This is the **second ad-format project** in the knowledge base after the parent
> `tc-pain-clinic-2026` campaign cut, and the first reference example to document the
> **shared-upstream variant** pattern (one shoot, multiple Edit/FCPXML branches off a
> common Creative-Context → Synthesis trunk).

---

## Provenance note (read first)

This project is a **variant edit** of the `tc-pain-clinic-2026` campaign shoot, not an
independent pipeline run. The upstream agents (Transcription, Creative Context,
Orchestrator, the three Transcript Agents, FCPXML Params, Synthesis) ran **once** for the
parent slug and their outputs live in `handoffs/tc-pain-clinic-2026/`. The `-organic`
variant forked at the Edit Agent: it built its own curated 54-quote organic pool
(`handoffs/tc-pain-clinic-2026-organic/tagged-quotes-v1.json`, a flat list filtered to
organic interview takes + orphans, excluding scripted safety lines), then ran its own Edit
(round 1, TIGHT, 15 entries) and FCPXML pass under the `-organic` slug. The parent shoot
also spawned a second variant (`-haas`, a Dr.-Haas-only micro-cut). All three branches
share the same FCP library, transcripts, and source multicam FCPXMLs.

**No Editing Coach pass ran for this variant**, and the Edit Agent did not leave an
`edit-agent-lessons-v[N].md`. Per SKILL-review.md v5.7 fallback, the captured feedback for
this review is the Edit Agent's `notes` fields in `pipeline-state.json` and the parent's
`edit-handoff-v[N].md` files. The **Editing and Quote Viewer sections of this file were
therefore never authored by Coach** — they are intentionally absent. This Skill Review pass
wrote only the System, Forward-Looking, and Reference Value sections, which is the correct
scope for the Coach-didn't-run path.

---

## Project Summary

A 30-second OTT/CTV ad for Twin Cities Pain Clinic, "organic-only" variant: built entirely
from how the doctors and administrator actually spoke in their interviews, deliberately
excluding the scripted "safety lines" the client read on camera. The cut runs across the
three client-approved message pillars used as acts — **No Wait, Easy Access** /
**An Elevated Level of Care** / **The Best Treatment Possible** — which are modular for A/B
reordering (no cross-act transitions). The TIGHT export is 15 entries (32 spoken clips
after segmentation + 3 act-divider cards in the FCPXML). Voice balance holds the client's
male+female physician requirement; Dr. Will leads access and treatment, Dr. Haas carries
care, Sheila supports access. Three of the fifteen entries are sourced from the orphan pool
(#80, #82, #83), confirming the orphan pool carried usable on-message material.

---

## Session Feedback: System

### Technical Issues

**1. Act-divider title cards stack at the sequence-start offset (CONFIRMED REPRODUCTION
of the documented `build_fcpxml.py` bug — now 2nd+ occurrence).**
All three act-divider title cards in `tc-pain-clinic-2026-organic_tight_cut_v1.fcpxml` are
emitted as `lane="1"` connected titles at `offset="86400314/24000s"` (= 3600.013s, the
sequence `tcStart` sentinel) instead of tracking cumulative spine duration to their act
positions. The spine **gaps** that host them advance correctly (offsets 0, 711711/24000s,
3011008/24000s), so only the title `offset` attribute is wrong. This is the exact bug
logged OPEN/high-priority in SKILL-review.md Phase 3 (Hammer NER 2026 finding (a):
"act-boundary title cards stack at the sequence-start offset instead of their act
positions — section-divider offset must track cumulative spine duration"). It reproduced
identically here, and **also in both sibling FCPXMLs on this shoot**
(`tc-pain-clinic-2026_haas_tight_cut_v2.fcpxml` and `tc-pain-clinic-2026_loose_cut_v1.fcpxml`).
That is a second confirmed project exhibiting the bug after Hammer NER 2026 — it has
crossed the threshold from "logged code follow-up" to "actively shipping broken title-card
placement on every multi-act cut." **Escalation recommendation: this is the single
highest-value code fix outstanding.** Status: OPEN → should move to IN PROGRESS.
Workaround in practice: Jeff strips/repositions act dividers at finishing in FCP (the cut
treats them as disposable, per the edit-handoff notes), so it has not blocked delivery —
but it silently wastes the divider work on every run.

**2. Caption-derived `text-style` artifacts baked into title resources.** The FCPXML's
title `text-style` definitions carry mis-transcribed caption fragments (e.g.
`ts2`/`ts3`/`ts4` contain "Yeah, Twinsay's pink thing, we know that pain / is not something
that we can wait on, and so / in within 48 hours..."). These are leftover caption-matcher
strings embedded in title styling, not the displayed act-label text (the act labels render
correctly from `ts1`). Cosmetic / harmless to the cut, but worth noting: the title-card
template is inheriting stray caption text into its style table. Likely the same
caption-matcher coupling that the `find_quote_range` TC-window narrowing touches. First
occurrence — logging as observation, not a rule.

**3. `.env` / git-crypt friction persists (carried, not new).** The project skill folder
still contains the deprecated `secrets/assembly_ai.key` (git-crypt-encrypted), which makes
`git` operations in a sandbox without git-crypt installed fail outright
(`external filter 'git-crypt clean' failed`). The Transcription summary again notes the
`.env` was missing on the run and had to be created manually, and re-files the standing
request that preflight auto-create `.env` from the legacy key. The v5.1 deprecation said
"remove on next Skill Review pass"; it has now survived multiple passes. **Recommend
deleting `secrets/assembly_ai.key` and the `secrets/` dir from the master on the next sync**
(see Phase 8 note) — it is both dead weight and an active git-operation hazard.

**4. No FCP import failure reported.** The single noted FCP-review caveat is benign: entry
#38 ("...but it doesn't have to be that way") rides a prior caption merged in the source,
so its clip tail should be verified in FCP. This is a source-caption boundary artifact, not
a generation failure.

#### Issues reported by Jeff (editing session, captured 2026-06-09)

These are the technical issues Jeff hit and worked through live during the edit. The
autonomous review pass could not surface them — there was no Coach pass and no
`edit-agent-lessons` doc — so they are captured here from Jeff directly. This is precisely
the gap the per-agent `session-issues.md` running log (Forward-Looking) is meant to close.

**Viewer rendering**

- **Blank Cowork sidebar artifact.** The viewer is built on React + Babel + Tailwind from
  CDNs, but the Cowork artifact pane blocks all network except three whitelisted libraries,
  so it rendered blank there. Resolution: switched to a **browser-first workflow** (rebuild
  the HTML, reload the tab) and stopped relying on the sidebar artifact. Shares a root cause
  with the viewer disk-write failure below.
- **Blank page #1 — generic act labels.** The build script reads act labels and speakers
  from `pipeline-state.json` under `creative-context`, but those keys weren't present, so it
  fell back to "Act 1/2/3." Entries tagged with the real act names matched no section and
  the body rendered empty. Fixed by writing the real `act_labels` into `pipeline-state.json`.
  (Directly related to the act-label/`creative-context` key plumbing — and a counter-example
  to Architecture #2's "clean label flow": the labels were clean in the data but absent from
  the state keys the viewer build reads.)
- **Blank page #2 — speaker color crash.** Speakers were first written as plain strings, but
  the template needs `{name, slug}` objects whose `slug` matches each quote's `speakerSlug`
  for the color lookup. The mismatch threw a runtime error that blanked the whole page. Fixed
  by writing speaker objects. Jeff also set up a **headless render test (Babel + jsdom)** to
  catch these crashes before handoff instead of on reload — a genuinely useful new safeguard;
  candidate to promote into the viewer build workflow (Coach/Claude-Code territory now).

**Data plumbing**

- **Runtime target not detected pre-emit.** The build script only looked for the runtime
  target in emitted `trimmed-quotes` files, so working rounds showed the wrong number.
  Patched to also read `editing-versions/`.
- **`source_quote_id` type mismatch.** First round wrote IDs as strings; the migrator matches
  integer quote numbers, so nothing linked. Fixed to integers.
- **Empty orphan pool.** The merged tagged-quotes file carried zero orphans, so the Quote
  Library's orphan section was silently empty and #92 wasn't available to rescue. Jeff
  ingested all 19 orphans verbatim from the orphan markdown into a v2 pool (and
  sentence-segmented #92). (Note: this contradicts the autonomous review's read that
  orphans #80/#82/#83 were promoted from a populated pool — the pool was empty until Jeff
  rebuilt it. The orphan-merge step upstream did not carry orphans into the merged file.)

**FCPXML generation**

- **`.fcpxmld` packages.** Sources were packages, not flat files — had to run
  `extract_fcpxml.py` (Phase 0) before the build, or the matcher finds nothing. Process
  prerequisite worth making explicit in the FCPXML SKILL.
- **Dr. Haas clips silently skipped.** Her catalog name ("Dr. Haas") didn't match the
  params/file naming ("Dr Haas"), so every one of her clips was dropped on the first build.
  Jeff patched the speaker matcher in `generate_fcpxml.py` to normalize punctuation/case.
  **This is the `_canonical_speaker` change the autonomous review found uncommitted and
  flagged as a mystery — it is Jeff's intentional fix and SHOULD be committed.** Resolves the
  open "decide whether to include the stray script changes" question, and is the real-world
  instance of the parked Phase-3 fuzzy speaker-name resolver + the cross-agent
  shared-vocabulary drift item (now: IMPLEMENTED, pending commit).
- **#38 caption merge.** "But it doesn't have to be that way" is merged into the previous
  caption block in the source, so it can't match as its own clip and rides the prior clip's
  tail — a source-data quirk, flagged for Jeff's FCP pass rather than fixed in code. (Matches
  the autonomous review's #38 caveat.)

**Workflow**

- **Viewer can't write to disk.** The viewer's Export/Save is meant to write JSON directly
  via a tool call, but that path doesn't work in this Cowork setup (same root cause as the
  blank artifact — sandboxed artifact pane). Tight selections never persisted. Settled
  workflow: Jeff pastes selections (op list, JSON, or screengrabs) and the agent reconstructs
  them canonically **with verbatim verification before each export** (Cardinal Rule 1 held).
  This is a recurring environment constraint, not a one-off — see Architecture note below.

#### Phase 3 follow-up tracking (status as of this pass)

- `scripts/transcribe.py` legacy key paths — SHIPPED v5.1; **prune still pending** (the
  `secrets/` artifact above is the residue). Recommend completing the prune this sync.
- `scripts/build_fcpxml.py` title-card offset stacking — **OPEN → escalate to IN PROGRESS.**
  Second confirmed reproduction (this project). Highest-priority code work.
- `scripts/build_fcpxml.py` `parse_act_structure` "Intro"/non-Act heading miss — N/A this
  project (acts are the three pillars, no Intro label; act-structure explicitly states
  "There is no Intro label").
- `scripts/build_fcpxml.py` slug→display-label canonicalization in `_canonicalize_section`
  — not exercised here in a way that surfaced drift; act labels propagated cleanly
  (see Architecture).
- `scripts/generate_fcpxml.py` `find_quote_range` TC-window narrowing — likely implicated
  in the caption-style-artifact finding (#2); verify on next pass.
- `scripts/generate_fcpxml.py` speaker-name normalization (`_canonical_speaker`) —
  **IMPLEMENTED this session, PENDING COMMIT.** Jeff's punctuation/case-normalizing matcher
  fixes the "Dr. Haas" vs "Dr Haas" silent clip-drop. This is the parked Phase-3 fuzzy
  speaker-name resolver, now real. Include in the v5.8 commit (it was the "stray uncommitted
  change" the autonomous review flagged). Cross-agent shared-vocabulary drift between catalog
  names and params/file naming is the root cause — consider whether speaker names should be
  canonicalized once upstream.
- `scripts/build_fcpxml.py` runtime-target detection — **PATCHED this session.** Now reads
  `editing-versions/` in addition to emitted `trimmed-quotes` files, so working rounds report
  the correct runtime target pre-emit.
- `scripts/build_quotes_viewer.py` — act-label/speaker source keys: build reads `act_labels`
  and speaker objects from `pipeline-state.json` under `creative-context`; when absent it
  falls back to generic "Act 1/2/3" and blanks the body. **NEW follow-up:** make the build
  fail loud (or read act labels from `act-structure-v[N].md` directly) instead of silently
  falling back; require speakers as `{name, slug}` objects with a schema check. (Viewer dev
  now lives in Claude Code — route there.)
- Headless render test (Babel + jsdom) — **NEW, introduced by Jeff this session.** Catches
  viewer runtime crashes before handoff. Candidate to formalize into the viewer build/QA
  step. (Claude Code territory.)
- Viewer Export/Save-to-disk + Cowork artifact network restriction — **environment
  constraint, not a code bug.** The artifact pane allows only three whitelisted CDN libs and
  blocks the disk-write tool path. Drove the browser-first + paste-and-reconstruct workflow.
  See Architecture & Design for the system-level implication.
- `.fcpxmld` package pre-extraction — **process prerequisite.** `extract_fcpxml.py` (Phase 0)
  must run before the build when sources are packages. Make explicit in SKILL-fcpxml.md.
- `scripts/quotes_viewer_template.jsx` / `build_quotes_viewer.py` — Hammer NER 2026 patches
  SHIPPED in v5.8 (Tight/Loose/Library membership rework). The variant's
  `trimmed-quotes-v1.json` already uses the v5.8 `membership` field, confirming the new
  schema is in service.

### Architecture & Design

**1. Shared-upstream variant pattern worked, and the slug discipline mostly held — with
one drift.** The fork-at-Edit design is sound: Creative Context → Synthesis ran once,
multiple cut variants branched off a common pool with their own slugs and handoff
subfolders. Slug discipline was largely correct — the `-organic` Edit and FCPXML outputs
write to `handoffs/tc-pain-clinic-2026-organic/` and `XML/imports/` with `-organic`-prefixed
filenames. **Drift to flag:** the `-organic` `pipeline-state.json` records the upstream
agents' `outputs` as `handoffs/tc-pain-clinic-2026/...` (the parent paths), which is
*accurate* (those files really do live under the parent slug) but means the variant's
state file is not self-contained — a reader of the `-organic` state alone is sent to a
different slug's folder for half the chain. This is the correct behavior for a variant but
should be **documented as a named pattern** so it doesn't read as a bug: "variant projects
inherit upstream outputs by reference from the parent slug; only the forked-from-Edit
agents write under the variant slug." Candidate for a short SKILL.md note on multi-variant
shoots (distinct from the existing multi-*project* SSD note).

**2. Dynamic act-label flow was clean.** The three pillar labels ("No Wait, Easy Access" /
"An Elevated Level of Care" / "The Best Treatment Possible") propagated verbatim and
consistently from `act-structure-v1.md` → Synthesis `part` tags → Edit `part` fields →
FCPXML title cards → reconstructed Final_Edit. No label drift, no slug/display mismatch.
The "Orphan" label was also handled correctly (orphan-pool quotes #80/#82/#83 were promoted
into real acts at edit time and carry the correct `part`, not "Orphan"). This is a
counter-example to the cross-agent shared-vocabulary drift seen on Nanos/Hammer NER — when
the act labels are short, human-readable strings used identically as both slug and display,
there is nothing to canonicalize and nothing drifts. Weak evidence (one project) toward a
forward-looking idea: prefer human-readable act labels as the single canonical form and
drop the slug↔label canonicalization layer entirely where possible.

**3. Synthesis segment-count discrepancy was caught and resolved correctly.** The parent
`pipeline-state.json` records that per-speaker summary docs under-counted segments (Dr. Will
52 vs. actual 59; Dr. Haas 78 vs. 94) and that Synthesis correctly treated the JSON as
ground truth and preserved all segments. Good hygiene — the validation block named the
discrepancy rather than silently inheriting bad tallies. No downstream impact: the Edit
Agent worked from the JSON, which was complete.

**4. Cascade tightness / stale state.** Only round-1 outputs exist for the variant; no
re-run cascade to evaluate. No stale-state warnings fired or were proceeded-through. The
variant's edit `based_on` correctly records `synthesis: 1, creative-context: 1`. State is
internally consistent.

**5. Handoff completeness gap (process, not data).** Because no Coach pass ran and the Edit
Agent left no `edit-agent-lessons` doc, the editorial-philosophy channel into the skill was
empty for this project. The data was fine; the *feedback-capture* path was not exercised.
This is exactly the failure mode v5.7 introduced the Edit-Agent lessons doc to prevent — and
it still no-opped here because the Edit Agent simply didn't write one for a variant cut.
**→ Coach should fold into SKILL-edit.md on next pass:** the Phase-7 "write
edit-agent-lessons" step should apply to variant cuts too, or explicitly state when a
variant may skip it (e.g., "variants inherit the parent's lessons doc; note the variant's
deltas in a short addendum"). Flagged for Coach per territory split.

**6. Cowork artifact pane constraints reshaped the viewer workflow (environment, recurring).**
Two of this session's hardest stoppages share one root cause: the Cowork artifact pane allows
only three whitelisted CDN libraries and blocks the viewer's disk-write tool path. The viewer
(React + Babel + Tailwind from CDNs) rendered blank in the sidebar, and Export/Save couldn't
persist selections. The settled workflow — **browser-first** (rebuild HTML, reload tab) plus
**paste-and-reconstruct** (Jeff pastes op lists / JSON / screengrabs; agent rebuilds canonically
with verbatim verification) — works and held Cardinal Rule 1, but it is a manual round-trip
imposed by the environment, not a design choice. System implication: the quote viewer should
be treated as a **browser-hosted tool, not a Cowork artifact**, and its persistence path
designed for the browser-first reality (now that viewer dev has moved to Claude Code, this is
the natural place to settle it). Pairs with the Final Cut Pro / artifact capability-audit notes.

### Capability Audit

### Opus 4.8 / Sonnet 4.6 with 1M-token context now standard
**Discovered:** Anthropic docs / model pages (anthropic.com/claude/opus, /sonnet).
**Applies to:** Whole pipeline; especially Edit Agent (Opus) and the Orchestrator's
sub-agent fan-out (Sonnet).
**Current pain it would address:** Long interviews + large merged pools (this shoot:
~210 segments across 3 speakers, ~98 quotes in the parent v2 pool) push context. A 1M
window (this very review ran on opus-4.8 1M) means the Edit Agent can hold the full
tagged-quotes pool + all prior rounds + reference examples simultaneously without the
"does not receive full conversation history" compromise noted in SKILL.md. Also: Claude
Sonnet 4 / Opus 4 retire on the API **June 15, 2026** — the frontmatter `model:` lines
(several still say `opus-4.7`) must be migrated before then or n8n/API runs break.
**Adoption cost:** Low for Cowork (pick the model). Non-trivial bookkeeping: every SKILL
frontmatter `model:` line should be audited and bumped to a non-retired model.
**Recommendation:** **Adopt now** — audit and bump all `model:` frontmatter ahead of the
June 15 retirement; consider documenting the 1M window as license to drop the
"Edit Agent doesn't get prior-session history" limitation.

### Cowork "Dreaming" — scheduled memory curation of past sessions
**Discovered:** Anthropic Cowork release notes / 2026 feature roundups.
**Applies to:** Skill Review Agent + the reference-examples knowledge base.
**Current pain it would address:** Lessons capture is manual and brittle — it depends on
Coach running and on the Edit Agent writing a lessons doc, both of which no-opped on this
variant. "Dreaming" reviews past agent sessions, surfaces recurring patterns, and curates
memory between runs. That is structurally the same job as the three-occurrence rule + the
lessons-learned corpus, done automatically.
**Adoption cost:** Medium — would need a defined memory store and a mapping from Dreaming's
output to the reference-examples format; risk of it diverging from the curated, Jeff-approved
lessons discipline.
**Recommendation:** **Investigate further** — could backstop the feedback-capture gap that
recurred here, but must not replace Jeff's approval step for rule promotion.

### AssemblyAI MCP Server (transcription connector)
**Discovered:** AssemblyAI April 2026 recap / MCP registry.
**Applies to:** Transcription Agent.
**Current pain it would address:** The v5.1 host-side launcher exists only because Cowork's
sandbox outbound allowlist doesn't include AssemblyAI (sandbox transcription returns 403).
An official AssemblyAI MCP server lets MCP clients transcribe/search transcripts directly —
potentially collapsing the host-side `start-editing` launcher step and the `.env`/preflight
dance back into an in-session tool call, IF the MCP transport isn't subject to the same
allowlist.
**Adoption cost:** Medium — depends on whether the connector is allowlisted in Cowork; needs
a test run. Auth moves from `.env` to the connector's credential store.
**Recommendation:** **Try on next project** — pilot the connector on one interview; if it
works in-sandbox it retires the launcher and the recurring `.env` friction in one move.

### Final Cut Pro MCP servers (live FCP control + FCPXML engine)
**Discovered:** MCP registry (dreliq9/fcp-mcp ~88 tools; elliotttate/finalcutpro-mcp ~99
tools; DareDev256/fcpxml-mcp-server ~40 tools).
**Applies to:** FCPXML Agent.
**Current pain it would address:** The pipeline generates FCPXML blind and Jeff imports +
verifies by hand (this project: verify #38 tail; every project: strip mis-placed act
dividers). A live-FCP-control MCP could place act dividers at real spine positions
(side-stepping the offset-stacking bug entirely), verify import success, and read back clip
boundaries — closing the open-loop "generate then hope it imports" gap.
**Adoption cost:** High — third-party MCP, AppleScript/JXA surface, trust/stability unknown
on Jeff's exact FCP version; would be a significant FCPXML-Agent redesign.
**Recommendation:** **Investigate further / Park** — promising for the import-verify loop
and a possible structural fix for the title-card bug, but a big dependency to take on; revisit
after the cheaper `build_fcpxml.py` offset fix ships.

### Orchestration pattern check
The parent shoot used the Orchestrator (v5.5) to fan out 3 Transcript Agents + FCPXML Params
as parallel sub-agents (13 files expected/verified) — the documented pattern worked cleanly.
The variant cuts (`-organic`, `-haas`) were **manual forks at the Edit Agent**, not
orchestrated. There's a latent pattern here worth naming: a "variant fan-out" where one
Orchestrator pass spawns N Edit-Agent sub-agents (one per cut variant) off a shared pool,
each emitting under its own slug. Not built; logged as a forward-looking candidate.

---

## Forward-Looking — Jeff's Ideas

> Captured live with Jeff during the 2026-06-09 Skill Review session. Jeff noted up front
> that these were short ads (atypical for Storyboard's usual documentary/testimonial work),
> so editorial feedback is light; his input centered on **how feedback is captured during a
> session** and **how the Review Agent itself functions**.

### Active in-session note capture (replace the physical notepad)
Jeff's framing: "When I do an editing session, I have a notepad that I jot down things that
go wrong or ideas I have on how to make it better. I'm wondering if there is a better way to
actively document notes while performing the edit." He asked whether agents can message each
other, or whether it would make more sense to have agents summarize issues as they come up so
he can share them as a running list with the Review Agent.

Resolution discussed in-session: pipeline agents do not message each other live — they
communicate through handoff documents. **Jeff's preferred design:** when an issue comes up
during a session, the active agent should summarize it on the spot and write it to a single
**shared issues file** (e.g. `handoffs/[project-slug]/session-issues.md`), **organized by
agent** — one section per pipeline agent — so every issue is clearly attributed and
structured rather than living in an undifferentiated running list. Each agent appends to its
own section as problems or ideas surface; Jeff can also add his own notes to the relevant
section mid-edit instead of using a physical notepad. The Skill Review Agent then reads the
file section-by-section as a primary input, which maps directly onto how it already reviews
the pipeline per-agent. This mirrors the existing handoff architecture and directly addresses
the feedback-capture gap this very review hit (no Coach notes, no Edit-Agent lessons doc
existed — see Architecture & Design #5).
**Implementation notes for next pass:** add a "log to `session-issues.md` under your agent's
section" instruction to each agent's SKILL file; seed the file with a fixed agent-section
template; have the Review Agent's Required Inputs list it explicitly.
**Priority:** Next project (Jeff confirmed the by-agent structure; exact filename/path TBD)
**Related Capability Audit finding:** Cowork "Dreaming" (auto memory curation could
complement, not replace, a deliberate running log); Architecture & Design #5 (handoff
completeness gap).

### Quote viewer feedback now belongs in Claude Code (development moved)
Jeff reports the quote viewer "still has a ton of quirkiness" and that he has **moved ongoing
development of that tool over to Claude Code**. Open question he raised: should viewer
feedback be recorded in Claude Code directly rather than in `quotes-viewer-roadmap.md`?
Decision to make deliberately: keep one canonical feedback sink so notes don't fragment across
two systems. Either (a) `quotes-viewer-roadmap.md` stays the sink and the Claude Code workflow
reads it, or (b) feedback moves into the Claude Code repo and the roadmap is retired/redirected.
This touches Coach's territory (Coach currently files viewer entries to the roadmap), so
**→ flag for Coach / Jeff:** if the sink moves, update SKILL-editing-coach.md's "file viewer
entries to quotes-viewer-roadmap.md" instruction accordingly.
**Priority:** Now (low-effort decision; prevents fragmented feedback)
**Related Capability Audit finding:** —

### Creative Context — deliverable is a one-line act summary + supporting points, no quotes
Jeff's framing: the Creative Context deliverable is **too long and often includes quotes**.
What he wants per act is a **one-line summary with the main supporting points listed
underneath** — fast to review, easy to approve or critique. **Resolution (folded into
SKILL-creative-context.md this pass, v5.8):** Phase 3 now defines the review deliverable as,
for each act, one summary line plus a few brief supporting bullets; explicitly **excludes
verbatim quotes** (references material by speaker name and topic only — quotes live downstream
in the Edit Agent's pool); and reframes the six roadmap dimensions as an internal menu the
bullets may draw on, not a template to fill out in full. Two named failure modes to avoid:
deliverable too long, and pasted-in quotes.
**Priority:** Done this pass.
**Related Capability Audit finding:** ties to the Ad-format lightweight track candidate
(short-form deliverables want lighter ceremony across the board).

### Review Agent legibility — make the review not a black box
Jeff's framing: "To be honest, I'm not even sure what you look at when you do a review." The
review process is opaque to him — he can't tell what inputs the Skill Review Agent examines or
what it checks. **Resolution (folded into SKILL-review.md this pass):** the Review Agent must
make its scope visible — open each review with a short "What I'm reviewing" summary (which
handoff docs and project files it read, which inputs were present vs. absent, which checks it's
about to run) and close (in Notifying Jeff) by restating plainly what it looked at and checked.
Implemented as a new "Review Legibility" section plus step 0 in Notifying Jeff.
**Priority:** Done this pass (SKILL-review.md v5.8).
**Related Capability Audit finding:** —

### [Draft candidate — Jeff to confirm] Variant fan-out via Orchestrator
A "variant fan-out" Orchestrator mode that spawns one Edit-Agent sub-agent per planned cut
variant (organic / safety-line / per-speaker) off a shared Synthesis pool, each writing
under its own `-variant` slug. Surfaced by this project's manual three-way fork.
**Priority:** Park (pending Jeff)
**Related Capability Audit finding:** Orchestration pattern check (above).

### [Draft candidate — Jeff to confirm] Ad-format lightweight track
A documented short-form/ad variant of the pipeline (lighter ceremony, dividers optional,
runtime measured in seconds not minutes). This is the second ad-format project and the
calibration is clearly different from documentary/testimonial work.
**Priority:** Next project (pending Jeff)
**Related Capability Audit finding:** —

---

## Reference Value
**Project type:** OTT/CTV Ad Campaign (:30 spot) — Healthcare. Second ad-format example
after the parent `tc-pain-clinic-2026` campaign cut.
**Distinctive elements:**
- **Shared-upstream variant** — first reference example documenting the fork-at-Edit
  pattern (one shoot → common Creative-Context/Synthesis trunk → multiple Edit/FCPXML
  branches under sibling slugs). Pair with the parent and `-haas` cuts to see all three.
- **"Organic-only" curation constraint** — the cut deliberately excludes scripted safety
  lines and is built from how subjects actually spoke, plus three promoted orphans. A clean
  case study in editing to a *source-provenance* constraint rather than a runtime/arc one.
- **Modular acts for A/B reordering** — three self-contained pillar acts, no cross-act
  transitions; the inverse of the documentary "continuous arc" projects in the corpus.
- **Aggressive ad-format trimming** — 54-quote pool → 15 entries → ~30s; segment-level
  trims throughout (verified verbatim, zero Cardinal Rule 1 violations).
**What future projects should look at:**
- **Multi-variant shoot handling** — how slugs, handoff subfolders, and `pipeline-state.json`
  upstream-by-reference work across sibling cuts (and the documented state-file caveat).
- **Act-divider title-card placement bug** — this is the cleanest confirmed reproduction of
  the `build_fcpxml.py` offset-stacking bug across three sibling FCPXMLs; reference it when
  prioritizing the code fix.
- **Clean act-label propagation** — counter-example to shared-vocabulary drift; short
  human-readable labels used identically as slug and display propagate without
  canonicalization.
- **Orphan-pool promotion** — three of fifteen final entries came from orphans; evidence the
  orphan pool is live editorial material, not a discard bin.
**Best paired with:** the parent `tc-pain-clinic-2026` campaign cut and the `-haas` variant
(same shoot, different cuts); `tccs-dr-pan-testimonials` and `dr-pan-intro` (healthcare tone,
aggressive bite-level trimming); `international-institute` (short-form runtime calibration,
title-card usage).

---

## Pipeline State for the Review

- **Coach pass:** did not run. No `skill-review-notes.md`, no `edit-agent-lessons-v[N].md`.
  Editing / Quote Viewer sections intentionally absent (Coach-didn't-run path, SKILL-review
  v5.7 fallback). Feedback inputs were the Edit Agent `notes` in `pipeline-state.json` and
  the parent's `edit-handoff-v1/v2.md`.
- **Handoff documents reviewed:** all upstream (parent slug) at v1; Synthesis v1; variant
  Edit v1 + FCPXML v1. Parent also carries a v2 Edit/Synthesis-augmented pool for the
  `-haas` variant (read for context, not part of this variant's chain).
- **`pipeline-state.json`:** internally consistent for the variant; upstream outputs
  referenced by parent-slug path (variant pattern, documented above). No stale-state
  warnings fired.
- **Cardinal Rule 1:** verified programmatically — every trimmed entry's kept text is a
  contiguous verbatim subset of its source segment. Zero violations. (Note: entry 1 begins
  a sentence with lowercase "we" as a verbatim consequence of a mid-thought head-trim;
  preserved exactly per Rule 1, not corrected.)
- **Cardinal Rule 2:** each act reads as a coherent self-contained beat; modular-act design
  means no cross-act narrative dependency to verify. No coherence gaps surfaced.

---

*Lessons Learned — TC Pain Clinic 2026 (Organic Variant) — System / Forward-Looking /
Reference Value sections generated by Skill Review Agent on opus-4.8 (1M) at
2026-06-09. Editing / Quote Viewer sections not authored (no Coach pass).*
