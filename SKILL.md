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
### Version 4.0 | April 2026

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

---

## The Pipeline

The editing workflow is divided into seven specialized agents. Each agent has its own skill
file, operates with a focused context window, and hands off structured output to the
project folder for the next agent to read. Jeff is surfaced only at creative decision points.

```
Creative Context Agent  →  act-structure.md (with roadmaps) + creative-brief-summary.md  ← Jeff approves
        ↓
┌───────────────────────────────────────────┐
│  Parallel fan-out                         │
│                                           │
│  FCPXML Params Agent  → fcpxml-params.md  │
│                                           │
│  Transcript Agent (×N) → per-speaker      │
│  (one per interview)     tagged quotes,   │
│                          orphans,         │
│                          discards,        │
│                          summary          │
└───────────────────────────────────────────┘
        ↓ (fan-in: wait for all)
Synthesis Agent          →  merged tagged-quotes.json, orphan-quotes.md,
                            discard-summary.md, transcript-summary.md
        ↓
Edit Agent               →  trimmed-quotes.json + HTML viewer + artifact  ← Jeff selects, trims, splits, interstitials
        ↓
FCPXML Agent             →  [ProjectName]_rough_cut.fcpxml                ← Jeff reviews in FCP
        ↓
[Jeff approves OR loops back to Edit Agent with review notes]
        ↓
Skill Review Agent       →  updates lessons-learned.md + SKILL files
```

### Human-in-the-Loop Pause Points
The pipeline pauses and waits for Jeff at these moments:
1. **After Creative Context Agent** — act structure proposed and iterated until Jeff approves
2. **During Edit Agent** — Jeff works collaboratively with the agent on selection, trimming, and splitting until the paper cut is finalized
3. **After FCPXML Agent** — Jeff imports and watches the cut, approves or returns to Edit Agent

### Loop-Back Support
After watching the FCPXML cut, Jeff may want to return to the Edit Agent to:
- Add quotes that were not selected but should have been
- Remove quotes that are no longer needed
- Adjust ordering, trims, or splits based on how the cut felt

When looping back, the Edit Agent receives:
- The original tagged-quotes.json (all quotes, nothing filtered)
- The previous trimmed-quotes.json (what was selected, trimmed, and split last time)
- Jeff's review notes
It does NOT receive the full conversation history from the previous session.

---

## Folder Structure

### Skill Folder
The skill folder travels with every project. When setting up a new project, copy the
entire skill folder from your most recent completed project. This ensures every project
runs the most current version of the skill.

```
documentary-junior-editor/
├── SKILL.md                        ← this file — master index
├── SKILL-creative-context.md       ← Creative Context Agent instructions
├── SKILL-transcript.md             ← Transcript Agent instructions
├── SKILL-fcpxml-params.md          ← FCPXML Params Agent instructions
├── SKILL-synthesis.md              ← Synthesis Agent instructions
├── SKILL-edit.md                   ← Edit Agent instructions (selection + trimming + splitting)
├── SKILL-fcpxml.md                 ← FCPXML Agent instructions
├── SKILL-review.md                 ← Skill Review Agent instructions
├── CHANGELOG.md                    ← version history
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
│   ├── creative-brief-summary.md   ← Creative Context Agent
│   ├── act-structure.md            ← Creative Context Agent (with narrative roadmaps)
│   ├── fcpxml-params.md            ← FCPXML Params Agent
│   ├── [speaker-slug]-tagged-quotes.json  ← Transcript Agent (per speaker)
│   ├── [speaker-slug]-orphans.md          ← Transcript Agent (per speaker)
│   ├── [speaker-slug]-discards.md         ← Transcript Agent (per speaker)
│   ├── [speaker-slug]-summary.md          ← Transcript Agent (per speaker)
│   ├── tagged-quotes.json          ← Synthesis Agent (merged from all speakers)
│   ├── orphan-quotes.md            ← Synthesis Agent (merged)
│   ├── discard-summary.md          ← Synthesis Agent (merged)
│   ├── transcript-summary.md       ← Synthesis Agent (with narrative assessment)
│   ├── edit-handoff.md             ← Edit Agent (structured handoff summary)
│   ├── trimmed-quotes.json         ← Edit Agent
│   ├── [project-slug]_quotes_view.html  ← Edit Agent (final-state HTML viewer)
│   └── review-notes.md             ← Jeff's notes after watching FCPXML cut
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

1. **Copy the skill folder from the GitHub repo** to the new project folder on your SSD.
   Run `git pull` in `storyboard-ops` first, then copy from:
   `storyboard-ops/skills/documentary-junior-editor`

   Always pull from the repo — never from a previous project folder on your SSD.
   This ensures you always have the most current skill files and the full knowledge base,
   regardless of which computer you are working on.

2. **Transcribe interviews (Step 0).** If `transcripts/text/` is empty but
   `transcripts/audio/` has .mp3 files, run the auto-transcription step before
   proceeding. See the cowork-session-guide.md Step 0 for the starter prompt and
   instructions. The script (`scripts/transcribe.py`) sends each audio file to
   AssemblyAI and saves formatted text transcripts to `transcripts/text/`.

3. **Confirm required files are present** in the project folder:
   - `transcripts/text/` — one transcript per interview subject
   - `xml/` — one captioned .xml per interview subject (full interview captions)
   - `xml/` — one sample narrative XML (one clip per interview on its timeline)

   If any of these are missing, do not start the pipeline. Flag what's missing and wait.

3. **Gather project documents** into the project folder before starting the first session.
   The following should be gathered into the project folder on your SSD:
   - Creative Launch meeting transcript
   - Interview guide + messaging framework (combined document)
   - All raw interview transcripts

4. **Start a Creative Context Agent session** in Cowork:
   - Point Cowork at the project folder on your SSD
   - The Creative Context Agent reads `SKILL-creative-context.md`
   - Provide any additional documents or past video samples when prompted
   - Work with the agent until the act structure is approved
   - The agent saves its outputs to the `handoffs/` folder

5. **After the Creative Context Agent completes,** the pipeline runs the FCPXML Params
   Agent and one Transcript Agent per interview subject in parallel, followed by the
   Synthesis Agent to merge outputs. Then Edit Agent, FCPXML Agent, and Skill Review
   Agent run in sequence. In Cowork, each agent is a separate session. In n8n, the
   pipeline handles sequencing automatically.

---

## Running in Cowork vs n8n

This skill is designed to work in both environments:

**Cowork (current):** Each agent is a separate Cowork session. After the Creative Context
Agent, run the FCPXML Params Agent session and each Transcript Agent session (one per
interview) — these can be run in any order since they are independent. Then run the
Synthesis Agent session, followed by Edit Agent, FCPXML Agent, and Skill Review Agent
sessions in sequence. The project folder is the shared memory between sessions.

**n8n + Claude API (Phase 4 build):** The pipeline runs automatically. n8n calls agents
via the Claude API, runs the FCPXML Params Agent and Transcript Agents in parallel,
fans in at the Synthesis Agent, pauses at human-in-the-loop points, and notifies Jeff
via the dashboard. The SKILL files and handoff document structure are identical — only
the orchestration mechanism changes.

The updated skills are backward-compatible with Cowork. The Cowork workflow serves as a
fallback if n8n has issues.

---

## Version History

See `CHANGELOG.md` for full version history.

Current version: 4.0 — April 2026

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
