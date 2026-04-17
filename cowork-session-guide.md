# Documentary Junior Editor — Cowork Session Guide

## Overview

This guide walks through running the full documentary editing pipeline in Cowork sessions. Each agent runs as a separate Cowork session. Jeff drives every creative decision — the agents do the heavy lifting between decision points.

---

## Before You Start: Confirm the Skill Is Up to Date

The `documentary-junior-editor` skill evolves between projects — the v4.0 release that introduced the Rough Cut → Discussion → Reduction workflow is a recent example. Before launching any new project (or any new session within an active project), confirm the local copy of `documentary-junior-editor/` matches the latest on GitHub. If it doesn't, pull first.

The repo lives at **github.com/SB-Jeff/documentary-junior-editor** and is normally cloned to two places on a working Mac:

- `~/Desktop/documentary-junior-editor/` — canonical machine-local copy (SSH remote)
- `[Project SSD]/documentary-junior-editor/` — project-folder copy that travels with the SSD

Whichever copy the new Cowork session will read from, make sure it's at the latest commit before launching the agent.

**Freshness check (run from the `documentary-junior-editor/` folder you're about to use):**

```bash
git fetch origin
git status                                     # expect "up to date with 'origin/main'"
git log --oneline origin/main..main            # commits you have that origin doesn't (should be empty)
git log --oneline main..origin/main            # commits origin has that you don't (should be empty)
```

If origin has commits you don't have locally, pull them:

```bash
git pull
```

If your local copy has uncommitted changes you want to keep first, see [After Session Review](#after-session-review-commit-skill-updates-back-to-github) at the end of this guide.

**Multi-project SSDs:** if a single SSD will host more than one video deliverable (e.g., a main testimonial and a tribute reel), each project's pipeline writes to its own `handoffs/[project-slug]/` subfolder rather than flat `handoffs/`. Establish the slug at the Creative Context phase (Step 1) and reuse it in every downstream agent's starter prompt.

---

## Project Folder Structure

Before starting, confirm the project SSD has this structure:

```
[Project Name]/
  cache/
  client media/
  documentary-junior-editor/     ← cloned from github.com/SB-Jeff/documentary-junior-editor (see "Before You Start" above)
  exports/
  graphics/
  handoffs/                      ← single project: write here directly
                                   multi-project SSD: use handoffs/[project-slug]/
  media/                         ← all raw footage (flat, no camera subfolders)
  music/
  transcripts/
    audio/                       ← exported .mp3 per interview subject
    text/                        ← transcripts land here (auto or manual)
  XML/
    exports/                     ← captioned source FCPXMLs (one per speaker) + sample XML
    imports/                     ← generated rough-cut FCPXMLs land here
  [Project Name].fcpbundle
```

### Pre-Pipeline Requirements

Before the editing pipeline can start, the Media Agent (or manual prep) must have completed:

1. **Footage ingested** to `media/` folder
2. **FCP library created** with Interview and B-roll events
3. **Multicams built** (one per interview subject, audio-synced)
4. **Audio exported** — one .mp3 per interview subject, saved to `transcripts/audio/`
5. **Captioned FCPXMLs exported** — one .fcpxmld per interview subject, saved to `XML/exports/` (used later by FCPXML Agent)
6. **Sample XML exported** — one per project, saved to `XML/exports/` (used later by FCPXML Agent for format/ID reference)

---

## Pipeline Steps

### Step 0: Auto-Transcription

**What it does:** Sends each .mp3 in `transcripts/audio/` to AssemblyAI for transcription with speaker diarization. Saves formatted .txt transcripts to `transcripts/text/`. Skips any audio file that already has a matching .txt.

**Starter prompt — copy and paste into a new Cowork session:**

> Transcribe the interview audio files for this project. The audio files are in `transcripts/audio/` and the transcripts should be saved to `transcripts/text/`. Use the transcription script at `documentary-junior-editor/scripts/transcribe.py`. Before running it: (1) install the required Python packages if not already installed (`pip3 install assemblyai python-dotenv --break-system-packages --user`), (2) locate the AssemblyAI API key — check `~/Desktop/storyboard-ops/file-api/.env` first, then check for a `.env` file in `documentary-junior-editor/`. Run the script against the project folder, monitor for errors, and verify that one .txt file was created per .mp3 in `transcripts/text/`. Report the speaker count and utterance count for each transcript when done.

**First-time setup notes (the starter prompt handles this, but for reference):**
1. Python packages needed: `assemblyai` and `python-dotenv`
2. The script searches for the API key in multiple locations automatically:
   - `documentary-junior-editor/.env` (project-local)
   - `~/Desktop/storyboard-ops/file-api/.env` (repo — Mac mini, Mac Studio, MacBook Pro)
3. If neither location has the key, set it explicitly: `ASSEMBLYAI_API_KEY=your_key`

**What to check when it's done:**
- One .txt file per .mp3 in `transcripts/text/`
- Open each transcript and spot-check speaker labels and timestamps
- Flag any interviews with audio issues before proceeding

---

### Step 1: Creative Context Agent

**Skill file:** `SKILL-creative-context.md`
**Model:** Opus 4.6
**Session type:** Cowork — collaborative with Jeff

**Inputs needed in project folder:**
- Interview transcripts in `transcripts/text/`
- Creative Launch transcript or notes (if available — Jeff can provide context conversationally if not)
- Interview guide (if available)

**Starter prompt — copy and paste into a new Cowork session:**

> You are the Creative Context Agent. Read `documentary-junior-editor/SKILL-creative-context.md` and follow it exactly. The project folder is mounted — read all available documents (Creative Launch transcript, interview guide, interview transcripts in `transcripts/text/`, and any reference examples in `documentary-junior-editor/reference-examples/`). Then work with me to develop and approve a 3-act narrative structure. If this SSD already hosts another project under `handoffs/`, establish the project slug for this deliverable up front and write all outputs to `handoffs/[project-slug]/` instead of flat `handoffs/`. Save the approved structure to `act-structure.md` and the creative brief to `creative-brief-summary.md`.

**What happens:**
1. Agent reads all available project documents and transcripts
2. Agent confirms whether the SSD is single-project or multi-project, and establishes the project slug if needed
3. Agent proposes a 3-act narrative structure
4. Jeff and agent iterate until the structure is approved

**Outputs saved to `handoffs/` (or `handoffs/[project-slug]/` for multi-project SSDs):**
- `act-structure.md` — Jeff-approved act labels and narrative roadmaps
- `creative-brief-summary.md` — editorial context and priorities

**Done when:** Jeff has approved the act structure and both handoff files are saved.

---

### Step 2: Transcript Agent (one session per interview subject)

**Skill file:** `SKILL-transcript.md`
**Model:** Sonnet 4.6
**Session type:** Cowork — runs per speaker, can run in parallel

Run one Cowork session per interview subject. Each session processes only its assigned transcript.

**Inputs:**
- `handoffs/act-structure.md` (from Step 1)
- `handoffs/creative-brief-summary.md` (from Step 1)
- One transcript from `transcripts/text/`

**Starter prompt — copy and paste into a new Cowork session (one per speaker):**

> You are the Transcript Agent. Read `documentary-junior-editor/SKILL-transcript.md` and follow it exactly. Your assigned interview is `transcripts/text/[SPEAKER NAME].txt`. Read `handoffs/act-structure.md` and `handoffs/creative-brief-summary.md` for context, then read the reference examples in `documentary-junior-editor/reference-examples/`. Catalog every usable quote from the assigned transcript — tagged by act label, verbatim, with rationale. Save all four required output files to `handoffs/`: tagged quotes JSON, orphans, discards, and content summary. Verify all four files exist on disk before reporting completion.

*(Replace `[SPEAKER NAME]` with the actual speaker name. For multi-project SSDs, replace `handoffs/` with `handoffs/[project-slug]/` throughout.)*

**What happens:**
1. Agent reads the approved act structure and its assigned transcript
2. Catalogs every usable quote — tagged by act label, verbatim, with rationale
3. Flags orphan quotes that don't fit any act
4. Summarizes what was excluded and why

**Outputs saved to `handoffs/` (four files per speaker):**
- `[speaker-slug]-tagged-quotes.json`
- `[speaker-slug]-orphans.md`
- `[speaker-slug]-discards.md`
- `[speaker-slug]-summary.md`

**Done when:** All four files per speaker are verified on disk. Wait for ALL speakers to complete before moving to Step 3.

---

### Step 3: Synthesis Agent

**Skill file:** `SKILL-synthesis.md`
**Model:** Sonnet 4.6
**Session type:** Cowork — mostly autonomous, surfaces cross-interview insights

**Inputs:**
- All per-speaker outputs from Step 2 (`handoffs/*-tagged-quotes.json`, etc.)
- `handoffs/act-structure.md`
- `handoffs/creative-brief-summary.md`

**Starter prompt — copy and paste into a new Cowork session:**

> You are the Synthesis Agent. Read `documentary-junior-editor/SKILL-synthesis.md` and follow it exactly. All per-speaker Transcript Agent sessions are complete. Discover all per-speaker files in `handoffs/`, validate that each speaker has all four required files, then merge them into combined handoff documents. Produce the cross-interview narrative assessment. Save all merged outputs to `handoffs/`: `tagged-quotes.json`, `orphan-quotes.md`, `discard-summary.md`, and `transcript-summary.md`.

**What happens:**
1. Validates that all per-speaker files are present (four files per speaker)
2. Merges per-speaker tagged quotes into a single renumbered list
3. Merges orphan lists, discard summaries, and content summaries
4. Produces a cross-interview narrative assessment — patterns, redundancies, and opportunities that only become visible when all interviews are seen together

**Outputs saved to `handoffs/`:**
- `tagged-quotes.json` — merged, renumbered across all speakers
- `orphan-quotes.md` — combined orphans
- `discard-summary.md` — combined discards
- `transcript-summary.md` — combined summary with narrative assessment

**Done when:** All merged files are saved. Jeff reviews the narrative assessment before proceeding.

---

### Step 4: Edit Agent — Rough Cut → Discussion → Reduction

**Skill file:** `SKILL-edit.md` (v4.0)
**Model:** Opus 4.6
**Session type:** Cowork — deeply collaborative with Jeff

This is the core creative session. As of v4.0, the Edit Agent runs in **three explicit phases** that Jeff and the agent move through together:

1. **Rough Cut.** First-pass selection that includes every quote that plausibly earns its place. Expect the rough cut to land at 1.5×–2× the target runtime — that's the design, not a failure. A rough cut that lands at target means quotes got missed.
2. **Discussion.** Collaborative review of the rough cut. The agent brings a proposal — which beats it would cut first if forced to reduce, which are load-bearing, which are uncertain, and why — so Jeff has a reactable surface. The viewer's **Review mode** is the primary surface here. The question is "does this tell the story?"
3. **Reduction.** Targeted trimming, splitting, and reordering against the agreed target runtime, informed by the Discussion. The viewer's **Edit mode** is the primary surface here. The question shifts to "which words come out?"

The interactive viewer that the agent builds (template at `documentary-junior-editor/scripts/quotes_viewer_template.jsx`) supports both modes via a toggle at the top — Review mode renders selected quotes as continuous narrative with no controls; Edit mode is the full interactive interface with trim controls, drag handles, splits, and interstitial placement. Both modes read from the same data block, so changes in one reflect in the other immediately.

**Inputs:**
- `handoffs/tagged-quotes.json` (merged, from Step 3)
- `handoffs/act-structure.md`
- `handoffs/creative-brief-summary.md`
- `handoffs/transcript-summary.md` (with narrative assessment)
- Reference examples in `documentary-junior-editor/reference-examples/`

**Starter prompt — copy and paste into a new Cowork session:**

> You are the Edit Agent. Read `documentary-junior-editor/SKILL-edit.md` (v4.0) and follow it exactly. Read all handoff documents from `handoffs/` — act structure, creative brief summary, transcript summary, and the merged `tagged-quotes.json`. Also read the reference examples in `documentary-junior-editor/reference-examples/`. Build the interactive JSX artifact (template at `documentary-junior-editor/scripts/quotes_viewer_template.jsx`) with Review/Edit mode toggle, default landing on Review. Then take us through the three phases — Rough Cut (over-inclusive first pass, no runtime gating), Discussion (collaborative review with a proposal of what to cut first), and Reduction (targeted trim against agreed runtime). Run the Cardinal Rule verification before saving the final outputs. Save: `handoffs/edit-handoff.md`, `handoffs/trimmed-quotes.json`, and `handoffs/[project-slug]_quotes_view.html`.

**Re-entry prompt — if revisiting the edit after reviewing the FCPXML in FCP:**

> You are the Edit Agent. Read `documentary-junior-editor/SKILL-edit.md` and follow it exactly. This is a re-entry session. Read `handoffs/edit-handoff.md` for context from the previous session and `handoffs/review-notes.md` for my notes from watching the FCPXML cut, then load the full `handoffs/tagged-quotes.json` into the interactive artifact. I want to make changes to the paper cut based on my review in Final Cut Pro.

**What happens:**
1. Agent loads all quotes into the interactive JSX artifact (with Review/Edit toggle)
2. **Rough Cut phase:** agent produces an over-inclusive first pass — every quote that plausibly belongs, no runtime gating
3. **Discussion phase:** Jeff reads the rough cut in Review mode; agent surfaces what it would cut first and why
4. **Reduction phase:** agent and Jeff trim, split, reorder, and deselect in Edit mode against the agreed target runtime
5. Cardinal Rule verification runs on all trimmed quotes before save

**Outputs saved to `handoffs/` (three files):**
- `edit-handoff.md` — structured handoff for the FCPXML Agent (paper cut state, notes, key files)
- `trimmed-quotes.json` — final paper cut with all editorial decisions
- `[project-slug]_quotes_view.html` — self-contained HTML viewer capturing the final state

**Done when:** Jeff approves the paper cut, the Cardinal Rule verification passes, and all three output files are saved.

---

### Step 5: FCPXML Agent

**Skill file:** `SKILL-fcpxml.md` (+ `SKILL-fcpxml-params.md` for reference IDs)
**Model:** Sonnet 4.6
**Session type:** Cowork — mostly autonomous

**Inputs:**
- `handoffs/trimmed-quotes.json` (from Step 4)
- `handoffs/edit-handoff.md` (from Step 4)
- `handoffs/act-structure.md`
- `handoffs/fcpxml-params.md` (generated from sample XML — contains reference IDs)
- Captioned FCPXMLs in `XML/exports/` (for timecode cross-reference)
- Sample XML in `XML/exports/` (for format/ID reference)

**Starter prompt — copy and paste into a new Cowork session:**

> You are the FCPXML Agent. Read `documentary-junior-editor/SKILL-fcpxml-params.md` and follow it exactly. First, read the sample narrative XML from `XML/exports/` and extract the FCPXML parameters (media reference IDs, angle IDs, format info) for each speaker. Save the parameters to `handoffs/fcpxml-params.md`. Then read `handoffs/trimmed-quotes.json`, `handoffs/edit-handoff.md`, and `handoffs/act-structure.md`, cross-reference timecodes against the captioned FCPXMLs, and generate an import-ready `.fcpxml` file. Save the output to `XML/imports/[project-slug]_rough_cut.fcpxml` (match the naming convention in `edit-handoff.md` if it specifies one).

**What happens:**
1. Agent reads the paper cut and source XMLs
2. Generates an import-ready FCPXML
3. Notifies Jeff when the cut is ready to review in FCP

**Output:**
- Final `.fcpxml` file in `XML/imports/`, ready to import into Final Cut Pro

**Done when:** Jeff imports the FCPXML into FCP and confirms it loads correctly.

---

### Step 6: Skill Review Agent (post-project)

**Skill file:** `SKILL-review.md`
**Model:** Sonnet 4.6
**Session type:** Cowork — runs after the project is complete

**Starter prompt — copy and paste into a new Cowork session:**

> You are the Skill Review Agent. Read `documentary-junior-editor/SKILL-review.md` and follow it exactly. This project is complete. Review the handoff files in `handoffs/`, the final edit output, and any notes I share about what worked and what didn't. Extract editorial patterns and lessons learned. Create a `Final_Edit.txt` and `lessons-learned.md` in a new folder under `documentary-junior-editor/reference-examples/[project-name]/`, and copy the raw transcripts there too. If any patterns should update the main skill files, propose the changes for my review.

**What happens:**
1. Reviews session logs from all pipeline steps
2. Extracts editorial patterns and lessons learned
3. Updates reference examples and knowledge base in the skill folder
4. Proposes changes to SKILL files and CHANGELOG.md if patterns warrant it

**This is the self-learning loop** — every completed project makes the skill smarter for the next one. **Don't skip the commit step that follows** (see [After Session Review](#after-session-review-commit-skill-updates-back-to-github) below) — without it, the lessons stay trapped on whichever machine ran the review.

---

## Quick Reference

| Step | Agent | Model | Collaborative? | Key Output |
|------|-------|-------|----------------|------------|
| 0 | Auto-Transcription | — (script) | No | .txt transcripts |
| 1 | Creative Context | Opus 4.6 | Yes | act-structure.md |
| 2 | Transcript (×N) | Sonnet 4.6 | Light | per-speaker tagged quotes |
| 3 | Synthesis | Sonnet 4.6 | Light | merged tagged-quotes.json |
| 4 | Edit | Opus 4.6 | Yes — heavy (3 phases) | trimmed-quotes.json + edit-handoff.md + HTML viewer |
| 5 | FCPXML | Sonnet 4.6 | Light | .fcpxml file |
| 6 | Skill Review | Sonnet 4.6 | Light | updated skill knowledge |

---

## After Session Review: Commit Skill Updates Back to GitHub

The Skill Review Agent (Step 6) often produces changes to skill files, reference examples, or `CHANGELOG.md`. **These changes need to be committed back to GitHub** so the next project — and any other machine you run on — picks them up automatically via the freshness check at the start of the next session.

If you skip this step, the lessons learned from this project stay trapped on whichever machine ran the review. The next project's agent will read stale skill files and make the same mistakes again.

From the `documentary-junior-editor/` folder where the review ran:

```bash
git status                                      # see what changed
git diff CHANGELOG.md SKILL*.md                 # review the SKILL/changelog edits
git add CHANGELOG.md SKILL*.md reference-examples/[project-name]/
git commit -m "vX.Y: brief description of what changed"
git push
```

If you're committing from the SSD copy and `git fetch` errors with `bad object refs/Icon?`, the SSD's `.git/` has macOS Finder icon artifacts in it. Clean them up first:

```bash
find .git -name 'Icon?' -delete
```

(If `find` complains about permissions, prefix with `chflags -R nouchg .git/`.)

After pushing, on the **other** machine where this repo is cloned, pull to bring it in sync:

```bash
cd ~/Desktop/documentary-junior-editor   # or whichever copy didn't run the review
git pull
```

---

## Troubleshooting

**Transcription fails:** Confirm the `assemblyai` and `python-dotenv` packages are installed (`pip3 install assemblyai python-dotenv --break-system-packages --user`). Confirm `~/Desktop/storyboard-ops/file-api/.env` exists with the AssemblyAI key. Check internet connection.

**Transcript Agent won't start:** Verify both `handoffs/act-structure.md` and `handoffs/creative-brief-summary.md` exist from Step 1. (For multi-project SSDs: check `handoffs/[project-slug]/`.)

**Synthesis Agent flags missing files:** Each speaker needs exactly four files in `handoffs/`. Go back to the Transcript Agent session for the flagged speaker and verify all files were saved.

**Edit Agent can't find quotes:** Confirm `handoffs/tagged-quotes.json` exists and is valid JSON (the merged output from the Synthesis Agent, not per-speaker files).

**Edit Agent's first pass is too short / hits target on first try:** The agent is treating the first pass as a draft instead of a rough cut. Remind it of the v4.0 three-phase workflow — Rough Cut should run 1.5×–2× target. Reduction is a separate, later phase.

**Viewer doesn't show the Review/Edit toggle:** The agent built an old-style viewer. Have it re-read `SKILL-edit.md` (v4.0+) and rebuild — the dual-mode toggle is required as of v4.0.

**FCPXML won't import into FCP:** Check that `fcpxml-params.md` was generated from the correct sample XML for this project. Reference IDs must match the FCP library.

**`git fetch` fails on the SSD with `bad object refs/Icon?`:** Finder icon artifacts in `.git/`. See the cleanup snippet in [After Session Review](#after-session-review-commit-skill-updates-back-to-github).
