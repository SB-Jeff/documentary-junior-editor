# Documentary Junior Editor — Cowork Session Guide
### Version 5.2 | May 2026

## Overview

This guide walks through running the full documentary editing pipeline in Cowork sessions. Each agent runs as a separate Cowork session. Jeff drives every creative decision — the agents do the heavy lifting between decision points.

The pipeline has eight agents. Each agent declares its required model in its SKILL frontmatter. Every handoff document closes with a "Next agent + model + launch prompt" footer so transitions between sessions are paste-and-pick rather than reconstructed from memory.

---

## Before You Start: Confirm the Skill Is Up to Date

The `documentary-junior-editor` skill evolves between projects — v5.1 (host-side launcher, .env replacing git-crypt, Full Disk Access prerequisite) is the most recent example. Before launching any new project (or any new session within an active project), confirm the local copy of `documentary-junior-editor/` matches the latest on GitHub. If it doesn't, pull first.

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

## One-Time Per-Machine Setup

Two one-time setup steps per Mac. After these are done, future projects just work.

### 1. Grant Claude Full Disk Access

Cowork's Bash sandbox bind-mounts your project folder into a Linux VM. macOS blocks
this for external SSDs unless the parent app has Full Disk Access. Without this, you
get cryptic `Could not open source directory` errors and every transcription session
falls back to host-side Terminal.

- Open **System Settings → Privacy & Security → Full Disk Access**.
- Click **+** and add **Claude** from `/Applications/`.
- Toggle Claude ON.
- Quit Claude entirely (Cmd+Q), then relaunch.

Verify by running `ls /sessions/*/mnt/` from the Bash tool in a Cowork session — your
connected SSD folder should appear. If you see only `outputs/`, Full Disk Access
didn't take — check that you actually quit and relaunched Claude.

### 2. Create `documentary-junior-editor/.env`

The Transcription Agent reads `ASSEMBLYAI_API_KEY` from
`documentary-junior-editor/.env` via python-dotenv. The file is gitignored.

```bash
echo 'ASSEMBLYAI_API_KEY=<your-key-here>' \
  > ~/Desktop/documentary-junior-editor/.env
```

Substitute `<your-key-here>` with the AssemblyAI key from
https://www.assemblyai.com/app/account.

When you copy the skill folder onto a project SSD, the `.env` travels with it. If
you start fresh from a `git clone` (which does NOT include the gitignored `.env`),
you'll need to recreate the `.env` once on that copy.

**You only do this once per machine.** It's not part of the per-project setup.

### Deprecated: `secrets/assembly_ai.key` + git-crypt

v5.0 used a git-crypt-encrypted key file in `secrets/assembly_ai.key`. v5.1 replaces
this with the `.env` flow above. The legacy file can be deleted on the next Skill
Review pass. If you encounter older docs referencing `git-crypt unlock`, ignore them
— `.env` is the supported path.

---

## Project Folder Structure

**Hard requirement: project SSD volume names must not contain spaces or
special characters** (`& ; : ' " < > | <space>`). The Cowork sandbox uses
virtiofs to bind-mount the SSD, and those characters break the mount.
Rename the volume before starting if needed (e.g., `TCCS Dr Pan &
Testimonials ` → `TCCS_2026`). This is a hard requirement, not a
recovery step — sessions started on a badly-named SSD will need to be
restarted after rename.

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
                                   pipeline-state.json lives here
  media/                         ← all raw footage (flat, no camera subfolders)
  music/
  transcripts/
    audio/                       ← exported audio per interview subject (.mp3, .wav, .m4a, .mov, .mp4)
    text/                        ← transcripts land here (Transcription Agent fills this in)
  XML/
    exports/                     ← captioned source FCPXMLs (one per speaker) + sample XML
    imports/                     ← generated rough-cut FCPXMLs land here
  [Project Name].fcpbundle
```

### Pre-Pipeline Requirements

Before the editing pipeline can start, the Media Agent (or manual prep) must have completed:

1. **Footage ingested** to `media/` folder
2. **FCP library created** with Interview and B-roll events
3. **Multicams built** (one per interview subject, audio-synced) — *or single-clip interviews where multicams aren't needed; the pipeline handles both shapes*
4. **Audio exported** — one audio file per interview subject in `transcripts/audio/`
5. **Captioned FCPXMLs exported** — one .fcpxmld per interview subject, saved to `XML/exports/`
6. **Sample XML exported** — one per project, saved to `XML/exports/` (FCPXML Params Agent reads this for format/ID reference and clip_type detection)

---

## Pipeline Steps

### Step 0: Transcription Agent

**Skill file:** `SKILL-transcription.md`
**Model:** Sonnet 4.6
**Session type:** Cowork — runs first when audio is present, no transcripts on disk

**What it does:** Detects audio files in `transcripts/audio/`, derives speaker names from filenames and confirms with Jeff, then presents a single bash command pointing at `documentary-junior-editor/start-editing` for Jeff to run in Terminal. After Jeff runs the command and reports back, the agent reads the new transcripts, validates each (non-empty, has timecodes, has speaker labels, plausible word count), and writes `handoffs/transcription-summary-v[N].md`.

The host-side launcher reads the AssemblyAI key from `documentary-junior-editor/.env` (no git-crypt). If the file is missing, the agent fails fast and tells Jeff exactly what to put in it.

**Video containers (`.mov`, `.mp4`) are pre-converted to `.mp3` in the
sandbox before the launcher runs.** The launcher only sees audio
extensions (`.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`). If you drop a
`.mov` or `.mp4` into `transcripts/audio/`, the Transcription Agent runs
`ffmpeg` in the Cowork sandbox (Phase 3 of `SKILL-transcription.md`) to
extract the audio track before presenting you the launcher command. The
original video file stays in place.

**Why a launcher and not direct sandbox execution:** Cowork's outbound network allowlist does not include AssemblyAI. Any sandbox-side call to `api.assemblyai.com` returns 403 from the proxy. Until the allowlist changes, transcription runs on the host. The launcher consolidates everything to one bash command with no copy-paste hazards (path has no extension; no chat auto-linking).

**Starter prompt — copy and paste into a new Cowork session (set model to Sonnet 4.6):**

> Start editing. The project folder is mounted. Read `documentary-junior-editor/SKILL-transcription.md` and follow it exactly. Detect audio files in `transcripts/audio/`, confirm speaker names with me, then give me the single bash command to run the launcher. After I report back that it's done, validate the new transcripts and save `handoffs/transcription-summary-v1.md` (or higher version if running again). Update `handoffs/pipeline-state.json` accordingly.

**What to check when it's done:**
- One .txt file per audio file in `transcripts/text/`
- `handoffs/transcription-summary-v[N].md` reports speaker count and validation results per transcript
- Open each transcript and spot-check speaker labels and timestamps
- Flag any interviews with audio issues before proceeding

**Trigger:** the Creative Context Agent on launch checks for audio without transcripts. If found, it pauses and gives you this starter prompt directly. You don't need to run Step 0 manually unless you want to.

---

### Step 1: Creative Context Agent

**Skill file:** `SKILL-creative-context.md`
**Model:** Opus 4.7
**Session type:** Cowork — collaborative with Jeff

**What's new in v5.0:** Phase 0 Discovery — the agent searches Google Drive (project folder by path or by keyword) and Gmail (project name + client domain) for relevant context, surfaces candidates with one-line summaries, and lets you approve which to ingest. Falls back to manual upload if Drive/Gmail connectors aren't connected.

**Inputs needed in project folder:**
- Interview transcripts in `transcripts/text/` (Transcription Agent produces these if needed; the Creative Context Agent will pause for it on launch if missing)
- *Optional:* Creative Launch transcript or notes, interview guide, messaging framework — Discovery picks these up automatically if they're in your Drive project folder, or you can upload manually

**Starter prompt — copy and paste into a new Cowork session (set model to Opus 4.7):**

> You are the Creative Context Agent. Read `documentary-junior-editor/SKILL-creative-context.md` and follow it exactly. The project folder is mounted. First, run Phase 0 Discovery — search Google Drive and Gmail for project context (project name: [PROJECT NAME], client domain: [CLIENT DOMAIN if any]) and surface candidates for my approval. Then read all approved documents plus the interview transcripts in `transcripts/text/`, plus reference examples in `documentary-junior-editor/reference-examples/`. Work with me to develop and approve a 3-act narrative structure. Save `creative-brief-summary-v1.md` and `act-structure-v1.md` (or higher version) to `handoffs/`. Update `handoffs/pipeline-state.json`. If audio is detected without transcripts, pause and give me the Transcription Agent launch prompt before proceeding. If this SSD already hosts another project, establish the project slug for this deliverable up front and write all outputs to `handoffs/[project-slug]/` instead of flat `handoffs/`.

**What happens:**
1. Audio-detection check: if audio is present without transcripts, pause and provide Transcription Agent launch prompt
2. Phase 0 Discovery: search Drive + Gmail, surface candidates, you approve
3. Agent reads approved documents, transcripts, and reference examples
4. Agent confirms whether the SSD is single-project or multi-project, establishes the project slug if needed
5. Agent proposes a 3-act narrative structure
6. Jeff and agent iterate until the structure is approved
7. Agent emits versioned outputs and updates `pipeline-state.json`

**Outputs saved to `handoffs/` (or `handoffs/[project-slug]/`):**
- `creative-brief-summary-v[N].md` — editorial context and priorities (in v5.0 framing — "starting points, not constraints")
- `act-structure-v[N].md` — Jeff-approved act labels and narrative roadmaps
- `pipeline-state.json` updated

**Done when:** Jeff has approved the act structure and both handoff files are saved.

---

### Step 2: FCPXML Params Agent + Transcript Agents (parallel fan-out)

These two run in parallel after the Creative Context Agent completes. They have no dependency on each other; only on the Creative Context outputs.

#### Step 2a: FCPXML Params Agent

**Skill file:** `SKILL-fcpxml-params.md`
**Model:** Sonnet 4.6
**Session type:** Cowork — autonomous

**What's new in v5.0:** Per-interview `clip_type` detection — multicam vs. single-clip. The output `fcpxml-params-v[N].md` carries a `## Clip Types` table per interview, with the existing format/ID fields adjusted per clip type.

**Starter prompt — copy and paste into a new Cowork session (set model to Sonnet 4.6):**

> You are the FCPXML Params Agent. Read `documentary-junior-editor/SKILL-fcpxml-params.md` and follow it exactly. The project folder is mounted. Read the sample narrative XML and per-interview captioned XMLs from `XML/exports/`. For each interview, detect whether it's multicam or single-clip and extract the appropriate FCPXML parameters (media reference IDs, angle IDs for multicam, asset ref ID + format for single-clip). Save `fcpxml-params-v1.md` (or higher) to `handoffs/`. Update `handoffs/pipeline-state.json`.

#### Step 2b: Transcript Agent (one session per interview subject)

**Skill file:** `SKILL-transcript.md`
**Model:** Sonnet 4.6
**Session type:** Cowork — runs per speaker, can run in parallel

**What's new in v5.0:** Segment decomposition at tag time. Each tagged quote includes a `segments[]` array with verbatim text and per-segment timecodes — the source pool the Edit Agent's timeline entries reference.

**Inputs:**
- `handoffs/act-structure-v[N].md` (latest version from Step 1)
- `handoffs/creative-brief-summary-v[N].md` (latest version from Step 1)
- One transcript from `transcripts/text/`

**Starter prompt — copy and paste into a new Cowork session (one per speaker, set model to Sonnet 4.6):**

> You are the Transcript Agent. Read `documentary-junior-editor/SKILL-transcript.md` and follow it exactly. Your assigned interview is `transcripts/text/[SPEAKER NAME].txt`. Read the latest `handoffs/act-structure-v[N].md` and `handoffs/creative-brief-summary-v[N].md` for context, plus reference examples in `documentary-junior-editor/reference-examples/`. Catalog every usable quote from the assigned transcript — tagged by act label, verbatim, with rationale, and decompose each into `segments[]` per the v5.0 schema. Save all four required output files (versioned `-v[N]`) to `handoffs/`: tagged quotes JSON with segments, orphans, discards, and content summary. Verify all four files exist on disk before reporting completion. Update `handoffs/pipeline-state.json`.

*(Replace `[SPEAKER NAME]` with the actual speaker name. For multi-project SSDs, replace `handoffs/` with `handoffs/[project-slug]/` throughout.)*

**Outputs saved to `handoffs/` (four files per speaker):**
- `[speaker-slug]-tagged-quotes-v[N].json` (with segments[])
- `[speaker-slug]-orphans-v[N].md`
- `[speaker-slug]-discards-v[N].md`
- `[speaker-slug]-summary-v[N].md`

**Done when:** All four files per speaker are verified on disk for every speaker. Wait for ALL speakers' Transcript Agents AND the FCPXML Params Agent to complete before moving to Step 3.

---

### Step 3: Synthesis Agent

**Skill file:** `SKILL-synthesis.md`
**Model:** Sonnet 4.6
**Session type:** Cowork — mostly autonomous, surfaces cross-interview insights

**What's new in v5.0:** Segments preserved through the merge. Cross-speaker version-consistency check (warns if speakers based on different Creative Context versions).

**Starter prompt — copy and paste into a new Cowork session (set model to Sonnet 4.6):**

> You are the Synthesis Agent. Read `documentary-junior-editor/SKILL-synthesis.md` and follow it exactly. All per-speaker Transcript Agent sessions are complete. Discover all per-speaker files in `handoffs/`, validate all four required files per speaker plus that all speakers were tagged against the same Creative Context version, then merge into combined handoff documents preserving the per-quote `segments[]` arrays. Produce the cross-interview narrative assessment. Save versioned merged outputs (`tagged-quotes-v[N].json`, `orphan-quotes-v[N].md`, `discard-summary-v[N].md`, `transcript-summary-v[N].md`) to `handoffs/`. Update `handoffs/pipeline-state.json`.

**Outputs saved to `handoffs/`:**
- `tagged-quotes-v[N].json` — merged, renumbered across all speakers, segments preserved
- `orphan-quotes-v[N].md` — combined orphans
- `discard-summary-v[N].md` — combined discards
- `transcript-summary-v[N].md` — combined summary with narrative assessment

**Done when:** All merged files are saved. Jeff reviews the narrative assessment before proceeding.

---

### Step 4: Edit Agent ↔ FCPXML Agent (multi-round loop)

The Edit Agent and FCPXML Agent run as a multi-round loop until Jeff approves the cut. Each round emits versioned outputs; previous rounds stay on disk.

#### Step 4a: Edit Agent

**Skill file:** `SKILL-edit.md`
**Model:** Opus 4.7
**Session type:** Cowork — deeply collaborative with Jeff

**What's new in v5.0:**
- **Quotes are clay; the timeline is the work product.** The data model is segments + timeline entries. The agent never says "split #11 into parts" — it produces new timeline entries when manipulation requires it. Splitting is implicit.
- **The HTML artifact is the work surface, not the deliverable.** Created at session start, updated via `update_artifact` after every decision, bidirectional via `sendPrompt()`. Auto-scrolls to and highlights current focus quote.
- **Full quote text always inlined in chat on first reference.** No more "what does that quote actually say?"
- **Wide rough cut + per-quote runtime recommendation.** `must-keep / probable-keep / probable-cut / optional` toward 2× target. Viewer toggles between full inventory and recommended-tight view.
- **Title-card-as-shortener** as a named pattern; agent proposes title cards in the rough cut when content reads cleaner on screen than spoken.
- **Context-beat suggestions** — agent flags narrative gaps where research-sourced context would land harder; surfaces in `edit-handoff.md` with `(research needed)` tag.
- **Brief is starting points** — language softened from v4.0 "must stay" to "currently planned to stay."
- **Three-phase Rough Cut → Discussion → Reduction loops**, not linear. Each round emits a new versioned `trimmed-quotes-v[N].json` and triggers a fresh FCPXML run.

**Inputs:**
- `handoffs/tagged-quotes-v[N].json` (latest merged, with segments)
- `handoffs/act-structure-v[N].md`
- `handoffs/creative-brief-summary-v[N].md`
- `handoffs/transcript-summary-v[N].md`
- For re-entry rounds: `handoffs/review-notes.md` (your notes from watching the previous FCPXML)
- Reference examples in `documentary-junior-editor/reference-examples/`

**Starter prompt — round 1 (set model to Opus 4.7):**

> You are the Edit Agent. Read `documentary-junior-editor/SKILL-edit.md` and follow it exactly. Read all latest handoff documents from `handoffs/` per `pipeline-state.json` — act structure, creative brief summary, transcript summary, and the merged tagged-quotes (with segments) — plus reference examples in `documentary-junior-editor/reference-examples/`. Build the live HTML artifact at session start (per the v5.0 spec — bidirectional, auto-scroll to focus, full quote text inlined in chat on first reference). Take us through Rough Cut → Discussion → Reduction. Run Cardinal Rule verification before saving. Save `handoffs/edit-handoff-v1.md`, `handoffs/trimmed-quotes-v1.json` (timeline entries with segments), and `handoffs/[project-slug]_quotes_view.html` (final state of the artifact). Update `handoffs/pipeline-state.json`.

**Re-entry prompt — round 2+ (after watching FCPXML in FCP):**

> You are the Edit Agent. Read `documentary-junior-editor/SKILL-edit.md` and follow it exactly. This is round [N+1]. Read `handoffs/edit-handoff-v[N].md` for context from the previous round, `handoffs/review-notes.md` for my notes from watching the FCPXML cut, the latest `handoffs/trimmed-quotes-v[N].json`, and `handoffs/pipeline-state.json`. Load the live HTML artifact from `handoffs/[project-slug]_quotes_view.html`. Work with me on revisions. Save `handoffs/edit-handoff-v[N+1].md`, `handoffs/trimmed-quotes-v[N+1].json`, and update the artifact. Update `handoffs/pipeline-state.json`.

**Outputs saved to `handoffs/` per round:**
- `edit-handoff-v[N].md` — structured handoff for the FCPXML Agent (paper cut state, notes, key files)
- `trimmed-quotes-v[N].json` — timeline of entries with `segments[]`, all editorial decisions
- `[project-slug]_quotes_view.html` — live artifact's final state for this round (overwrites; same name across rounds)

#### Step 4b: FCPXML Agent

**Skill file:** `SKILL-fcpxml.md` (+ `SKILL-fcpxml-params.md` for reference IDs)
**Model:** Sonnet 4.6
**Session type:** Cowork — mostly autonomous

**What's new in v5.0:**
- **Branched generation by `clip_type`.** Multicam → `<mc-clip>` references with angle selection (existing). Single-clip → `<asset-clip>` references directly with format, tcFormat, audioRole. Captions match against direct children of `<asset-clip>` in the single-clip case. Mixed projects handled per-interview.
- **Segment-aware clip generation.** Each timeline entry's `segments[]` produces one clip per source segment in entry order. Internal drops within an entry produce gaps in the source-clip play but stay within the entry's clip cluster.
- **Caption-matcher TC-window optimization** promoted to standard practice (±15s buffer per quote).

**Starter prompt — round N (set model to Sonnet 4.6):**

> You are the FCPXML Agent. Read `documentary-junior-editor/SKILL-fcpxml-params.md` and `documentary-junior-editor/SKILL-fcpxml.md` and follow them exactly. The project folder is mounted. Per `handoffs/pipeline-state.json`, read the latest `handoffs/fcpxml-params-v[N].md`, `handoffs/trimmed-quotes-v[N].json` (timeline entries with segments), `handoffs/edit-handoff-v[N].md`, and `handoffs/act-structure-v[N].md`. Cross-reference timecodes against the captioned FCPXMLs in `XML/exports/`, branch generation logic by per-interview `clip_type`, and emit one clip per source segment per timeline entry. Save the output to `XML/imports/[project-slug]_rough_cut_v[N].fcpxml` (or `_reduction_v[N].fcpxml` if the round was a Reduction emission). Update `handoffs/pipeline-state.json`.

**Output:**
- `[project-slug]_rough_cut_v[N].fcpxml` (or `_reduction_v[N].fcpxml`) in `XML/imports/`, ready to import into Final Cut Pro

**Done when:** Jeff imports the FCPXML into FCP, watches it, and either approves (proceed to Step 5 — Skill Review) or appends notes to `handoffs/review-notes.md` and re-launches the Edit Agent for the next round.

---

### Step 5: Skill Review Agent (post-project)

**Skill file:** `SKILL-review.md`
**Model:** Opus 4.7
**Session type:** Cowork — runs after Jeff approves the final cut

**What's new in v5.0:** Reads versioned diffs across all rounds — `act-structure-v1.md` vs. `v2.md`, `trimmed-quotes-v1.json` vs. `v2.json` vs. `v3.json`, etc. — as first-class data for lessons-learned extraction.

**Starter prompt — copy and paste into a new Cowork session (set model to Opus 4.7):**

> You are the Skill Review Agent. Read `documentary-junior-editor/SKILL-review.md` and follow it exactly. This project is complete. Review the handoff files in `handoffs/` (all versions, not just latest), the final FCP edit if I provide one, `handoffs/pipeline-state.json` for the round-by-round trajectory, and any notes I share. Extract editorial patterns and lessons learned. Create a `Final_Edit.txt` and `lessons-learned.md` in a new folder under `documentary-junior-editor/reference-examples/[project-name]/`, and copy the raw transcripts there too. If patterns warrant changes to the SKILL files, propose them for my review. End with the GitHub push command.

**This is the self-learning loop** — every completed project makes the skill smarter for the next one. **Don't skip the commit step that follows** (see [After Session Review](#after-session-review-commit-skill-updates-back-to-github) below) — without it, the lessons stay trapped on whichever machine ran the review.

---

## Quick Reference

| Step | Agent | Model | Collaborative? | Key Output |
|------|-------|-------|----------------|------------|
| 0 | Transcription | Sonnet 4.6 | Light (speaker confirmation) | .txt transcripts + summary |
| 1 | Creative Context | Opus 4.7 | Yes | act-structure-v[N].md (with Phase 0 Discovery) |
| 2a | FCPXML Params | Sonnet 4.6 | No | fcpxml-params-v[N].md (with clip_type) |
| 2b | Transcript (×N speakers) | Sonnet 4.6 | Light | per-speaker tagged quotes (with segments) |
| 3 | Synthesis | Sonnet 4.6 | Light | merged tagged-quotes-v[N].json |
| 4a | Edit (round N) | Opus 4.7 | Yes — heavy (3 phases, live artifact) | trimmed-quotes-v[N].json + edit-handoff-v[N].md |
| 4b | FCPXML (round N) | Sonnet 4.6 | No | rough_cut_v[N].fcpxml |
| ↺ | (Jeff watches; loops 4a → 4b until approved) |  |  |  |
| 5 | Skill Review | Opus 4.7 | Light | updated reference-examples + SKILL files |

`pipeline-state.json` in `handoffs/` tracks current versions and dependency edges throughout. Stale-state warnings surface in agent launches.

---

## After Session Review: Commit Skill Updates Back to GitHub

The Skill Review Agent (Step 5) often produces changes to skill files, reference examples, or `CHANGELOG.md`. **These changes need to be committed back to GitHub** so the next project — and any other machine you run on — picks them up automatically via the freshness check at the start of the next session.

If you skip this step, the lessons learned from this project stay trapped on whichever machine ran the review. The next project's agent will read stale skill files and make the same mistakes again.

**Preferred path: use the `commit-skill-changes` helper.** This helper
syncs SSD-side SKILL edits to the Desktop clone, reads a multi-line
commit message from `.commit-message`, and pushes to GitHub in one step.
From the project SSD's `documentary-junior-editor/` folder:

```bash
echo 'v5.2: TCCS Dr Pan & Testimonials review pass

[paste full v5.2 CHANGELOG entry bullet list here, or shorter summary]' \
  > .commit-message

bash commit-skill-changes
```

If the helper is unavailable or you want fine-grained control, the manual
`git` flow below also works.

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

**Transcription Agent fails with "AssemblyAI API key file is missing":** Create `documentary-junior-editor/.env` on this Mac with one line: `ASSEMBLYAI_API_KEY=<your-key>`. Get the key from https://www.assemblyai.com/app/account. The `.env` file is gitignored, so it doesn't travel via `git clone` — but it does travel via `cp -R` from your Desktop clone to a new project SSD.

**Launcher fails with "Could not open source directory" or sandbox-side bash errors:** Claude doesn't have Full Disk Access. Open System Settings → Privacy & Security → Full Disk Access, add Claude, toggle ON, quit Claude entirely (Cmd+Q), and relaunch. One-time per Mac.

**Launcher returns 403 Forbidden from AssemblyAI:** The key in `.env` is invalid, revoked, or has hit a quota. Rotate the key in the AssemblyAI dashboard, update `.env`, re-run.

**SSD disconnect / reconnect mid-session — agents keep asking for folder access:** The Cowork session's permission grant to the project folder is tied to the mount. If you unmount and remount the SSD partway through the pipeline, every subsequent agent session will need you to re-select the workspace folder, and any in-flight tool calls may fail. **Keep the SSD continuously mounted across the pipeline.** If a remount is unavoidable, expect to re-grant folder access on each agent's first turn, and verify the project's `pipeline-state.json` is intact before continuing.

**Transcription Agent skips files unexpectedly:** It skips audio files that already have a matching .txt in `transcripts/text/`. To force re-transcription, delete or rename the existing .txt first.

**Creative Context Agent says "audio detected without transcripts":** Run the Transcription Agent first using the launch prompt the agent gave you. Then return to Creative Context and re-launch.

**Creative Context Discovery doesn't find Drive/Gmail content:** Check that the Google Drive and Gmail MCP connectors are connected to this Cowork session. If not, connect them or paste the relevant docs manually — Discovery falls back gracefully.

**Transcript Agent or Synthesis Agent surfaces a stale-state warning:** An upstream agent has run since this agent last did. Either re-run from the upstream version (the warning's recommendation), or proceed with the mismatch acknowledged. The warning includes both options.

**Synthesis Agent flags missing files:** Each speaker needs four `-v[N]` files in `handoffs/`. Go back to the Transcript Agent session for the flagged speaker and verify all files were saved at the expected version.

**Edit Agent's first pass is too short / hits target on first try:** The agent is treating the first pass as a draft instead of a rough cut. Remind it of the v5.0 three-phase workflow — Rough Cut should run 1.5×–2× target. Reduction is a separate, later phase. Also check the v5.0 runtime-recommendation field — quotes should be wide-tagged, not pre-trimmed.

**Edit Agent abbreviates quotes in chat:** v5.0 says full quote text should be inlined on first reference. If the agent is consistently abbreviating, remind it of the live-artifact + first-reference-inlined contract from `SKILL-edit.md`.

**Live HTML artifact doesn't update mid-session:** The agent should call `mcp__cowork__update_artifact` after every editorial decision. If you see chat decisions without artifact updates, the agent has drifted — remind it of the "viewer is the work surface, not the deliverable" framing.

**FCPXML Agent generates wrong clip references for a single-clip interview:** Check that `fcpxml-params-v[N].md` has `clip_type: single_clip` for that interview (FCPXML Params Agent should detect this automatically; if it didn't, re-run with explicit instruction). The FCPXML Agent branches on `clip_type` per interview.

**FCPXML caption matcher times out on long interviews:** v5.0 standard practice is to narrow the per-quote search window using `startTC`/`endTC` ±15s. If the agent isn't doing this, remind it of `SKILL-fcpxml.md` Phase 3 Timing Extraction guidance.

**FCPXML won't import into FCP:** Check that `fcpxml-params.md` was generated from the correct sample XML for this project. Reference IDs must match the FCP library.

**`git fetch` fails on the SSD with `bad object refs/Icon?`:** Finder icon artifacts in `.git/`. See the cleanup snippet in [After Session Review](#after-session-review-commit-skill-updates-back-to-github).

---

*v5.2 — May 2026 — see CHANGELOG.md for detailed version history.*
