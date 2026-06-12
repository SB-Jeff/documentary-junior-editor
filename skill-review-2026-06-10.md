# Skill Review — 2026-06-10

**Scope:** full multi-agent skill system review — all SKILL-*.md files, README, cowork-session-guide.md,
quotes-viewer-roadmap.md, and the `scripts/` toolchain — against two questions:
(1) areas for improvement, (2) readiness to move from Cowork sessions to the
**storyboard-ops n8n + Claude API pipeline** (Phase 4).

**Method:** four parallel review agents (edit loop / fan-out stage / FCPXML stage / entry-exit + guide),
each reading its files in depth and cross-checking against the v5.9 master SKILL.md and the shipped
v5.9 viewer code. Findings synthesized and deduplicated here.

**Headline:** the architecture (versioned handoffs + `pipeline-state.json` spine) is the right shape
for the port, and ~70% of desktop pain evaporates online. But the claim at SKILL.md:193 — *"the skill
is identical in both worlds; only the orchestrator differs"* — does not hold today. Three generations
of the Edit Agent coexist in the repo, the state file is a completion ledger rather than a work queue,
and several silent-failure paths that a human catches in Cowork would sail through an automated pipeline.

**How to use this doc:** each finding is a checkbox with a triage tag, a severity tag, and file:line
citations. IDs (D1, C1, B1, …) are stable for cross-referencing. Suggested sequencing is in §12.

---

## Triage — added 2026-06-12

Filter applied: *"implement, then jump straight into the next editing session to test."* Tags:

| Tag | Meaning |
|---|---|
| **[NOW]** | Safe + valuable before the next session; the session itself is the test. |
| **[NOW\*]** | Do now, but in **modified form** — see the note on the item, not the original wording. |
| **[HOLD]** | Right change, wrong moment — restructure/feature work that needs its own project + shakedown run, not pre-session cleanup. |
| **[PORT]** | Defer until n8n port work actually starts. Zero Cowork benefit; some items add agent burden or break scripts if done early. |
| **[DECIDE]** | Needs Jeff's call before anyone implements anything. |
| **[LATER]** | Fine anytime, low priority — not in the pre-session set. |
| **[SKIP]** | Not worth doing. |

**The pre-session [NOW] set in one line:** doc reconciliation (D1–D11, C2–C4, C11–C12, O3/O6/O7/O9,
S4/S6/S7, P2/P3/P7/P8, F4, Q1), code fixes testable on fixtures (C1, C5, C7, C8, B3, B6), orchestrator
hardening (B4, B5, O1, O2), connector fix (F1), the two guardrails that stop the list regrowing
(S1, S2/W7), and the additive verify pass (W1) + W3 in its softened form.

**Explicit warnings:**
- **Q7 is a trap for the test plan** — envelope changes break `build_quotes_viewer.py` and
  `build_fcpxml.py` unless all three move in one coordinated commit. Port-prep work, not a quick fix.
- **Q10 / P1 / S3 / W2(C6)** are rewrites of battle-tested material — own project, fixture-verified,
  never slipped in the night before a session.
- **P4** is tagged SKIP deliberately: the Cardinal Rules repetition is a designed safety mechanism;
  the token cost only matters in the paid-per-call API world.

**See also §13 (capability audit, 2026-06-12):** new Claude Code features supersede or reshape
several findings — notably B4/B5/O1/O8 (Dynamic Workflows), F1/F2 (stable MCP naming, subagent
definitions), S1/S2 (hooks + plan mode), and much of the [PORT] set (headless mode + Agent SDK).
The [NOW] prose fixes are still worth doing — they're cheap and platform-independent — but check
§13 before investing in any [LATER]/[PORT] item the platform may now provide.

---

## 1. Version & documentation drift (systemic — highest priority)

The self-modification loop demonstrably leaks: several of these have been tracked as to-dos since
v5.1 without being executed. See §5 for the structural fix.

- [ ] **[NOW]** **D1 — HIGH. Three generations of the Edit Agent coexist.**
  `SKILL-edit-pipeline.md` is a v5.0 fossil (four-tier `runtime_recommendation`, :101-103, :153-155);
  `SKILL-edit.md` describes v5.7 (two-tier, :336-339, :712-743); the shipped viewer is v5.9
  (tight/loose membership — `build_quotes_viewer.py:354` *deletes* the `runtime_recommendation`
  field the skill instructs the agent to emit; migration map at :363-371). An Edit Agent following
  SKILL-edit.md emits and discusses a field the toolchain drops. Full divergence list in §7.4.
  *NOW scope: update SKILL-edit.md to the v5.9 membership model. The structural two-variant fix is
  Q10 [HOLD]; add a "stale — do not port from this" banner to SKILL-edit-pipeline.md in the meantime.*
- [ ] **[NOW]** **D2 — HIGH. README.md:40-59 teaches the dead git-crypt setup and inverts the migration.**
  Walks through `brew install git-crypt` + unlocking `secrets/assembly_ai.key` from Apple Passwords,
  then says `.env` "is being phased out in favor of git-crypt" — the exact opposite of
  SKILL.md:455-459 and :692-696. `secrets/` doesn't exist on disk. Worst onboarding trap in the repo;
  SKILL-transcription.md:437-439 has requested this fix since v5.1.
- [ ] **[NOW]** **D3 — HIGH. SKILL-edit.md describes a viewer that no longer exists.**
  Three-view claim incl. Review view (:557-559, :1102-1106) vs shipped two views Edit + Library
  (`quotes_viewer_template.jsx:1284-1287, 2136-2139`); "Rough/Tight sub-toggle" (:566-571, :725-731)
  vs shipped Tight/Loose membership toggle (jsx:22-23, :887-888, :1199-1203); Export described as
  invoking `build_fcpxml.py` (:584-589) vs shipped write-JSON + copy-launch-prompt behavior
  (jsx:879-918); CDN-based React/Babel/Tailwind required (:655-657, :1648-1650) vs shipped fully
  offline vendored build (`build_quotes_viewer.py:15-28`, jsx:111) — the skill still mandates the
  approach the blank-page fix removed; drag-from-handle-only (:562-563) vs whole-card pointer-event
  drag constrained within acts (jsx:736-744) while :1173-1175 claims cross-act reorder.
- [ ] **[NOW]** **D4 — MED. Version footers stale despite commit c456042 "bump SKILL footers":**
  SKILL-synthesis.md:511 says v5.4; SKILL-transcription.md:529 says v5.4 (and its closing note
  :531-532 contradicts SKILL.md:761-767 which marks that item RESOLVED); SKILL-orchestrator.md:415
  and SKILL-transcript.md:541 say v5.5; SKILL-edit.md footer v5.7; SKILL-edit-pipeline.md footer v5.0
  (:567-572); cowork-session-guide.md:2,486 say v5.7. If footers mean "last changed at," document that
  convention; otherwise sync them.
- [ ] **[NOW]** **D5 — MED. Agent-count wording wrong in three places.**
  SKILL-review.md:4,:32 "Ninth and final agent" vs SKILL.md:147 "ten agents"; SKILL.md:721 still says
  "across all eight agents."
- [ ] **[NOW]** **D6 — MED. README.md:141-153 SKILL-file table missing three agents**
  (transcription, orchestrator, editing-coach); its SKILL-review description (:153) is pre-v5.4 scope.
- [ ] **[NOW]** **D7 — MED. README.md:182-183 references `cowork-session-guide-restore.md` — file does not exist.**
- [ ] **[NOW]** **D8 — MED. README.md:95-103 instructs running `transcribe.py` directly,** bypassing the
  canonical `start-editing` launcher and its preflight (SKILL-transcription.md:69-84).
- [ ] **[NOW]** **D9 — MED. cowork-session-guide.md is two versions behind:** Step 5b starter prompt (:369)
  instructs the Skill Review Agent to do editorial-pattern analysis that SKILL-review.md:41-48,
  :659-662 explicitly moved to the Coach — the agent receives two conflicting briefs at launch.
  Guide also misses the v5.9 Creative Context deliverable format and Review Legibility sections.
  Note: the guide prompt's "propose them for my review" gate is *safer* than SKILL-review.md's
  actual flow — see S1.
- [ ] **[NOW]** **D10 — MED. Editing Coach written against the retired model.** SKILL-editing-coach.md:187-188
  four-tier vocabulary; Known Pattern `must-keep-as-workspace` (:291-302) prescribes a fix that
  shipped (tight/loose) but was never closed out; expects `trimmed-quotes-v[N]-tight.json` variant
  files (:130, :141-142) the viewer doesn't write; doesn't list `edit-agent-lessons-v[N].md` as an
  input despite SKILL-edit.md:1663-1671 saying Coach reads it first-class.
- [ ] **[NOW]** **D11 — LOW. Stale internal references:** SKILL-edit.md:1503-1505 "legacy viewer … until the
  Phase 3 follow-up template ships" (it shipped); jsx:18 header comment still claims three views;
  SKILL-review.md:391-392 hedges "if cowork-session-guide.md exists" (it does); SKILL.md:251-252
  tree still draws deprecated `secrets/assembly_ai.key`; `scripts/transcribe.py:38-46` still carries
  the legacy `storyboard-ops/file-api/.env` lookup SKILL.md:761-767 says to prune.
- [ ] **[SKIP]** **D12 — LOW. Folder-case mismatch:** SKILL.md:323 `xml/` vs guide:122-124 `XML/exports`/`XML/imports`
  vs SKILL-review.md:191 "`xml/` (or `XML/`)". Becomes a real bug on a case-sensitive online filesystem.
  *(Revisit at port time; harmless on macOS.)*
- [ ] **[SKIP]** **D13 — LOW. Three coordinate systems for the same pipeline:** guide Steps 0-5b, SKILL.md
  ten-agent diagram, SKILL-review ordinal ("ninth"). Pick one. *(Cosmetic.)*

## 2. Doc-vs-code drift — FCPXML stage

Six of the seven "OPEN" footer items are implemented; the docs still direct the agent to hand-patch
correct output. One item documented as fixed is NOT fixed.

- [ ] **[NOW]** **C1 — HIGH. Project-UID contradiction (the one that matters most).**
  SKILL-fcpxml-params.md:337-358 says the script "no longer copies `uid` or `modDate`… The script is
  correct." Code does the opposite: `generate_fcpxml.py:1102-1106` copies reference-project `uid` and
  `modDate` into every output — per the doc's own rationale (:343-349) this re-triggers the
  duplicate-multicam-on-second-import bug. Either the fix was reverted or never landed. Reconcile in
  code, then fix the doc. *Testable against `design-samples/` fixtures before the session.*
- [ ] **[NOW]** **C2 — HIGH. Single-clip support is implemented; docs say it isn't.**
  `build_spine()` branches per speaker (`generate_fcpxml.py:855-924`); `parse_params_md` reads Clip
  Types + Asset Refs (`build_fcpxml.py:325-364, 311-323`) and validates per-type (:375-414). But
  SKILL-fcpxml.md:531-539 still instructs a manual mc-clip→asset-clip post-process, footer item (2)
  (:663-665) lists branching as OPEN, and SKILL.md:769-771 says the script "supports only multicam."
  Delete the manual workaround instructions.
- [ ] **[NOW]** **C3 — HIGH. Caption-window narrowing is implemented; §2.3 workaround instruction still live.**
  `_tc_string_to_seconds` (`generate_fcpxml.py:119-164`), `_narrow_caption_search_window` (:167-223),
  wired through `find_captions_for_quote` (:291-354) and `build_spine` (:844-848). SKILL-fcpxml.md:469-492
  still mandates manual caption pre-trimming "on every long-interview project." Also: there is no
  function named `find_quote_range` anywhere — SKILL-fcpxml.md:489 and SKILL.md:777-778 cite a
  nonexistent symbol.
- [ ] **[NOW]** **C4 — HIGH. Params-parser mismatch is fixed; doc still says OPEN.**
  SKILL-fcpxml-params.md:252-271 and :430-444 are stale; the `os.path.basename()` issue is fixed by
  `_resolve_reference_file` (`build_fcpxml.py:254-290`) yet SKILL-fcpxml.md footer item (6) (:666-668)
  lists it OPEN. The "produce the handoff three times" redundancy (:256-261, :447-451) existed only
  for the old parser — now pure drift surface; collapse to one format.
- [ ] **[NOW]** **C5 — HIGH. Title-card offset-stacking bug confirmed still open (matches v5.9 escalation).**
  `generate_fcpxml.py:646-715`: gap-level offset advances (:674, :714) but inner title keeps hardcoded
  sentinels (gap start :674; title offset/start :681-683), and title duration `120120/120000s` (1.001s)
  exceeds the 0.67s gap (:684 vs :669) — the 1s→0.67s change (:662-664) never updated the duration.
  *Testable against fixtures; verify in FCP before the session if possible. Fix this BEFORE touching W2/C6.*
- [ ] **[HOLD]** **C6 — HIGH. v5 non-spoken entries are silently dropped.** SKILL-fcpxml.md:249-256 says
  title_card / interstitial / context_beat entries are generated; `build_fcpxml.py:703-724` drops all
  three with a stderr warning. Nothing tells the agent they'll be missing. Rendering these is the
  single biggest "script should own it" gap. *Same item as W2 — feature work in the same code region
  as C5; do after C5 is fixed and FCP-verified. NOW-sized interim: add one line to SKILL-fcpxml.md
  Phase 2/3 telling the agent these entries are currently dropped.*
- [ ] **[NOW]** **C7 — MED. `parse_act_structure` misses "Intro"/"Epilogue"/"Prologue"** — regex only matches
  `(?:Act|Part|Section)` (`build_fcpxml.py:794-797`). Interacts with the undocumented
  "Opening"→"Intro" rename at `generate_fcpxml.py:666`. *Small regex fix.*
- [ ] **[NOW]** **C8 — MED. Slug→label canonicalization gap.** `_canonicalize_section`
  (`generate_fcpxml.py:718-742`) does exact + substring only; `act-1-addie` vs `Act 1 — Addie` fails
  (punctuation not normalized). Same gap in `build_fcpxml.py:1016-1024`. *Small normalization fix.*
- [ ] **[DECIDE]** **C9 — MED. Act-boundary card guarantee not met.** SKILL-fcpxml.md:402-418 requires one card per
  act regardless; code emits only on section *change* of spoken quotes (`generate_fcpxml.py:824-831`)
  — an act with no spoken quotes gets no card; out-of-order part sequences (A→B→A) emit duplicates.
  Code comment at :821-824 ("exactly once per declared act") is false as written.
  *Jeff's call: should an act with no spoken quotes get a divider card, and what should A→B→A emit?*
- [ ] **[LATER]** **C10 — MED. single_clip attrs hardcoded, not sourced.** Doc says format/tcFormat/audioRole come
  from the captioned source (SKILL-fcpxml.md:359-363; params records them,
  SKILL-fcpxml-params.md:391-392); code hardcodes `NDF`/`dialogue`/sequence format
  (`generate_fcpxml.py:910-912`) and `parse_params_md` never reads those fields. Drop-frame sources
  silently mis-time. *Only bites on drop-frame sources — rare for this footage.*
- [ ] **[NOW]** **C11 — MED. Resource-remap location stale.** SKILL-fcpxml.md:396-398 points at
  `build_tccs_rough_cut_v1.py` (does not exist in repo); `merge_speaker_resources` is already in
  `generate_fcpxml.py:459-595`. Likewise :445 ("currently NOT handled") vs implemented
  library/event/uid pass-through (`build_fcpxml.py:1085-1088`, `generate_fcpxml.py:1077-1094`).
- [ ] **[NOW]** **C12 — LOW. Speaker-lookup description stale in both directions** —
  SKILL-fcpxml-params.md:243-250 says exact-dict lookup with fuzzy "parked"; code already has
  `_canonical_speaker` normalization (`generate_fcpxml.py:800-808`) and fuzzy fallbacks in
  `find_speaker_fcpxml` (`build_fcpxml.py:806-843`).
- [ ] **[LATER]** **C13 — LOW. Dead code: `generate_fcpxml.py` docstring (:6-18) and Excel-driven `main()`
  (:1155-1212) with hardcoded Epicor speakers; the openpyxl import at :22 is why the stub hack at
  `build_fcpxml.py:30-43` exists. Delete the dead path, delete the stub. *Safe anytime; zero behavior
  gain, so not pre-session churn.*

## 3. Silent-failure paths & live bugs

These matter doubly for the port: online, nobody is watching stdout.

- [ ] **[NOW\*]** **B1 — HIGH. Fuzzy caption matching silently truncates quotes — Cardinal Rule 1 risk.**
  Sentences with <2 normalized words return no match (`generate_fcpxml.py:237-238`); unmatched
  sentences are skipped without breaking the chain (:342); acceptance threshold 0.55 (:261). The clip
  plays *less than the verified verbatim text*; surfaced only as a stdout line, exit 0.
  *Modified form (see W3): loud warning + non-zero exit + `--allow-partial` override — NOT a hard
  fatal. Test against a reference-examples project before trusting it live.*
- [ ] **[NOW\*]** **B2 — HIGH. Speaker-key misses degrade to warnings with success exit.** `build_spine` skips
  unknown speakers (`generate_fcpxml.py:833-835`); 0-clip output is explicitly "not fatal"
  (`build_fcpxml.py:1106-1112`, exit 0); `EXIT_NO_CAPTION=4` (:56) is defined and never used. The
  only backstop is the manual Phase 3 clip-count check (SKILL-fcpxml.md:578-583). Root feed: the
  speaker name confirmed in chat at the very first human touchpoint becomes filename/slug/params key,
  and a one-character drift surfaces only as missing clips in FCP many sessions later (guide:476;
  validation step parked at SKILL-review.md:285-286, unbuilt). *Same modified form as B1/W3.*
- [ ] **[NOW]** **B3 — HIGH. Tight/Loose exports overwrite each other.** Both windows of the same round write
  the same `trimmed-quotes-v[N].json` (jsx:891-899) — silently clobbering, violating the system's own
  never-overwrite rule (SKILL-edit.md:1328-1329). Coach expects `-tight` variant files that never
  appear (D10). Real bug, not just doc drift.
- [ ] **[NOW]** **B4 — HIGH. Concurrent writers race on `pipeline-state.json`.** Every sub-agent updates the
  file (`SKILL-orchestrator.md:211, 243`) and all launch concurrently (:248-251, :367-369) —
  last-writer-wins; lost entries then fail the Orchestrator's own Phase 3 check 5 (:266-267) with no
  diagnosis path. Fix: single-writer rule (sub-agents return results; Orchestrator commits state) —
  cheapest high-impact change in this review.
- [ ] **[NOW]** **B5 — MED. Orchestrator validation is existence-only** (file exists, non-zero, four-file set,
  state updated — :260-267). Truncated/malformed JSON passes and fails one agent later, after Jeff
  was told the fan-out succeeded. Cheap fix: parse each `*-tagged-quotes-v[N].json` and assert
  non-empty `segments[]` (the Transcript skill already self-checks this at SKILL-transcript.md:453;
  the Orchestrator shouldn't trust it per its own rule at :262-263).
- [ ] **[NOW]** **B6 — MED. `find_speaker_fcpxml` substring fallback can bind the wrong interview** — first
  sorted hit on any name-token substring (`build_fcpxml.py:826-832`); shared surnames or short names
  ("Ben" matching "Reuben…") silently mis-bind. *Small fix: require unambiguous match or fail loudly.*
- [ ] **[LATER]** **B7 — MED. 23.98fps hardcoded throughout** (`generate_fcpxml.py:53-55, :153-155, :629-643,
  :667-669`); params extracts frame rate (SKILL-fcpxml-params.md:407) but nothing consumes it.
  Non-23.98 projects mis-time silently. *Only bites on non-23.98 projects.*
- [ ] **[NOW\*]** **B8 — MED. Two-writers concurrency on the live viewer.** SKILL-edit.md mandates artifact
  rebuild after every decision (:144-147, :595-607) while the viewer holds Jeff's *unsynced* pending
  tweaks (jsx:1270); a rebuild can clobber un-sent in-viewer edits, and "if chat and viewer disagree,
  the viewer is wrong" (:140) points the wrong way for this case. No section addresses it. Sharpest
  workflow risk in the Edit skill. *Modified form: do NOT build a locking mechanism — add a one-line
  rule to SKILL-edit.md: "before rebuilding the artifact, ask Jeff to send or discard pending tweaks."*
- [ ] **[LATER]** **B9 — LOW. `FractionTime.from_string` crashes on decimal-seconds attrs** (`int(s) * 24000`,
  `generate_fcpxml.py:46-47`) — `duration="35.5s"` raises ValueError.
- [ ] **[LATER]** **B10 — LOW. `_PARAM_SECTIONS` substring/order-dependent heading match**
  (`build_fcpxml.py:67-79, :146-153`) — missing "Reference FCPXML" section lets "reference" match
  "Format Reference"; surfaces later as FileNotFoundError.
- [ ] **[LATER]** **B11 — LOW. `start-editing` falls back to `pip3 install --break-system-packages`** into system
  Python (:89-93); key "validation" is length-only (:70-74) — a revoked key passes preflight.

## 4. Orchestration & sub-agent design

- [ ] **[NOW]** **O1 — HIGH. Transcript Agent cannot be a non-interactive sub-agent as written.**
  "Wait for Jeff's confirmation" (SKILL-transcript.md:119-125), "ask Jeff to confirm" speaker identity
  (:194), "present the full tagged list in chat" (:357) — but the Orchestrator runs it as a Task-tool
  sub-agent with no channel to Jeff (SKILL-orchestrator.md:177, :248-251). It stalls, guesses, or
  silently skips. :84-87's "instructions are identical either way" is the problem: the skill needs an
  explicit orchestrated-mode branch that suppresses interactive pauses.
- [ ] **[NOW]** **O2 — HIGH. Flat vs slugged path schema conflict.** SKILL-transcript.md uses flat `handoffs/`
  everywhere (:13-14, :213, :331, :391-457, :479); the Orchestrator's sub-agent prompt says
  `handoffs/[project-slug]/` (:202-213) but also "follow SKILL-transcript.md exactly" (:190);
  Synthesis has a real resolution procedure (SKILL-synthesis.md:66-87). A standalone Transcript run
  on a multi-project SSD writes flat and Synthesis reports the speaker missing. Same ambiguity in
  SKILL-edit.md (inputs flat :196-211; build writes slugged :545; Phase 6/7 save flat :650-651,
  :1331-1333) while Coach reads slugged (:120-153) and the viewer writes slugged (jsx:892, :1159).
  Give every skill the same directory-resolution block Synthesis has.
- [ ] **[NOW]** **O3 — MED. Orphan re-decomposition assigned to an agent forbidden to do it.**
  SKILL-transcript.md:411-413 names "the Synthesis Agent or a follow-up Transcript re-run" — Synthesis
  never alters text/segments (SKILL-synthesis.md:57-60, :238-241) and doesn't receive raw transcripts
  (:101-102). Only the re-run path is real; delete the false option. *One-line doc fix.*
- [ ] **[LATER]** **O4 — MED. Failure handling has no partial-state story.** No sub-agent timeout/hang handling
  (SKILL-orchestrator.md:257 assumes Task always returns); after a mixed batch, successful sub-agents
  already bumped versions — undefined state; "abandon and continue without" (:287-289) collides with
  Synthesis's speaker-completeness hard stop (SKILL-synthesis.md:159-162).
- [ ] **[PORT]** **O5 — MED. Cross-speaker version check unimplementable from cited outputs.**
  SKILL-orchestrator.md:294-301 wants per-output Creative Context version verification, but the
  tagged-quotes JSON (SKILL-transcript.md:334-375) is a bare array with no provenance fields. Same gap
  undermines Synthesis's check (:114-131). Fix: metadata envelope (speaker, version, based_on,
  schema_version) in the JSON — also what makes the DB migration clean. *Depends on Q7 — same
  coordinated-commit warning applies.*
- [ ] **[NOW]** **O6 — MED. Synthesis act-label-drift handling contradictory.** Phase 1.4
  (SKILL-synthesis.md:186-196) flag-don't-correct, no stop; quality check 5.5 (:424-427) requires zero
  drift; Synthesis can't re-tag (:57-58) — unsatisfiable with no resolution path. *Cheap doc fix:
  define the path (flag → ask Jeff → proceed-with-documented-exception).*
- [ ] **[NOW]** **O7 — MED. Transcript Agent told to calibrate "good quote selection" (:146-148) while forbidden
  to curate (:225-232);** also forces all N parallel sub-agents to each read every reference project —
  pure token cost at fan-out scale. *Cheap doc fix.*
- [ ] **[LATER]** **O8 — LOW-MED. Expected-count formula (4N+1, :271-277) defined only for first runs;** re-run
  scenarios (:333-353) never restate the math. Speaker discovery is one-directional — nothing checks
  the transcript inventory against the act-structure speaker list before fan-out (:113, :137-139 vs
  SKILL-synthesis.md:158-162).
- [ ] **[NOW]** **O9 — LOW. Orchestrator self-contradictory read instruction** (:119-121): "read on launch …
  you don't read the whole file." *Rides along with the other orchestrator edits.*
- [ ] **[LATER]** **O10 — LOW. Project slug can be established by two different agents** — Transcription Phase 0.5
  derives from folder name (SKILL-transcription.md:134-147); Creative Context asks Jeff
  (SKILL-creative-context.md:237-247). No reconciliation step if they disagree.
- [ ] **[LATER]** **O11 — LOW. No fallback when the highest version-set is incomplete** (crash mid-write) while a
  complete lower set exists — Synthesis just stops (:174-184).

## 5. Self-modification loop (Skill Review Agent)

- [ ] **[NOW]** **S1 — HIGH. No approval gate before skill edits land.** Phase 6 (SKILL-review.md:482-516)
  edits "surgically" with no show-diffs-first requirement; Phase 8 syncs to master; "Notifying Jeff"
  (:615-630) happens *after* save + sync. The only "propose for my review" language lives in the
  stale guide prompt (D9). Add a mandatory present-diffs → approve → apply step.
- [ ] **[NOW]** **S2 — HIGH. No mechanical drift lint.** Every leak in §1 (stale footers, agent counts, ghost
  files, README) would be caught by a ~20-line CI/lint script: grep version footers, agent-count
  strings, referenced-file existence, dead symbol names. Run it as part of Skill Review Phase 6 and/or
  pre-commit. *(= W7.)*
- [ ] **[HOLD]** **S3 — MED. Phase 8 sync is file-copy between two clones, not git** (:588-605) — can clobber
  edits pulled from another Mac; git already solves this; the procedure routes around it. *Changing
  the multi-Mac sync flow right before a session risks confusion — own change, done deliberately.*
- [ ] **[NOW]** **S4 — MED. Push uses `git add -A`** (:644) from a folder that may contain stray artifacts;
  the better `commit-skill-changes` helper (guide:400-415) is never mentioned by the file that owns
  the push step. *Cheap doc fix.*
- [ ] **[DECIDE]** **S5 — MED. Phase 7 commits raw client interview transcripts to GitHub** (:520-531) — PII /
  contractual exposure, doubly so when the knowledge base becomes server-hosted. Add a
  consent/redaction checkpoint. *Jeff's call: do client transcripts belong in the repo at all?*
- [ ] **[NOW]** **S6 — MED. Ambiguous authority branch:** fallback chain (:110-134) lets editorial lessons be
  applied to SKILL-edit.md "directly if Jeff directs it" despite :499-502 declaring it Coach
  territory. *Cheap doc fix.*
- [ ] **[NOW]** **S7 — LOW. "May update" list (:484-497) omits SKILL-orchestrator.md and
  cowork-session-guide.md** — no agent owns updating either, which is plausibly why the guide is two
  versions stale. Skill edits are never tested (next paying project = regression suite); no rollback
  procedure beyond git. *Cheap doc fix for the ownership gap; the testing question is a PORT-era topic.*

## 6. Prompt-engineering hygiene

- [ ] **[HOLD]** **P1 — MED. SKILL-edit.md is 1,723 lines; Phase 3 alone ~430 lines with 8+ named patterns
  inlined.** Late-file rules (Phase 5 trimming principles :1198-1257) are the most likely to be
  dropped by a long-context model. Extract a referenced patterns library; it also gives the Coach's
  three-occurrence promotions a clean landing place. *Rewrite of the most battle-tested file —
  own project with a shakedown run, never pre-session cleanup.*
- [ ] **[NOW]** **P2 — MED. Correction-by-appendix.** SKILL-creative-context.md Phase 3: :444-459 prescribes a
  six-dimension roadmap; the v5.9 patch at :461-476 then overrides it to one-line + bullets. A model
  reading top-down plans the wrong deliverable first. Rewrite in place; format rule first. (Same
  pattern risk anywhere v5.9 patched by appending.)
- [ ] **[NOW]** **P3 — MED. Three near-synonymous dispositions** — never-add (:731-737), demote (:1136-1139),
  drop — distinguished only by adjectives, and the demote path no longer exists under tight/loose.
  Redefine against the membership model. *(Part of the D1/D3 SKILL-edit.md update.)*
- [ ] **[SKIP]** **P4 — LOW. Cardinal Rules boilerplate on agents it doesn't constrain** — ~27-29 prime-position
  lines on Transcription (:25-51) and Orchestrator (:51-79) to conclude "not applicable." Keep the
  two-line pointer, cut the essay; in the API world this is paid-per-call weight. *Deliberate SKIP:
  the repetition is a designed safety mechanism; token cost only matters post-port. Revisit then.*
- [ ] **[LATER]** **P5 — LOW. SKILL.md devotes ~37% (lines 528-844) to version history** that every agent reads
  first (:18-19). Move history to CHANGELOG.
- [ ] **[LATER]** **P6 — LOW. Duplicated blocks in SKILL-edit.md:** auto-scroll described twice (:588-592,
  :636-641); Rule 2 timing explained three ways (:61-68, :1372-1391, :1707-1714).
- [ ] **[NOW]** **P7 — LOW. `entry_id` namespace self-contradiction:** :326-331 retires `e_NNN`, then every
  example in the same file uses it (:389, :435-463, :928, :969, :984-989, :1263, :1547-1607). Viewer
  uses the `"1"/"1a"` form (jsx:79). Fix the examples. *(Part of the D1/D3 SKILL-edit.md update.)*
- [ ] **[NOW]** **P8 — LOW. Mid-segment-cut exception missing from the absolutes:** :405-409 prohibition,
  :410-424 documents `_editCuts` as accepted practice, but the "never do" list (:1189-1196) and the
  pipeline variant (:402-406, "server rejects") carry no exception. *(Part of the same update.)*
- [ ] **[LATER]** **P9 — LOW. Magic strings / inference dependencies:** unversioned `review-notes.md` with round
  attribution "from context" (:209-211, SKILL.md:344); brief-language watchwords depending on exact
  upstream phrasing (:221-230); model IDs hardcoded in frontmatter + a dozen prose spots (single-source
  them); supported audio extensions disagree across SKILL-transcription.md:91-92 (`.mp3 .wav .m4a
  .mov .mp4`) vs start-editing:101 (`mp3 wav m4a aac flac`) vs guide:153-159.
- [ ] **[PORT]** **P10 — LOW. `run_script(...)` pseudo-tool** (SKILL-fcpxml.md:496-517) — Agent-SDK-style call
  the desktop agent must reinterpret as Bash every run. Pick per-runtime wording (or fix via the
  shared-core restructure, §7.4).

## 7. Schema & data-model gaps (port-blocking)

### 7.1 pipeline-state.json — completion ledger, not work queue

The n8n claim (SKILL.md:191-193, :516-521) is made against a schema that can't support it yet:

- [ ] **[NOW]** **Q1 — HIGH. Type contradiction:** `based_on.transcript` is the string `"all-current"` in the
  master example (SKILL.md:207) but a `{speaker-slug: version}` map in Synthesis
  (SKILL-synthesis.md:138-140, :454-455). A machine consumer breaks on one. (The map is right; fix
  the master.) *One-line fix — the only Q item worth doing now.*
- [ ] **[PORT]** **Q2 — HIGH. No work-queue semantics:** no `status` (queued/running/failed/blocked), no error
  records, no attempts/leases. Only successful completions are recorded; failure state lives in chat
  ("report to Jeff and wait," SKILL-orchestrator.md:281-292). A resuming orchestrator can't
  distinguish "never ran" from "ran and failed." *In Cowork, Jeff IS the work queue — adding this now
  is pure agent burden.*
- [ ] **[PORT]** **Q3 — MED. Schema doesn't cover the pipeline it would queue:** no orchestrator (written anyway
  per SKILL-orchestrator.md:310-323, with novel fields), no editing-coach, no review entries;
  `dependencies` map (SKILL.md:212-219) missing the same nodes; `schema_version` still 1, no
  migration story. Inconsistent entry shapes within the master example itself (some carry
  `outputs`/`last_run`, per-speaker entries don't).
- [ ] **[PORT]** **Q4 — MED. `"stale": []` is never specified** — no writer, no element shape, no computation
  rule. Staleness is recomputed conversationally per agent and resolved by asking Jeff; those
  decision policies must become explicit rules for automation.
- [ ] **[PORT]** **Q5 — MED. Version assignment is decentralized and racy** — each agent self-increments to "next
  unused N" by reading disk (SKILL-transcript.md:386-388; SKILL-synthesis.md:138, :268-269). A queue
  should assign versions.
- [ ] **[PORT]** **Q6 — Action: publish a JSON Schema** (bump schema_version), add the missing agents + edges,
  pick the map form, define or delete `stale`, add status/error/attempts, adopt the single-writer
  rule (B4) — or move state to a transactional store, which fixes the race for free.

### 7.2 Handoff JSON provenance

- [ ] **[PORT]** **Q7 — HIGH. Tagged-quotes JSON has no envelope** — no speaker slug, version, based_on, or
  schema_version inside the file; identity lives in the filename (O5). Add a metadata envelope; it's
  also the cleanest path to DB-backed storage. *⚠ TRAP for the implement-then-test plan: changing
  bare array → envelope object breaks `build_quotes_viewer.py` and `build_fcpxml.py` unless all three
  move in ONE coordinated commit with fixture tests. Do as dedicated port-prep work.*
- [ ] **[PORT]** **Q8 — MED. Known unsettled bits:** `segments[].idx` "local to the quote" stated only in
  Synthesis (:236-237); orphans markdown-only while the viewer track wants `is_orphan:true` JSON
  entries (quotes-viewer-roadmap.md:547-551); `source_quote_id` int-vs-string unsettled (:552-554).
  *Decide alongside Q7.*

### 7.3 Params/completeness contradictions

- [ ] **[DECIDE]** **Q9 — MED. Params completeness check #2 contradicts the collision lesson:**
  SKILL-fcpxml-params.md:466-468 requires no duplicate media ref IDs across speakers; per-speaker
  exports routinely share `r2`/`r3` (SKILL-fcpxml.md:380-385) — the whole reason
  `merge_speaker_resources` exists. An obedient Params Agent stops on every normal project.
  *Almost certainly "relax the check" — confirm, then it's a one-line NOW fix.*

### 7.4 SKILL-edit.md vs SKILL-edit-pipeline.md — the failed delta-file contract

The pipeline variant claims "editorial substance identical … only deltas" (:19-23) but froze at v5.0.
Porting from it today loses: tight/loose membership (resurrects four-tier), Cardinal Rule 2's formal
status + proposal-time verification, mid-segment cuts/`_editCuts`, the tweak/override log (the
Coach's primary input — the Coach loop doesn't exist in the pipeline runtime), `edit-agent-lessons`
emission, and every v5.1-v5.7 editorial pattern (section pointers reference headings since rewritten).

- [ ] **[HOLD]** **Q10 — HIGH (structural). Extract the runtime-independent editorial core** (Cardinal Rules,
  data model, phases, patterns, verification) into one shared file with two thin runtime adapters
  (Cowork artifact mechanics vs server tool surface). Nothing currently forces the variants to move
  together; this is effectively a prerequisite for the port. The pipeline variant's tool-surface
  design (server-owned state, delta ops, validation at the tool layer — :48-52, :111-198) is the
  right architecture to keep — re-synced to v5.9. *Own project, fixture-verified, with a shakedown
  session — a botched extraction silently loses v5.4–v5.7 editorial learning. Interim NOW measure:
  the "stale — do not port from this" banner on SKILL-edit-pipeline.md (see D1).*

## 8. Fragile / manual steps (Cowork-today improvements)

- [ ] **[NOW]** **F1 — HIGH. Hardcoded MCP connector-instance UUIDs** in SKILL-creative-context.md:127-134
  (`mcp__28a0f4cc-…`, `mcp__76ba9669-…`). Per-install; the Gmail UUID already resolves to nothing on
  this machine. Name the capability, not the tool string.
- [ ] **[SKIP]** **F2 — HIGH. ~7+ manual session transitions per project** with by-hand model selection
  (footers throughout; guide:163-369). Nothing detects a wrong model — an Edit round on Sonnet just
  produces quietly worse output. *The port solves this natively; interim machinery is wasted effort.*
- [ ] **[LATER]** **F3 — MED. Host transcription loop has no machine-readable completion signal**
  (SKILL-transcription.md:308-312 "wait; don't poll") — agent depends on Jeff pasting Terminal
  output. Launcher should write a status JSON the agent reads.
- [ ] **[NOW]** **F4 — MED. Save-helper dependency undocumented:** the viewer's tier-2 persistence requires
  Jeff to manually run `python3 scripts/viewer_save_server.py` (CHANGELOG v5.9 P1); no SKILL file
  mentions starting it. SKILL-edit.md:573-577, :618-627 still describe tier-1-only. *Cheap doc fix;
  directly improves the next session.*
- [ ] **[SKIP]** **F5 — LOW. Discovery seeding typed twice** (chat + launch-prompt placeholders,
  SKILL-creative-context.md:135-137 vs guide:191).
- [ ] **[SKIP]** **F6 — LOW. Output filename decision is 3-way ambiguous** (SKILL-fcpxml.md:284-294, :308-311).
  *Live with it; the port's structured outputs dissolve it.*
- [ ] **[DECIDE]** **F7 — LOW. Mid-quote zero-duration TC verification "against the source audio"**
  (SKILL-fcpxml.md:457-464) — unactionable as written in any environment; needs script support or
  deletion. *Jeff's call: build it or delete it (deletion is the cheap honest option).*

## 9. Portability — environment-dependency catalog (target: storyboard-ops n8n + Claude API)

*(Reference analysis, not a checklist — consult when port work starts.)*

| Dependency | Where (representative) | Port difficulty |
|---|---|---|
| Host-side `start-editing` launcher + network-allowlist workaround | SKILL-transcription.md:10-15, 69-84, 285-334; start-editing; SKILL.md:686-691 | **Easy — deletes itself.** Server calls AssemblyAI directly. New constraint: multi-GB audio upload. |
| `.env` per-Mac key (+ dead fallback paths) | transcribe.py:25-48; start-editing:56-74; SKILL.md:455-459 | **Easy** — server secret store. |
| ffmpeg-in-sandbox video conversion | SKILL-transcription.md:217-234 | **Easy** — server ffmpeg, or skip (AssemblyAI accepts video). |
| Full Disk Access / SSD bind-mounts / virtiofs volume naming | SKILL.md:447-453; guide:51-65, 97-103, 452 | **Easy (removal)** — concept disappears. |
| 45s shell timeout (shaped §2.3 workaround) | SKILL-fcpxml.md:476, 546-547 | **Easy** — server jobs; code fix already exists (C3). |
| Manual git pull/push, multi-Mac sync, skill-copy-per-project | SKILL.md:428-445; SKILL-review.md:572-656; guide:15-41, 394-441 | **Medium — net simplification.** Becomes deploy/versioning of prompt assets; Phase 8 apparatus deletes itself. |
| Session-per-agent + copy-paste prompts + manual model choice | every handoff footer; SKILL.md:501-514 | **Easy-Medium.** API `model` param + orchestration replaces footers; rewrite footer language everywhere; single-source model IDs. |
| Task-tool parallel sub-agents (Orchestrator) | SKILL-orchestrator.md:177, 248-251, 367-369 | **Medium.** n8n/queue workers replace it natively — SKILL-orchestrator.md largely becomes workflow config, not a prompt. Most environment-coupled file. |
| Filesystem as inter-agent bus (`handoffs/`, glob + highest-version discovery) | all Required Inputs/emit sections (~40 sites) | **Medium.** Maps cleanly to object store/DB, but every read/emit section needs the storage-abstraction rewrite; identity should move from filenames to envelopes (Q7). |
| `pipeline-state.json` mutable shared file, concurrent writers | §7.1 | **Easy and an upgrade** — DB row + transactions fixes B4 free. Schema work in Q1-Q6 first. |
| Drive/Gmail MCP discovery (hardcoded UUIDs) | SKILL-creative-context.md:120-199 | **Medium** — server-side OAuth APIs; abstract tool names (F1). Manual-upload fallback already written (:185-191). |
| Cowork artifact loop (`update_artifact`, `callMcpTool` bash bridge, clipboard transport) | SKILL-edit.md:144-147, 553-634; jsx:309-349, 1106-1174 | **Medium-Hard.** In the web app the viewer becomes the app — which is what SKILL-edit-pipeline.md designs for; needs Q10 first. Clipboard/sendPrompt sections invert into real message channels. |
| Localhost save helper (127.0.0.1:8765) | jsx:336-349; CHANGELOG v5.9 P1 | **Hard as-is** — replaced by the web app's real backend save API; `persistFile()` tiers give the insertion point. |
| Agent told to open multi-MB FCPXMLs for verification | SKILL-fcpxml.md:572-583 | **Medium** — must move into `build_fcpxml.py --verify` emitting a JSON report (plumbing half-exists at build_fcpxml.py:888-915). Doesn't survive API context limits. |
| `.fcpxmld` directory packages | SKILL-fcpxml.md:143-211; extract_fcpxml.py | **Medium** — server extraction trivial; browser dir/zip upload UX needed; ingest normalization makes Phase 0 disappear. |
| `file:///` library location + event UID matching Jeff's Mac | SKILL-fcpxml-params.md:325-336, 470-473 | **Easy to carry, impossible to verify server-side** — user-confirmed metadata + verify-after-import loop. |
| Final Cut Pro + .fcpbundle + raw media — the last mile | SKILL.md:346; guide:107-137, 335-337 | **Hard / irreducible.** Pipeline ends at "download .fcpxml," resumes at "upload review notes / captioned exports." Design the seam explicitly; longer feedback loop raises the value of fixing C1/C5 in code first. |
| Human-in-the-loop pauses (speaker confirm, act approval, watch loop, stale-state decisions) | SKILL.md:153-165; throughout | **Easy-Medium mechanically** (n8n wait nodes + notifications), but every "ask Jeff" decision policy must be made explicit first (Q4). |

**Net read:** Transcript, Synthesis, Params, and the FCPXML generation core are mostly portable —
read→think→write logic that maps 1:1 to storage + DB. The genuinely hard residue: (a) the Edit
surface (Q10 + backend persistence), (b) the FCP seam, (c) moving file-opening verification into
scripts.

## 10. Guide-only knowledge — extract before any port

Verified present ONLY in cowork-session-guide.md (a port consuming SKILL files drops these).
All tagged **[LATER]** — safe doc moves anytime; required before port kickoff.

- [ ] **[LATER]** **G1.** Pre-pipeline "Media Agent" requirements (guide:128-137): footage ingest, FCP library
  events, multicams built + audio-synced, audio exports, captioned FCPXML exports, sample XML. The
  term exists nowhere else — the pipeline has unstated upstream preconditions. → SKILL.md.
- [ ] **[LATER]** **G2.** Behavioral-drift remedies / prompt-repair playbook (guide:444-483): first-pass-too-short,
  quote abbreviation, artifact-not-updating, stale-state both-options protocol. → platform-neutral ops
  doc or the relevant SKILLs.
- [ ] **[LATER]** **G3.** FCPXML symptom→cause→fix diagnostics (guide:472-480): silent speaker-drop symptom,
  `r2` collision + alphabetical high-water remap, `<media uid>` stability for multicam re-import,
  TC-fallback slowness. → SKILL-fcpxml.md troubleshooting section.
- [ ] **[LATER]** **G4.** Quick Reference matrix (guide:377-390) — only single view of step × model ×
  collaboration weight × key output, incl. the between-rounds Coach row and `coach-briefing-v[N].md`
  (named nowhere else). → SKILL.md.
- [ ] **[LATER]** **G5.** Full project-folder tree with `cache/`, `client media/`, `media/` flat rule,
  `XML/exports` vs `XML/imports` (guide:107-126) — differs from SKILL.md:321-347's smaller tree.
  Reconcile.
- [ ] **[SKIP]** **G6.** Cowork-only mechanics fine to leave in the guide (rewrite per environment): SSD volume
  naming, remount behavior, launcher extension contract (`.aac`/`.flac`, pre-convert video),
  `commit-skill-changes` workflow, `Icon?` cleanup, git freshness recipe.

## 11. Pre-port script work (biggest leverage, environment-independent)

- [ ] **[NOW]** **W1.** `build_fcpxml.py --verify`: per-speaker clip_type sanity + per-entry segment clip
  counts → JSON report (replaces SKILL-fcpxml.md:572-583 manual phase; B1/B2 backstop). *Purely
  additive — safe.*
- [ ] **[HOLD]** **W2.** Render title_card / interstitial / context_beat entries (C6). *After C5 is fixed and
  FCP-verified — same code region.*
- [ ] **[NOW\*]** **W3.** Make verbatim truncation and speaker-drop loud: non-zero exit (use the defined
  `EXIT_NO_CAPTION`) + prominent warning + explicit `--allow-partial` override (B1, B2). *Softened
  from "fatal-by-default" — a hard fatal could brick FCPXML generation mid-session on a harmless
  two-word sentence. Test against a reference-examples project first.*
- [ ] **[LATER]** **W4.** `--summarize` mode for cut selection counts/runtime estimate (the ask-Jeff step stays
  human; SKILL-fcpxml.md §1.6).
- [ ] **W5.** *(Split — see individual items:)* C1 **[NOW]**, C5 **[NOW]**, C7 **[NOW]**, C8 **[NOW]**,
  C10 **[LATER]**, B7 **[LATER]**.
- [ ] **W6.** *(Split:)* B3 export filename collision **[NOW]**; F3 launcher status JSON **[LATER]**.
- [ ] **[NOW]** **W7.** Drift lint script (S2) + wire into Skill Review Phase 6 / pre-commit.

## 12. Suggested order of operations

1. **Pre-session [NOW] pass** *(triaged 2026-06-12 — this is the implement-then-test set).*
   Docs: D1–D11, C2–C4, C11–C12, O3/O6/O7/O9, S4/S6/S7, P2/P3/P7/P8, F4, Q1, plus the
   SKILL-edit-pipeline "stale" banner. Code (fixture-test first): C1, C5, C7, C8, B3, B6, W1,
   W3 (softened form). Orchestrator: B4, B5, O1, O2. Connectors: F1. Guardrails: S1, S2/W7.
   B8 as the one-line rule. Pending decisions to unblock more: C9, Q9, S5, F7.
2. **Next editing session = the regression test.** One fan-out, several edit rounds, several FCPXML
   builds exercise exactly this set. Log anything that misbehaves against the finding IDs.
3. **[HOLD] projects, each with its own shakedown:** Q10 shared editorial core + runtime adapters
   (re-synced to v5.9), P1 patterns-library extraction, W2/C6 non-spoken entry rendering, S3 sync flow.
4. **[LATER] cleanup batch** whenever convenient: C10, C13, B7, B9–B11, O4, O8, O10, O11, P5, P6,
   P9, F3, W4, G1–G5 (G extraction becomes mandatory at port kickoff).
5. **Port kickoff ([PORT] set):** Q2–Q8 (state schema, envelopes — coordinated commits with script
   updates), O5, P10; then wire n8n — at which point SKILL-orchestrator.md mostly becomes workflow
   config, the pause points become wait-nodes + notifications, and the FCP seam is an explicit
   download/upload boundary.

---

## 13. Capability audit — 2026-06-12 (new Claude Code features since the system was designed)

*Verified against live Claude Code docs (current to 2026-06-09) and changelog (through v2.1.129+),
not training data. This fulfills the SKILL-review.md Phase 3 capability-audit mandate for this cycle.
IDs N1–N8 for cross-referencing.*

The system was designed Dec 2025–Jan 2026 around constraints that no longer exist. The Orchestrator
Agent (v5.5) — built to avoid launching one session per transcript — is the pattern the platform has
since absorbed natively.

- [ ] **N1 — Dynamic Workflows (v2.1.154+). Supersedes most of SKILL-orchestrator.md.**
  Claude Code can run a JavaScript orchestration script: deterministic fan-out of subagents (up to 16
  concurrent), **structured-output schemas enforced per agent**, results collected in script variables
  outside the conversation context, resumable within a session. Saved workflows live in
  `.claude/workflows/` and accept args. Mapping to findings:
  - **B4 (state-file race)** — solved structurally: the script is the single writer; sub-agents
    return results, the script commits `pipeline-state.json` once.
  - **B5 (existence-only validation)** — solved structurally: schema validation rejects malformed
    tagged-quotes JSON at the tool layer instead of one agent downstream.
  - **O8 (expected-count math)** — becomes an assertion in code, not a Nanos anecdote in prose.
  - **O4 (partial-failure story)** — improves: failed agents return null; the script decides
    retry/report explicitly.
  - Re-run patterns ("just Alice," "params only") become workflow **args**, not prose scenarios.
  *The [NOW] prose fixes for B4/B5/O1 are still worth doing — cheap, and they protect the manual
  fallback path — but don't over-invest in orchestrator prose the workflow will replace.*
- [ ] **N2 — Custom subagent definitions (`.claude/agents/*.md`). Supersedes F2's core; gives O1 a
  cleaner fix.** Each pipeline agent becomes a definition file with `model:` **enforced by the
  harness** (not read from frontmatter by a human), `tools:` allowlists, `background: true`,
  optional `memory: project`, per-agent hooks, and `isolation: worktree`. For O1: the subagent
  definition *is* the non-interactive variant — interactive SKILL files stay as-is for manual runs;
  the agent definition carries the no-pauses behavior. No "orchestrated mode" branch needed.
- [ ] **N3 — First-class skills (`.claude/skills/`, slash-invoked, auto-discovered).** The SKILL-*.md
  files are skills by convention ("read this file first"); converted to real skills they're invoked
  as `/creative-context` etc., auto-discovered with live change detection, and can be preloaded into
  subagents (`skills:` field). The "Next agent + model + launch prompt" footers — among the most
  fragile seams in the system — stop being load-bearing. Frontmatter supports `name`, `description`,
  tool allow/deny, `context: fork` (model lives on subagent definitions, N2, not skills).
- [ ] **N4 — Hooks. Turns S1 and S2 from discipline into enforcement.**
  - **S1 (approval gate):** a `PreToolUse` hook matching Edit/Write on `SKILL-*.md` blocks
    unapproved skill edits (exit code 2 = blocked); or run Skill Review in **plan mode** — propose
    diffs, Jeff approves, then it executes.
  - **S2/W7 (drift lint):** the lint runs as a Stop or pre-commit hook — version footers, agent
    counts, dead file references checked mechanically on every cycle, so the §1 drift class cannot
    silently re-accrue.
  - `SubagentStart`/`SubagentStop` hooks can validate fan-out outputs as they land (reinforces B5).
- [ ] **N5 — Headless mode + Agent SDK. Reshapes the [PORT] set.**
  `claude -p` now has `--resume`, `--json-schema` (enforced output), `--output-format json`; the
  Agent SDK (Python/TS) provides sessions, subagents, skills, MCP, file handling, structured outputs,
  and memory out of the box. **From 2026-06-15, headless/SDK usage draws from a separate Agent SDK
  credit bucket** (not interactive limits). Port implication: instead of n8n + raw Claude API
  (rebuilding session/tool/file plumbing), n8n nodes call headless Claude Code or the SDK and run
  *the same skill + agent definitions* the Cowork workflow uses. This makes SKILL.md:193's
  "identical in both worlds" claim achievable, and shrinks Q2–Q6's scope (much of the work-queue
  machinery comes from the SDK session model rather than hand-built state). Re-scope the [PORT]
  items against the SDK before building anything.
- [ ] **N6 — Stable MCP server naming + project-scoped `.mcp.json`. Fixes F1 at the platform level.**
  Per-install UUID tool names (the `mcp__28a0f4cc-…` problem in SKILL-creative-context.md:127-134)
  are replaced by stable server names referenced in `.mcp.json` (project root) or `~/.claude/.mcp.json`.
  The F1 [NOW] fix should write capability-style names and note the `.mcp.json` path.
- [ ] **N7 — Checkpointing + `/rewind`.** Session-turn snapshots with rewind — a recovery path for
  the self-modification loop beyond git archaeology (complements S1/S6; doesn't replace the gate).
- [ ] **N8 — Background agents / forked subagents.** `background: true` agents and Ctrl+B
  backgrounding suit the long transcription runs (pairs with F3's status-JSON idea).

**The Cowork caveat:** these are Claude Code features; the pipeline currently runs in Cowork desktop
sessions. The non-interactive stages — fan-out, Synthesis, FCPXML — could move to Claude Code today
and gain all of the above, including **no sandbox network allowlist** (the `start-editing` AssemblyAI
launcher workaround stops being necessary at all). The Edit Agent is the exception: the live HTML
artifact workflow is Cowork-specific. Realistic target shape: **hybrid** — Cowork for the
collaborative edit rounds, Claude Code (eventually headless under n8n) for everything around them.

**Suggested pilot (after the next session, not before — same don't-destabilize logic as the HOLD
items):** convert the Step 2 fan-out to a saved workflow + agent definitions (N1+N2) on a real
project. It's the lowest-risk stage to pilot (outputs are fully validated by Synthesis anyway), it
natively exercises the B4/B5/O1 fixes, and it's the dress rehearsal for the n8n-calls-headless
architecture (N5).

---

*Produced by a four-agent parallel review on 2026-06-10; triage tags added 2026-06-12 against the
"implement, then test in the next editing session" filter; §13 capability audit added 2026-06-12.
Line numbers reference the repo state at commit c456042 (v5.9). Re-verify line refs after any edits.*
