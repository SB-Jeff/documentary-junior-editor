# documentary-junior-editor

The editing skill for Storyboard Films — a multi-agent workflow that turns raw
interview transcripts into an import-ready FCPXML rough cut for Final Cut Pro.
Self-contained. Works in two places:

- **Cowork sessions** — launch a Claude Desktop session against these SKILL
  files and edit documentary projects conversationally. This is the day-to-day
  workflow for most projects.
- **Pipeline mode** — the [storyboard-ops](https://github.com/SB-Jeff/storyboard-ops)
  server loads these files at runtime to run the same workflow as an automated,
  dashboard-driven pipeline. You don't need to understand the pipeline to use
  the skill.

Read `SKILL.md` first for the editorial substance (Cardinal Rule, folder
structure, agent responsibilities). This README is just about how to use the
repo on a new machine.

---

## Setup on a new machine (Cowork use)

You need this repo locally so you can copy the skill into each new project's
SSD folder, run the transcription script, and commit improvements back.

### One-time setup

```bash
# 1. SSH access to GitHub — one keypair per machine. The comment helps you
#    identify it later in https://github.com/settings/keys.
ssh-keygen -t ed25519 -C "your-email — $(scutil --get ComputerName)" -f ~/.ssh/id_ed25519 -N ""
pbcopy < ~/.ssh/id_ed25519.pub
#    Then paste the public key at https://github.com/settings/ssh/new

# 2. Clone the repo via SSH
cd ~/Desktop
git clone git@github.com:SB-Jeff/documentary-junior-editor.git
cd documentary-junior-editor

# 3. Install git-crypt and unlock the encrypted secrets
brew install git-crypt
#    Get the master key from your team's secure store. For Storyboard Films,
#    it's in Apple Passwords under "git-crypt master key — documentary-junior-editor"
#    (synced via iCloud Keychain across team Macs). Copy the password value to
#    clipboard, then:
pbpaste | base64 -d > /tmp/git-crypt-master.key
git-crypt unlock /tmp/git-crypt-master.key
rm /tmp/git-crypt-master.key
#    The AssemblyAI key in secrets/assembly_ai.key is now readable on this machine.

# 4. Install Python dependencies for the helper scripts
pip3 install assemblyai python-dotenv openpyxl
```

The decrypted `secrets/assembly_ai.key` is what the Transcription Agent
(`SKILL-transcription.md`) reads. Older scripts (e.g., `scripts/transcribe.py`)
may still read `ASSEMBLYAI_API_KEY` from a `.env` file — that path is being
phased out in favor of git-crypt. If you need to run a legacy script before it's
updated, mirror the same key value into a gitignored `.env` file.

### What NOT to do

You do **not** need to clone `storyboard-ops` or run any servers on this
machine. Those are only for pipeline development. Cowork uses the SKILL files
directly through Claude Desktop.

---

## Daily workflow

### Before starting a new project

```bash
cd ~/Desktop/documentary-junior-editor
git pull
```

This grabs any improvements made on other machines (editorial tweaks, new
reference examples, script fixes).

### Setting up a project SSD

Per `SKILL.md` section on folder structure — copy the skill into the project
SSD's working folder:

```bash
cp -r ~/Desktop/documentary-junior-editor [ProjectSSD]/[ProjectName]/documentary-junior-editor
```

The project name on the SSD must match the project name in the operations
system exactly (no abbreviations). Folder convention details are in `SKILL.md`.

### Running transcription

If the project has interview audio that needs transcribing:

```bash
python3 ~/Desktop/documentary-junior-editor/scripts/transcribe.py /path/to/project/folder
```

The script looks for audio files in `<project>/transcripts/audio/` and saves
formatted text transcripts to `<project>/transcripts/text/`. Already-transcribed
files are skipped automatically.

### Running the Cowork session

Open Claude Desktop, reference the SKILL files from the project SSD's
`documentary-junior-editor/` folder, and work through the pipeline
conversationally. `cowork-session-guide.md` in this repo walks through how
to structure the session from start to finish.

---

## Pushing changes back

If you improve something during a session — tighter trimming guidelines,
a new reference example, a script fix, whatever — commit and push so it
shows up on your other machines.

```bash
cd ~/Desktop/documentary-junior-editor
git add <files you changed>
git commit -m "Brief description of what changed and why"
git push
```

If you're adding a **reference example** (a finished edit worth learning from),
it goes under `reference-examples/<project-slug>/` — see the existing examples
for structure (Final_Edit.txt, lessons-learned.md, transcripts/).

If you're editing a **SKILL file**, keep in mind the file is consumed by both
Cowork and the pipeline — so any wording should make sense in either context.
The `-pipeline` variants (e.g., `SKILL-edit-pipeline.md`) are pipeline-specific
and reference MCP tools that don't exist in Cowork; don't edit those unless
you're intentionally working on the pipeline path.

---

## What's in this repo

### Top-level SKILL files

| File | Used by | Purpose |
|---|---|---|
| `SKILL.md` | Both | Master index. Cardinal Rule, folder structure, agent sequence. |
| `SKILL-creative-context.md` | Both | Reads transcripts, proposes act structure + narrative roadmap. First agent in the flow. |
| `SKILL-transcript.md` | Both | Per-interview: tags every quote against the act structure, flags orphans and discards. |
| `SKILL-synthesis.md` | Both | Merges per-interview outputs into a unified tagged-quotes catalogue. |
| `SKILL-edit.md` | Cowork | Interactive paper-cut session: selection, trimming, ordering, splitting via JSX artifact. |
| `SKILL-edit-pipeline.md` | Pipeline | Same role as SKILL-edit.md but uses server-side viewer tools instead of JSX artifacts. |
| `SKILL-fcpxml.md` | Both | Generates import-ready FCPXML rough cut from the finalized paper cut. |
| `SKILL-fcpxml-params.md` | Both | Extracts technical parameters (media ref IDs, angle IDs, library location) from source FCPXMLs. |
| `SKILL-review.md` | Both | Session review at end of project — captures lessons learned and skill improvement suggestions. |

### Scripts (in `scripts/`)

| Script | Purpose |
|---|---|
| `transcribe.py` | Sends interview audio in `transcripts/audio/` to AssemblyAI; saves text transcripts to `transcripts/text/`. Safe to re-run — skips already-done files. |
| `generate_fcpxml.py` | Library of FCPXML generation functions (caption parsing, fuzzy quote matching, spine assembly). Has a project-specific `main()` for Excel-driven workflows. Also imported by `build_fcpxml.py`. |
| `build_fcpxml.py` | Wrapper around `generate_fcpxml.py` — takes JSON inputs (trimmed-quotes.json, fcpxml-params.md) and emits FCPXML. Used by the pipeline, but you can also call it from a Cowork session if you're working from JSON. |
| `extract_fcpxml.py` | Converts `.fcpxmld` packages (FCP's directory format) into bare `.fcpxml` files that can be parsed as XML. |
| `generate_quotes.py` | Older helper — extracts a tagged-quotes starting point from transcripts. |
| `add_edit_tab.py` | Excel helper for the old Cowork workflow. |
| `quotes_viewer_template.jsx` | JSX template for the interactive quote viewer rendered in Cowork sessions. |

### Reference examples (in `reference-examples/`)

Finished edits from past projects. Each subfolder typically has:
- `Final_Edit.txt` — the locked paper cut
- `lessons-learned.md` — what worked, what didn't, editorial patterns worth remembering
- `transcripts/` — raw source transcripts so you can see how they became the final cut

The Creative Context agent reads these at the start of each project to
calibrate. When you finish a project and learn something generalizable, that's
a candidate for a new reference example.

### Guides

- `cowork-session-guide.md` — walks through how to structure a Cowork
  session from the opening "let's start a new project" to the final FCPXML.
- `cowork-session-guide-restore.md` — recovery playbook if a Cowork session
  gets interrupted mid-project.

### Other

- `SPEC-pipeline-v4.md` — design doc for the pipeline implementation.
  Reference only — you don't need this for Cowork use.
- `CHANGELOG.md` — version history of the skill.

---

## Related repos

- **[SB-Jeff/storyboard-ops](https://github.com/SB-Jeff/storyboard-ops)** —
  The operations system that wraps this skill in a server + dashboard for
  the automated pipeline mode. Not needed for Cowork use.

---

## Version

Current skill version: see `SKILL.md` header.
