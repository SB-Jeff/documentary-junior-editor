# Lessons Learned — Crisis Nursery Testimonial
## Completed: April 17, 2026
## Project Type: Nonprofit Testimonial
## Subjects: 2 (Tyanna Bryant, mother/protagonist; TJ Bryant, her son, supporting voice)

> Project Type tag `Nonprofit Testimonial` — first reference example of this type in
> the knowledge base. Distinct from `Nonprofit Fundraising` in that the ask is
> implicit (stigma reduction, permission-giving) rather than an explicit donation
> or call-to-action. Future single-protagonist stories about service recipients at
> a nonprofit should look here first.

### Project Summary
Testimonial piece for the Crisis Nursery built around Tyanna Bryant, a mother of
six who first used the nursery's childcare-respite services when her eldest, TJ,
was young — and who now sits on a board of directors. TJ (now an adult) adds a
limited-entry supporting voice that closes the emotional loop from the child's
perspective. The editorial core is dismantling stigma: the piece begins with the
fear and suspicion that kept other mothers in Tyanna's community away from the
nursery, moves through her personal turning point using the service, and lands
on a board-of-directors / permission-to-ask-for-help close.

### Act Structure
Three-act structure, approved by Jeff in Creative Context:

1. **The Stigma of Asking for Help** — community distrust, isolation, the fear
   of losing children to the system. Establishes what the nursery is up against
   emotionally before showing what it does.
2. **A Partner in Parenting** — the service itself: first visit, staff warmth,
   TJ's crocodile-tears goodbye when he aged out, the ICU moment where the
   nursery opened its doors with no waiting list. TJ's two entries land here.
3. **A Place Every Parent Deserves** — the family-court vindication, the
   personal climb ("mountains... seas"), the board-of-directors role, the
   direct ask to other parents, and TJ's closing tribute to his mother.

The arc moves external → internal → external-again: community stigma → one
family's experience → Tyanna reclaiming the external narrative from a position
of authority.

### What Worked Well
- **Two-voice structure with asymmetric weight.** Tyanna carries 19 of the 22
  final beats; TJ carries 3. TJ's limited entries (one mid-Act 2, one mid-Act 2
  closer, one mid-Act 3 tribute) gave the piece a second perspective without
  diluting the protagonist. This is the pattern to reference when a future
  project has a primary subject plus a close family member.
- **Lead-with-vulnerability, close-with-authority placement.** The board-of-
  directors quote (seq #19) was deliberately held for Act 3 rather than used up
  front as credentialing. That ordering — vulnerability first, authority last —
  is the move that makes the permission-to-ask-for-help land. (See
  `feedback_board_directors_placement.md` in user memory.)
- **Split of source #7 into #7a / #7b.** Tyanna's long "sending them off to
  strangers" answer contained two distinct beats: the fear (end of Act 1) and
  the coping move of prepping TJ to talk before she left him there (start of
  Act 2). Splitting let both beats live in the act where they belonged without
  repeating the surrounding sentences.
- **TJ's "I could really see how lucky I am" tribute as second-to-last.** Pulling
  his voice up just before Tyanna's final "hope" beat produced a lift that a
  straight Tyanna → Tyanna close would not have had.

### What Was Difficult
- **First pass treated as a draft, not a rough cut — good Act 3 quotes got
  missed.** The 7:29.6 runtime initially looked like a "deliberate overrun
  to preserve Act 3 integrity," but the more honest read (surfaced in the
  v4.0 skill-review discussion with Jeff) is that the Edit Agent was
  optimizing toward target runtime in the first pass, producing something
  closer to a draft than a rough cut. Good Act 3 quotes got dropped before
  they ever made it into the viewer. The failure mode was runtime rigidity
  in the first pass, not arc length. This is the project that prompted the
  v4.0 workflow reframe: first pass is a **rough cut** (longer, over-
  inclusive, no runtime gate), then a **Discussion** phase surfaces what
  can come out, then **Reduction** trims against agreed target.
- **FCPXML Params parser mismatch.** The `SKILL-fcpxml-params.md` human-readable
  format (per-speaker sections with `### [Speaker Name]` bullets) was not the
  format `build_fcpxml.py`'s `parse_params_md` parser actually consumed. The
  FCPXML Agent had to reformat the file by hand mid-pipeline. Flagged as an
  OPEN known issue in CHANGELOG v3.5 with an interim "produce BOTH forms" fix
  in the skill; the permanent call (update skill or update parser) is Jeff's.
- **Caption-matcher timing on Tyanna's ~708-caption source.** `build_fcpxml.py`'s
  fuzzy matcher scans `captions × max_span` windows per sentence with
  `search_hint` resetting to 0 at each quote, so a long source forces every
  quote to pay the full scan cost. The whole run exceeded the 45-second shell
  timeout. Validated workaround: pre-narrow each quote's caption search to a
  ±15-second window around its `startTC`/`endTC`. Match scores held 0.85–1.00
  and total match time dropped to ~2 seconds. Flagged as a known issue; the
  permanent fix belongs in `generate_fcpxml.py`'s `find_quote_range`.
- **Folder-layout drift.** The project used uppercase `XML/exports/` + `XML/
  imports/` rather than lowercase `xml/`, and stored sources as `.fcpxmld`
  packages that had to be extracted before parsing. The multi-deliverable
  handoff folder (`handoffs/crisis-nursery-testimonial/`) also meant the
  rough-cut filename dropped the `_v<N>` suffix. Documented in
  `SKILL-fcpxml.md` as "Folder-layout variants the agent may see."

### Corrections Jeff Made
- **Reframed first-pass from draft to rough cut (workflow-level, not per-quote).**
  The meaningful correction on this project wasn't which specific quote to
  cut — it was a workflow-level realization that the Edit Agent's first
  pass was already trimmed toward target runtime when it shouldn't have
  been. Jeff's framing, captured during the v4.0 skill review: *"the goal
  initially is to tell the best possible story that has a logical
  progression and makes sense as a stand-alone narrative. So it doesn't
  matter if something is 5 minutes or 12 minutes. Is the narrative
  compelling? And then we look at it again and see what we can cut without
  losing any of the integrity of the story."* The skill now reflects this
  as the three-phase Rough Cut → Discussion → Reduction workflow.
- **Placed board-of-directors quote late, not early.** This wasn't a correction
  against the first pass so much as a confirmed judgment — the skill now
  encodes it as a rule ("lead with vulnerability, close with authority")
  rather than a per-project note.
- **Split #7 into #7a and #7b rather than picking one half.** Confirmed that
  non-destructive splits of a single source quote across act boundaries are
  the right move when both beats earn their place.

### Cardinal Rule Status
**Zero violations.** Every quote in `trimmed-quotes.json` is verbatim from the
raw transcripts — trims are head/tail only, splits preserve the source
sentences intact, no paraphrase or substitution anywhere in the edit. The
FCPXML Agent's fuzzy matcher confirmed 0.85–1.00 match scores across all 22
beats against the caption source, which is consistent with verbatim text.

### Rules That Emerged
The following rules were written into the skill files during the v4.0 review:

1. **First pass is a rough cut, not a draft.** Added to `SKILL-edit.md`
   Phase 3 as the governing principle of the first pass. Include every
   quote that plausibly earns its place; err long (1.5x–2x target);
   runtime is not a constraint here. The earlier "Act 3 arc priority"
   rule drafted against this project is a specific expression of this
   broader principle — "never pre-truncate the closing act" survives as
   guidance, but the bigger rule is that nothing gets pre-truncated
   anywhere in the first pass.
2. **Three-phase Edit Agent workflow: Rough Cut → Discussion → Reduction.**
   Added to `SKILL-edit.md` Phases 3 and 4. The Discussion phase is now
   an explicit part of the Edit Agent's job — the agent brings a proposal
   for what could come out and why, giving Jeff a reactable surface
   rather than cold pruning.
3. **Dual-mode viewer (Review / Edit toggle).** Added to `SKILL-edit.md`
   Phase 2 viewer spec. Review mode renders selected quotes as continuous
   narrative (no controls, for the Discussion phase); Edit mode is the
   current interactive interface (for the Reduction phase). Both modes
   read from the same data block.
4. **Limited-entry supporting voice pattern.** Added to `SKILL-edit.md`
   Phase 3 Selection Principles. Protagonist + close-relation second voice
   with 2–4 deliberate entry points, not even distribution. This reference
   example is the pattern's first codified case.
5. **Lead with vulnerability, close with authority.** Added to `SKILL-edit.md`
   Phase 3 Ordering Principles. Promoted from user memory to skill-file
   rule so it syncs across machines via git.
6. **Runtime estimation in two numbers.** Added to `SKILL-edit.md` Phase 3.
   Estimate rough-cut length and target length separately; long-form
   emotional testimonials run 25–30% longer than word-count math predicts.
7. **Dual-form handoff in `fcpxml-params.md`.** Added to `SKILL-fcpxml-params.md`
   as an interim measure pending Jeff's reconciliation call. Produce the
   parser-expected flat top-level sections (`## Media Ref IDs`, `## Angle IDs`,
   etc.) first, then the per-speaker human-readable block below.
8. **Folder-layout variants documented.** Added to `SKILL-fcpxml.md` —
   agents should handle uppercase `XML/exports/`+`XML/imports/`,
   `.fcpxmld` package extraction, and multi-deliverable output naming that
   may drop the `_v<N>` suffix.
9. **Caption-matcher known issue.** Added to `SKILL-fcpxml.md` — agents
   hitting a timeout on a long interview should pre-narrow the caption
   search per quote using the existing `startTC`/`endTC` fields (±15s
   buffer) as a validated workaround until `find_quote_range` is fixed.

### Reference Value
**Future projects that should reference this example:**

- **Single-protagonist nonprofit testimonials** where the subject has both a
  personal story and an earned present-day authority (board seat, staff role,
  public advocacy). Look at the Act 3 ordering — earned authority goes at the
  close, not up front.
- **Two-voice pieces with asymmetric weight** — a primary subject plus a
  limited-entry second voice (spouse, child, colleague). Look at TJ's three
  entries and where they're placed.
- **Projects with community-level stigma as the central obstacle** (mental
  health, childcare, addiction recovery, immigration support). Look at Act 1
  — the stigma is named from the community's perspective before the personal
  story begins, which gives the personal turn more weight.
- **Any project that will run long on Act 3.** Look at the runtime discussion
  in the edit handoff and the updated `SKILL-edit.md` guidance.

**What to look at specifically:**
- `Final_Edit.txt` — the 22-beat sequence with act dividers
- `transcripts/Tyanna Bryant.txt` and `transcripts/TJ Bryant.txt` — source
  material, useful for seeing what was cut and why
- The split of source #7 into #7a / #7b across the Act 1→2 boundary
- The placement of the board-of-directors quote (seq #19) late in Act 3, not
  early as credentialing
