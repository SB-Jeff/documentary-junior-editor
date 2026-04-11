# Lessons Learned — Dr. Pan Intro
## Completed: 2026-03-29
## Project Type: New Staff Introduction
## Subjects: 1 — Dr. Kristin Pan (sole speaker)

> The Project Type tag is used by future agents to filter for relevant reference examples
> when processing new projects. Use established types (B2B Testimonial, Nonprofit,
> Recruiting, Brand Film) or create a descriptive new type label if none fits.

### Project Summary

A physician introduction video for Twin Cities Cosmetic Surgery, introducing Dr. Kristin Pan to prospective patients. Single speaker throughout — the narrative lives entirely on her words. The practice currently has two male surgeons; Dr. Pan brings a female perspective that the video needed to convey naturally without making it feel like a marketing pitch. Processed through the full v3.2.1 pipeline (Creative Context → parallel FCPXML Params + Transcript Agent → Synthesis Agent → Edit Agent → FCPXML Agent). This is the first project to use text interstitials and the first run through the merged Edit Agent for this project.

### Act Structure

**Act 1 — The Legacy (7 spoken quotes + 2 text interstitials):** Dr. Pan's origin story. Plastic surgery as the family world — father practiced 30 years, brother followed into the field. Drawn to medicine by admiration for her father's work helping people through vulnerable times. Credential arc bridged by text interstitials (Cincinnati medical school, NIH research, Hopkins residency) with spoken quotes carrying the emotional weight. Closes with "surgeon's surgeon" — the broadest, most vivid credibility anchor.

**Act 2 — A Different Kind of Care (6 spoken quotes):** The patient experience with the female perspective woven in. Opens with patient vulnerability (nervous, personal, insecurities), moves through Dr. Pan's care approach (comfort, communication, counseling), and closes with the female perspective delivered naturally — her passion for working with women, and the comfort of a female provider. The female perspective lands as an extension of empathy, not a marketing differentiator. Editor plans an intercut between quotes #14 and #15 in FCP for a cohesive female-perspective close.

**Act 3 — Feeling Like Yourself (2 spoken quotes):** The emotional payoff. Post-procedure fulfillment, culminating in "I finally feel like myself again." Short and resonant — the emotion does the work because Acts 1 and 2 did the buildup.

### What Worked Well

**Text interstitials for credential bridging.** Two text cards (T1: Cincinnati/NIH background, T2: Hopkins residency) were added to Act 1 to bridge credential gaps where no clean spoken quote existed. This freed the spoken quotes to carry emotional and experiential weight while factual credentials were conveyed visually. This pattern should be considered early in the Creative Context session for credential-heavy intro videos.

**The "weave, don't isolate" strategy for fragile material.** The creative brief correctly identified that Dr. Pan was guarded when asked directly about the female perspective. The solution — weaving it into Act 2's patient care section — carried through the entire pipeline without any agent isolating it as a standalone talking point. The strongest quotes (#34 "I feel passionate about working with other women" and #29 "comfort and familiarity with a female provider") were delivered naturally when the conversation moved to what she loves about her work.

**The Synthesis Agent's narrative assessment on a single-speaker project.** Even with one interview, the intra-interview analysis was valuable. The redundancy report identified four key clusters and correctly flagged the strongest version in each. The cross-references section identified the "vulnerable" echo between Acts 1 and 2 and the "confidence/feeling like yourself" thread from Act 2 to Act 3 — both exploited in the final edit. The gap report accurately predicted Act 3's thin coverage and the lack of a transition bridge between Acts 1 and 2.

**No loop-back needed.** Jeff approved the FCPXML cut on the first pass. The merged Edit Agent (selection + trimming in one session) likely contributed — the v3.1 era required selection changes during the separate Trim Agent session.

**Aggressive trimming.** 14 of 15 spoken quotes were trimmed, many from 20-30 second passages down to 5-8 second sound bites. Only #18 ("surgeon's surgeon") was left untrimmed. Consistent with the v3.1 finding — New Staff Introduction videos rely on sound bites, not conversational passages.

### What Was Difficult

**Non-contiguous trims caused wrong clips in the FCPXML.** Quotes #2 and #10 had middle content trimmed, leaving two non-contiguous kept portions. The caption matcher only found one portion for each, producing clips that were too short (#2 missing "for 30 years") or started at the wrong position (#10 missing "I really admired the kind of career that he had"). This is a code-level bug in `generate_fcpxml.py` — see Rules That Emerged below.

**FCPXML timing padding was too tight.** The ~2 frame padding (~0.08 seconds) produced clips where the editor had to extend to capture the full line. It is always easier to cut excess than to wonder whether something is missing. Updated to 2 seconds in v3.2.2.

**FCPXML naming convention.** The output was named `Dr Pan Intro AI Narrative - 1.fcpxml` rather than the spec's `[ProjectName]_rough_cut.fcpxml`. Jeff discussed naming preferences with the FCPXML Agent directly. The spec should be updated to reflect the preferred convention once established.

### Corrections Jeff Made

**No major corrections to quote selection or ordering.** The Edit Agent's first pass aligned well with Jeff's preferences — a significant improvement over the v3.1 era where 3 quotes were swapped during the separate Trim session. The merged Edit Agent workflow appears to produce better first-pass results.

**Text interstitials were added during the Edit session.** T1 and T2 were not proposed by the Creative Context Agent or Transcript Agent — they emerged during the Edit session as a solution to credential bridging. Future projects should consider flagging interstitial opportunities earlier in the pipeline.

### Cardinal Rule Status

No violations. All 14 trimmed quotes verified as verbatim subsets of their originals. The Edit Agent's Phase 6 Cardinal Rule verification step passed cleanly.

### Rules That Emerged

**1. Non-contiguous trims need full-range clip matching.** When a trim removes middle content, the FCPXML Agent should match the full original quote to get the overall clip range, not match the trimmed text sentence by sentence. Only formal splits (`split: true`) should produce separate clips. Added to SKILL-fcpxml.md in v3.2.2.

**2. FCPXML timing padding should be 2 seconds, not ~2 frames.** The editor should always be cutting excess rather than extending to find missing content. Updated in SKILL-fcpxml.md v3.2.2.

**3. Text interstitials should be suggested by the Edit Agent.** When the Edit Agent identifies credential gaps, factual context needs, or narrative bridges that no spoken quote covers cleanly, it should suggest a text interstitial. The viewer should support creating interstitials interactively. Planned enhancement — not yet implemented.

**4. The multi-project folder structure works.** The `handoffs/[project-slug]/` subfolder pattern kept Dr. Pan Intro and Facial Rejuvenation separate within the same SSD folder without collisions. Validated the v3.2.1 documentation.

### Reference Value

This is the definitive New Staff Introduction reference in the knowledge base (replacing the earlier v3.1 version). Future projects of this type should reference it for:

- **Text interstitial usage:** How credential gaps were bridged with text cards while spoken quotes carried emotional weight — a pattern for any credential-heavy intro
- **Handling fragile interview material:** The "weave, don't isolate" strategy for the female perspective is a transferable pattern for any topic where the speaker is guarded
- **Trim aggressiveness calibration:** The Final_Edit.txt shows how far Jeff trimmed each quote — useful calibration for the Edit Agent's trim recommendations on similar projects
- **Non-contiguous trim awareness:** A documented edge case where aggressive mid-quote trimming caused FCPXML generation errors — future FCPXML Agents should watch for this
- **Single-speaker pipeline adaptation:** How the Synthesis Agent's cross-interview analysis becomes intra-interview analysis, and how it still provides valuable editorial intelligence
- **The #14/#15 intercut plan:** An example of editorial intent that will be handled at the FCP level — parts of quote #14 wrapping around quote #15 to create a cohesive female-perspective close
