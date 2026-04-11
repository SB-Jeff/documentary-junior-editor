# Documentary Junior Editor — Session Issues Log
## April 7, 2026

This documents issues encountered while building the transcription script into the documentary-junior-editor skill and updating the cowork-session-guide.md. Use this as a reference for the next Cowork session to address these problems.

---

## Issue 1: Cowork Sandbox Cannot Reliably Write to Mounted Desktop Folder

**What happened:** When Cowork writes a file to the mounted Desktop storyboard-ops folder, the file frequently appears as 0 bytes on the actual Desktop. This happened repeatedly with `cowork-session-guide.md` — it showed 271 lines inside the Cowork sandbox but `wc -l` on the Mac mini showed 0. Occasionally it would sync on a second check, but never reliably.

**Impact:** Any file Cowork creates or edits in the mounted folder can't be trusted to actually persist. Every file write needs manual verification from Terminal.

**To address:** Need a reliable mechanism for getting files from Cowork to the Desktop. Options include: presenting files as downloads, using heredoc Terminal commands, or finding a way to make the mount sync reliable.

---

## Issue 2: Cowork Cannot Push to GitHub

**What happened:** The sandbox has no access to GitHub credentials. `git push` fails with "could not read Username." Every commit and push must be done manually from Terminal.

**Impact:** Creates a two-step workflow for every repo change: Cowork makes the edit, then the user runs Terminal commands. Error-prone and tedious.

**To address:** Investigate whether Cowork can be configured with a GitHub personal access token, or whether there's an MCP connector for GitHub that could handle pushes.

---

## Issue 3: Cowork Cannot Run Scripts on the Local Machine

**What happened:** The transcription script needs to call the AssemblyAI cloud API, which requires network access the Cowork sandbox doesn't have. The script also needs Python packages installed on the Mac mini, not in the sandbox. So "auto-transcription" is really a manual Terminal step.

**Impact:** The user expected transcription to run automatically when launching a Cowork session on the project folder. Instead it requires: opening Terminal, navigating to the SSD path, running the python3 command with the full path. This defeats the purpose of automation.

**To address:** Consider whether an MCP server running locally on the Mac mini could execute the transcription script when triggered from Cowork. Alternatively, the n8n orchestration layer (from the CLAUDE.md architecture) could handle this — a webhook triggers transcription when a new project folder is detected.

---

## Issue 4: Python Package Installation on Homebrew-Managed Systems

**What happened:** `pip3 install assemblyai` failed on the Mac mini because Homebrew manages the system Python and blocks pip installs by default. Required `--break-system-packages --user` flags.

**Impact:** Not obvious from the error message. Easy to miss on a fresh machine.

**To address:** Document the exact install command in the skill's README or setup checklist. Consider using a Python virtual environment instead (`python3 -m venv`) to avoid the Homebrew conflict entirely.

---

## Issue 5: AssemblyAI SDK Breaking Changes

**What happened:** The `speech_model` parameter was deprecated. First attempt with `speech_model=aai.SpeechModel.best` got "deprecated, use speech_models." Fix was `speech_models=["universal-3-pro", "universal-2"]` (list format).

**Impact:** Scripts can break silently when the SDK updates. The error message was clear in this case, but may not always be.

**To address:** Pin the assemblyai package version in requirements or document the known-working version. Currently working with v0.59.0.

---

## Issue 6: API Key Discovery Is Fragile

**What happened:** The transcription script loads the AssemblyAI key from `.env` files using python-dotenv. If python-dotenv isn't installed, the `.env` loading silently fails (caught by try/except ImportError), and the script errors with "ASSEMBLYAI_API_KEY not set" — which doesn't point to the missing package as the root cause.

**Impact:** Misleading error message. User sees "key not set" and thinks the key is missing, when actually the package that reads the key file isn't installed.

**To address:** Add a more explicit error message when python-dotenv is not installed. Or check for the package at script startup and print a clear install instruction if missing.

---

## Issue 7: Google Drive Legacy Copy Caused Confusion

**What happened:** The Cowork session initially mounted the Google Drive copy of storyboard-ops instead of the Desktop copy. These had different git histories (4 vs 6 commits), different remotes, and divergent file states.

**Impact:** Work was initially done against the wrong copy. Required re-mounting and manual file copying.

**To address:** The Google Drive copy of storyboard-ops should be deleted or clearly marked as deprecated. The Desktop copy is the single source of truth, synced via GitHub. In new Cowork sessions, always select the Desktop folder explicitly.

---

## Issue 8: Git Lock File from Interrupted Operations

**What happened:** A previous interrupted git operation left a stale `.git/HEAD.lock` file that blocked new commits.

**Impact:** Minor — one-time fix with `rm .git/HEAD.lock`. But could be confusing if it happens again.

**To address:** Know the fix: `rm ~/Desktop/storyboard-ops/.git/HEAD.lock`

---

## Pending Items

1. **cowork-session-guide.md** — The 271-line version with all starter prompts exists in the Cowork sandbox and was presented as a download. Needs to be placed at `~/Desktop/storyboard-ops/skills/documentary-junior-editor/cowork-session-guide.md`, committed, pushed, and copied to the SSD.

2. **Delete Google Drive storyboard-ops copy** — Remove or archive the old Google Drive copy to prevent future confusion.

3. **Evaluate automation options** — The transcription step should ideally be triggered automatically, not via manual Terminal commands. Consider MCP server or n8n webhook approaches.
