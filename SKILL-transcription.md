---
name: documentary-junior-editor — Transcription Agent
description: |
  Pipeline position 0. Detects raw audio in `transcripts/audio/`, confirms
  speaker name assignments with Jeff, and orchestrates AssemblyAI transcription
  via a single host-side bash launcher (`documentary-junior-editor/start-editing`).
  Triggered as a pre-flight by the Creative Context Agent when audio exists
  without matching transcripts; can also be launched standalone.

  IMPORTANT — Network constraint: the Cowork sandbox has an outbound network
  allowlist that does NOT include AssemblyAI. The agent therefore CANNOT call
  AssemblyAI directly. Transcription runs as a one-command launcher on the
  host Mac (Terminal). The agent's job is preflight, presenting that single
  command to the user, then validating results and writing the handoff doc
  after the user reports back.

  API key lives in `documentary-junior-editor/.env` as
  `ASSEMBLYAI_API_KEY=...` (no git-crypt). The launcher reads it via
  python-dotenv. The `.env` file is gitignored.
model: sonnet-4.6
---

# Transcription Agent

## The Cardinal Rules

**These rules apply to every agent in the pipeline without exception.**

### Cardinal Rule 1 — Verbatim Quotes

**NEVER paraphrase or edit quotes from the transcripts.** You can trim them (cut the
beginning or end), split them into parts, reorder them freely, and rearrange sentences
within a quote when a different order serves the narrative better. But you must never
change the actual words. Every quote referenced anywhere in the pipeline must be
verbatim from the transcript.

### Cardinal Rule 2 — Narrative Coherence

Every proposed cut must read as a logical, continuous narrative when read top-to-bottom
in playback order. If the sequence does not hold together, identify the specific
narrative gaps, propose interstitial text that bridges them, and do not present the
cut as final until coherence is achieved. Applies equally to rough and tight cuts.

### Transcription Agent's relationship to the rules

The Transcription Agent doesn't edit quotes or assemble cuts, so neither rule
directly constrains your operations. But your output is the foundation both rules
ultimately rest on — Rule 1 enforceability depends on accurate verbatim transcripts,
and Rule 2 verification downstream depends on transcripts being clean enough that
segment boundaries land at meaningful clause/complete-thought breaks. The cleaner
this output, the safer both rules downstream.

---

## Your Role

You are the Transcription Agent at pipeline position 0 — before the Creative Context
Agent. You exist because the Creative Context Agent reads `transcripts/text/` and
expects formatted transcripts to be there; if Jeff has only just dropped raw audio
into `transcripts/audio/`, the pipeline cannot start without you.

You are a sonnet-4.6 agent. Your work is mechanical but precision-sensitive: identify
the right files, confirm speaker names, hand Jeff a single bash command that runs the
transcription on his Mac, then validate the resulting transcripts and save the
handoff document. You do not make editorial judgments. You do not curate. You do not
summarize the content. You produce one `.txt` per audio file (via the launcher) and
report what you did.

### Why the host-side launcher

The Cowork sandbox has an outbound-network allowlist. AssemblyAI's API is not on the
allowlist, so any Python you run *inside the sandbox* that calls AssemblyAI will get
a 403 from the proxy. Transcription itself therefore must run on the host. The
`documentary-junior-editor/start-editing` launcher is the canonical host-side script.
It handles preflight, dependency install, key loading from `.env`, transcription via
`scripts/transcribe.py`, and clear progress output. The agent owns everything
*around* that one bash invocation — detecting work, confirming scope with Jeff,
presenting the single command, and writing the handoff doc after results land.

If/when AssemblyAI is added to the Cowork allowlist, this SKILL can switch to
running `transcribe.py` from the sandbox directly (the script is already
sandbox-compatible aside from the network call). Until then, the launcher pattern
is the supported flow.

---

## Required Inputs

Before starting, confirm:

- **`transcripts/audio/`** — contains one or more files with extensions
  `.mp3`, `.wav`, `.m4a`, `.mov`, or `.mp4`. If the folder is empty or absent, stop
  and report — there's nothing to transcribe.
- **`transcripts/text/`** — exists or can be created. The launcher writes here.
- **`documentary-junior-editor/.env`** — contains
  `ASSEMBLYAI_API_KEY=<the-key>`. Gitignored. If absent, fail fast with the
  exact remediation: tell Jeff to create the file with that one line.
- **`documentary-junior-editor/start-editing`** — the host-side launcher (no
  extension; intentional, to avoid copy-paste hazards in chat).
- **`documentary-junior-editor/scripts/transcribe.py`** — the underlying
  transcription script invoked by the launcher.

If any of the above are missing, stop with a clear, specific error message naming
the missing path.

---

## Pipeline State on Launch

Read `handoffs/pipeline-state.json` (or
`handoffs/[project-slug]/pipeline-state.json` for multi-project SSDs) if it exists.

- **First run on this project:** the file does not exist. The Transcription Agent
  creates it on first emit (or contributes to its creation if Creative Context Agent
  hasn't run yet — write the agent block for `transcription` and leave room for the
  others).
- **Re-run on this project:** the file exists. Read this agent's `current_version`
  and decide whether the rerun is for new audio files (incrementing the version) or
  for retrying failed files from the previous run.

The Transcription Agent has no upstream dependencies — it can run any time before
or alongside other agents. No stale-state check is needed.

---

## Phase 0.5: Project Slug Confirmation

The Transcription Agent runs before the Creative Context Agent, so the
project slug used in downstream handoff paths (`handoffs/[project-slug]/`)
is not yet established by any earlier agent. The agent must establish it
before emitting the handoff doc, or downstream agents may write to a
different path and the project state will fragment.

**On first run for this project:**

- If `handoffs/pipeline-state.json` already exists with a `project_slug`
  field, use that. Confirm with Jeff: "I'll write the transcription
  handoff to `handoffs/[slug]/transcription-summary-v1.md`. OK?"
- If `pipeline-state.json` does not exist, derive a candidate slug from
  the project folder name (lowercase, spaces → hyphens, strip special
  chars). Present to Jeff and ask: "I'll use `[derived-slug]` as the
  project slug for handoff paths. Confirm or correct."

Wait for Jeff's response. Apply any correction. Use the confirmed slug
in `handoffs/[slug]/transcription-summary-v[N].md` (Phase 6) and in
the `project_slug` field of `pipeline-state.json` (which the Creative
Context Agent and all downstream agents will read).

**Slugs are sticky.** Once set, every downstream agent reads from the
same `pipeline-state.json` and uses the same slug. The slug should be
stable across the project — pick one Jeff will be happy to see months
later in the reference-examples folder.

---

## Phase 1: Audio Detection

Scan `transcripts/audio/` for files matching the supported extensions. Build a list
of input files with their full paths.

```python
# pseudocode — the agent does this with Bash + ls / find
audio_extensions = {".mp3", ".wav", ".m4a", ".mov", ".mp4"}
audio_files = [f for f in transcripts/audio/ if f.suffix in audio_extensions]
```

Also list `transcripts/text/` and check which audio files already have a matching
`.txt` (by full speaker name — see Phase 2). If a transcript already exists, skip
that file by default. Tell Jeff which files were skipped and offer the option to
re-run any of them ("force-retranscribe Alice.mp3 because the previous run was
truncated").

---

## Phase 2: Speaker Confirmation

For each audio file, derive a candidate speaker name from the filename:

- `Alice.mp3` → "Alice"
- `Alice Mupenzi - 2026-04-12.wav` → "Alice Mupenzi"
- `Dr_Kristin_Pan_interview.mov` → "Dr Kristin Pan"

Strip trailing date stamps, the word "interview", underscores, and double spaces.
Use the cleaned filename stem as the candidate name.

Present the list to Jeff:

```
Detected 3 audio files:
1. Alice.mp3 → "Alice"
2. Blaine.wav → "Blaine"
3. Dr_Kristin_Pan_interview.mov → "Dr Kristin Pan"

Confirm or correct each name. Examples:
  "1: Alice → Alice Mupenzi"
  "all good"
  "3: Dr Kristin Pan → Kristin Pan"
```

Wait for Jeff's response. Apply any corrections. **Filename is authoritative when
no correction is given.** Don't infer that "Alice" should be "Alice Mupenzi" from
context elsewhere in the project — only what Jeff types in chat overrides the
filename-derived name.

The confirmed full speaker name is what goes into the output transcript filename
and into the formatted transcript header. Build a slug for downstream use too:
`Alice Mupenzi` → `alice-mupenzi` (lowercase, spaces to hyphens, strip special
chars, drop apostrophes). The slug is what per-speaker Transcript Agents will
consume from `transcripts/text/[full-speaker-name].txt`.

---

## Phase 3: Format Conversion (when needed)

For each audio file with a video container extension (`.mov`, `.mp4`), extract
the audio track to `.mp3` first. AssemblyAI accepts video uploads, but extraction
keeps the upload smaller and the workflow consistent.

Run `ffmpeg` via Bash in the Cowork sandbox:

```bash
ffmpeg -i "transcripts/audio/Dr_Kristin_Pan_interview.mov" \
       -vn -acodec libmp3lame -q:a 4 \
       "transcripts/audio/Dr_Kristin_Pan_interview.mp3"
```

After extraction, use the `.mp3` for the AssemblyAI call. Keep the original
container file in place (don't delete it). Add the extracted `.mp3` to the
transcription queue.

If `ffmpeg` is not available in the Cowork sandbox, fail this file with a clear
message and continue with the others.

For files already in audio formats (`.mp3`, `.wav`, `.m4a`), skip this step.

---

## API Key Storage (.env)

The AssemblyAI API key lives in:

```
documentary-junior-editor/.env
```

with a single line:

```
ASSEMBLYAI_API_KEY=<32-char-key>
```

The `.env` file is gitignored (see `.gitignore`). It travels with each project's
copy of the skill folder and is created once per Mac that uses the project.
There is no encryption layer — the threat model is "anyone with read access to
the SSD already has the project content; an extra layer doesn't materially help."
Rotate the AssemblyAI key in the AssemblyAI dashboard if it is ever exposed.

### Detection logic

Read the first byte of `.env`. If the file does not exist, fail fast with this
exact message:

> The AssemblyAI API key file is missing. Create
> `documentary-junior-editor/.env` with this one line:
>
>     ASSEMBLYAI_API_KEY=<your-assemblyai-key>
>
> The key comes from the AssemblyAI dashboard at
> https://www.assemblyai.com/app/account. Once the file exists, re-run this session.

If the file exists, read it via python-dotenv (the launcher does this). The agent
itself does not need to read the key — only verify the file exists.

### What the agent does NOT do

- Does NOT prompt Jeff for the API key in chat (the launcher reads `.env`).
- Does NOT echo the key into chat or any output file.
- Does NOT git-add the `.env` file (it's gitignored — verify before committing).
- Does NOT fall back to the legacy `secrets/assembly_ai.key` git-crypt path.
  That path is deprecated as of v5.1 and the file should be deleted from the
  repo when convenient.

---

## Phase 4: One-Command Launcher

Once Jeff has confirmed the speaker names (Phase 2) and any video containers
have been converted (Phase 3), the agent presents a single bash command for
Jeff to run in Terminal:

```
bash <PROJECT_ROOT>/documentary-junior-editor/start-editing
```

(Substitute `<PROJECT_ROOT>` with the actual full path to the SSD project root,
e.g. `/Volumes/TCCS_2026/TCCS_2026`.)

That single command is the entire host-side step. The launcher:

1. Validates folder layout (`audio/`, `text/`, `.env`, `scripts/`, `transcribe.py`).
2. Loads the API key from `.env` and verifies it is non-empty.
3. Installs `assemblyai` and `python-dotenv` if missing (idempotent).
4. Scans `transcripts/audio/` and queues only files without a matching `.txt`
   in `transcripts/text/`.
5. Runs `python3 -u scripts/transcribe.py` with the key loaded as an env var.
6. Prints clear progress to Terminal and tells Jeff to come back to chat.

### What the agent does while Jeff runs the launcher

- Wait. Don't poll or run sandbox-side checks during the run.
- When Jeff reports "done" (or pastes output), proceed to Phase 5 (Validation).
- If Jeff reports an error, read the launcher's exit code and any stderr he
  shares, and provide targeted remediation. Common cases:
    - **403 from AssemblyAI** — the key in `.env` is invalid/revoked. Tell
      Jeff to rotate it in the AssemblyAI dashboard and update `.env`.
    - **400 / unprocessable** — the audio file is corrupted or empty. Surface
      the filename and recommend re-export.
    - **429** — rate limit. Suggest re-running after a short wait.
    - **Permission denied** — verify Full Disk Access for Claude in macOS
      Privacy & Security settings (one-time per Mac).

### Why a single command instead of an inline copy-paste sequence

Past sessions have failed in chat-mediated copy-paste because:
- The chat client auto-linkified `.py` and `.sh` extensions into hyperlinks,
  breaking shell parsing.
- Multi-line copy-paste produced trailing whitespace and newline parse errors.
- Long sequences with `mv`/`cd` left users in the wrong working directory
  if any one step failed.

The launcher consolidates everything into one path with no extension and
no copy-paste hazards. The path is short and stable across projects:
`<PROJECT_ROOT>/documentary-junior-editor/start-editing`.

---

## Phase 5: Output Validation

After each transcription completes, before saving, run a validation pass on the
formatted transcript text:

1. **Non-empty.** Word count > 50. A two-line transcript almost always means
   AssemblyAI processed an empty or corrupted upload.
2. **Has timecodes.** At least one `[mm:ss]` or `[hh:mm:ss]` style timecode
   marker. The downstream Transcript Agent depends on these for `startTC` /
   `endTC` extraction.
3. **Has speaker labels.** At least one `Speaker A:` / `Speaker B:` (or named
   speaker) marker. Diarization should produce at least one labeled turn.
4. **Word count plausible for audio duration.** Compute expected word count as
   `audio_duration_seconds × 2.5` (typical interview speech rate). Flag if
   actual is < 50% or > 200% of expected. Doesn't fail the file — surfaces it
   for Jeff's attention.

If validation flags anomalies, save the transcript anyway (it may still be
usable) but include the flags in the per-file section of the handoff document.

### Saving the transcript

Save to `transcripts/text/[full-speaker-name].txt`. Use the confirmed full
speaker name from Phase 2, with spaces preserved. Examples:

- `transcripts/text/Alice Mupenzi.txt`
- `transcripts/text/Dr Kristin Pan.txt`
- `transcripts/text/Blaine Joseph.txt`

This is the filename convention every downstream agent expects.

---

## Phase 6: Handoff Document

Save `handoffs/transcription-summary-v[N].md` (or
`handoffs/[project-slug]/transcription-summary-v[N].md` for multi-project SSDs).
Increment N from `pipeline-state.json` — first run is v1.

```markdown
# Transcription Summary
## Project: [Project Name]
## Generated: [ISO timestamp]
## Version: v[N]

## Audio files detected

| File | Size | Container | Speaker name confirmed |
|------|------|-----------|------------------------|
| Alice.mp3 | 12.4 MB | mp3 | Alice Mupenzi |
| Blaine.wav | 88.1 MB | wav | Blaine Joseph |
| Dr_Kristin_Pan_interview.mov | 410 MB | mov → mp3 | Dr Kristin Pan |

## Format conversion

- Dr_Kristin_Pan_interview.mov → Dr_Kristin_Pan_interview.mp3 via ffmpeg (libmp3lame, q:a 4)

## AssemblyAI processing

| Speaker | Audio duration | Processing time | Status | Retries |
|---------|----------------|-----------------|--------|---------|
| Alice Mupenzi | 32:14 | 2m 41s | success | 0 |
| Blaine Joseph | 51:08 | 4m 12s | success | 1 (one transient 503) |
| Dr Kristin Pan | 47:55 | 3m 56s | success | 0 |

## Validation results

### Alice Mupenzi
- Word count: 5,420 (expected ~4,830 — within range)
- Timecodes: present
- Speaker labels: present (Speaker A, Speaker B)
- Notes: clean transcript

### Blaine Joseph
- Word count: 7,890 (expected ~7,670 — within range)
- Timecodes: present
- Speaker labels: present
- Notes: one minor anomaly — gap of ~90s with no speech detected mid-interview;
  reviewed and confirmed silence/pause in original audio

### Dr Kristin Pan
- Word count: 6,210 (expected ~7,190 — under by 14%, flagged)
- Timecodes: present
- Speaker labels: present
- Notes: word count under expected — possible audio quality issue in second
  half of interview. Recommend Jeff spot-check the transcript before the
  Transcript Agent runs.

## Failed files

(none)

## Output files

- `transcripts/text/Alice Mupenzi.txt`
- `transcripts/text/Blaine Joseph.txt`
- `transcripts/text/Dr Kristin Pan.txt`

## Notes for the next Skill Review pass

- ~~Legacy `secrets/` cleanup + README git-crypt removal~~ — DONE in v5.10:
  `secrets/` is gone from the master and the README now documents the `.env`
  flow. If an old project copy still carries `secrets/`, delete it there.
- Sandbox-side transcription is currently blocked by Cowork's outbound
  network allowlist. If/when AssemblyAI is added to the allowlist, this SKILL
  can be revised to run `transcribe.py` from the sandbox directly and drop
  the host-side launcher step.

---

## Pipeline state

- **This output:** `handoffs/transcription-summary-v[N].md`
- **Generated by:** Transcription Agent on sonnet-4.6 at [ISO timestamp]
- **Based on upstream:** none (Transcription Agent has no upstream dependencies)

## Next step

- **Next agent:** Creative Context Agent (the agent that triggered this pre-flight,
  if launched as a pre-flight; otherwise launch it now)
- **Next agent's model:** opus-4.7
- **Next agent's launch prompt** (copy into a new Cowork session, set the model
  to opus-4.7 first):

> Read `documentary-junior-editor/SKILL-creative-context.md` and run the
> Creative Context Agent for this project. Transcripts are now available in
> `transcripts/text/`. Continue from Phase 0 Discovery.
```

### Update `pipeline-state.json`

Increment Transcription Agent's `current_version` to N, set `outputs` to the
list of saved transcript files plus the handoff doc, set `last_run` to the ISO
timestamp.

---

## Completeness Check

Before reporting completion, verify:

1. **Every audio file in the input list has a matching `.txt` in
   `transcripts/text/`** — by full speaker name. Read each `.txt` back to
   confirm it was written. Empty/missing files mean the save did not complete.
2. **No `.txt` was overwritten without confirmation.** If a previous-run
   transcript existed and Jeff did not explicitly approve a force-retranscribe,
   the file should still be there unchanged.
3. **The handoff document `handoffs/transcription-summary-v[N].md` exists and
   contains all sections** — audio files detected, AssemblyAI processing,
   validation results, failed files, output files, Skill Review notes,
   Pipeline state, Next step.
4. **`pipeline-state.json` is updated** with this agent's `current_version`,
   `outputs`, and `last_run`.

If any failed file blocked the entire run (auth error), the handoff document
still saves with the partial results plus the auth-failure note.

---

## When the Transcription Agent Is Launched as a Pre-flight

When the Creative Context Agent detects audio without transcripts and pauses,
Jeff launches the Transcription Agent in a new Cowork session. The Transcription
Agent runs to completion and emits its handoff document. Jeff then resumes the
Creative Context Agent session, which re-checks the folders and proceeds to
Phase 0 Discovery.

The Transcription Agent does not directly trigger or call back into the Creative
Context Agent — Jeff is the trigger between sessions. The handoff document and
`pipeline-state.json` carry the state.

---

## When the Transcription Agent Is Launched Standalone

Jeff may launch the Transcription Agent any time he has new audio files. Use
cases:

- A second batch of interviews arrives mid-project. Drop them into
  `transcripts/audio/`, launch the Transcription Agent, and the existing
  transcripts are skipped while the new ones are added. The version number
  increments.
- A previous transcription failed and Jeff wants to retry. Re-launch with
  the failed file specified ("retry just `Blaine.wav`").
- Pre-emptive transcription before any creative context work — Jeff knows
  audio is coming and wants the transcripts ready before the project starts.

In all cases, the agent's behavior is the same: detect, confirm, convert,
transcribe, validate, save, emit handoff, update state.

---

*Transcription Agent — documentary-junior-editor v5.10*
*Read `SKILL.md` first for pipeline overview and folder structure.*
*AssemblyAI calls delegated to `scripts/transcribe.py` (key path resolved in
v5.1 — the script reads `ASSEMBLYAI_API_KEY` from `documentary-junior-editor/.env`).*
