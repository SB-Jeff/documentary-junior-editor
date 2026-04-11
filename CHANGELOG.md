# Documentary Junior Editor — Changelog

## v3.4 — 2026-04-09

### Narrative Coherence Rule added to SKILL-edit.md

New rule with the same prominence as the Cardinal Rule. The paper cut must read as a coherent story. After every change to selection or ordering, the Edit Agent must read the assembled sequence for narrative flow. Quote fragments that don't stand alone may work when paired with other fragments — evaluate sequences, not isolated pieces. Thread multiple trimmed quotes together to build narratives. Suggest interstitials when no quote bridges a gap, but first try to solve it with transcript material.

**Why:** On the Pacer Center project, the Edit Agent evaluated quotes in isolation rather than as a flowing sequence. Jeff had to repeatedly ask the agent to check coherence, and it found problems it should have caught on its own.

### Viewer is the single source of truth (SKILL-edit.md)

Every editorial suggestion must be reflected in the interactive viewer before moving on. The agent must not describe changes in chat without applying them to the artifact. If the chat and the viewer disagree, the viewer is wrong and must be fixed. Updates happen after every batch of changes, not accumulated for a single update at the end.

**Why:** On the Pacer Center project, the Edit Agent made suggestions in chat that weren't consistently reflected in the viewer — wrong ordering, quotes in wrong acts, trims not shown. Jeff had to bridge the gap manually and request sync, and the synced output sometimes still didn't match.

### Selection and trimming are simultaneous (SKILL-edit.md)

The first pass should be trimmed selects, not a wide net followed by tightening. When the agent proposes a quote, it should simultaneously propose which portion earns its place. Runtime estimation added to first-pass guidance.

**Why:** The Pacer Center first pass came in at 28 quotes / ~12 minutes against a 3–5 minute target because quotes were selected untrimmed. The tightening pass to 22 quotes / ~6 minutes was avoidable work.

### Narrative roadmaps elevated to editorial instructions (SKILL-edit.md)

Strengthened language: roadmaps from the Creative Context Agent are the editorial plan Jeff approved, not background context. The Edit Agent must check proposals against roadmaps and flag conflicts explicitly rather than silently departing.

**Why:** On the Pacer Center project, the Edit Agent drifted from the roadmaps and Jeff had to redirect it back to the act structure multiple times.

### Version management added (SKILL-edit.md, SKILL-fcpxml.md)

Editing passes saved as versioned files (`trimmed-quotes-v1.json`, `trimmed-quotes-v2.json`). The latest version is always also saved as `trimmed-quotes.json`. Viewer supports version dropdown for comparison. FCPXML filenames match versions (`_rough_cut_v1.fcpxml`, `_rough_cut_v2.fcpxml`). Version history documented in `edit-handoff.md`.

**Why:** On the Pacer Center project, the first FCPXML was too long. Jeff went back for a shorter cut, but the Edit Agent overwrote the original files. There was no way to compare versions or trace which edit produced which FCPXML.

### Long interview handling added to SKILL-transcript.md

Interviews over ~45 minutes should be processed in two halves to maintain cataloguing quality. The Transcript Agent splits the work, processes each half with a fresh context re-read, and combines the outputs.

**Why:** The Pacer Center project had a 57-minute and a 90+ minute interview. Overall cataloguing quality did not feel as strong as previous projects with 15–30 minute interviews.

### Case-setup act assignment guidance added to SKILL-transcript.md

Quotes that establish a case's backstory often belong to the preceding act (where the emotional weight of the setup lands), not the act where the case resolves.

**Why:** On the Pacer Center project, #23 and #24 (Timmy's backstory) were tagged to "PACER in Action" but reassigned to "The Wall" during editing because the setup works better before the vulnerability moment.

### Transcription documented as Step 0 (SKILL.md, cowork-session-guide.md)

SKILL.md's "Setting Up a New Project" now includes a transcription step before confirming files are present. The cowork-session-guide's Step 0 now has a full Cowork starter prompt that handles dependency installation, API key location, script execution, and output verification — no Terminal required.

**Why:** On the Pacer Center project, transcription was a significant friction point. Jeff assumed it was part of the pipeline but it wasn't documented. The script existed on another machine but had to be hunted down and debugged through multiple Terminal round trips.

### Reference example: Pacer Center (Nonprofit Fundraising)

First nonprofit fundraising project in the knowledge base. Two speakers (Norma — surrogate parent, Karen Malka — PACER advocate). 22 quotes + 2 interstitials across 4 acts. Establishes patterns for: protagonist + expert two-voice structure, case stories as narrative engine, interstitials for procedural context, profanity handling for formal audiences, and emotional close structure (extraordinary → universal bridge).

### Version bumped: SKILL.md, SKILL-edit.md, SKILL-transcript.md, SKILL-fcpxml.md → v3.4

---

## v3.3.1 — 2026-03-31

### Skill source of truth moved from Google Drive to GitHub

The storyboard-ops project (including all skills) is now version-controlled in a private GitHub repository and synced across machines via Git. Google Drive is no longer the source of truth for skill files.

**What changed:**
- cowork-session-guide.md: "Before You Start" updated — skill folder source changed from Google Drive to `storyboard-ops/skills/` with `git pull` reminder
- Workflow: before starting a new project, run `git pull` in `storyboard-ops` to ensure the latest skill version, then copy into the project folder as before

**Why:** Jeff works across three machines (Mac mini, Mac Studio, MacBook Pro). Google Drive's streaming mode caused empty/broken files when syncing the codebase. Git provides reliable syncing with full version history for both application code and skills.

---

## v3.3 — 2026-03-30

### Text interstitial support

Added the ability to create, position, edit, and remove text interstitials — factual on-screen text cards (credentials, titles, context) that appear between spoken quotes in the paper cut. Modeled on the Dr. Pan Intro project, which used two text interstitials (items 4 and 6 in the final edit) to cover education and residency that no spoken quote addressed.

**JSX viewer template changes (quotes_viewer_template.jsx):**
- New `initialInterstitials` array in the data block for pre-baked interstitials
- Interstitial state management: add, edit, remove, and position interstitials in the sequence
- "Add text interstitial" button appears after each selected quote in "Selected only" mode
- Interstitial cards render as indigo-bordered dashed cards with "TEXT INTERSTITIAL" badge, visually distinct from spoken quote cards
- Click interstitial text to edit, click ✕ to remove
- Interstitials included in save/restore state
- Summary bar shows interstitials alongside selected quotes
- Stats line includes interstitial count

**SKILL-edit.md changes:**
- Edit Agent now proactively suggests interstitials when it identifies gaps — credentials, factual context, transitions, or missing information that no quote covers
- Guidance for when and how to suggest interstitials, with reference to Dr. Pan Intro as model
- Interstitial viewer features documented in Interactive Viewer Features section
- Phase 5 Final Review updated to include interstitials in the read-through
- Handoff checklist updated to confirm interstitials

### Final-state HTML viewer required as Edit Agent deliverable

The Edit Agent must now save a self-contained HTML viewer to the project handoffs folder before completing. This ensures Jeff can review the paper cut at any time without a Cowork session.

**What changed:**
- SKILL-edit.md: New handoff document #3 — `handoffs/[project-slug]_quotes_view.html`
- File naming convention: `[project-slug]_quotes_view.html`
- Must contain final state: all quotes (selected and unselected), trims, interstitials, section assignments baked into the data block
- Self-contained: React 18 + Babel + Tailwind from CDNs, opens in any browser
- Viewer file path must be documented in `edit-handoff.md` under Key Files
- edit-handoff.md description updated to include viewer path and interstitial summary

### SKILL.md updated
- Pipeline diagram updated to show HTML viewer and interstitials as Edit Agent outputs
- Project folder structure updated with `[project-slug]_quotes_view.html` in handoffs
- Multi-project folder structure updated accordingly

### Version bumped: SKILL.md → v3.3, SKILL-edit.md → v3.3

---

## v3.2.2 — 2026-03-29

### FCPXML timing padding increased from ~2 frames to 2 seconds

The previous ~2 frame padding (~0.08 seconds) produced clips that were too tight — the editor frequently had to extend clips to capture the full line. Increased to 2 seconds on each end. It is always easier to cut excess than to wonder whether something is missing.

**What changed:**
- SKILL-fcpxml.md: Phase 3 Timing Extraction updated from "~2 frames" to "2 seconds"

### Non-contiguous trim handling documented in SKILL-fcpxml.md

When a trim removes middle content from a quote (e.g., "My dad was a plastic surgeon, for 30 years" from an original that includes "he's retired now, but he was in private practice" in between), the sentence-level caption matcher could only find one of the two kept portions. This caused clips to be too short or to start at the wrong position — confirmed on quotes #2 and #10 in the Dr. Pan Intro project.

**What changed:**
- SKILL-fcpxml.md: New "Non-Contiguous Trims" section added to Phase 3 with detection and handling guidance. When detected, the FCPXML Agent should match the full original quote for clip range instead of matching the trimmed text sentence by sentence. Formal splits (`split: true`) remain separate clips.

### Reference example: Dr. Pan Intro (updated)

Replaced the v3.1 reference example with the v3.2.1 pipeline run. Updated Final_Edit.txt (now includes text interstitials T1 and T2, uses merged numbering from Synthesis Agent), updated lessons-learned.md with findings from the full pipeline review including the non-contiguous trim bug and timing padding issue.

### Version bumped: SKILL-fcpxml.md → v3.2.2

---

## v3.2.1 — 2026-03-28

### Transcript Agent: four required outputs, mandatory file verification

Fixed a reliability issue where one of two parallel Transcript Agents completed successfully while the other either asked unnecessary questions or reported completion without saving all required files. Root cause: the skill file said "three outputs" in multiple places but actually requires four (tagged-quotes.json, orphans.md, discards.md, AND summary.md). The summary was produced in Phase 1 but not listed in Phase 3's output requirements, so an agent could consider itself done after three files.

**What changed:**
- SKILL-transcript.md: Description, Phase 3 heading, and completeness check all updated from "three" to "four" outputs. Summary.md added as explicit Output 4 in Phase 3.
- SKILL-transcript.md: New mandatory file verification step — agent must read back all four files from disk and confirm they exist before reporting completion. Presenting in chat is not sufficient.
- SKILL-transcript.md: Completion section now requires listing all four file paths with confirmation. Includes warning that the Synthesis Agent validates all four and will reject incomplete sets.
- SKILL-synthesis.md: Phase 1.3 gap reporting updated with specific remediation guidance — tells Jeff which speaker's Transcript Agent needs to be re-run, and describes the common failure pattern (agent reports completion without saving files).
- SKILL-transcript.md, SKILL-synthesis.md version bumped to v3.2.1

### Multi-project folder support

Documented the scenario where multiple video projects share a single SSD folder (same FCP library, same transcripts, same source FCPXMLs). When this happens, each project's handoffs go in `handoffs/[project-slug]/` subfolders instead of flat `handoffs/`.

**Why:** The TCCS shoot produced both a Dr. Pan Intro and a Facial Rejuvenation Testimonial from the same interviews. Starting the second project in the same folder caused a collision — the Creative Context Agent would have overwritten the first project's handoffs. The fix was project-slug subfolders, but the skill files didn't document this pattern.

**What changed:**
- SKILL.md: New "Multi-Project Folders" section with subfolder structure and guidance on when to use it
- SKILL-creative-context.md: New "Multi-Project Detection" step in Required Inputs — the Creative Context Agent now checks for existing handoff subfolders and asks Jeff to establish a project slug at the start. Handoff save paths updated to reference `[project-slug]/` variant.
- SKILL-creative-context.md version bumped to v3.2.1

### Edit Agent: edit-handoff.md added as standard output

The Edit Agent now produces `handoffs/edit-handoff.md` as a standard handoff document alongside `trimmed-quotes.json`. This structured summary gives the FCPXML Agent clear context about the paper cut state — including notes about skipped trims, splits, and edge cases. Added to SKILL-edit.md output specification, SKILL-fcpxml.md required inputs, and SKILL-review.md required inputs.

**Why:** The Facial Rejuvenation project revealed that the Edit Agent needs a way to communicate context that the data alone doesn't convey — such as "Act 3 has no trims yet" or specific editorial intent behind splits. Without this document, the FCPXML Agent has to infer state from the data.

### Edit Agent: "skip to FCPXML" workflow documented

Added note to SKILL-edit.md that Jeff may choose to skip detailed trimming on some sections and proceed to FCPXML generation. This is a valid workflow — not every act needs full trimming before the rough cut is generated.

### Reference example: Facial Rejuvenation

First multi-speaker B2B testimonial processed through the full v3.0+ pipeline. Two speakers (Erin Harmon — patient, Dr. JD Luck — practitioner). Includes transcripts, Final_Edit.txt, and lessons-learned.md. Notable for the Act 2 call-and-response structure (patient experience interleaved with practitioner philosophy) and clean scope boundary management (body surgery confined to single trust beat).

### Version bumped: SKILL-edit.md, SKILL-fcpxml.md, SKILL-review.md → v3.2.1

---

## v3.2 — 2026-03-28

### Interactive viewer overhaul (quotes_viewer_template.jsx)

Major upgrade to the quote viewer's interactive editing capabilities. All changes are in the REACT COMPONENT section of the template — the data block format is unchanged.

**Character-range text editing** — Replaced sentence-level trim editor with a character-range selection model. Users highlight text and press Delete to toggle words between kept and cut. Cuts snap to word boundaries automatically. The Delete key inverts state: kept text becomes cut, cut text becomes kept. Orphaned spaces between cuts are absorbed automatically.

**Quote splitting UI** — The viewer now supports interactive quote splitting. A scissors button (✂) appears on each selected quote card. Clicking it opens split mode, where clickable markers appear between every word. Place one or more split markers, then confirm. The quote becomes independent sub-quotes (e.g., #82a, #82b) that inherit existing text cuts, section assignment, and selection state. Each sub-quote is a fully independent card with its own editing, drag, and section reassignment.

**Drag-and-drop reordering** — Replaced up/down arrow buttons with drag-and-drop. Selected quotes show a 6-dot grip handle on the left edge. Drag a card onto another card within the same section to reorder. A blue indicator line shows the drop position (above or below target). Cross-section dragging is blocked.

**Color-coded section filters** — Section filter buttons at the top now use each section's assigned color (blue, amber, emerald, etc.) instead of uniform black. Both active and inactive states reflect the section color, making it easy to visually associate filter buttons with their quote cards.

**Checkbox-only selection** — Quote selection now only toggles via the checkbox in the upper right of each card, not by clicking anywhere on the card. This prevents accidental deselection when working in "Selected only" mode.

**String-based quote IDs** — Internal data model changed from integer `num` to string `id` field for all lookups, state management, and React keys. Display still uses `q.num` (integer) plus `q.subLabel` for split quotes. This enables the `"82a"` / `"82b"` identifier pattern for split quotes.

**HTML viewer pattern** — The primary working viewer is now an HTML file wrapping the JSX with React 18 + Babel standalone + Tailwind CSS CDN. This provides full interactivity without a build step. Console warnings from CDN scripts are suppressed.

### SKILL-edit.md updated

Updated to reflect new viewer features: character-range editing workflow, split UI interaction, drag-and-drop reordering, color-coded filters, and the updated split data model (`id`/`num`/`subLabel` fields).

---

## v3.1.1 — 2026-03-27

### Project type renamed: "New Staff Introduction"

"Physician Introduction / Single-Speaker Intro" renamed to "New Staff Introduction" across all skill files, reference examples, and changelog. The category covers any video introducing a new high-level staff member — audience can be internal, external, or both. The goal is always to establish credibility, trust, and rapport.

### Reference example: HDG COO Intro

Second new staff introduction added to the knowledge base. Erin GaN, COO at Health Dimensions Group — internal audience (~3,000 team members). Pre-pipeline reference (edited manually). Includes Final_Edit.txt from VTT captions and lessons-learned.md. Full interview transcript to be added when available.

---

## v3.1 — 2026-03-26

### Selection Agent + Trim Agent merged into Edit Agent (SKILL-edit.md)

The separate Selection Agent (SKILL-selection.md) and Trim Agent (SKILL-trim.md) have been merged into a single Edit Agent (SKILL-edit.md). Pipeline reduced from 8 agents to 7.

**Why:** The Dr. Pan Intro project proved that selection and trimming are too intertwined to separate. During the Trim session, 3 quotes were swapped (deselected and replaced with previously unselected quotes), the sequence was substantially reordered, and a quote was split — all decisions that required access to the full quote pool and couldn't happen in an isolated trim-only context. The artifact viewer already gave Jeff access to all quotes, undermining the isolation rationale.

**What changed:**
- SKILL-selection.md and SKILL-trim.md replaced by SKILL-edit.md
- Edit Agent handles selection, trimming, and subclip splitting in a single collaborative session
- Internal phases preserve focused-task quality: Pre-Selection Review → First Pass Selection → Collaborative Editing → Final Review → Cardinal Rule Verification → Handoff
- selection-state.json eliminated as a cross-agent handoff document
- Edit Agent produces trimmed-quotes.json directly for the FCPXML Agent

### Subclip splitting

Quotes can now be split into independently orderable subclips. Each subclip becomes a first-class entry with its own sequence position, trim, and timecode range.

**Why:** The Dr. Pan edit required interleaving parts of quote #21 with quote #14 to create a single cohesive thought (#21a → #14 → #21b). The previous system could only represent splits as trim annotations, not as independently orderable items.

**Data model:** Split quotes use `num: "21a"`, `parentNum: 21`, `split: true`, `split_part: "a"`. Each subclip can be reordered, trimmed, and placed anywhere in the sequence independently.

**Note:** As of v3.2, the viewer template fully supports interactive splitting UI. See v3.2 changelog above.

### Cardinal Rule protection shifted to active verification

The previous approach relied on context isolation — the Trim Agent received only selected quotes, not the full transcript. In practice, the artifact gave Jeff access to all quotes, undermining the isolation. The Edit Agent now protects the Cardinal Rule through an active verification step (Phase 6) that checks every trimmed quote is a verbatim subset of its original before saving the handoff.

### SKILL-fcpxml.md updated with Phase 0

Added Phase 0: Extract .fcpxml Files from .fcpxmld Packages. The FCPXML Agent now checks for .fcpxmld packages in xml/ and runs scripts/extract_fcpxml.py before proceeding. Also added note about single-interview projects using the subject's file as both caption source and reference.

### New Staff Introduction added as project type

Added "New Staff Introduction" to SKILL-creative-context.md project type examples. Introduces a new high-level staff member — audience can be internal, external, or both. Structure: origin/identity → philosophy/approach → emotional payoff. Based on the Dr. Pan Intro project — first single-speaker intro video in the pipeline.

### Single-speaker project guidance

Added note to SKILL-review.md that cross-interview analysis sections should be adapted to intra-interview analysis for single-speaker projects.

### All skill files updated to v3.1

Version bumped across: SKILL.md, SKILL-creative-context.md, SKILL-edit.md (new), SKILL-synthesis.md, SKILL-fcpxml.md, SKILL-fcpxml-params.md, SKILL-review.md.

### Reference example: Dr. Pan Intro

First new staff introduction added to the knowledge base. Includes transcripts, Final_Edit.txt, and lessons-learned.md.

---

## v3.0 — 2026-03-19

### Multi-agent pipeline expansion: 6 agents to 8 agents

**New agents:**
- **FCPXML Params Agent** (SKILL-fcpxml-params.md) — extracts FCPXML technical parameters from sample narrative XML. Previously embedded in Transcript Agent Phase 0 Step 3. Now runs in parallel with Transcript Agents as a dedicated Haiku 4.5 agent.
- **Synthesis Agent** (SKILL-synthesis.md) — merges per-speaker Transcript Agent outputs into combined handoffs. Produces narrative assessment with speaker coverage map, redundancy report, gap report, recommended speaker weight, and cross-references.

### Transcript Agent scoped to single interview
- Each instance processes one interview transcript (previously handled all interviews)
- Output filenames use speaker slugs: `[speaker-slug]-tagged-quotes.json`, `[speaker-slug]-orphans.md`, `[speaker-slug]-discards.md`, `[speaker-slug]-summary.md`
- Phase 2 (Preliminary Narrative Assessment) removed — moved to Synthesis Agent
- Phase 0 Step 3 (FCPXML param extraction) removed — moved to FCPXML Params Agent
- Phase 0 Steps 1-2 (file validation, extract_fcpxml.py) removed — handled by Project Setup Validator
- Captioned XML no longer a required input for the Transcript Agent
- All "Structure Agent" references removed

### Dynamic act labels (fully implemented)
- All hardcoded section names (Opening, Challenge, Solution, Impact) removed from SKILL files and JSX template
- Act labels are set by Creative Context Agent per project and flow through entire pipeline
- JSX quotes_viewer_template.jsx: sectionColors, sections array, and reassign dropdown now derive dynamically from quote data via `buildSectionColors()` function
- Color palette (6 colors) cycles for any number of sections; Orphan always gets gray
- SECTION_CONFIG data block field added for explicit section configuration

### Narrative roadmaps (new Creative Context Agent output)
- Creative Context Agent Phase 3 added: develops per-section narrative roadmap after act structure approved
- Each roadmap covers: how section opens/closes, emotional arc, speaker assignments, key moments, what it accomplishes
- Roadmaps included in act-structure.md handoff document
- Selection Agent uses roadmaps as editorial direction for sequencing and ordering

### Creative context inputs relaxed
- Creative Launch transcript and interview guide changed from "Essential — must have before starting" to "Soft Requirement — preferred but not blocking"
- Jeff may provide context conversationally; pipeline does not hard-block on file presence

### Project type diversity
- Added Recruiting Video and Brand Film examples to Creative Context Agent
- All project type examples reframed as illustrations, not defaults
- Added explicit note: "let the interviews drive the structure"

### Skill Review Agent updates
- Updated to reflect 8-agent pipeline (sixth to eighth agent)
- Added review sections for FCPXML Params Agent, per-interview Transcript Agents, and Synthesis Agent
- Added dynamic act label consistency check to lessons learned categories
- Added project type tagging guidance for reference examples

### Dropped outputs
- `tagged-quotes.md` (human-readable version) dropped — dashboard quote viewer renders JSON directly

### Cowork compatibility
- All changes are backward-compatible with manual Cowork sessions
- Each agent can still be run as a separate Cowork session pointing at the project folder
- Cowork workflow serves as fallback if n8n has issues

---

## 2026-03-04

### Trimming guidance updated
- Second Pass Editorial Principle #10 rewritten: "Trim for meaning, not brevity." Don't trim quotes just because they're verbose or conversational. Only trim when the content genuinely changes — speaker pivots to a different topic, repeats with a weaker version, or trails into something unrelated. Natural speech patterns are part of documentary authenticity.

### Fuzzy matching bug documented
- Added "Known Issue: Fuzzy Matching with Short Quotes" subsection under FCPXML Generation.
- Short sentences with common words (under ~8 words) can match to the wrong location in the interview when the 0.65 threshold is too permissive.
- Documented five recommended algorithm improvements: proximity constraints, minimum text length for sentence matching, context-aware matching, higher thresholds for short strings, and fallback to whole-quote matching for short quotes.
- Based on BBBS 2026 comparison: ~12 of 49 clips landed on wrong region due to this issue.

## 2026-03-03

### Scope broadened beyond B2B
- Description, intro, and all references updated to treat branding films, client hero stories, nonprofit fundraisers, recruiting videos, and B2B testimonials equally — no single project type given top billing.

### Multi-pass editing workflow added
- V1 (wide selects) and V2+ (tightening passes) workflow documented.
- Versioning & non-destructive editing: dict-based rebuild method for JSX data block updates; warning against regex insertion (caused 18 corrupted trims in testing).

### Second Pass Editorial Principles added
- 10 principles for tightening passes, including quote redistribution (#9) and trimming guidance (#10).

### Narrative structures expanded
- Three-Act / Cold Open structure listed first as primary pattern.
- Problem → Solution structure listed as alternative (previously the only option).
- "Other Structures" section added for thematic, chronological, and parallel structures.

### Speaker Roles generalized
- Replaced B2B-specific roles with universal patterns: Primary Subject, Supporting Voices, Institutional Voice, Independent Validator.

### JSX viewer improvements
- Collapsible Selected Quotes panel (default collapsed, scroll constraint, removed sticky positioning).
- Safe JSX editing method documented (dict-based rebuild).

### FCPXML generation updates
- JSX viewer designated as primary source of truth (over Excel).
- Versioned output naming (_v1, _v2, etc.).
- Reference PDF generation added as standard post-FCPXML step.

### Session Retrospective added
- New end-of-session step for continuous skill improvement.

### Phase 0 updated
- Cowork local-folder-only limitation documented (no portable drive support).

### Editorial Rules
- Added #11: Quote redistribution between sections.
