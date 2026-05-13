# Lessons Learned — TCCS Dr Pan & Testimonials
## Completed: 2026-05-13
## Project Type: Customer Testimonial
## Subjects: 2 — Lynette Wiest (patient, primary) + Dr. JD Luck (practitioner, supporting)
## Clip types: multicam (both speakers)
## Total rounds (Edit Agent): 1 (skip-to-FCPXML; no Discussion / Reduction)

### Project Summary

A ~2-minute patient testimonial for Twin Cities Cosmetic Surgery, framed
around facial rejuvenation. Lynette — cancer survivor disappointed by prior
plastic surgeons — finds Dr. Luck and undergoes a transformation. Dr. Luck's
practitioner voice interleaves through Acts 2 and 3 as supporting context.
The brief explicitly framed this as a beauty / confidence story with
survivor's stakes, not a cancer story. Two transcripts (Dr. Kristin Pan, Erin)
were tagged out of scope at the Creative Context phase.

### Act Structure

Three acts: "Who Is That?" → "Truly Cared" → "A Lifesaver". Approved at v1,
held through pipeline without revision. Act labels survived into the rough
cut as title cards (editing aid) and were stripped at finishing per workflow
rule (the surviving "A Lifesaver" card in the final delivery was an
oversight, not a stylistic choice).

### What Worked Well

- The Cardinal Rule held cleanly. All 7 trims were word-level head-trims of
  their source segments. No tail trims, no mid-cuts, no paraphrasing.
- Front-trim default established by the `facial-rejuvenation` reference was
  reaffirmed — every trim removed throat-clearing ("So", "Yeah, so", "Like,
  you know, yeah, he"), no exceptions.
- Edit Agent's two of three probable-cut calls were correct — e_012 ("every
  waking hour") and e_018 (workplace double-take) were both dropped in
  finishing. The third (e_008 "kind of left the room") was actually kept in
  the final cut, which is a useful signal that probable-cut judgments aren't
  reliably aligned with the editor's call.
- Act structure was solid first-pass and held end-to-end. Creative Context
  did not need a v2.
- Skip-to-FCPXML workflow was the right call for this project. Multi-round
  Discussion / Reduction would have been overhead given Jeff's preference for
  FCP-side trimming with audio/visual cues.
- Dr. Luck's quotes acted correctly as supporting / interleaved rather than
  carrying acts on their own.

### What Was Difficult

**Transcription stage (mostly resolved in v5.1 / v5.1.1):**
- Cowork sandbox couldn't reach AssemblyAI — outbound network allowlist
  excludes it. Host-side launcher pattern is the supported workaround until
  the allowlist changes.
- Drive name with space + ampersand (`TCCS Dr Pan & Testimonials `) broke
  virtiofs bind-mounts in the sandbox. SSD had to be renamed to `TCCS_2026`.
- Original v5.0 SKILL assumed git-crypt for the AssemblyAI key. The
  remediation steps assumed local repo clone, master key on this Mac, known
  key location — none of which held. Replaced with `.env` flow in v5.1.
- Chat client auto-linked `.py` / `.sh` paths into markdown hyperlinks,
  breaking shell parsing on paste. `start-editing` launcher has no extension
  for this reason.
- Repo URL drift in older SKILL.md (`storyboard-ops` vs.
  `documentary-junior-editor`) sent the agent to a nonexistent path until
  reconciled in v5.1.

**FCPXML stage:**
- Same drive-name issue resurfaced — bash sandbox was effectively unusable
  through the FCPXML run. Every file operation routed through Read/Write/Edit
  tools; execution via Script Editor + AppleScript.
- `build_fcpxml.py` expected v4 quote schema; Edit Agent emitted v5 timeline
  with `entries` and `segments[]`. Pipeline script was bypassed entirely and
  a custom adapter (`build_tccs_rough_cut_v1.py`) was written from scratch.
- All speakers' source `.fcpxmld` files used `r2` as their multicam resource
  ID — naive merge would have wired clips to the wrong speakers. Adapter
  performs dynamic resource-ID remap (Dr. Luck shifted to `r8+`, title at
  `r11`).
- Multi-output FCPXML import creates duplicate multicams. Each emitted XML
  re-declares the full `<media>` block; importing two outputs into the same
  FCP library produces two copies of the multicam. Separate problem from the
  merge-collision issue.
- Latent bug in `build_fcpxml.py`: `parse_params_md()` uses
  `os.path.basename()` on `.fcpxmld/Info.fcpxml` paths, stripping the
  package name. Moot for this project (script was bypassed) but pending fix.

**Operational / environmental:**
- Terminal and Script Editor are tier "click" — no typing allowed. Workaround
  was AppleScript file + Finder Open + click Run.
- Multi-monitor display switching returned black screenshots after Terminal
  clicks; build status had to be confirmed from pre-switch screenshots.
- SSD disconnect/reconnect mid-session broke folder permission grant; agents
  repeatedly asked for re-access on subsequent sessions.
- Transcription Agent's handoff doc was never written for this project, and
  the project slug drifted (transcription summary referenced
  `handoffs/lynette-testimonial/`; pipeline ran in
  `handoffs/tccs-dr-pan-testimonials/`). Pipeline tolerated this — downstream
  agents read the `.txt` files directly — but it's a hygiene gap.

### Corrections Jeff Made

The Edit Agent emitted 22 entries totaling 269s (target 120s; tight cut
230s). The final cut runs 131s — Jeff trimmed another ~100s past the tight
cut. See `Final_Edit.txt` in this folder for the full entry-by-entry record.
Specific moves:

- **Lynette gets the final word.** Plan ended on e_022 (Dr. Luck "post-op
  never gets old"). Jeff moved e_022 to mid-Act 3 and closed on Lynette's
  e_021 ("really good plastic surgeons who truly care").
- **Dr. Luck's philosophy moved out of cold-open.** Plan opened Act 2 with
  e_006 (Dr. Luck "I never sell anybody anything"). Final order puts Lynette
  first to establish the prior-consult contrast, then Dr. Luck speaks.
- **Three must-keep entries dropped beyond the probable-cuts:** e_013
  (chin-scar "stayed obsessed" — the most specific care-quality detail per
  the Edit Agent's own note), e_015 (cell-phone POV, which broke the
  flagged claim/evidence pair with e_014), and e_019 (Clovis "mission
  accomplished").
- **Heavy segment-level pruning inside entries that were kept.** Almost
  every retained entry shipped with at least one segment dropped vs the
  Edit Agent's plan. Examples: e_020 (#40 "damaged goods" arc) kept only
  segs 3-4, dropping the "damaged goods" preface and "self-esteem through
  the roof" middle; e_016 (#45) kept only seg 1, dropping the introductory
  "Dr. Luck cared and he wanted me to have the best outcome" line; e_009,
  e_003, e_005 each shipped one segment short of plan. The Edit Agent's
  segment selection was consistently looser than what the editor would
  ship.
- **Five entries restored a segment the Edit Agent had dropped.** Examples:
  e_010 (#6) regained seg 2 ("This is what a facelift does"); e_017 (#15)
  regained seg 2 ("more just lifted up"); e_021 (#22) regained seg 1
  (affordability) — even though the Edit Agent's note explicitly dropped
  affordability as "different theme that doesn't fit emotional close". The
  editor reads tail beats and codas as completing the rhythm where the
  agent reads them as redundant.
- **A whole source-pool quote was added that the Edit Agent never
  selected.** Quote #16 ("under-eye area was what surprised me... it's
  impressive what he did") is in the Synthesis Agent's source pool (tagged,
  not orphaned), but the Edit Agent didn't pick it for any timeline entry.
  Jeff pulled it in during finishing — the entire 12s "outcome / no
  bruising / smooth / impressive" beat in Act 3 comes from this
  unselected-but-cataloged quote.
- **3 Flow transitions added** at offsets 7.22s, 74.03s, 113.86s. Neither
  the Edit Agent nor the FCPXML Agent emit transitions; these are finishing
  decisions.
- **All act title cards stripped** per workflow rule (one survived by
  oversight — see Rules That Emerged).

What these corrections reveal about the editor's preferences:
- Patient voice carries the close; practitioner is supporting throughout, not
  framing.
- Practitioner philosophy reads stronger after the patient sets up the
  contrast, not as a cold-open hook.
- Outcome / visual-result material belongs in Act 3 even when the Edit
  Agent's selection skipped over a whole tagged quote covering it. The Edit
  Agent under-weights outcome-description material relative to character /
  emotional beats.
- Tail beats and codas earn their place even when the Edit Agent calls them
  redundant — the editor restores them more often than the agent retains
  them.
- Segment-level pruning is heavier than entry-level pruning. The agent's
  entries are kept, but the agent's segment-selection inside each entry is
  consistently looser than what ships.
- Front-trim only, never tail-trim, never mid-cut.
- Significant editorial decisions happen in FCP with audio / visual cues,
  not abstractly in the viewer.

### Multi-round Trajectory

One round only. `skip_to_fcpxml: true` set in `trimmed-quotes-v1.json`. No
Discussion or Reduction phases. This was a deliberate choice — the multi-
round loop's value drops sharply when the editor prefers FCP-side trimming.
There is no v2 of any handoff document on this project, and no inter-version
diff signal to extract.

### Cardinal Rule Status

No violations. `cardinal_rule_verified: true` in `pipeline-state.json` and
confirmed in `edit-handoff-v1.md`. All 7 trims were word-level subsets of
source segments. All segments within entries in source order. No cross-quote
contamination.

### Rules That Emerged

1. **Act title cards are an editing aid; delete at finishing.** Currently
   informal practice. Should be explicit in `SKILL-edit.md` and/or
   `SKILL-fcpxml.md`, with an end-of-finishing checklist item.
2. **Project SSD drive names must avoid spaces and special characters.**
   Currently in troubleshooting only; should be in `cowork-session-guide.md`
   under "Project Folder Structure" as a hard requirement, not a recovery
   note.
3. **Project slug must be set before the Transcription Agent emits its
   handoff doc.** The Transcription Agent runs before Creative Context, so
   it can't pull the slug from there. Either ask Jeff up front for the slug,
   or have a per-project slug file the agent reads from.
4. **For single-speaker or low-complexity projects, `skip_to_fcpxml` is a
   valid first-pass workflow** and should be available as an opt-in default
   rather than an exception.
5. **Editor reserves final selection and ordering for FCP.** Agent output is
   a structural and selection scaffold, not a final cut. Multi-round Edit
   Agent loops should not be the default expectation.
6. **Keep the SSD continuously mounted across the pipeline.** Disconnecting
   and reconnecting breaks the Cowork session's permission grant; agents
   then repeatedly re-ask for folder access.

### Phase 3 Follow-up Code Change Tracking

| Item | Status |
|------|--------|
| `scripts/transcribe.py` — drop `.env` fallbacks, read from `.env` | **SHIPPED in v5.1** |
| `scripts/build_fcpxml.py` — v5 schema (`entries` + `segments[]`), per-interview `clip_type` branching, per-segment clip generation | **NOT SHIPPED** — Jeff wrote `build_tccs_rough_cut_v1.py` adapter for this project. Highest priority next code work. Fold adapter back into canonical script. |
| `scripts/generate_fcpxml.py` — `find_quote_range` TC-window narrowing | Status to verify next pass |
| `scripts/quotes_viewer_template.jsx` — segment-level UI, status badges, bidirectional `sendPrompt()`, current-focus highlight, title-card / context-beat entry types | **PARTIALLY SHIPPED** (v5.0-native rebuild done); design drift and lost prior functionality surfaced this round, **parked for separate review** |
| `secrets/assembly_ai.key` (deprecated git-crypt file) | Delete from repo |

New follow-ups identified this project:
- `scripts/build_fcpxml.py` — multi-speaker resource-ID remap logic (currently in adapter)
- `scripts/build_fcpxml.py` — multi-output multicam re-import duplication: emit references to library multicams by UID instead of re-declaring `<media>` blocks
- `scripts/build_fcpxml.py` — `parse_params_md()` basename bug fix
- Optional: move ffmpeg pre-conversion of `.mov`/`.mp4` into `start-editing` launcher (currently sandbox Phase 3)
- Send Anthropic feedback re: AssemblyAI not on Cowork outbound allowlist

### Reference Value

**Use this reference for future projects that are:**
- Medical / professional-services testimonials (cosmetic surgery, dental,
  legal, financial) with a single subject as primary voice and a single
  practitioner as supporting voice
- Two-subject multicam projects where one subject must clearly carry the
  emotional through-line and the other is a credentialing presence
- Projects where the subject has a difficult backstory (illness, loss) but
  the brief explicitly wants the difficult element as a single establishing
  beat, not the spine of the piece

**Particularly strong editorial decisions worth referencing:**
- **Patient-voice close.** Subject closes the film with the universal /
  generous statement; practitioner's wrap-up beat moves earlier.
- **Practitioner-as-counterpoint, not as opener.** Practitioner philosophy
  reads stronger after the patient establishes the problem context.
- **Pull from the cataloged-but-unselected source pool for outcome /
  visual-result material in Act 3.** The Edit Agent's entry selection is
  not exhaustive — fully tagged quotes can be missing from the timeline.
  Treat the full `tagged-quotes-v[N].json` as the candidate pool, not just
  the Edit Agent's `trimmed-quotes-v[N].json` entries.
- **Front-trim discipline.** Every kept quote that needed shortening had
  filler removed from the head only, never tail-trimmed or mid-cut.
- **Restore tail beats and codas.** When the Edit Agent has dropped the
  last segment of a quote as "redundant," check it against the audio —
  more often than not, that last beat lands the rhythm.

**Cautions for similar projects:**
- When the Edit Agent flags a cross-reference pair as "keep both; do not
  merge or reorder," treat it as a suggestion rather than a hard constraint.
  A pair can survive intact while the editor reorders the surrounding act —
  the agent's pairing flag should not lock the position of either quote.
- Mid-quote zero-duration segments flagged by Synthesis need verification
  against source audio before locking. The FCPXML Agent should surface these
  for manual check rather than silently using estimated timecodes.

### Pipeline State for the Review

- All handoff documents reviewed: 1 version per agent (no v2 emissions this
  project — `skip_to_fcpxml: true` short-circuited the multi-round loop)
- `pipeline-state.json` is internally consistent; no stale-state warnings
  were proceeded-through (none fired)
- No Cardinal Rule violations to document

---

*Lessons Learned — TCCS Dr Pan & Testimonials Lynette Patient Testimonial — generated by Skill Review Agent 2026-05-13*
