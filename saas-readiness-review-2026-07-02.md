# SaaS-Readiness Review — documentary-junior-editor

**Date:** 2026-07-02
**Scope:** Design + readiness assessment for moving the system from a Claude Cowork/Claude Code-led local workflow to an online application inside the Storyboard Ops platform.
**Settled inputs (Jeff, this session):**
- **Hosting:** leverage what's already set up (Vercel account/integration + the Storyboard Ops n8n stack) unless there's a compelling reason to introduce something new. *Verdict below: there isn't — Vercel + n8n cover Phase A cleanly.*
- **Tenancy:** single-tenant now (Storyboard Films org + invited collaborators); data model designed so multi-tenancy can be added without a rewrite.
- **Media:** video stays local. Uploaded to the cloud: (1) interview **audio** for AssemblyAI transcription, (2) **caption FCPXMLs** per speaker + the **sample timeline XML** — the inputs the FCPXML builder needs for timecoding and building `.fcpxml` exports.

This review does **not** re-litigate the settled decisions in START-HERE.md (act-by-act live-partner Edit model; viewer-first phased cloud plan; the three-tier Library/Timeline/Cuts membership model).

---

## 1. TL;DR

The system is in better shape for a cloud move than a "local scripts + Claude sessions" description suggests, for one structural reason: **every stage communicates through versioned JSON/Markdown files with stable schemas, not through shared memory or chat context.** The handoff contract (`tagged-quotes` → `trimmed-quotes` → `export-request` → `.fcpxml`, plus `pipeline-state.json` and the live `viewer-state.json`/`agent-cursor.json` channel) survives the move intact — only the I/O layer underneath it changes (local SSD → cloud storage/DB, localhost HTTP → authenticated API).

**The phased plan holds, but with one reframe.** The boundary is not "viewer goes to cloud, pipeline stays local." The real boundary is the **text/XML plane vs. the media/FCP plane**:

- Cloud-capable *now or soon*: the viewer, all handoff state, transcription (already an AssemblyAI API call), timecode validation, the `_editCuts→segments` converter, and — because the FCPXML builder never touches raw media, only caption XMLs — **the FCPXML build itself**, given Jeff's decision to upload caption XMLs + the sample timeline.
- Hard-local *indefinitely*: raw footage on project SSDs, the Final Cut Pro library, and the human import-and-watch step.
- The genuinely hard Phase A problem is **not the viewer — it's the live agent.** Today the Edit Agent is a human-supervised Claude Code session reading/writing local files. A hosted viewer without the agent is a 1–2-week project; a hosted viewer *with* the live-partner loop requires server-side agent orchestration (Claude API worker, likely an n8n workflow) and is the bridge into Phase B.

**Recommendation:** split Phase A into three sub-phases — **A1** hosted viewer (no live agent, cloud save/load, export produces the same JSON the local pipeline consumes), **A2** cloud FCPXML export build (upload caption XMLs, build server-side, download `.fcpxml`), **A3** server-side Edit Agent (the live loop, via Claude API + n8n). A1 is the smallest viable first step and is defined as Milestone 1 in §7.

---

## 2. Current-State Architecture Map

### 2.1 The pipeline (stages and where they run)

```
                         ┌─ runs in Cowork/Claude sessions ─────────────────────┐
 audio (.mp3/.wav) ──►  Step 0 Transcription  ──►  transcripts/text/*.txt
                          (AssemblyAI API; .env key)
                        Step 1 Creative Context ──► creative-brief, act-structure
                        Step 2 Orchestrator ──► fans out:
                          ├─ FCPXML Params agent  ──► fcpxml-params-v[N].md
                          └─ Transcript agent ×N  ──► [speaker]-tagged-quotes-v[N].json
                          (Orchestrator = single writer of pipeline-state.json;
                           validate_timecodes.py = hard pre-handoff gate)
                        Step 3 Synthesis ──► tagged-quotes-v[N].json (merged pool)
                         └──────────────────────────────────────────────────────┘
                         ┌─ runs as a local Claude Code session + local app ────┐
                        Step 4a Edit Agent  ◄──live loop──►  Quote Viewer (Chrome)
                          │                                   served by viewer_save_server.py
                          │                                   @ 127.0.0.1:8765
                          └─ on export-request: launches
                        Step 4b FCPXML Agent ──► build_fcpxml.py ──► XML/imports/*.fcpxml
                         └──────────────────────────────────────────────────────┘
                         ┌─ hard-local, human ──────────────────────────────────┐
                        Jeff imports .fcpxml into Final Cut Pro (local .fcpbundle,
                        local media volumes), watches, writes review-notes.md
                         └──────────────────────────────────────────────────────┘
```

All inter-stage state lives on the project SSD under `handoffs/` (flat for single-project SSDs, `handoffs/[slug]/` for multi-project). Everything is versioned (`v[N]`), never overwritten. `pipeline-state.json` is the dependency graph / work queue, already designed to be read by n8n as an orchestrator contract (SKILL.md says so explicitly).

### 2.2 The live-partner Edit loop (the part Phase A targets)

```
   Jeff (Chrome tab)                          Edit Agent (Claude Code session)
   ┌──────────────────────┐                  ┌──────────────────────────────┐
   │ Quote Viewer          │                  │ each turn:                   │
   │ (self-contained HTML: │  viewer-state    │  1. read viewer-state.json   │
   │  React 18 inlined,    │ ───.json (500ms──►  2. act / respond / rebuild  │
   │  data BAKED at build) │    debounced      │  3. write agent-cursor.json │
   │                       │    autosave)      │     (clears staleness pill)  │
   │ staleness pill ◄──────│◄── agent-cursor──│                              │
   │ Export button ────────│──► export-request.json ──► launches FCPXML agent│
   └──────────┬───────────┘                  └──────────────────────────────┘
              │ all traffic via viewer_save_server.py @ 127.0.0.1:8765
              │   GET /            → serves the built viewer HTML
              │   POST /save       → writes handoffs/**.json (sandboxed, .json only)
              │   GET /read?path=  → polls agent-cursor.json
              │   GET /list?path=  → lists saved cuts (Open menu)
              └── files on the project SSD are the entire event bus
```

Key properties of the current design:

- **Files are the protocol.** No websockets, no queue, no API. Honest-async by design (the staleness pill is an explicit read-acknowledgement, not fake realtime).
- **The viewer HTML is a build artifact.** `build_quotes_viewer.py` bakes project data (quote pool, rounds, act structure, agent notes) into a self-contained HTML file at build time. Agent notes appearing on Library cards require a *rebuild + browser refresh*.
- **Persistence already degrades through tiers:** `window.cowork.callMcpTool` (Cowork artifact — now legacy) → local HTTP helper (current standard) → browser download (never lose data). This tiering is the reason the save path is easy to re-point at a cloud API.
- **The Edit Agent is a human-supervised session.** Its "turn" happens when Jeff talks to it. There is no daemon; if the session isn't running, the loop is dead and the pill goes amber.

### 2.3 Trust boundaries and security today

There are none, deliberately: single machine, single user, server binds `127.0.0.1` only, path-sandboxed writes under `handoffs/`, `.json`-only. Fine locally; **nothing is reusable as-is on a public network** — no TLS, no auth, no per-project authorization, last-write-wins saves, non-atomic file writes.

---

## 3. Pressure-Test of the Phased Plan

**Verdict: the plan is right, and survives pressure — but the phase boundary is drawn in a slightly wrong place, and Phase A hides its hardest problem.**

1. **"Viewer first" is correct.** The viewer is the highest-value, lowest-entanglement piece: it's already a self-contained React app with an abstracted save layer, and it's the surface Jeff (and eventually collaborators/clients) actually touch. Nothing in this review argues for a different first move.
2. **"Pipeline stays local because it's entangled with media + FCP" is only half-true.** Audit result: the *only* stages that touch media or FCP are Step 0's audio read (input side) and the human FCP import (output side). Everything between — creative context, transcript tagging, synthesis, editing, timecode validation, and crucially the **FCPXML build** — operates purely on text and XML. `generate_fcpxml.py` needs caption FCPXMLs + a reference timeline + params; it never opens a media file. With Jeff's decision to upload audio and caption XMLs, the pipeline's cloud blocker list shrinks to: raw media, the `.fcpbundle`, and the *orchestration model* (Claude sessions driven by a human). That third item is the real Phase B work, and it's an engineering problem, not a physics problem.
3. **The hidden hard part of Phase A is the agent, not the viewer.** "Cloud viewer" implicitly promises the live-partner loop from anywhere. But the loop's other half is a Claude Code session on the Mac attached to the SSD. Moving the viewer alone gives you remote *editing*; the agent goes silent unless (a) the Mac session stays running against synced state, or (b) the agent moves server-side (Claude API worker). Pretending otherwise would make Phase A look one-third of its real size. Hence the A1/A2/A3 split in §5.
4. **One risk the plan under-weights: dual-viewer divergence.** During the hybrid period there will be a local viewer path and a cloud viewer path. Two build targets of a 3,500-line JSX template will drift. Mitigation (§6): make the cloud viewer canonical as soon as A1 ships, keep the local build as an emergency fallback only, and keep the save-contract identical so the same template serves both.

---

## 4. SaaS-Readiness Scorecard

Verdicts: **PORTS-CLEAN** (moves with config/I-O-layer changes only) · **NEEDS-REWORK** (same concept, real engineering) · **HARD-BLOCKER** (stays local by design or requires a new system).

| Component | Verdict | Why / what it becomes |
|---|---|---|
| **Handoff data model** (versioned `tagged-quotes`, `trimmed-quotes`, `viewer-state`, `agent-cursor`, `export-request`, `pipeline-state.json` schemas) | **PORTS-CLEAN** | Already a machine-readable, versioned contract. Files become rows/objects: Postgres JSONB per artifact + version, or objects in blob storage with a DB index. Schemas unchanged. |
| **Viewer UI** (`quotes_viewer_template.jsx`, ~3.5k lines React 18) | **PORTS-CLEAN → light rework** | Plain React, no framework lock-in, vendored deps. Two changes: (1) baked-at-build-time data → fetched-at-load data (kills the rebuild-to-show-agent-notes cycle — a UX win, not just a port cost); (2) delete the `window.cowork` tier, point the helper tier at same-origin API routes. |
| **Save/read/list contract** (`viewer_save_server.py`'s 3 endpoints) | **NEEDS-REWORK (small)** | The *contract* ports clean; the *server* is disposable. Reimplement `/save`, `/read`, `/list` as authenticated API routes over cloud storage. Add: TLS (free on Vercel), auth, per-project authorization, optimistic versioning (current code is last-write-wins and non-atomic). ~294 lines to replace — this is the smallest load-bearing piece of the whole migration. |
| **`build_quotes_viewer.py`** (data baking + JSX compile) | **NEEDS-REWORK** | Splits in two: the JSX compile becomes a normal frontend build (Vite/Next); the data-assembly logic (discover latest versions, migrate v4→v5, merge agent notes) becomes a server-side "project loader" API. Logic is reusable; the single-HTML-artifact packaging is not. |
| **Live agent loop** (Edit Agent as Claude Code session; file polling; agent-cursor acks) | **NEEDS-REWORK (the big one)** | The *protocol* (state doc + cursor ack + staleness pill) ports beautifully to DB rows + a poll/subscribe endpoint. The *agent runtime* does not: it must become a server-side worker (Claude API, orchestrated by n8n or a queue consumer) triggered by state changes / pending messages. This is Phase A3 and the bridge to Phase B. Until then, cloud viewer runs agent-less or with the Mac-side session reading synced state. |
| **Transcription (Step 0)** | **PORTS-CLEAN** | Already an AssemblyAI API call; the only local part is reading audio off the SSD. Jeff's decision: audio gets uploaded → the call can originate from a cloud job. `.env` key moves to platform secrets. |
| **Pipeline agents (Creative Context, Orchestrator, Transcript ×N, Synthesis)** | **NEEDS-REWORK** | Skills are explicitly orchestrator-agnostic (SKILL.md's Cowork-vs-n8n section; model routing in frontmatter; `pipeline-state.json` as work queue). The rework is building the n8n workflows + Claude API calls + human-pause points — planned Phase 4/B work, not a redesign. |
| **FCPXML build** (`build_fcpxml.py`, `generate_fcpxml.py`) | **PORTS-CLEAN (given uploads)** | Pure deterministic Python over caption XMLs + reference timeline + params; no media access, no macOS dependency. With caption FCPXMLs + sample timeline uploaded (Jeff's decision), this runs as a cloud job (n8n step or container); output `.fcpxml` is downloaded for local FCP import. Frame rate is hardcoded NTSC 23.98 (`24000/1001`) — fine for now, parameterize when it matters. |
| **`validate_timecodes.py`, `editcuts_to_segments.py`** | **PORTS-CLEAN** | Pure functions with tests. Become library code in the cloud build job / API validation layer. (Note: the interior-cut detector exists in *both* Python and JSX, kept byte-equivalent by hand — in the cloud these should share one implementation or a golden test suite.) |
| **Auth & multi-tenancy** | **GREENFIELD** | Nothing exists. Single-tenant decision keeps this small: one org, invited users, per-project membership. Model it as `org → users → projects` from day one so multi-tenant later = adding orgs, not restructuring. |
| **Raw media (footage, graphics, music) + project SSDs** | **HARD-BLOCKER (by design)** | Stays local per settled plan + Jeff's media decision. The cloud never needs it. |
| **Final Cut Pro** (`.fcpbundle`, import, watch/approve) | **HARD-BLOCKER (by design)** | Human step on Jeff's Mac, indefinitely. The cloud's job is to put a correct `.fcpxml` one click away. Library/event UIDs in `fcpxml-params` must keep matching the local library — that params file remains the local↔cloud contract. |
| **Cowork dependency** (`window.cowork.callMcpTool`) | **NON-ISSUE** | Already a legacy tier; current sessions use the HTTP helper. In the cloud it's dead code to delete, not a dependency to migrate. |

---

## 5. Recommended Phase A Target Architecture (Cloud Viewer)

**Stack (per "leverage what exists"):** Next.js app on **Vercel** (the viewer template is already React 18 — it drops into a Next page), **Vercel Postgres/Neon** for state + index, **Vercel Blob or S3** for uploaded artifacts (audio, caption XMLs) and generated exports, simple invite-only auth (Auth.js or Clerk), and the existing **Storyboard Ops n8n** instance for the Python jobs (A2+). No new platforms needed; the compelling-reason bar for anything else was not met.

```
                    ┌────────────────────────── VERCEL ──────────────────────────┐
  Jeff / invited    │  Next.js app                                                │
  users (browser)──►│   • Viewer UI (ported quotes_viewer template,               │
   HTTPS + auth     │     data fetched per project — no more baked HTML)          │
                    │   • API routes (same contract as viewer_save_server):       │
                    │       POST /api/p/[slug]/save    (optimistic version check) │
                    │       GET  /api/p/[slug]/read    GET /api/p/[slug]/list     │
                    │       POST /api/p/[slug]/upload  (audio, caption XMLs)      │
                    │       GET  /api/p/[slug]/exports (download .fcpxml / JSON)  │
                    └───────┬───────────────────────────────┬────────────────────┘
                            │                               │
                   Postgres (Neon)                  Blob store (Vercel Blob/S3)
                   • orgs/users/projects            • uploaded audio
                   • artifacts (JSONB, versioned,   • caption FCPXMLs + sample timeline
                     mirrors handoffs/ schema)      • generated .fcpxml exports
                   • viewer_state / agent_cursor
                     rows (the live channel)
                            │
                            │ (A2+) job trigger: export-request row → webhook
                            ▼
                    ┌── Storyboard Ops n8n (existing) ───────────────────────────┐
                    │ • FCPXML build job: editcuts_to_segments → build_fcpxml     │
                    │   → verify → write .fcpxml to blob (A2)                     │
                    │ • Transcription job: audio → AssemblyAI → transcript (A2/B) │
                    │ • Edit Agent worker: Claude API, reads viewer_state,        │
                    │   writes agent_cursor + notes (A3)                          │
                    └─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        Jeff's Mac (hard-local): download .fcpxml → import into FCP → watch
        + `djed sync` CLI: push handoffs/ up, pull exports down (hybrid bridge)
```

**Design commitments:**

1. **Keep the JSON contract identical.** API routes accept/return the exact shapes the viewer and skills already use. That's what lets the local pipeline and the cloud viewer coexist during the hybrid period, and what lets the Mac-side Edit Agent keep working against synced state before A3.
2. **The hybrid bridge is a small sync CLI** (`djed sync --slug <slug>`): pushes `handoffs/` artifacts up, pulls saved cuts/exports down. This — not a fileserver, not mounting the SSD to the cloud — is how the two worlds meet in Phase A. It's ~a day of work and it's the piece that makes A1 useful on day one.
3. **Single-tenant, multi-tenant-shaped schema:** `orgs(id) → users(org_id) → projects(org_id, slug) → artifacts(project_id, kind, version, body JSONB)`. One org row for Storyboard Films now; selling it later means inserting org rows, not migrating.
4. **Live channel = rows, not files:** `viewer_state` and `agent_cursor` become single-row-per-project tables with version counters. The staleness pill logic ports unchanged; add optimistic concurrency (reject save if `base_version` is stale) to fix the existing last-write-wins race — which matters the moment a second browser tab exists, let alone a second user.
5. **Agent notes become data, not build inputs.** With fetched data, the agent (local now, worker later) posts notes through the same save API and the viewer picks them up on next poll — the rebuild+refresh friction (hardening item D2) disappears structurally.

**Phase A sub-phases:**

- **A1 — Hosted viewer (Milestone 1, §7).** Viewer on Vercel behind auth; save/read/list against Postgres; `djed sync` bridge; export produces `trimmed-quotes-v[N]-tight.json` for download/sync. No agent, no Python in the cloud. Jeff can review and edit a cut from any browser, anywhere.
- **A2 — Cloud export build.** Upload caption XMLs + sample timeline per project; export-request triggers the n8n FCPXML job; `.fcpxml` + verify report land in blob storage, one click to download. Also: transcription job (upload audio → AssemblyAI → transcript stored). After A2, the *only* local steps are shooting, exporting caption XMLs from FCP, and importing the result.
- **A3 — Server-side Edit Agent + unified chat.** Claude API worker (n8n) implementing the SKILL-edit loop: wake on viewer-state change or pending message, act, write cursor + notes. This is the live-partner experience, hosted — and it is the front door to Phase B, since the same orchestration pattern then absorbs the upstream pipeline stages one by one. A3 also introduces the **single-chat routing model** (§5c) — one conversation surface in the web app instead of one session window per agent.

### 5c. Unified chat & the routing agent (requirement added 2026-07-02)

**Requirement (Jeff):** today the agents live across multiple session windows; a core appeal of the online system is that everything happens in **one chat**, with questions routed to the right specialist — e.g. an act-structure question mid-edit goes to Creative Context; a "search quotes from this interview" question in the Library reaches the agent that tagged that transcript.

**Why the web app makes this structural, not a workaround:** in Cowork, chat and agent are the same thing (a session), so N agents = N windows. In the web app the chat is rows in the DB and the agent behind it is an API call — one thread can be served by any number of specialists.

**Design — the router's job splits in two, and the split matters:**

1. **Read questions (most traffic) → no dispatch.** This pipeline already externalizes every agent's knowledge into artifacts: act-structure questions are answered from `act-structure-v[N].md` + the creative brief; per-transcript quote search is a query over that speaker's tagged-quotes JSON. The Transcript agent that tagged an interview has no memory the file doesn't contain. So the resident chat agent answers these directly with retrieval tools over the artifact store — fast, cheap, no specialist run.
2. **Work requests → specialist dispatch.** "Re-tag this interview," "revise Act 2's premise" spawn a real specialist run: that stage's SKILL file as system prompt, its frontmatter-declared model, output written as a **new versioned artifact** through `pipeline-state.json`'s dependency graph, exactly as in the pipeline today.

**Two rules that make it work:**

- **UI context rides with every message.** The viewer knows where Jeff is (view, act, selected quote/speaker). Sending `{view, act, selection}` as structured metadata with each chat message does more for routing accuracy than any intent classifier.
- **Reads are safe anytime; writes are gated.** A chat detour must never silently mutate an upstream artifact mid-edit (that would invalidate the working timeline). Stage mutations require explicit confirmation, a version bump, and downstream staleness marks — the discipline `pipeline-state.json` already encodes.

**Rollout:** A3 ships the router as a thin layer with Edit as the resident specialist and the other stages available as *read-only answerers* (tool access to their artifacts). Dispatchable specialist *runs* (mutations) arrive with Phase B, since they are the same n8n + Claude API orchestration Phase B builds anyway.

**The chat *surface* ships earlier than the chat *brain* (M1 scope decision, 2026-07-02):** the viewer gets an in-viewer chat panel in **Milestone 1**, not A3. The channel already exists — `pending_message` in `viewer-state.json` and the agent's `agent-cursor.json` replies — so M1 renders it as a proper message thread and relays it through cloud state + `djed sync` to the **local Edit Agent session**, which remains the responder until A3 moves the agent server-side. Honest connection states: "Connected · reading your live edits" when a local session is attached, "Agent offline — messages will queue" when not. This kills the two-window problem from day one; A3 then swaps the responder, not the UI.

### 5d. Mid-edit structure revision (requirement added 2026-07-02)

**Requirement (Jeff):** the act structure is set early (from input docs + transcripts) and the quotes are tagged against it — but sometimes the structure **doesn't hold up once the edit is underway.** Today, revising it implies redoing the upstream agent work (re-tag every speaker, re-synthesize) and endangers the in-flight edit. The system must support going back to the drawing board on structure **without losing edit work and without blindly re-running everything.**

**Why it's tractable — what's structure-dependent and what isn't:** quote identity (`num`/`source_quote_id`), verbatim text, timecodes, and `segments[]` are all independent of the act structure; the only structure-dependent field is the act assignment (`part`). Timeline entries reference quotes by stable ID, so trims, membership, and sequencing survive a structure change. This yields **three tiers of revision cost — always take the cheapest that applies:**

1. **Pure reshape** (rename / merge / split acts, move a theme between acts) → deterministic **re-mapping** of existing tagged-quotes + the live timeline. No agent re-runs. Seconds, edit state fully preserved.
2. **New theme enters the structure** → **incremental relevance re-scan**, cheapest material first: the orphans + discards artifacts already hold everything judged not-relevant under the old structure. Full per-speaker re-tag only if that comes up dry — and new finds merge into the pool as *additions*, never a replacement that orphans the edit.
3. **Premise change** → genuine re-run of tagging + synthesis, but as a deliberate, confirmed choice — not the default blast radius of a structure tweak.

**Workflow:**

1. Jeff flags mid-edit (unified chat, from wherever he is) that the structure isn't holding.
2. **Creative Context specialist run** (the §5c write path) revises `act-structure` v[N]→v[N+1] **and emits an explicit act mapping** — renamed/merged/split/added/deleted acts; themes newly in or out of scope. The mapping artifact is the new contract this capability rests on.
3. A deterministic **migration step** consumes the mapping → re-mapped `tagged-quotes` + timeline versions. Nothing overwritten; lineage recorded in `pipeline-state.json` (`based_on` + staleness marks).
4. Optional incremental re-scan per tier 2, only when the mapping says new themes exist.
5. **Reconciliation in the viewer, not chat** (per Jeff's decide-in-edit-context rule): changed-act quotes flagged; newly relevant quotes land in the Library badged "new in v[N+1] structure"; timeline entries whose act was deleted enter a visible "needs a home" state rather than being dropped.

**Scoping note:** the migration tool (steps 3–5's data work) is deterministic Python with **no cloud dependency** — it can be built for local sessions whenever this scenario next bites, and carries into the SaaS unchanged. The one-chat version of the workflow lands with A3/Phase B (it needs dispatchable specialist runs). This scenario is also the flagship test case for the §5c write-gating rules: a structure revision is exactly the kind of mutation that must confirm, version-bump, and mark staleness rather than silently invalidate the working cut.

### 5e. Anytime feedback on agent work (requirement added 2026-07-02)

**Requirement (Jeff):** be able to comment on an agent's work **at any moment** — a note on a card, a proposal, a cut decision, a seam flag, or the session as a whole — with the feedback **durably recorded and applied to future sessions.**

**What exists today (the raw material):** the pipeline already has a learning loop — `tweak-log` captures Jeff's overrides implicitly, `review-notes.md` captures post-watch notes, `edit-agent-lessons` captures the agent's own retro, and the **Editing Coach (Step 5a) + Skill Review (Step 5b)** read all of it to propose SKILL-edit diffs (that's how "no spoken self-IDs" got promoted). What's missing is **explicit, in-the-moment capture**: today Jeff's judgment about *why* he overrode something is only recorded if he happens to say it in chat, and it's end-of-session batch, not point-at-the-thing.

**Design:**

- **Capture:** a "Comment on agent" affordance on every agent-produced element (agent notes, proposals, seam flags) plus a global feedback button in the top bar. Each comment records full context automatically: project, round, the entry/output it targets, the agent output as it stood, timestamp. No form-filling — Jeff types one sentence and moves on.
- **Storage:** a durable per-project feedback log — locally `handoffs/agent-feedback.json` (append-only), in the cloud a first-class `feedback` table.
- **Application, two speeds:**
  1. **This session:** the agent reads new feedback on its next turn (same channel discipline as `viewer-state.json`) and adjusts behavior immediately.
  2. **Future sessions:** the existing Coach/Skill Review path consumes the log — cross-project lessons promote into SKILL-edit (the established promotion pipeline); project-specific guidance is surfaced as *standing feedback* at the next session start. Each item carries a status (`new → applied / promoted / declined`) so feedback never silently evaporates.

**Scope:** the capture UI is cheap (a comment box writing rows) — **include it in Milestone 1**, even though no live agent reads it in the cloud yet: the log syncs down via `djed sync`, and the local Edit Agent + Coach consume it exactly like their existing inputs. The automated application loop rides with A3/Phase B. The local viewer could also gain this affordance ahead of the cloud if wanted — same JSON append, no cloud dependency.

### 5f. Full-pipeline interaction map — what actually needs live chat (added 2026-07-02)

**Context (Jeff):** the chat isn't just the Edit Agent. A session today starts with discovery (find + triage relevant documents), then transcription from audio, then the Creative Context review and act-structure proposal — all conversations currently spread across Cowork session windows, all of which must land in the web app. This section is the stage-by-stage audit of every human touchpoint (from the SKILL files + cowork-session-guide), classified by what UI it actually needs.

**The finding: interactions fall into four patterns, and only one of them is true chat.**

| Stage | Human touchpoints | Pattern |
|---|---|---|
| **Transcription (Step 0)** | Confirm/correct speaker names; run launcher; completion check | Structured choice + job progress. *In the cloud: audio upload → AssemblyAI job; the Terminal-launcher handoff disappears entirely.* |
| **Creative Context (Step 1)** | Discovery triage ("which docs should I ingest — 1, 2, 4 / all / skip"); **creative-brief review; act-structure proposal + iteration until explicit approval; roadmap review** | Doc triage = structured choice (checkbox list). Brief/structure/roadmaps = **TRUE LIVE CHAT** — the heaviest front-of-project conversation, multi-round by design. |
| **Orchestrator (Step 2)** | One plan confirmation ("here's the fan-out — proceed?"); then progress + validation reports | Structured choice (plan card + Proceed) + job progress. Sub-agents (Transcript ×N, FCPXML Params) are deliberately non-interactive in orchestrated mode. |
| **Synthesis (Step 3)** | Conditional stale-version warning (re-run stale tagger vs. proceed); validation report | Structured choice (conditional dialog) + status. |
| **Edit (Step 4a)** | Act-by-act live-partner loop: categorize/flag, over-inclusive build, continuous refine, export queueing | **TRUE LIVE CHAT** + shared viewer state (the M1 chat panel; already designed). |
| **FCPXML (Step 4b)** | Cut selection (loose/tight/both); build result or failure detail | Structured choice (export modal — already exists in the viewer) + job status. |
| **Editing Coach (Step 5a)** | Override-cluster conversations ("here's the pattern — why?"); SKILL-edit diff approvals | **TRUE LIVE CHAT** (reasoning capture) + structured diff-approval cards. |
| **Skill Review (Step 5b)** | Findings discussion; forward-looking idea intake; per-diff SKILL-file approval gate | **TRUE LIVE CHAT** + structured diff-approval cards. |

**The four UI patterns this reduces to:**

1. **One persistent per-project chat thread** (the §5c router chat) — carries the genuine conversations: Creative Context's brief/structure/roadmap iteration, the Edit loop, Coach reasoning, Skill Review discussion. One thread for the project's life, stage-aware, not one window per agent.
2. **Structured decision cards, rendered inside the thread** — doc triage checklists, speaker-name confirm lists, orchestrator plan cards, stale-state re-run/proceed dialogs, loose/tight export choice, diff approve/reject cards. Today these are prose questions in chat scrollback; as cards they're one-tap decisions with a recorded outcome. (This is Jeff's decide-in-context rule generalized: decisions presented in the form they're made in, not as chat menus.)
3. **A pipeline stage rail** (project home): Setup → Discovery → Transcription → Story structure → Tagging/Synthesis → Edit → Export → Review, showing each stage's state (pending/running/needs-you/done — driven by `pipeline-state.json`, which already encodes exactly this) with job progress for the autonomous stretches.
4. **Upload/file surfaces** — audio, caption XMLs, manual doc upload when Discovery connectors aren't available.

**Design consequence:** "migrating the Cowork sessions" does **not** mean rebuilding N chat windows in the browser. It means one thread + decision cards + a stage rail. The conversation-heavy stages (Creative Context, Edit, Coach, Review) are where the §5c routing agent earns its keep; the rest of the pipeline becomes *quieter* in the web app than it is in Cowork, because approvals and progress stop masquerading as conversation.

**Phasing:** unchanged — M1 ships the Edit-stage screen (viewer + chat panel). But the app shell (project home, stage rail, thread) should be *designed* now so M1's screen slots into it rather than becoming its own dead end. Upstream stages arrive with A2 (transcription + export jobs) and A3/Phase B (Creative Context conversation, orchestrated tagging, Coach/Review). **Next deliverable: a UI/flow mockup of the full app shell** — the project lifecycle from "new project" through export.

## 5b. Phase B Hard Boundaries (what keeps the pipeline local/hybrid)

1. **Raw media never leaves local volumes** — size, cost, and no pipeline stage needs it (settled + confirmed by Jeff's media decision).
2. **Final Cut Pro is local and human.** Import, multicam resolution against library/event UIDs, watching, finishing. The `fcpxml-params` file (library location, event UID, asset/angle refs) is the permanent contract between cloud-built XML and the local library — treat any change to it as a breaking change.
3. **Caption XML export from FCP is a manual local step** that feeds the cloud (A2 uploads). Until FCP has automation for this, a human on the Mac starts every project.
4. **The upstream pipeline stays session-driven until A3 proves the worker pattern.** Don't port Creative Context/Transcript/Synthesis to n8n before the Edit Agent worker has validated Claude-API orchestration + human-pause points on the stage that matters most.

---

## 6. Gaps & Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | **Scope creep in "Phase A"** — cloud viewer implicitly promising the live agent | High | Adopt the A1/A2/A3 split explicitly; A1's definition of done (§7) contains no agent. |
| 2 | **Dual-viewer drift** during hybrid (local build vs cloud app of the same 3.5k-line template) | High | Cloud becomes canonical at A1 ship; local build frozen as fallback; identical save contract; shared template source. |
| 3 | **No auth/versioning heritage** — current save path is unauthenticated, last-write-wins, non-atomic | High (in cloud) | Greenfield auth + optimistic version checks in the A1 API; never expose the raw file semantics. |
| 4 | **Python/JS duplicate logic** (interior-cut detection kept byte-equivalent by hand in `editcuts_to_segments.py` and the JSX) | Medium | Golden test fixtures shared by both; longer-term single implementation (server-side validation). |
| 5 | **Upstream data quality still open** — Transcript-stage collapsed-TC root cause unresolved (hardening A1); gate catches symptoms only | Medium | Keep `validate_timecodes.py` as a hard gate in the cloud upload/ingest path — bad TCs should be rejected at upload, not discovered at export. |
| 6 | **Interior-cut fidelity limitation** rides along to the cloud (`kept_ranges` schema extension deferred) | Low-Med | Carry the existing warnings (`_fidelity`, `fidelity_warnings[]`) into the cloud UI verbatim; schedule `kept_ranges` as a schema v6 item, cross-stage. |
| 7 | **n8n job runtime for Python** — Vercel functions aren't the place for `build_fcpxml.py`; n8n host must run the scripts (or a small container service) | Medium | Decide at A2 kickoff: n8n Execute-Command on its host vs. a one-container job runner. Either works; pick when A2 starts, not now. |
| 8 | **Clock/staleness assumptions** — pill logic compares timestamps from one machine today; cloud introduces multiple clocks | Low | Use DB version counters, not wall-clock comparisons, in the ported staleness logic. |
| 9 | **Engineering ownership** (START-HERE's open question b) | High | A1 is deliberately sized so one engineer (or a supervised Claude Code build) can ship it in ~1–2 weeks; don't start A2/A3 without a named owner. |

---

## 7. Prioritized Migration Path

**Milestone 1 (the smallest viable step) — "One project, in a browser, from anywhere":**
Stand up the Next.js app on Vercel with auth; port the viewer template to fetch project data from API routes; implement `/save`, `/read`, `/list` + project loader against Postgres; build `djed sync`; load **one real project** (e.g., epicor-rf-fager) via sync.
**Done means:** Jeff opens `https://<app>/p/epicor-rf-fager` on any machine, sees the current cut with agent notes and the ?-summary popovers, edits membership/trims, saves a named cut, **comments on any agent note via the feedback affordance (§5e) and the comment lands in the project feedback log**, **messages the agent from the in-viewer chat panel and gets a reply from the local Edit Agent session over sync (§5c scope note)**, exports `trimmed-quotes-…-tight.json`, syncs it down to the SSD, and the *unchanged local pipeline* builds a verify-PASS FCPXML from it.

Then, in order:

2. **Harden M1** — optimistic versioning, per-project authz, artifact history view, kill dual-viewer drift (local build frozen).
3. **A2: cloud export build** — caption XML + sample-timeline upload, n8n FCPXML job (with `validate_timecodes` gating ingest), `.fcpxml` + verify report downloadable. Add the transcription upload job here too.
4. **A3: server-side Edit Agent** — Claude API worker on n8n implementing SKILL-edit's loop against the DB-backed live channel; staleness pill semantics unchanged.
5. **Phase B proper** — port upstream stages (Creative Context → Orchestrator/Transcript → Synthesis) to n8n workflows one at a time, using `pipeline-state.json`'s schema as the queue contract it was designed to be. Includes the **mid-edit structure-revision workflow** (§5d) once specialist dispatch exists — though its deterministic migration tool can be built earlier, locally, if the scenario bites first. Media and FCP stay local; the boundary is the caption-XML upload (in) and the `.fcpxml` download (out).

**Decision this unblocks (START-HERE "next action"):** this document is option (a). The remaining open item is (b) — naming the engineering owner for Milestone 1.
