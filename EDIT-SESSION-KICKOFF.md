# Edit-stage kickoff (viewer-edit-redesign)

How to start the redesigned **Edit Agent + live viewer** on a project that has
already cleared the upstream pipeline. This is the act-by-act live-partner flow
on the `viewer-edit-redesign` branch — see `SPEC-viewer-edit-redesign.md` and
`SKILL-edit.md`.

## When to use
After the upstream agents (Transcript → Synthesis → Creative Context → FCPXML
Params) have run **in Cowork** and written their handoffs to the project's SSD
folder. Those steps are unchanged by this redesign. This note covers only the
**edit stage**, which runs here (a Claude Code session on the branch) because the
redesigned flow needs a persistent local app + an agent that reads/writes disk —
the model we moved to, off Cowork's chat artifact.

## Prereqs
- Upstream handoffs are on the mounted SSD under `<ssd-root>/handoffs/` (slugged
  subdir `<ssd-root>/handoffs/<slug>/` or flat — the build handles both):
  `tagged-quotes-v*.json`, `act-structure-v*.md`, `creative-brief-summary-v*.md`,
  `transcript-summary-v*.md`, `orphan-quotes-v*.md`.
- This repo checked out on branch **`viewer-edit-redesign`** (the redesign is not
  on `main` yet).
- Python 3 and Node available (the build inlines vendored React + compiles the
  JSX via `scripts/vendor/@babel/standalone`).

## 1 — Build the viewer
```
python3 scripts/build_quotes_viewer.py \
  --slug <slug> \
  --ssd-root <ssd-root> \
  --output <ssd-root>/handoffs/<slug>/<slug>_quotes_view.html \
  [--client "Client Name"] [--project "Project Name"]
```
Reads `<ssd-root>/handoffs/<slug>/` and falls back to flat `<ssd-root>/handoffs/`.
`--client` / `--project` set the header eyebrow ("Client · Project" over the edit
name); omit to fall back to the derived title.

## 2 — Serve it as the persistent app
```
python3 scripts/viewer_save_server.py \
  --serve <ssd-root>/handoffs/<slug>/<slug>_quotes_view.html \
  --root <ssd-root>
```
Open **http://127.0.0.1:8765/** in Chrome. The top-bar pill reads **● Saved**
when the viewer is autosaving `handoffs/<slug>/viewer-state.json` — the channel
the agent reads each turn. Leave this running for the whole session.

## 3 — Start the Edit Agent (a fresh Claude Code session, on the branch)
Paste this to a new session:

> You are the Edit Agent for the documentary-junior-editor pipeline, on the
> `viewer-edit-redesign` branch. Read `SKILL-edit.md` end-to-end and follow it
> exactly — the act-by-act live-partner flow.
>
> Project slug: `<slug>`. Handoffs are on the mounted SSD at
> `<ssd-root>/handoffs/`. The viewer is already built and served at
> http://127.0.0.1:8765/ (app server running, `--root <ssd-root>`).
>
> Each turn: first read `handoffs/<slug>/viewer-state.json` to see my current
> cut, then write your read-acknowledgement to `handoffs/<slug>/agent-cursor.json`
> (`{ "read_at": "<ISO now>", "message": "<one line>" }`) so my staleness pill
> clears. Work one act at a time, you first: present your categorization and flag
> low-confidence tags; build the over-inclusive Timeline with a visible
> `agent_note` for every plausible quote you leave out (write
> `handoffs/<slug>/edit-agent-notes-v[N].json` with `by_num` + `seam_flags`, then
> rebuild — step 1 — so they render); refine with me until I call the act done.
> When I queue an export (`handoffs/<slug>/export-request.json`, status
> "requested"), launch the FCPXML Agent yourself via the Task tool per
> `SKILL-fcpxml.md`, save the `.fcpxml`, set the request status to "built", and
> tell me where it landed. Preserve both Cardinal Rules.
>
> Start with the Intro act.

## Notes / known frictions
- **Live loop:** you edit in the viewer → it autosaves `viewer-state.json` → you
  message the agent in chat → it reads state + writes `agent-cursor.json` (pill
  flips green) → it responds. No copy-paste, no new session.
- **agent_note + seam-flags are baked at build time** (from
  `edit-agent-notes-v[N].json`). After the agent writes that file it must re-run
  the build (step 1); reload the tab to see the reasons/flags. (Cut membership,
  trims, splits, and saved cuts are live via `viewer-state.json` / Open and do
  NOT need a rebuild — only the agent's notes do.)
- **Export** never leaves the session: the viewer queues `export-request.json`;
  the Edit Agent fulfils it by launching the FCPXML Agent (Task tool).
- This is the validation run for the live loop — the last unproven piece of the
  redesign. If it holds up on a real project, that's the green light to merge
  PR #1 to `main`.
