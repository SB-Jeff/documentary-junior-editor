# Edit-stage kickoff

How to start the redesigned **Edit Agent + live viewer** on a project that has
already cleared the upstream pipeline. This is the act-by-act live-partner flow
(merged to `main` 2026-07-02) — see `SPEC-viewer-edit-redesign.md` and
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
- This repo checked out on **`main`**, pulled current.
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
Open **http://127.0.0.1:8765/** in Chrome. The strip's pill reads **● Synced**
when the viewer is autosaving `handoffs/<slug>/edits/main/current.json` — the
channel the agent reads each turn. Leave this running for the whole session.

## 3 — Start the Edit Agent (a fresh Claude Code session, on the branch)
Paste this to a new session:

> You are the Edit Agent for the documentary-junior-editor pipeline. Read
> `SKILL-edit.md` end-to-end and follow it
> exactly — the act-by-act live-partner flow.
>
> Project slug: `<slug>`. Handoffs are on the mounted SSD at
> `<ssd-root>/handoffs/`. The viewer is already built and served at
> http://127.0.0.1:8765/ (app server running, `--root <ssd-root>`).
>
> Each turn: first read `handoffs/<slug>/edits/<open edit>/current.json` (main
> unless my edit chip says otherwise) to see my current cut, then write your
> read-acknowledgement to `handoffs/<slug>/agent-cursor.json`
> (`{ "read_at": "<ISO now>", "message": "<one line>" }`) so my staleness pill
> clears. Versioning is yours to write: when I say "move to Act N" snapshot my
> step (`scripts/edits_store.py snapshot --who jeff --label "..."`), and land
> every proposal with `scripts/edits_store.py propose` — it becomes a step and my
> viewer adopts it live (no rebuild, no reload). Work one act at a time, you
> first: present your categorization and flag low-confidence tags; build the
> over-inclusive Timeline with a visible `agent_note` for every plausible quote
> you leave out (write `handoffs/<slug>/edit-agent-notes-v[N].json` with
> `by_num` + `seam_flags`, then rebuild — step 1 — so they render); refine with
> me until I call the act done.
> When I queue an export (`handoffs/<slug>/export-request.json`, status
> "requested"), launch the FCPXML Agent yourself via the Task tool per
> `SKILL-fcpxml.md`, save the `.fcpxml`, set the request status to "built", and
> tell me where it landed. Preserve both Cardinal Rules.
>
> Start with the Intro act.

## Standing rules (v5.16)
- **Never open the served viewer in the agent's own browser.** Jeff's Chrome tab is the
  one instance; the agent verifies proposals by reading `edits/<edit>/current.json` and
  the step files. (Two instances alternated overwriting the live file on Valley Outreach.)
- **Log Jeff's corrections as they happen** to `handoffs/<slug>/drafts/edit-session-
  corrections.md`; restate them from memory at every act hand-off (health check).
- **One session** from transcription through the edit is the default; fresh session at the
  export if the harness has summarized.

## Notes / known frictions
- **Live loop:** you edit in the viewer → it autosaves `edits/<edit>/current.json`
  → you message the agent in chat → it reads state + writes `agent-cursor.json`
  (pill flips green) → it responds. Its proposals land as steps you see within
  seconds (banner + History). No copy-paste, no new session.
- **Versions (v5.15):** one Main edit, always saved. **History** = the steps the
  agent writes as you move act to act ("Claude: Act 1 proposal", "Jeff: Act 1
  revision") — View any step read-only, Restore it as a new step. **Save as**
  forks an alternative edit; the agent assists on whichever edit is open.
- **agent_note + seam-flags are baked at build time** (from
  `edit-agent-notes-v[N].json`). After the agent writes that file it must re-run
  the build (step 1); reload the tab to see the reasons/flags. (Cut membership,
  trims, splits, edits and steps are live via `current.json` / History and do
  NOT need a rebuild — only the agent's notes do.)
- **Export** never leaves the session: the viewer queues `export-request.json`;
  the Edit Agent fulfils it by launching the FCPXML Agent (Task tool).
- The live loop is validated (H+S IBEW 2026-06-30; hosted §7 test 2026-07-17)
  and merged to `main` — this doc is now the standing kickoff, not a test plan.
