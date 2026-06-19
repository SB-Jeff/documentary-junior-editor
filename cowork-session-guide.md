# Documentary Junior Editor — Cowork Session Guide
### Version 5.10 | June 2026

## Overview

This guide walks through running the full documentary editing pipeline in Cowork sessions. Each agent runs as a separate Cowork session — with one exception: the Orchestrator Agent (Step 2, new in v5.5) launches Transcript Agents and FCPXML Params Agent as parallel sub-agents from within a single Cowork session, collapsing what used to be N+1 sessions into 1. Jeff drives every creative decision — the agents do the heavy lifting between decision points.

The pipeline has ten agents (v5.5):
- **Step 0** Transcription · **Step 1** Creative Context · **Step 2** Orchestrator (launches FCPXML Params + Transcript ×N as sub-agents) · **Step 3** Synthesis · **Step 4** Edit ↔ FCPXML loop (multi-round, optionally with Editing Coach between rounds) · **Step 5a** Editing Coach (at-close) · **Step 5b** Skill Review

Each agent declares its required model in its SKILL frontmatter. Every handoff document closes with a "Next agent + model + launch prompt" footer so transitions between sessions are paste-and-pick rather than reconstructed from memory.

---

## Before You Start: Confirm the Skill Is Up to Date

The `documentary-junior-editor` skill evolves between projects — v5.10 (drift-linted docs, loud `build_fcpxml.py` failure exits, `--verify` reports, Skill Review approval gate) is the most recent example. Before launching any new project (or any new session within an active project), confirm the local copy of `documentary-junior-editor/` matches the latest on GitHub. If it doesn't, pull first.

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

v5.0 used a git-crypt-encrypted key file in `secrets/assembly_ai.key`; v5.1 replaced
this with the `.env` flow above. The deprecated `secrets/` artifact was removed from the
master repo in v5.10 — if an old project copy still carries a `secrets/` folder, delete it
there. If you encounter older docs referencing `git-crypt unlock`, ignore them
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

### Step 2: Orchestrator Agent (v5.5+)

**Skill file:** `SKILL-orchestrator.md`
**Model:** Sonnet 4.6
**Session type:** Cowork — single coordination session that launches sub-agents

**What's new in v5.5:** This step replaces the prior pattern of launching N+1 separate Cowork sessions (one Transcript Agent per speaker plus one FCPXML Params Agent). A single Orchestrator session launches all of those as parallel sub-agents, waits for completion, validates outputs exist on disk, and hands off to Synthesis. For a 10-speaker project, this collapses 11 manual session launches into 1.

**Starter prompt — copy and paste into a new Cowork session (set model to Sonnet 4.6):**

> Read `documentary-junior-editor/SKILL-orchestrator.md` and run the Orchestrator Agent for this project. Creative Context has emitted approved `act-structure-v[N].md` and `creative-brief-summary-v[N].md` at version [N]. Discover all speaker transcripts in `transcripts/text/`, plan the sub-agent fan-out (Transcript Agent per speaker + FCPXML Params Agent), surface the plan for my confirmation, then launch the sub-agents in parallel — Transcript Agents in ORCHESTRATED (non-interactive) mode per `SKILL-transcript.md`'s "Invocation Mode" section. Validate all expected output files exist on disk — including parsing each tagged-quotes JSON and checking its `segments[]` — before handing off to Synthesis. You are the single writer of `handoffs/[project-slug]/pipeline-state.json`: sub-agents report their entry data back to you and do not touch the file; write the orchestrator entry plus every sub-agent's entry yourself, only after validation passes.

*(For multi-project SSDs, replace `handoffs/` with `handoffs/[project-slug]/` throughout. For single-project SSDs, just `handoffs/`.)*

**How it runs:** The Orchestrator first reads `pipeline-state.json` and the Creative Context handoff version. It discovers speakers from `transcripts/text/`, plans which sub-agents need to launch (skipping any that are already current), then surfaces the plan to you for one-click confirmation before any sub-agents fire. After your approval, it launches all sub-agents in parallel via a single Task-tool message. Each sub-agent runs independently with its own context window, in **ORCHESTRATED (non-interactive) mode** per `SKILL-transcript.md`'s "Invocation Mode" section — sub-agents never pause for user input; stale-state issues are recorded in their summaries, speaker identity is taken as given, and the in-chat review is skipped. The Orchestrator waits for all returns, then independently verifies the expected output files exist on disk (don't trust sub-agent self-reports alone) and content-validates each `[speaker-slug]-tagged-quotes-v[N].json` — parses the JSON, asserts a non-empty quote list, asserts every quote has a non-empty `segments[]`, and spot-checks `part` labels against the approved act structure. When validation passes, it hands off to Synthesis.

**Single-writer rule for `pipeline-state.json`:** sub-agents do NOT write `pipeline-state.json` — concurrent writes would race and silently erase each other. They report their entry data back in their final reports, and the Orchestrator writes every entry itself (each sub-agent's entry plus its own orchestrator entry), only after Phase 3 validation has passed. No entries are written for sub-agents that failed validation.

**Outputs saved to `handoffs/[project-slug]/` (created by sub-agents, validated by Orchestrator):**
- Per speaker (×N speakers, 4 files each): `[speaker-slug]-tagged-quotes-v[N].json`, `[speaker-slug]-orphans-v[N].md`, `[speaker-slug]-discards-v[N].md`, `[speaker-slug]-summary-v[N].md`
- One project-wide: `fcpxml-params-v[N].md`
- Total expected: 4N + 1 files

**Done when:** Orchestrator reports all sub-agents completed AND validation passes (file count matches, every tagged-quotes JSON parses with non-empty `segments[]`, all `pipeline-state.json` entries written by the Orchestrator). Move to Step 3.

#### Re-run patterns

The Orchestrator is designed to be re-invoked for targeted scope without launching sub-agents you don't need:

- **Creative Context updated to v2 → re-run all Transcript Agents:** Just relaunch the Orchestrator. It detects the version bump and re-runs all speakers at the new version. FCPXML Params is unaffected and stays at v1.
- **Single speaker needs re-tag:** Add scope to the prompt — "re-run only the Heather and Kevin Transcript Agents at the current Creative Context version."
- **FCPXML Params re-extraction:** Rare. Explicitly request — "re-run only the FCPXML Params Agent."

#### Falling back to manual standalone sessions

The standalone session pattern (one Cowork session per Transcript Agent, one for FCPXML Params) still works — both skill files remain valid for direct invocation. Use it for surgical one-off work where the Orchestrator's plan-and-confirm overhead is more than the work itself. For first runs and bulk re-runs, the Orchestrator is the default.

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
**Session type:** the redesigned edit step runs as a **persistent local app**, not a Cowork chat artifact — see `EDIT-SESSION-KICKOFF.md`. Today that means a Claude Code session on the `viewer-edit-redesign` branch (future: a standalone app); the upstream pipeline still runs in Cowork.

**What's new — the act-by-act live-partner redesign (supersedes the in-Cowork artifact model of v5.0–v5.10):**
- **Quotes are clay; the timeline is the work product.** Data model is segments + timeline entries; splitting is implicit (in the viewer, Split breaks #N → #Na/#Nb and Rejoin merges them back verbatim).
- **Persistent local app, shared via disk — not a chat artifact.** The viewer is served by `viewer_save_server.py` and opened in Chrome; it autosaves the full working state to `handoffs/<slug>/viewer-state.json` on every edit. The Edit Agent reads that file at the top of each turn and writes `handoffs/<slug>/agent-cursor.json` as its read-acknowledgement (drives the staleness cue). The old `update_artifact` / `sendPrompt` / copy-paste paths are retired.
- **Three tiers: Quote Library → Timeline → Cuts.** Library = every catalogued quote (the categorize surface + rejected-quotes home; each not-used quote carries the agent's `agent_note`). Timeline = the working cut (membership `tight`). Cuts = recoverable bin (membership `loose`). Inside the Timeline view, a **Review | Edit** mode toggle — Review is a clean read with the agent's coherence **seam-flags** inline. Internal membership values stay tight/loose.
- **Act by act, agent goes first.** Per act the agent presents its categorization (flagging low-confidence tags), builds an over-inclusive Timeline with a visible `agent_note` for every plausible quote it leaves out, then refines with Jeff. No step indicator — the views drive it.
- **Full quote text inlined in chat on first reference.**
- **Title-card-as-shortener** and **context-beat suggestions** as before. Title cards are authored: add/edit use one inline card, and removal is **Delete** (not Drop — there's no Library to return an authored card to).

**Inputs:**
- `handoffs/tagged-quotes-v[N].json` (latest merged, with segments)
- `handoffs/act-structure-v[N].md`
- `handoffs/creative-brief-summary-v[N].md`
- `handoffs/transcript-summary-v[N].md`
- For re-entry rounds: `handoffs/review-notes.md` (your notes from watching the previous FCPXML)
- Reference examples in `documentary-junior-editor/reference-examples/`

**Session setup — build + serve the viewer.** Build the viewer with `build_quotes_viewer.py`, then start the app server: `python3 scripts/viewer_save_server.py --serve <handoffs/<slug>/<slug>_quotes_view.html> --root <ssd-root>`, and open `http://127.0.0.1:8765/` in Chrome. The server serves the viewer AND persists everything it writes — saved cuts, the tweak log, and the live `viewer-state.json` the agent reads each turn. The top-bar **● Saved** pill confirms the channel is live (Offline = the server isn't running). Full kickoff in `EDIT-SESSION-KICKOFF.md`.

**Starter prompt — round 1 (set model to Opus 4.7; see `EDIT-SESSION-KICKOFF.md` for the full version):**

> You are the Edit Agent on the `viewer-edit-redesign` branch. Read `documentary-junior-editor/SKILL-edit.md` and follow it exactly — the act-by-act live-partner flow. The viewer is built and served at http://127.0.0.1:8765/. Read the latest handoffs per `pipeline-state.json` (act structure, creative brief, transcript summary, merged tagged-quotes) plus the reference examples. Each turn: read `handoffs/<slug>/viewer-state.json`, then write `handoffs/<slug>/agent-cursor.json`. Work act by act, you first — categorize + flag low-confidence tags, build the over-inclusive Timeline with `agent_note` reasons for what you leave out, then refine with me. Preserve both Cardinal Rules. When I queue an Export (`export-request.json`), launch the FCPXML Agent yourself via the Task tool. Save `handoffs/edit-handoff-v1.md`, `handoffs/trimmed-quotes-v1.json`, and update `pipeline-state.json`. Start with the Intro act.

**Re-entry prompt — round 2+ (after watching FCPXML in FCP):**

> You are the Edit Agent on the `viewer-edit-redesign` branch. Read `documentary-junior-editor/SKILL-edit.md` and follow it exactly. This is round [N+1]. Read `handoffs/edit-handoff-v[N].md`, `handoffs/review-notes.md` (my notes from the FCPXML cut), the latest `handoffs/trimmed-quotes-v[N].json`, and `handoffs/pipeline-state.json`. Rebuild + re-serve the viewer (it carries the prior round forward as a saved cut); read `viewer-state.json` / write `agent-cursor.json` each turn as in round 1. Work the revisions act by act. Save `handoffs/edit-handoff-v[N+1].md`, `handoffs/trimmed-quotes-v[N+1].json`, and update `pipeline-state.json`.

**Outputs saved to `handoffs/` per round:**
- `edit-handoff-v[N].md` — structured handoff for the FCPXML Agent (paper cut state, notes, key files)
- `trimmed-quotes-v[N].json` — timeline of entries with `segments[]` and `membership`, all editorial decisions. This is the full-timeline export; the Timeline-only export of the same round writes the separate `trimmed-quotes-v[N]-tight.json` — distinct filenames, the two never overwrite each other.
- `[project-slug]_quotes_view.html` — the built viewer served as the app (rebuilt per round; same name across rounds).
- `viewer-state.json` / `agent-cursor.json` — the live-partner channel (working state ↔ read-acknowledgement). `editing-versions/<name>.json` — named saved cuts.

**Viewer Export behavior (redesign):** Export writes the cut JSON (Timeline → `trimmed-quotes-v[N]-tight.json`, full timeline → `trimmed-quotes-v[N].json`) and **queues** `handoffs/<slug>/export-request.json`. The **Edit Agent fulfils it** — on its turn it reads the request and launches the FCPXML Agent itself via the Task tool, then marks the request `built`. No copy-paste, no new Cowork session; the viewer does **not** build FCPXML itself.

**At project close (once, not per round):**
- `edit-agent-lessons-v[N].md` — the Edit Agent's own capture of editorial lessons, structural patterns, and schema/tooling gaps from the session (SKILL-edit.md Phase 7, item 5). This is the lightweight, reliable feedback path: the Editing Coach and Skill Review Agents read it as a first-class input, and it stands on its own if neither runs.

#### Step 4b: FCPXML Agent

**Skill file:** `SKILL-fcpxml.md` (+ `SKILL-fcpxml-params.md` for reference IDs)
**Model:** Sonnet 4.6
**Session type:** Cowork — mostly autonomous

**What's new in v5.0:**
- **Branched generation by `clip_type`.** Multicam → `<mc-clip>` references with angle selection (existing). Single-clip → `<asset-clip>` references directly with format, tcFormat, audioRole. Captions match against direct children of `<asset-clip>` in the single-clip case. Mixed projects handled per-interview.
- **Segment-aware clip generation.** Each timeline entry's `segments[]` produces one clip per source segment in entry order. Internal drops within an entry produce gaps in the source-clip play but stay within the entry's clip cluster.
- **Caption-matcher TC-window optimization** promoted to standard practice (±15s buffer per quote).

**What's new in v5.7 (from the Hammer NER 2026 FCPXML review):**
- **Cut-selection confirmation (Phase 1, step 1.6).** Before generating, the agent counts timeline entries by `membership` and states both cuts — the **loose** cut (all entries) and the **tight** cut (membership-tight entries only) — with entry counts and approximate runtimes, then asks which to emit: loose, tight, or both. It does not assume the handoff's designated cut. Removes the regenerate-when-Jeff-wanted-the-other-cut round-trip.
- **Reference FCPXML required for all projects.** The Params Agent must set the reference FCPXML (`Project Sample.fcpxmld`) even on all-multicam projects — `build_fcpxml.py` needs it for the project skeleton. (See Step 2 / SKILL-fcpxml-params.md.)
- **Speaker keys must match the timeline.** Params speaker names come from the Synthesis `speaker` field, not FCPXML media metadata. (See Troubleshooting — as of v5.10 a mismatch fails loudly instead of silently dropping clips.)

**What's new in v5.10:**
- **Loud failure exits.** `build_fcpxml.py` exits non-zero on verbatim truncation (a quote sentence fails caption matching — exit 4) or on speaker misses / zero-clip output (exit 6), with a prominent warning block. The output FCPXML is still written either way — non-zero means "written but incomplete," not "no file." `--allow-partial` downgrades these to warnings with exit 0; use it only when Jeff has explicitly said a partial cut is acceptable.
- **`--verify` report (always pass it).** Emits `<output_basename>.verify.json` next to the output: per-speaker clip counts vs. expected, per-entry segment clip counts, clip_type sanity checks, truncated sentences, and act-divider count. The agent reads this report instead of hand-counting clips in the output XML.
- **Non-spoken entries are currently dropped.** Explicit `title_card` / `interstitial` / `context_beat` timeline entries are NOT yet rendered by the script — it drops them with a stderr warning listing per-type counts (tracked as W2/C6 in `skill-review-2026-06-10.md`). Act-boundary divider cards are unaffected. The agent must tell Jeff exactly which entries won't appear in the cut.

**Starter prompt — round N (set model to Sonnet 4.6):**

> You are the FCPXML Agent. Read `documentary-junior-editor/SKILL-fcpxml-params.md` and `documentary-junior-editor/SKILL-fcpxml.md` and follow them exactly. The project folder is mounted. Per `handoffs/pipeline-state.json`, read the latest `handoffs/fcpxml-params-v[N].md`, `handoffs/trimmed-quotes-v[N].json` (timeline entries with segments and membership; check for a `-tight` sibling export), `handoffs/edit-handoff-v[N].md`, and `handoffs/act-structure-v[N].md`. Cross-reference timecodes against the captioned FCPXMLs in `XML/exports/`, branch generation logic by per-interview `clip_type`, and emit one clip per source segment per timeline entry. **Before generating, count the entries by membership, state the loose cut (all entries) vs. tight cut (membership-tight only) with entry counts, and ask me which cut(s) to produce — loose, tight, or both — and don't generate until I confirm.** Run `build_fcpxml.py` with `--verify` and read the `.verify.json` report rather than hand-counting clips. If the script exits non-zero (truncation = exit 4, speaker miss / zero clips = exit 6 — the file is still written), report exactly what failed; do not pass `--allow-partial` without my explicit say-so. If the script warns that non-spoken entries (title_card/interstitial/context_beat) were dropped, list them for me. Save the output to `XML/imports/[project-slug]_rough_cut_v[N].fcpxml` (and/or `_tight_cut_v[N].fcpxml`, or `_reduction_v[N].fcpxml` if the round was a Reduction emission). Update `handoffs/pipeline-state.json`.

**Output:**
- `[project-slug]_rough_cut_v[N].fcpxml` (and/or `_tight_cut_v[N].fcpxml`, or `_reduction_v[N].fcpxml`) in `XML/imports/`, ready to import into Final Cut Pro
- `<output_basename>.verify.json` alongside it — the `--verify` report the agent reads to confirm per-speaker/per-entry clip counts, clip_type sanity, and act-divider count

**Done when:** Jeff imports the FCPXML into FCP, watches it, and either approves (proceed to Step 5a/5b) or appends notes to `handoffs/review-notes.md` and re-launches the Edit Agent for the next round.

---

### Step 5a: Editing Coach Agent (at-close, v5.4+)

**Skill file:** `SKILL-editing-coach.md`
**Model:** Opus 4.7
**Session type:** Cowork — conversational

**What it does:** Reads the Edit Agent's session feedback (the quote viewer's override log + Jeff's reasoning), identifies patterns where the Edit Agent's defaults diverged from Jeff's judgment, and turns those patterns into targeted updates to `SKILL-edit.md` and quote-viewer roadmap entries. Writes the Editing and Quote Viewer sections of the project's `lessons-learned.md`. Hands off to Skill Review via `skill-review-notes.md`.

**Starter prompt — copy and paste into a new Cowork session (set model to Opus 4.7):**

> Read `documentary-junior-editor/SKILL-editing-coach.md` and run the Editing Coach Agent for this project in **at-close mode**. Jeff has approved the final FCPXML cut. Read the saved viewer state, the tweak log (or fall back to my memory if not persisted), and the trimmed-quotes JSON variants. Walk me through the override patterns one cluster at a time, capture my reasoning per cluster, propose SKILL-edit.md diffs for my approval, file viewer roadmap entries, and write the Editing + Quote Viewer sections of `handoffs/[project-slug]/lessons-learned.md`. Leave a handoff note at `handoffs/[project-slug]/skill-review-notes.md` for the Skill Review Agent.

Coach can also run **between-rounds** during Step 4 — invoke it after any Edit Agent round (typically between rough and tight) to course-correct the Edit Agent before the next pass. Use the same skill file, but tell it "between-rounds mode" in the prompt; output is a briefing for the next Edit Agent invocation rather than the full at-close ceremony.

**Coach is optional as of v5.7.** The Edit Agent now writes its own `edit-agent-lessons-v[N].md` at project close, so the feedback loop no longer depends on the tweak-log → Coach → Review chain firing. Run Coach when you want the deeper at-close conversation and SKILL-edit.md diffs; skip it when the Edit Agent's lessons doc already captures what the session taught. Skill Review (Step 5b) reads the lessons doc directly when Coach didn't run.

---

### Step 5b: Skill Review Agent (post-project, after Coach)

**Skill file:** `SKILL-review.md`
**Model:** Opus 4.7
**Session type:** Cowork — runs after Jeff approves the final cut

**Scope (v5.4+): pipeline-wide concerns ONLY** — technical issues, system design observations, a Capability Audit, Jeff's forward-looking ideas, and the reference-example contribution. Editorial-pattern analysis (override patterns, rule promotion to `SKILL-edit.md`) is the Editing Coach's job; Skill Review reads Coach's `skill-review-notes.md` as an input but does not re-do that analysis. When Coach didn't run, it reads the Edit Agent's `edit-agent-lessons-v[N].md` directly and flags any editorial-philosophy items "→ Coach should fold into SKILL-edit.md."

**What's new in v5.9–v5.10:**
- **Review Legibility (v5.9):** the agent opens with a "What I'm reviewing" summary (inputs read, inputs absent, checks about to run) and closes by restating what it looked at — the review is not a black box.
- **MANDATORY approval gate (v5.10, Phase 6):** no SKILL file is written before Jeff approves the specific change. The agent presents each proposed edit in chat as a diff-style before/after, waits for approval, and applies only approved edits.
- **Drift linter (v5.10):** `python3 scripts/lint_skill_drift.py` runs before proposing edits and again after applying them — version footers, agent counts, dead file references, retired symbols. All findings must be clean or explicitly acknowledged by Jeff.

**Starter prompt — copy and paste into a new Cowork session (set model to Opus 4.7):**

> You are the Skill Review Agent. Read `documentary-junior-editor/SKILL-review.md` and follow it exactly. This project is complete and I've approved the final cut. Start with the Review Legibility summary — tell me what you're reading and which checks you'll run. Read Coach's `skill-review-notes.md` and the Coach-written `lessons-learned.md` sections if Coach ran; if not, read `handoffs/edit-agent-lessons-v[N].md` directly. Review `handoffs/pipeline-state.json` for the round-by-round trajectory plus the handoff files (all versions, not just latest). Your scope is pipeline-wide concerns only — Phase 1 technical issues, Phase 2 system design, Phase 3 Capability Audit, Phase 4 my forward-looking ideas — not Edit-Agent editorial analysis (that's Coach territory; flag anything editorial "→ Coach"). Write the System, Forward-Looking, and Reference Value sections of `lessons-learned.md`. Create `Final_Edit.txt` under `documentary-junior-editor/reference-examples/[project-name]/`, copy the raw transcripts there, and move the finished `lessons-learned.md` there. For skill-file updates: run `python3 scripts/lint_skill_drift.py` first, propose each edit to me as a diff-style before/after, wait for my approval, apply only approved edits, then re-run the linter until clean. End with the `commit-skill-changes` push block.

**This is the self-learning loop** — every completed project makes the skill smarter for the next one. **Don't skip the commit step that follows** (see [After Session Review](#after-session-review-commit-skill-updates-back-to-github) below) — without it, the lessons stay trapped on whichever machine ran the review.

---

## Quick Reference

| Step | Agent | Model | Collaborative? | Key Output |
|------|-------|-------|----------------|------------|
| 0 | Transcription | Sonnet 4.6 | Light (speaker confirmation) | .txt transcripts + summary |
| 1 | Creative Context | Opus 4.7 | Yes | act-structure-v[N].md (with Phase 0 Discovery) |
| 2 | Orchestrator | Sonnet 4.6 | Light (plan confirmation only) | launches FCPXML Params + Transcript Agent (×N) as parallel sub-agents; validates 4N+1 output files |
| 3 | Synthesis | Sonnet 4.6 | Light | merged tagged-quotes-v[N].json |
| 4a | Edit (round N) | Opus 4.7 | Yes — heavy (3 phases, live artifact) | trimmed-quotes-v[N].json (+ -tight.json from Tight-window export) + edit-handoff-v[N].md |
| ↻ | (optional) Editing Coach between rounds | Opus 4.7 | Yes (conversational) | coach-briefing-v[N].md |
| 4b | FCPXML (round N) | Sonnet 4.6 | Light (loose/tight/both cut confirmation) | rough_cut_v[N].fcpxml (and/or tight_cut) + .verify.json report |
| ↺ | (Jeff watches; loops 4a → 4b until approved) |  |  |  |
| 5a | Editing Coach (at-close) | Opus 4.7 | Yes (conversational) | Editing + Quote Viewer sections of lessons-learned.md; SKILL-edit.md diffs |
| 5b | Skill Review | Opus 4.7 | Light | System + Forward-Looking + Reference Value sections of lessons-learned.md; reference-examples/[project]/ |

`pipeline-state.json` in `handoffs/` tracks current versions and dependency edges throughout. Stale-state warnings surface in agent launches.

---

## After Session Review: Commit Skill Updates Back to GitHub

The Skill Review Agent (Step 5b) often produces changes to skill files, reference examples, or `CHANGELOG.md` — Jeff-approved per the Phase 6 gate, drift-linted before and after. **These changes need to be committed back to GitHub** so the next project — and any other machine you run on — picks them up automatically via the freshness check at the start of the next session.

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

**Edit Agent's first pass is too short / hits target on first try:** The agent is treating the act's first build as a draft instead of an over-inclusive rough cut. Per act, the wide build (Timeline + Cuts) should run ~1.5×–2× target; winnowing happens later by Cutting to the Cuts bin, not by pre-trimming. Quotes should be wide-tagged.

**Edit Agent abbreviates quotes in chat:** full quote text should be inlined on first reference. If the agent is consistently abbreviating, remind it of the first-reference-inlined contract in `SKILL-edit.md`.

**Agent seems out of sync with the viewer:** the agent should read `handoffs/<slug>/viewer-state.json` at the top of every turn and write `agent-cursor.json` (which clears the staleness pill). If the pill stays amber after you message it, the agent skipped the read — remind it of the live-partner contract in `SKILL-edit.md`. If the top-bar pill shows **Offline**, the app server isn't running, so the agent can't see edits at all.

**FCPXML Agent generates wrong clip references for a single-clip interview:** Check that `fcpxml-params-v[N].md` has `clip_type: single_clip` for that interview (FCPXML Params Agent should detect this automatically; if it didn't, re-run with explicit instruction). The FCPXML Agent branches on `clip_type` per interview.

**FCPXML caption matcher times out on long interviews:** Fixed in v5.10 — TC-window narrowing shipped (`_narrow_caption_search_window` in `generate_fcpxml.py`, ±15s buffer around each segment's `startTC`/`endTC`); no manual caption pre-trimming is needed on any project. If a timeout still happens, either the fix regressed or the TCs in `tagged-quotes-v[N].json` are missing/unparseable — open the JSON and verify the source pool has populated `startTC`/`endTC` per segment. If TCs are absent, the matcher falls back to a full-range scan (the legacy behavior) and is slow accordingly; flag it to Jeff rather than hand-narrowing.

**Multi-speaker output FCPXML has missing or wrong-speaker clips:** Each speaker's captioned FCPXML has its own resources block, and they typically all start at `r2`. `build_fcpxml.py` resolves the collision automatically by merging per-speaker resources with dynamic ID remap (first speaker alphabetical keeps its IDs; subsequent speakers shift above the high-water mark). If you see a warning like "speaker 'X' source has no `<resources>`; skipping in merge", that speaker's source FCPXML is malformed — re-export from FCP. If clips reference the wrong speaker after import, check the FCPXML Params handoff for matching `Media Ref IDs` / `Asset Ref IDs` against the speaker filenames in `XML/exports/`.

**Output FCPXML has very few clips, or zero:** The most common cause is a speaker-name mismatch between `fcpxml-params-v[N].md` and the timeline — `build_spine()` does an exact dict lookup on speaker name, so wrong/short/legacy names (e.g. params `Isiah` / `Mike & Janna Stern` vs. timeline `Isaiah Allen` / `Jana Stern` / `Mike Stern`) drop those speakers' clips. **The silent drop is fixed in v5.10:** the script now exits non-zero (exit 6) with a prominent warning block naming the zero-clip speakers, and the `--verify` report lists per-speaker clip counts — if speakers ever drop *silently* again, the fix regressed. Relatedly, an ambiguous speaker-source-file match (`find_speaker_fcpxml`'s fuzzy fallback hitting multiple files) now errors listing the candidates instead of silently binding the first sorted hit. Fix remains the same: the Params Agent must use the canonical `speaker` values from `tagged-quotes-v[N].json`, not FCPXML `<media name=...>` metadata (SKILL-fcpxml-params.md, v5.7). Re-run FCPXML Params with corrected keys, or normalize names before generating.

**Act-boundary title cards stack at the start of the timeline instead of at act positions:** Fixed in v5.10 — divider offsets now track cumulative spine duration, and `parse_act_structure()` also recognizes non-"Act"-prefixed headings (Intro/Opening/Epilogue etc.). Dividers land at their act boundaries; confirm the act-divider count in the `--verify` report. If you see stacking again, the fix regressed — report it, don't strip dividers by hand.

**Duplicate multicams appear in the FCP library after re-importing a later FCPXML version:** Fixed in v5.10 — source multicam `uid` attributes are preserved through the resource merge so FCP recognizes existing library multicams, and generated `<project>` elements carry no `uid`/`modDate` (FCP assigns a fresh project UID on import), which removed the re-import duplication/re-processing cause. If duplicates reappear, check that `library_location` / `event_name` / `event_uid` in the params handoff match the destination library; if they do, the fix regressed.

**`build_fcpxml.py` won't run / "no reference FCPXML" (v5.7):** The `## Reference FCPXML` field in `fcpxml-params-v[N].md` is blank or says "no single_clip interviews." The reference (`Project Sample.fcpxmld` in `XML/`) is required for *every* project — it supplies the project skeleton regardless of clip type. Re-run the Params Agent so it sets the field, or fill it in by hand from the sample XML in `XML/`.

**FCPXML won't import into FCP:** `library_location`, `event_name`, and `event_uid` in `fcpxml-params-v[N].md` must match the destination FCP library — the FCPXML Params Agent extracts these from each speaker's source FCPXML, so a mismatch usually means the source FCPXMLs were exported from a different library than the one you're importing into. Re-export the captioned interviews from the destination library and re-run the FCPXML Params Agent. Multicam recognition on re-import relies on the `<media uid=...>` attribute being stable across exports (FCP keeps these stable on the source multicams).

**`git fetch` fails on the SSD with `bad object refs/Icon?`:** Finder icon artifacts in `.git/`. See the cleanup snippet in [After Session Review](#after-session-review-commit-skill-updates-back-to-github).

---

*v5.10 — June 2026 — see CHANGELOG.md for detailed version history.*
