# Lessons Learned — Facial Rejuvenation
## Completed: 2026-03-28
## Project Type: B2B Testimonial
## Subjects: 2 — Erin Harmon (patient, primary voice) and Dr. JD Luck (practitioner, supporting voice)

> The Project Type tag is used by future agents to filter for relevant reference examples
> when processing new projects. Use established types (B2B Testimonial, Nonprofit,
> Recruiting, Brand Film, New Staff Introduction) or create a descriptive new type label
> if none fits.

### Project Summary

A patient testimonial for Twin Cities Cosmetic Surgery's facial rejuvenation practice. Two speakers: Erin Harmon, a 47-year-old patient who had comprehensive facial rejuvenation (deep plane facelift, neck lift, brow lift, lip lift, upper blepharoplasty, CO2 laser), and Dr. JD Luck, the facial rejuvenation specialist. The narrative follows a personal transformation arc — a woman who decided to stop deferring her own needs and found a surgeon she trusted completely. Editorially distinctive for its clear scope boundary (body surgery backstory confined to a single trust beat) and for running the first multi-speaker testimonial through the full v3.0+ pipeline.

### Act Structure

**Act 1 — "Time to Fight Back":** Erin's emotional "why" — feeling less like herself as she aged, her son moving out as a turning point, deciding to invest in herself. Dr. Luck provides a single beat of clinical empathy (reassuring nervous patients). 6 quotes (5 Erin, 1 Dr. Luck).

**Act 2 — "The Right Hands":** Finding and trusting Dr. Luck. Erin's contrast between fake consultations elsewhere and Dr. Luck's authenticity. Dr. Luck carries the care philosophy — education over selling, multiple counseling sessions, cell phone calls the night of surgery. The most balanced act for speaker weight. 9 quotes (2 Erin, 7 Dr. Luck).

**Act 3 — "Look at Her":** Transformation and emotional payoff. Natural results, "you are not 47," the boyfriend date night reveal, the "you're pretty" mirror moment. Dr. Luck matches with the yearbook photo reveal and the surgeon's indescribable experience of seeing patients transform. 9 quotes (5 Erin, 4 Dr. Luck).

### What Worked Well

**The scope boundary held perfectly.** The creative brief flagged body surgery as a single establishing beat for trust, and the complication story as entirely off the table. Both boundaries were respected by every agent in the pipeline. The Transcript Agents correctly tagged body surgery content as Orphan, and the complication story was excluded from tagged quotes entirely. This is a useful model for future projects with adjacent-but-excluded content — define the boundary in the creative brief and it propagates cleanly.

**The Synthesis Agent's cross-references directly shaped the edit.** The narrative assessment identified six cross-references (yearbook moment, fake-vs-real care, education-over-selling consultation, natural results, mirror moments, boyfriend arc). Several of these mapped directly to the Edit Agent's sequencing decisions — particularly the fake-vs-real care interleave in Act 2 and the mirror moment pairing in Act 3. Cross-references are proving to be the highest-value section of the narrative assessment.

**Act 2's call-and-response structure.** The final edit interleaves Erin's narrative with Dr. Luck's philosophy: Erin's disappointment elsewhere (#6) → Dr. Luck's authenticity (#91) → consultation detail (#95, #96) → Erin confirming trust (#30) → Dr. Luck's care philosophy sequence (#103 → #87 → #86 → #88). This patient-experience/practitioner-philosophy weave is the strongest section of the edit and a good template for two-speaker testimonials.

**First-pass FCPXML approved without loop-back.** The full pipeline — Creative Context through FCPXML — ran end to end with Jeff approving the FCPXML cut on first review. No review-notes.md was needed. This validates the pipeline's ability to produce a usable rough cut from raw transcripts in a single pass.

**Front-trim pattern was consistent and efficient.** All 6 trims removed lead-in phrases (throat-clearing, context-setting clauses) to start at the meat of the quote. No end-trims, no mid-trims. This is a clean, predictable pattern the Edit Agent can recommend proactively.

### What Was Difficult

**Act 3 trims were skipped.** Jeff chose to go straight to FCPXML without trimming Act 3 quotes. He then approved the cut as-is. This suggests either (a) Act 3's quotes were strong enough untrimmed, or (b) Jeff preferred to hear the rough cut before deciding on fine-grained trims and decided they weren't needed. The Edit Agent should be prepared for this workflow — not every act needs to be fully trimmed before FCPXML generation.

**Handoff filename inconsistency.** The Edit Agent produced `paper-cut.json` rather than the documented `trimmed-quotes.json`. The FCPXML Agent needs to know which name to look for. This should be standardized.

**The edit-handoff.md was useful but undocumented.** The Edit Agent generated a structured handoff document (`edit-handoff.md`) summarizing the paper cut status, key files, and notes for the FCPXML Agent. This is a valuable practice — especially the note about Act 3 having no trims — but it's not in the skill file's output specification.

### Corrections Jeff Made

**Selection was relatively close to first pass.** The edit-handoff.md reports 24 quotes selected with trims applied — no evidence of major selection overhauls during the session. The Edit Agent's recommendations aligned well with Jeff's editorial judgment on this project.

**All trims were front-trims.** Quotes #6, #25, #29, #61, #82, and #86 were trimmed. In every case, the trim removed a lead-in clause to start at the core statement. This pattern is consistent with the Dr. Pan Intro finding that Jeff favors sound bites over passages.

**No splits needed.** Unlike the Dr. Pan Intro project (which required the #21/#14 intercut), this project's quotes were self-contained enough to stand alone. Splits are project-dependent — they're essential for some editorial structures but not others.

### Cardinal Rule Status

No violations. All trimmed text is a verbatim subset of the originals. The character-range trim editor in the v3.2 viewer likely helped — it makes trims a physical deletion operation rather than a text-rewriting operation.

### Rules That Emerged

**1. The Edit Agent should produce an `edit-handoff.md` as a standard output.** A structured summary of what's done, what files to use, and any notes for the FCPXML Agent is valuable. The note about Act 3 having no trims was particularly useful — without it, the FCPXML Agent would have to infer this from the data.

**2. The Edit Agent's output JSON should consistently be named `trimmed-quotes.json` or `paper-cut.json` — pick one.** The skill files document `trimmed-quotes.json` but the Edit Agent produced `paper-cut.json` on this project. Standardize to avoid confusion.

**3. Front-trimming is Jeff's default pattern for this type of project.** The Edit Agent should proactively recommend front-trims (removing lead-in phrases and throat-clearing) as the first-pass trim strategy for B2B testimonials.

**4. "Skip to FCPXML" is a valid workflow.** Jeff may choose to skip detailed trimming on some sections and go straight to FCPXML generation. The Edit Agent should accommodate this gracefully — offer trims but don't insist on them for every act before moving to FCPXML.

**5. Transcript Agent reliability requires explicit file verification.** When two Transcript Agents ran in parallel, one completed cleanly while the other asked unnecessary questions and reported completion without saving all required files. The Synthesis Agent caught the missing files, but it required Jeff to re-run the failing agent. The skill file said "three outputs" but actually requires four (summary.md was missing from the count). Fixed in v3.2.1: the skill now says "four required output files," includes a mandatory file verification step (read back each file from disk before reporting done), and warns that the Synthesis Agent validates all four.

**6. Multi-project folders need explicit detection at pipeline start.** This SSD folder contained both the Dr. Pan Intro and Facial Rejuvenation projects. Starting the second project caused a handoff folder collision. Fixed in v3.2.1: the Creative Context Agent now checks for existing handoff subfolders and establishes a project slug when multiple projects share a folder.

### Reference Value

This is the first multi-speaker B2B testimonial processed through the full v3.0+ pipeline (parallel Transcript Agents, Synthesis Agent merge, unified Edit Agent). Future two-speaker testimonial projects should reference it for:

- **Act 2 call-and-response structure:** The patient-experience/practitioner-philosophy interleave is a strong template for two-speaker testimonials where one speaker is the patient and the other is the provider.
- **Scope boundary management:** How to define and enforce a content boundary (body surgery = single beat, complication = off the table) across the entire pipeline.
- **Front-trim calibration:** All trims on this project were front-trims — useful calibration for the Edit Agent's trim recommendations.
- **Cross-reference value:** The Synthesis Agent's cross-references directly influenced the edit — shows that this section of the narrative assessment pays off editorially.
- **Clean pipeline run:** Full pipeline without loop-back, validating the end-to-end process for standard two-speaker testimonials.
