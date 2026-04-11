# Documentary Junior Editor — Cowork Session Guide

## Overview

This guide walks through running the full documentary editing pipeline in Cowork sessions. Each agent runs as a separate Cowork session. Jeff drives every creative decision — the agents do the heavy lifting between decision points.

---

## Project Folder Structure

Before starting, confirm the project SSD has this structure:

```
[Project Name]/
  cache/
  client media/
  documentary-junior-editor/     ← copy latest from ~/Desktop/storyboard-ops/skills/
  exports/
  graphics/
  media/                         ← all raw footage (flat, no camera subfolders)
  music/
  transcripts/
    audio/                       ← exported .mp3 per interview subject
    text/                        ← transcripts land here (auto or manual)
  [Project Name].fcplib
```

### Pre-Pipeline Requirements

Before the editing pipeline can start, the Media Agent (or manual prep) must have completed:

1. **Footage ingested** to `media/` folder
2. **FCP library created** with Interview and B-roll events
3. **Multicams built** (one per interview subject, audio-synced)
4. **Audio exported** — one .mp3 per interview subject, saved to `transcripts/audio/`
5. **Captioned FCPXMLs exported** — one .xml per interview subject, saved to `Transcripts and XML files/` (used later by FCPXML Agent)
6. **Sample XML exported** — one per project (used later by FCPXML Agent)

---

## Pipeline Steps

### Step 0: Auto-Transcription

**What it does:** Sends each .mp3 in `transcripts/audio/` to AssemblyAI for transcription with speaker diarization. Saves formatted .txt transcripts to `transcripts/text/`. Skips any audio file that already has a matching .txt.

**First-time setup (once per machine):**
1. Install Python packages: `pip3 install assemblyai python-dotenv --break-system-packages --user`
2. The script automatically finds the API key from `~/Desktop/storyboard-ops/file-api/.env` on the Mac mini — no extra setup needed.

**How to run (from Terminal on the Mac mini):**

```bash
python3 "[SSD Path]/[Project Name]/documentary-junior-editor/scripts/transcribe.py" "[SSD Path]/[Project Name]"

# Example:
python3 "/Volumes/Pacer Center 2026/Pacer Center 2026/documentary-junior-editor/scripts/transcribe.py" "/Volumes/Pacer Center 2026/Pacer Center 2026"
```

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

> You are the Creative Context Agent. Read `documentary-junior-editor/SKILL-creative-context.md` and follow it exactly. The project folder is mounted — read all available documents (Creative Launch transcript, interview guide, interview transcripts in `transcripts/text/`, and any reference examples in `documentary-junior-editor/reference-examples/`). Then work with me to develop and approve a 3-act narrative structure. Save the approved structure to `handoffs/act-structure.md` and the creative brief to `handoffs/creative-brief-summary.md`.

**What happens:**
1. Agent reads all available project documents and transcripts
2. Agent proposes a 3-act narrative structure
3. Jeff and agent iterate until the structure is approved

**Outputs saved to `handoffs/`:**
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

*(Replace `[SPEAKER NAME]` with the actual speaker name, e.g., `Karen` or `Norma`)*

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

### Step 4: Edit Agent

**Skill file:** `SKILL-edit.md`
**Model:** Opus 4.6
**Session type:** Cowork — deeply collaborative with Jeff

This is the core creative session. Selection, trimming, and splitting happen here.

**Inputs:**
- `handoffs/tagged-quotes.json` (merged, from Step 3)
- `handoffs/act-structure.md`
- `handoffs/creative-brief-summary.md`
- `handoffs/transcript-summary.md` (with narrative assessment)
- Reference examples in `documentary-junior-editor/reference-examples/`

**Starter prompt — copy and paste into a new Cowork session:**

> You are the Edit Agent. Read `documentary-junior-editor/SKILL-edit.md` and follow it exactly. Read all handoff documents from `handoffs/` — act structure, creative brief summary, transcript summary, and the merged `tagged-quotes.json`. Also read the reference examples in `documentary-junior-editor/reference-examples/`. Load all quotes into the interactive JSX artifact (template at `documentary-junior-editor/scripts/quotes_viewer_template.jsx`), take a first pass at selection and ordering, then work with me through selection, trimming, and splitting until the paper cut is finalized. Run the Cardinal Rule verification before saving the final `handoffs/trimmed-quotes.json`.

**Re-entry prompt — if revisiting the edit after reviewing the FCPXML in FCP:**

> You are the Edit Agent. Read `documentary-junior-editor/SKILL-edit.md` and follow it exactly. This is a re-entry session. Read `handoffs/edit-session-handoff.md` for context from the previous session, then load the full `handoffs/tagged-quotes.json` into the interactive artifact. I want to make changes to the paper cut based on my review in Final Cut Pro.

**What happens:**
1. Agent loads all quotes into the interactive JSX artifact
2. Agent takes a first pass at selection and ordering
3. Jeff and agent iterate — selecting, deselecting, reordering, trimming, splitting
4. Paper cut is finalized
5. Cardinal Rule verification runs on all trimmed quotes

**Outputs saved to `handoffs/`:**
- `trimmed-quotes.json` — final paper cut with all editorial decisions
- `edit-session-handoff.md` — summary for re-entry if needed

**Done when:** Jeff approves the paper cut and the Cardinal Rule verification passes.

---

### Step 5: FCPXML Agent

**Skill file:** `SKILL-fcpxml.md` (+ `SKILL-fcpxml-params.md` for reference IDs)
**Model:** Sonnet 4.6
**Session type:** Cowork — mostly autonomous

**Inputs:**
- `handoffs/trimmed-quotes.json` (from Step 4)
- `handoffs/act-structure.md`
- `handoffs/fcpxml-params.md` (generated from sample XML — contains reference IDs)
- Captioned FCPXMLs (for timecode cross-reference)
- Sample XML (for format/ID reference)

**Starter prompt — copy and paste into a new Cowork session:**

> You are the FCPXML Agent. Read `documentary-junior-editor/SKILL-fcpxml-params.md` and follow it exactly. First, read the sample narrative XML from the `xml/` folder and extract the FCPXML parameters (media reference IDs, angle IDs, format info) for each speaker. Save the parameters to `handoffs/fcpxml-params.md`. Then read `handoffs/trimmed-quotes.json` and `handoffs/act-structure.md`, cross-reference timecodes against the captioned FCPXMLs, and generate an import-ready `.fcpxml` file. Save the output FCPXML to the project folder.

**What happens:**
1. Agent reads the paper cut and source XMLs
2. Generates an import-ready FCPXML
3. Notifies Jeff when the cut is ready to review in FCP

**Output:**
- Final `.fcpxml` file ready to import into Final Cut Pro

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

**This is the self-learning loop** — every completed project makes the skill smarter for the next one.

---

## Quick Reference

| Step | Agent | Model | Collaborative? | Key Output |
|------|-------|-------|----------------|------------|
| 0 | Auto-Transcription | — (script) | No | .txt transcripts |
| 1 | Creative Context | Opus 4.6 | Yes | act-structure.md |
| 2 | Transcript (×N) | Sonnet 4.6 | Light | per-speaker tagged quotes |
| 3 | Synthesis | Sonnet 4.6 | Light | merged tagged-quotes.json |
| 4 | Edit | Opus 4.6 | Yes — heavy | trimmed-quotes.json |
| 5 | FCPXML | Sonnet 4.6 | Light | .fcpxml file |
| 6 | Skill Review | Sonnet 4.6 | Light | updated skill knowledge |

---

## Troubleshooting

**Transcription fails:** Confirm the `assemblyai` and `python-dotenv` packages are installed (`pip3 install assemblyai python-dotenv --break-system-packages --user`). Confirm `~/Desktop/storyboard-ops/file-api/.env` exists with the AssemblyAI key. Check internet connection.

**Transcript Agent won't start:** Verify both `handoffs/act-structure.md` and `handoffs/creative-brief-summary.md` exist from Step 1.

**Synthesis Agent flags missing files:** Each speaker needs exactly four files in `handoffs/`. Go back to the Transcript Agent session for the flagged speaker and verify all files were saved.

**Edit Agent can't find quotes:** Confirm `handoffs/tagged-quotes.json` exists and is valid JSON (the merged output from the Synthesis Agent, not per-speaker files).

**FCPXML won't import into FCP:** Check that `fcpxml-params.md` was generated from the correct sample XML for this project. Reference IDs must match the FCP library.
