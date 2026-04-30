---
name: documentary-junior-editor
description: |
  Multi-agent pipeline for documentary-style video editing. Turns raw interview
  transcripts into structured narratives and import-ready FCPXML timeline files for
  Final Cut Pro. Designed for Storyboard Films' B2B and nonprofit documentary projects.

  Use this skill whenever the user mentions: editing interviews, reviewing transcripts,
  selecting quotes, building a paper cut, narrative structure from interviews, documentary
  editing, string-outs, selects, assembly edits, or generating FCPXML/XML for Final Cut Pro.
  Also trigger when the user uploads transcript files (.txt, .srt, .vtt) alongside interview
  footage references or FCPXML files.
---

# Documentary Junior Editor — Master Skill Index
### Version 5.0 | April 2026

This is the master index for the documentary-junior-editor skill. Read this file first at
the start of every session. It describes the pipeline, the folder structure, how agents
hand off to each other, and how to set up a new project.

---

## The Cardinal Rule

**This rule applies to every agent in the pipeline without exception.**

**NEVER paraphrase or edit quotes from the transcripts.** You can trim them (cut the
beginning or end), split them into parts (e.g., #82a and #82b for different sections),
reorder them freely, and rearrange sentences within a quote when a different order serves
the narrative better. But you must never change the actual words. Every quote in the paper
cut must be verbatim from the transcript. If you need a quote that doesn't exist, go back
to the raw transcript and find the actual words — then assign it a new number.

**Sentence-level reordering is a powerful tool.** Sometimes a quote reads better when you
lead with the conclusion and follow with the setup, or when you move a vivid phrase to the
front. The words stay verbatim — only the order changes.

This rule is repeated at the top of every agent skill file. Its prominence is intentional.
A long context window can bury instructions. This one cannot be buried.

### How the rule generalizes in v5.0 — segments and timeline entries

The Cardinal Rule's existing language ("trim them, split them into parts, reorder them
freely, rearrange sentences") generalizes naturally to the v5.0 data model. Source quotes
are decomposed into **segments** — meaningful, self-contained pieces of an idea, typically
a clause or phrase that completes a thought. The unit of rearrangement is the segment:
smaller than a sentence, larger than a word.

The paper cut is no longer a list of quotes with trim annotations; it is a **timeline of
entries**. Each entry has `segments[]`, where each segment references its source quote
and source segment with optional per-segment head/tail trim. A timeline entry is a
contiguous-in-source-order play of segments from one source quote, with arbitrary internal
drops allowed (head, middle, tail, or any combination — Alice #6 with "head-trim +
middle-drop + tail-trim" is one entry, not three). Two cases produce new entries: when
playback order diverges from source order, or when segments come from different source
quotes.

The agent never says "split #11 into parts." It produces new timeline entries when the
manipulation requires it. Splitting is implicit. Verbatim integrity is preserved at the
segment level — words within a segment never change.

---

## The Pipeline

The editing workflow is divided into eight specialized agents. Each agent has its own
skill file, operates with a focused context window, and hands off structured output to
the project folder for the next agent to read. Jeff is surfaced only at creative
decision points.

```
Transcription Agent      →  transcripts/text/[speaker].txt + transcription-summary-v[N].md
        ↓ (invoked by Creative Context when audio detected without transcripts)
Creative Context Agent   →  Phase 0 — Discovery (Drive + Gmail)
                            creative-brief-summary-v[N].md + act-structure-v[N].md  ← Jeff approves
        ↓
┌───────────────────────────────────────────┐
│  Parallel fan-out                         │
│                                           │
│  FCPXML Params Agent  → fcpxml-params-v[N].md (with per-interview clip_type)
│                                           │
│  Transcript Agent (×N) → per-speaker      │
│  (one per interview)     tagged-quotes-v[N].json (with segments[]),
│                          orphans, discards, summary
└───────────────────────────────────────────┘
        ↓ (fan-in: wait for all)
Synthesis Agent          →  merged tagged-quotes-v[N].json (segments preserved),
                            orphan-quotes, discard-summary, transcript-summary
        ↓
┌─────────────────────────────────────────────────────────────────┐
│  Multi-round Edit ↔ FCPXML loop (Lesson 6)                      │
│                                                                 │
│  Edit Agent (round N)  →  trimmed-quotes-v[N].json (timeline    │
│                            entries with segments[]),            │
│                            edit-handoff-v[N].md,                │
│                            [project-slug]_quotes_view.html      │
│                            (live artifact, updated mid-session) │
│        ↓                                                        │
│  FCPXML Agent          →  [project-slug]_rough_cut_v[N].fcpxml  │
│        ↓                                                        │
│  Jeff watches in FCP. Approves OR appends to review-notes.md    │
│  and re-launches Edit Agent for round N+1.                      │
└─────────────────────────────────────────────────────────────────┘
        ↓ (Jeff approves)
Skill Review Agent       →  reads versioned diffs across all rounds,
                            updates lessons-learned + SKILL files
```

### Human-in-the-Loop Pause Points

The pipeline pauses and waits for Jeff at these moments:

1. **Before Transcription** — speaker confirmation: agent presents derived speaker names
   from filenames; Jeff confirms or corrects.
2. **After Creative Context Agent** — discovery candidates presented for ingestion approval;
   act structure proposed and iterated until Jeff approves.
3. **During Edit Agent** — Jeff works collaboratively with the agent on the live HTML
   artifact across multiple rounds (Rough Cut → Discussion → Reduction → loop).
4. **After each FCPXML Agent run** — Jeff imports and watches the cut. He either approves
   (proceed to Skill Review) or appends notes to `review-notes.md` and re-launches Edit
   for another round.

### Multi-Round Iteration

The Edit Agent is built for indefinite iteration with the FCPXML Agent. Each round emits a
versioned `trimmed-quotes-v[N].json` and triggers a fresh FCPXML run. There is no fixed cap
on rounds — the project ends when the cut is right. Each round's output is preserved
on disk; previous versions are not overwritten.

When re-entering the Edit Agent for a new round, the agent reads:
- The full `tagged-quotes-v[N].json` (current version — all source material)
- The previous round's `trimmed-quotes-v[N-1].json` (what was selected last round)
- `handoffs/review-notes.md` (your notes from watching the FCPXML cut)
- `pipeline-state.json` (which versions are current and which are stale)

It does NOT receive the full conversation history from the previous session.

### Pipeline State Tracking

A single file at `handoffs/pipeline-state.json` (or `handoffs/[project-slug]/pipeline-state.json`
for multi-project SSDs) tracks the current version of each agent's output and the
dependency edges between them. Every agent reads this file on launch — it surfaces
stale-state warnings when an upstream agent has run since this agent last did. Every
agent writes to this file on emit, recording which upstream versions it consumed.

In Cowork today, stale-state warnings are surfaced to Jeff so he can decide pace and
order. In the n8n + Claude API build (Phase 4 of the storyboard-ops roadmap), the same
file becomes the orchestrator's work queue and the cascade automates. The skill is
identical in both worlds; only the orchestrator differs.

The schema:

```json
{
  "schema_version": 1,
  "project_slug": "international-institute",
  "last_updated": "2026-04-29T15:30:00Z",
  "agents": {
    "transcription":   {"current_version": 1, "outputs": ["transcription-summary-v1.md"], "last_run": "..."},
    "creative-context":{"current_version": 2, "outputs": ["creative-brief-summary-v2.md", "act-structure-v2.md"], "last_run": "..."},
    "fcpxml-params":   {"current_version": 1, "outputs": ["fcpxml-params-v1.md"], "last_run": "..."},
    "transcript":      {"alice-mupenzi": {"current_version": 2, "based_on": {"creative-context": 2}}, "..."},
    "synthesis":       {"current_version": 2, "based_on": {"transcript": "all-current"}, "last_run": "..."},
    "edit":            {"current_version": 3, "based_on": {"synthesis": 2}, "last_run": "..."},
    "fcpxml":          {"current_version": 2, "based_on": {"edit": 2, "fcpxml-params": 1}, "last_run": "..."}
  },
  "dependencies": {
    "transcription": [],
    "creative-context": [],
    "fcpxml-params": [],
    "transcript": ["creative-context"],
    "synthesis": ["transcript"],
    "edit": ["synthesis", "creative-context"],
    "fcpxml": ["edit", "fcpxml-params"]
  },
  "stale": []
}
```

---

## Folder Structure

### Skill Folder
The skill folder travels with every project. When setting up a new project, copy the
entire skill folder from your most recent completed project. This ensures every project
runs the most current version of the skill.

```
documentary-junior-editor/
├── SKILL.md                        ← this file — master index
├── SKILL-transcription.md          ← Transcription Agent instructions (v5.0, new)
├── SKILL-creative-context.md       ← Creative Context Agent instructions
├── SKILL-transcript.md             ← Transcript Agent instructions
├── SKILL-fcpxml-params.md          ← FCPXML Params Agent instructions
├── SKILL-synthesis.md              ← Synthesis Agent instructions
├── SKILL-edit.md                   ← Edit Agent instructions (selection + trimming + splitting)
├── SKILL-fcpxml.md                 ← FCPXML Agent instructions
├── SKILL-review.md                 ← Skill Review Agent instructions
├── CHANGELOG.md                    ← version history
├── secrets/                        ← git-crypt encrypted in storyboard-ops
│   └── assembly_ai.key             ← AssemblyAI key, read by Transcription Agent
├── design-samples/                 ← reference fixtures for skill implementation
│   └── single-clip/                ← Ben + Sample (Nanos 2026 Boston) — single-clip FCPXML reference
├── reference-examples/             ← knowledge base of completed projects
│   ├── alamo-auto-supply/         ← B2B Testimonial
│   │   ├── Final_Edit.txt
│   │   ├── lessons-learned.md
│   │   └── transcripts/
│   ├── eikenhout/                 ← B2B Testimonial
│   │   ├── Final_Edit.txt
│   │   ├── lessons-learned.md
│   │   └── transcripts/
│   ├── mars-electric/             ← B2B Testimonial
│   │   ├── Final_Edit.txt
│   │   ├── lessons-learned.md
│   │   └── transcripts/
│   ├── uneeda/                    ← B2B Testimonial
│   │   ├── Final_Edit.txt
│   │   ├── lessons-learned.md
│   │   └── transcripts/
│   ├── dr-pan-intro/              ← New Staff Introduction
│   │   ├── Final_Edit.txt
│   │   ├── lessons-learned.md
│   │   └── transcripts/
│   ├── hdg-coo-intro/             ← New Staff Introduction
│   │   ├── Final_Edit.txt
│   │   ├── lessons-learned.md
│   │   └── transcripts/
│   ├── facial-rejuvenation/       ← B2B Testimonial
│   │   ├── Final_Edit.txt
│   │   ├── lessons-learned.md
│   │   └── transcripts/
│   ├── pacer-center/              ← Nonprofit Fundraising
│   │   ├── Final_Edit.txt
│   │   ├── lessons-learned.md
│   │   └── transcripts/
│   └── crisis-nursery-testimonial/ ← Nonprofit Testimonial
│       ├── Final_Edit.txt
│       ├── lessons-learned.md
│       └── transcripts/
└── scripts/
    ├── extract_fcpxml.py
    ├── generate_fcpxml.py
    ├── generate_quotes.py
    ├── add_edit_tab.py
    └── quotes_viewer_template.jsx
```

### Project Folder
The project folder on the SSD is where agent handoff documents are saved. Each agent
reads from and writes to this folder.

```
[Project Name]/
├── documentary-junior-editor/      ← copy of skill folder for this project
├── transcripts/text/               ← raw interview transcripts (one per interview)
├── xml/                            ← source FCPXMLs with captions + generated paper cuts
├── graphics/                       ← titles, lower thirds, logos
├── handoffs/                       ← agent handoff documents (created during pipeline)
│   ├── pipeline-state.json         ← current versions + dependency edges + stale flags
│   ├── transcription-summary-v[N].md           ← Transcription Agent
│   ├── creative-brief-summary-v[N].md          ← Creative Context Agent
│   ├── act-structure-v[N].md                   ← Creative Context Agent (with narrative roadmaps)
│   ├── fcpxml-params-v[N].md                   ← FCPXML Params Agent (with per-interview clip_type)
│   ├── [speaker-slug]-tagged-quotes-v[N].json  ← Transcript Agent (per speaker, with segments[])
│   ├── [speaker-slug]-orphans-v[N].md          ← Transcript Agent (per speaker)
│   ├── [speaker-slug]-discards-v[N].md         ← Transcript Agent (per speaker)
│   ├── [speaker-slug]-summary-v[N].md          ← Transcript Agent (per speaker)
│   ├── tagged-quotes-v[N].json                 ← Synthesis Agent (merged, segments preserved)
│   ├── orphan-quotes-v[N].md                   ← Synthesis Agent (merged)
│   ├── discard-summary-v[N].md                 ← Synthesis Agent (merged)
│   ├── transcript-summary-v[N].md              ← Synthesis Agent (with narrative assessment)
│   ├── edit-handoff-v[N].md                    ← Edit Agent (structured handoff summary)
│   ├── trimmed-quotes-v[N].json                ← Edit Agent (timeline of entries with segments[])
│   ├── [project-slug]_quotes_view.html         ← Edit Agent (live artifact, final state on session end)
│   └── review-notes.md                         ← Jeff's notes after watching FCPXML cut (unversioned)
└── [FCP Library].fcpbundle         ← Final Cut Pro library
```

### Multi-Project Folders

A single client shoot sometimes produces multiple video projects that share the same
SSD folder — same FCP library, same transcripts, same source FCPXMLs. For example,
a shoot for Twin Cities Cosmetic Surgery produced both a "Dr. Pan Intro" and a
"Facial Rejuvenation Testimonial" from the same set of interviews.

When multiple video projects share a single SSD folder, use project-slug subfolders
inside `handoffs/` to keep each project's pipeline documents separate:

```
[Shared Folder Name]/
├── documentary-junior-editor/
├── transcripts/text/
├── xml/
├── handoffs/
│   ├── [project-slug-1]/           ← all handoffs for first video project
│   │   ├── creative-brief-summary.md
│   │   ├── act-structure.md
│   │   ├── tagged-quotes.json
│   │   ├── trimmed-quotes.json
│   │   ├── edit-handoff.md
│   │   ├── [project-slug-1]_quotes_view.html
│   │   ├── fcpxml-params.md
│   │   └── ...
│   └── [project-slug-2]/           ← all handoffs for second video project
│       ├── creative-brief-summary.md
│       ├── act-structure.md
│       └── ...
└── [FCP Library].fcpbundle
```

**How agents handle this:** When starting any session, the first agent (Creative Context)
asks Jeff which video project this session is for and establishes the project slug. All
handoff paths for that session use `handoffs/[project-slug]/` instead of `handoffs/`.
Downstream agents receive the project slug and use it for all reads and writes. The
project slug is set once per pipeline run and does not change.

**When to use subfolders vs. separate folders:** If the shoot produced interviews that
will only be used for one video, use a standard single-project folder. If the same
interviews may be used across multiple videos (different edits, different angles, intro
video + testimonial from the same shoot), use the multi-project subfolder structure.
The Creative Context Agent should ask Jeff at setup time if multiple projects are planned
from this material.

---

## Reference Examples — Knowledge Base

The `reference-examples/` folder contains completed projects that agents use as editorial
reference. Each project includes:

- **transcripts/** — the raw interview transcripts used on that project
- **Final_Edit.txt** — the finished edit transcript, showing which quotes were selected,
  how they were ordered, and how they were trimmed
- **lessons-learned.md** — written by the Skill Review Agent after the project completed.
  Captures editorial decisions, corrections Jeff made, new rules that emerged, and patterns
  specific to this project type.

### How Agents Use Reference Examples
- **Transcript Agent** — reads Final_Edit.txt examples to understand what "good quote
  selection" looks like for this type of project
- **Creative Context Agent** — reads act structures from similar past projects when
  proposing narrative structure
- **Edit Agent** — references Final_Edit.txt examples when recommending which quotes
  to select, how to order them, and how aggressively to trim
- **Skill Review Agent** — reads all lessons-learned.md files to understand the full
  history of editorial decisions before writing new lessons

Reference examples should be tagged by project type. When possible, agents filter for
examples of the same type as the current project.

### Growing the Knowledge Base
After every completed project, the Skill Review Agent automatically:
1. Adds a new folder to `reference-examples/` in the skill directory containing
   the transcripts, Final_Edit.txt, and lessons-learned.md for that project
2. Updates any SKILL files that need to change based on lessons learned
3. Updates CHANGELOG.md with a summary of what changed

The GitHub repo (storyboard-ops/skills/) is the single source of truth for the knowledge base.
After updates, commit and push to GitHub. When you copy the skill folder to a new project,
run `git pull` first to ensure you have the full knowledge base including all past projects —
regardless of which computer you are working on.

---

## Setting Up a New Project

Before starting a new editing session:

1. **Pull the skill from GitHub.** Run `git pull` in `~/Desktop/storyboard-ops` to ensure
   the latest skill files and knowledge base. Then copy the skill folder into the new
   project folder on your SSD:
   `storyboard-ops/skills/documentary-junior-editor` → `[Project SSD]/documentary-junior-editor/`.

   Always pull from the repo — never from a previous project folder. This ensures you
   always have the latest skill files regardless of which Mac you're on.

2. **One-time per Mac: ensure git-crypt is unlocked.** The `secrets/assembly_ai.key` file
   is git-crypt encrypted in `storyboard-ops`. Each Mac needs `git-crypt` installed
   (`brew install git-crypt`) and the master key imported once
   (`git-crypt unlock ~/path/to/master-key`). After that, `git pull` retrieves the file
   in cleartext form for the agent to read. If a fresh Mac hasn't been unlocked, the
   Transcription Agent fails with a clear message telling you what to do.

3. **Confirm required files are present** in the project folder. The Transcription Agent
   handles the audio-to-text path; the rest you provide:
   - `transcripts/audio/` — one audio file per interview subject (`.mp3`, `.wav`, `.m4a`,
     `.mov`, `.mp4`); the Transcription Agent will produce the matching .txt files.
     If you already have transcripts, drop them in `transcripts/text/` and the
     Transcription Agent skips files with matching .txt.
   - `XML/exports/` — one captioned `.fcpxml` per interview subject (full interview
     captions) plus one sample narrative XML (one clip per interview on its timeline).
   - **Optional but recommended:** Creative Launch meeting transcript or notes,
     interview guide, messaging framework. The Creative Context Agent's Phase 0
     Discovery searches Google Drive and Gmail for these automatically — you can also
     drop them into the project folder if discovery isn't connected.

4. **Start a Creative Context Agent session** in Cowork.
   - Point Cowork at the project folder on your SSD.
   - On launch, the Creative Context Agent checks for audio without transcripts.
     If found, it pauses and gives you the launch prompt for the Transcription Agent.
     Run that in a separate Cowork session, then return.
   - With transcripts present, Creative Context runs Phase 0 — Discovery (Drive + Gmail
     search for project context), then iterates with you on the act structure until
     approved.
   - All outputs are versioned (`creative-brief-summary-v[N].md`, `act-structure-v[N].md`)
     and tracked in `pipeline-state.json`.

5. **The pipeline cascades from there.** FCPXML Params Agent and one Transcript Agent per
   interview run in parallel. Synthesis Agent merges. Edit Agent and FCPXML Agent run as
   a multi-round loop until the cut is right. Skill Review Agent runs at the end to
   capture lessons and update the knowledge base.

   In Cowork today, each agent is a separate session — handoff documents and
   `pipeline-state.json` are the shared memory. In n8n + Claude API (Phase 4 of the
   storyboard-ops roadmap), the same `pipeline-state.json` becomes the orchestrator's
   work queue and the cascade automates.

---

## Running in Cowork vs n8n

This skill is designed to work in both environments:

**Cowork (current):** Each of the eight agents is a separate Cowork session. The
Transcription Agent runs first when audio is present. The Creative Context Agent then
runs Discovery + brief construction. After Creative Context, the FCPXML Params Agent and
each Transcript Agent (one per interview) run in parallel — these can be run in any
order since they're independent. Then Synthesis Agent merges. Edit Agent and FCPXML
Agent run as a multi-round loop until the cut is approved. Skill Review Agent runs at
the end. The project folder (with `pipeline-state.json` as the spine) is the shared
memory between sessions.

Every agent declares its required model in its SKILL frontmatter. Every handoff document
closes with a "Next agent + model + launch prompt" footer so you copy-paste the next
session's prompt and pick the right model from muscle memory.

**n8n + Claude API (Phase 4 build):** The pipeline runs automatically. n8n reads
`pipeline-state.json` as the work queue, calls agents via the Claude API with the model
declared in each SKILL frontmatter, runs Transcript Agents and the FCPXML Params Agent in
parallel, fans in at the Synthesis Agent, pauses at human-in-the-loop points, and
notifies Jeff via the dashboard. The SKILL files, handoff document structure, and
`pipeline-state.json` schema are identical — only the orchestration mechanism changes.

The v5.0 skills are backward-compatible with Cowork. The Cowork workflow serves as a
fallback if n8n has issues.

---

## Version History

See `CHANGELOG.md` for full version history.

Current version: 5.0 — April 2026

### v5.0 highlights (major)

- **Quotes are clay.** Source quotes decompose into segments; the paper cut is a timeline
  of entries, each composed of one or more source segments. New entries form when
  playback order diverges from source order or when segments come from multiple source
  quotes. Splitting is implicit. Cardinal Rule preserved verbatim; framing expanded.
- **New Transcription Agent at pipeline position 0.** Replaces the prompt-driven Step 0
  script invocation. Owns audio detection, speaker confirmation, format conversion,
  AssemblyAI calls with retry logic, output validation. Reads the API key from a
  git-crypt-encrypted file in `storyboard-ops`. Runs entirely in the Cowork sandbox.
- **Universal pipeline versioning.** Every handoff is `-v[N]` suffixed; no agent ever
  overwrites. `pipeline-state.json` tracks current versions and dependency edges across
  all eight agents. Stale-state warnings surface in Cowork; n8n consumes the same file
  as a work queue.
- **Edit Agent built for multi-round iteration.** Indefinite Rough Cut → Discussion →
  Reduction → FCPXML round → review → next round, with all rounds preserved on disk.
  Edit and FCPXML stay separate sessions to preserve the model split (Opus / Sonnet);
  better waypoint signaling reduces orchestration friction.
- **Live HTML artifact as Edit Agent work surface.** Created at session start, updated
  via `update_artifact` after every decision, bidirectional via `sendPrompt()`,
  auto-scrolls to current focus. Full quote text always inlined in chat on first
  reference. End-of-session, final state saved as `[project-slug]_quotes_view.html`.
  *(JSX template rewrite flagged as Phase 3 follow-up code change.)*
- **Wide rough cut + per-quote runtime recommendation.** Rough cut stays wide for
  visibility; each quote tagged `must-keep / probable-keep / probable-cut / optional`
  toward 2× target. Viewer toggles between full inventory and recommended-tight view.
- **Title-card-as-shortener pattern.** Promoted from incidental to a named editorial
  move in `SKILL-edit.md`. Trigger: content reads cleaner on screen than spoken.
- **Context-beat suggestions.** Edit Agent flags narrative gaps where external context
  (stat, date, framing) would land harder than spoken material. Agent doesn't research;
  Jeff fills in. Surfaces in `edit-handoff.md` with `(research needed)` tag.
- **Brief is starting points, not constraints.** Replaced "must stay / immovable / locked
  in" language with "currently planned to stay / load-bearing in current structure /
  tentatively committed" throughout the creative-brief-summary.
- **Creative Context Agent Phase 0 — Discovery.** Drive + Gmail searched at session
  start; candidates surfaced for Jeff's approval before ingestion. Falls back to manual
  upload if connectors aren't connected.
- **FCPXML Agent handles both multicam and single-clip footage.** Per-interview
  `clip_type` detection in Params Agent; branched generation logic in FCPXML Agent.
  Validation samples at `design-samples/single-clip/` (Ben + Sample from Nanos 2026
  Boston).
- **Every agent declares model in SKILL frontmatter; every handoff closes with a "Next
  agent + model + launch prompt" footer.** Single source of truth — Jeff reads it in
  Cowork today, n8n consumes it tomorrow.

### Reference example
- **International Institute of Minnesota** (Fund a Need 2026) — second `Nonprofit
  Fundraising` example after Pacer Center. Three speakers; final edit hand-refined in
  FCP from 20:47 rough cut to 5:12 fund-a-need pitch. Validates the runtime-recommendation
  layer, the title-card-as-shortener pattern, and the "brief is starting points" framing
  (three brief-locked beats were dropped in FCP).

### Known issues carried into v5.0

- **`scripts/transcribe.py` legacy key path** — `SKILL-transcription.md` documents the
  encrypted-key flow but the script still looks at `~/Desktop/storyboard-ops/file-api/.env`.
  Phase 3 follow-up code change.
- **`scripts/build_fcpxml.py` clip_type branching** — `SKILL-fcpxml.md` documents the
  multicam / single_clip code paths but the Python script supports only multicam.
  Phase 3 follow-up code change.
- **`scripts/quotes_viewer_template.jsx` v5.0 features** — `SKILL-edit.md` specifies
  bidirectional `sendPrompt()` buttons, segment-level reorder UI, status badges,
  source attribution per segment, runtime-recommendation toggle. Template still v4.0.1.
  Phase 3 follow-up code change.
- **FCPXML Params parser-format mismatch** carried forward from v4.0; documented in
  `SKILL-fcpxml-params.md`, `parse_params_md` permanent fix still pending.
- **FCPXML caption-matcher performance** workaround promoted to standard practice in
  `SKILL-fcpxml.md`; permanent fix to `find_quote_range` still pending.

## v4.0 — April 2026

### Edit Agent workflow reframe (major)
- **First pass is a rough cut, not a draft.** The Edit Agent's first pass
  prioritizes narrative integrity and logical progression over runtime. Whether
  the rough cut lands at 5 minutes or 12 minutes does not matter for this
  pass — the question is "is the story compelling?" Reduction to target runtime
  happens later, after review.
- **Three-phase Edit Agent workflow: Rough Cut → Discussion → Reduction.** The
  Discussion phase is now an explicit collaborative step in the Edit Agent's
  job, not an afterthought. The agent brings a proposal for what could come
  out and why, giving Jeff a reactable surface rather than cold pruning.

### Dual-mode viewer spec (SKILL-edit.md)
- The JSX/HTML viewer now renders with a **Review / Edit** toggle. Review mode
  shows the quotes as continuous narrative (speaker labels, act dividers, no
  trim controls) for reading the story. Edit mode retains the full interactive
  interface (trims, reorders, splits, interstitials). Default landing is
  Review mode — reading the narrative comes before cutting words.

### Rules promoted from practice (SKILL-edit.md)
- **Limited-entry supporting voice pattern** — single-protagonist + close-
  relation second voice that enters sparingly at deliberate beats, not
  evenly distributed.
- **Lead-with-vulnerability, close-with-authority placement** — when a
  subject has both personal vulnerability and earned present-day authority,
  open with vulnerability and save authority for the close rather than
  front-loading credentials.
- **Runtime-estimation calibration** — long-form emotional testimonials run
  roughly 25–30% longer than word-count math predicts. Estimate rough-cut
  length and target length as two separate numbers.

### Reference example
- **Crisis Nursery Testimonial** (Tyanna + TJ Bryant) — first `Nonprofit
  Testimonial` in the knowledge base; validates the single-protagonist +
  limited-entry supporting-voice pattern (TJ enters exactly three times).

### Known issues carried into v4.0
- **FCPXML Params parser-format mismatch** (SKILL-fcpxml-params.md) — OPEN.
  The documented handoff format and what `build_fcpxml.py` actually parses
  disagree; interim guidance instructs the Params Agent to produce both
  forms. Awaiting Jeff's call on which side to reconcile.
- **FCPXML caption-match performance on long interviews** (SKILL-fcpxml.md) —
  the fuzzy matcher can exceed the 45s shell timeout on interviews with
  ~700+ captions; narrowing per-quote using `startTC`/`endTC` (±15s) is a
  validated workaround.

## v3.5 — April 2026

Consolidated into v4.0 before release (version label superseded). See
`CHANGELOG.md` v4.0 entry for the full set of v3.5 material plus the workflow
reframe that tipped the release into a major version bump.

## v3.4 — April 2026
- Narrative Coherence Rule: paper cut must read as a coherent story; read-through
  required after every change; quote fragments evaluated in assembled context
- Viewer is the single source of truth: every editorial suggestion reflected in viewer
  before moving on; no chat/viewer drift
- Selection and trimming are simultaneous: first pass should be trimmed selects, not
  wide net followed by tightening
- Version management: versioned saves (v1, v2), viewer dropdown, matching FCPXML filenames
- Long interview handling: transcripts over ~45 min processed in segments
- Transcription as Step 0: documented in SKILL.md setup and cowork-session-guide
- Reference example: Pacer Center (first Nonprofit Fundraising project)

---

*This file is the entry point for the documentary-junior-editor skill. Always read it
first. Then read the specific agent SKILL file for the session you are starting.*
