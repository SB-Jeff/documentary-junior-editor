# Lessons Learned — International Institute of Minnesota
## Completed: 2026-04-29
## Project Type: Nonprofit Fundraising
## Subjects: 3 (Alice Mupenzi — refugee, IIMN client; Blaine Joseph — IIMN board member; Jane Graupman — IIMN Executive Director, 37-year tenure)

> The Project Type tag is used by future agents to filter for relevant reference examples
> when processing new projects. This is the second `Nonprofit Fundraising` example after
> Pacer Center. Future fundraising-pitch projects should reference both.

### Project Summary

A 2026 Fund-a-Need gala video for the International Institute of Minnesota — a refugee-services nonprofit. The narrative arc follows Alice Mupenzi from a Rwandan refugee camp through resettlement and IIMN services, into Jane Graupman's account of how the post-January-2025 federal policy shifts have collapsed refugee admissions, ending on a fundraising appeal grounded in IIMN's continuing work. Editorially distinctive for being the first project where the agent's rough cut (20:47) and Jeff's final FCP edit (5:12) diverged so dramatically — a 76% runtime reduction that operated less as a tightening pass and more as a re-conception toward the Fund-a-Need format. The data this project generated is the strongest signal yet that fundraising-pitch runtime calibration is its own thing.

### Act Structure

The approved act structure — three acts plus narrative roadmaps — was:

- **Act 1: A Refugee's Life** — Alice alone. Deprivation, endurance, the rarity of escape. The life she knew before the airport.
- **Act 2: Building a Life** — IIMN as co-protagonist. Alice primary, Jane and Blaine as supporting voices. Six movements: airport welcome → housing/CNA path → college → naturalization → oath ceremony → "right under the wire" hinge.
- **Act 3: The Antidote** — Jane leads. The systemic darkness post-January-2025 (arrests, Operation Paris, policy stacking, 39-country list). IIMN as the antidote. Closing on a fundraising appeal.

In the final edit, the underlying shape of these three acts held — but all three act-divider title cards were dropped, and Jeff's FCP refinement re-balanced the proportions significantly. Act 1 compressed substantially via a title-card replacement of Alice's longer DRC-and-camp backstory. Act 2 contracted from 23 cut entries in v3 to roughly 12 in the final. Act 3 expanded materially via five Jane fragments documenting Operation Paris re-interviews that had been tagged but not selected in the rough cut.

### What Worked Well

**Synthesis Agent's narrative assessment proved its weight.** The cross-references it produced (e.g., #52 as alternative to #51, redundancy clusters across speakers) tracked closely with the editorial moves Jeff actually made in FCP — including swapping #51 for #52 in the final. The Edit Agent's first-pass selection ignored some of these signals; the final edit honored them. Future Edit Agent runs should weight Synthesis cross-references more heavily during selection.

**Per-speaker Transcript Agents catalogued thoroughly.** All 10 quotes Jeff added in FCP came from the previously-tagged-but-unselected pool. Zero orphans were pulled. That means the Transcript Agents' tagging was complete — the agent had access to every quote Jeff later wanted. The gap was in selection, not in cataloguing.

**Versioned trimmed-quotes (v1, v2, v3) were diff-able.** v3 introduced the Act 1 reduction work and an Act 1 interstitial. The interstitial text Jeff carried into the final was verbatim from v3 — clear evidence that the Reduction phase produced useful editorial product even though the FCPXML pipeline was never re-run on v3. This validates the v5.0 framing that every Reduction round emits a fresh FCPXML, and the versioning infrastructure that makes inter-version diffs first-class data.

**Cardinal Rule held cleanly.** Zero violations across all per-speaker outputs, the merged synthesis, three trimmed-quotes versions, both rough-cut FCPXMLs, and Jeff's final FCP edit. The sentence-level reorder Jeff did inside Alice #11 (leading with later sentences) is permitted by the rule — verbatim words, only order changed.

### What Was Difficult

**Runtime calibration was off by 4×, not 25–30%.** The rough cut at 20:47 against a ~5-minute Fund-a-Need target was less a "rough cut" than a survey of strong material. The v4.0 calibration ("long-form emotional testimonials run 25–30% longer than word-count math predicts") didn't fit. Fund-a-Need pitches have a different runtime profile — short-form event appeals, not long-form testimonials. The v5.0 wide-rough-cut + per-quote runtime-recommendation layer is the response: the agent now tags each quote toward 2× target so Jeff sees what would survive a tight cut while still seeing what was left on the table.

**The agent never proposed sentence-level reorder.** Across 23 surviving quotes in the final edit, Jeff did sentence-level reordering inside Alice #11 (led with later sentences, came back to earlier ones). The Edit Agent treated each quote as a near-atomic block with optional head/tail trims and split-into-sub-clips operations — never proposed an intra-quote rearrangement. This was the largest single capability gap and the foundation of v5.0's data-model rewrite (segments + timeline entries).

**Three brief-locked beats were dropped in FCP.** Stephen Miller, the seizure-medication block, and the "I was the luckiest" hinge — all marked "must stay / immovable / locked in" in the brief — were absent from the final. Jeff's framing during the review: editing is iterative; brief commitments are starting points, not constraints. v5.0 softens the brief language accordingly.

**The FCPXML Agent never ran on `trimmed-quotes-v3.json`.** The Edit Agent began a Reduction pass producing v3, then the pipeline died — Jeff opened v2's FCPXML in FCP and refined manually. v3's reduction work effectively informed but didn't drive the final edit. v5.0 makes the Edit↔FCPXML loop explicit: each Edit Agent round emits a versioned `trimmed-quotes-v[N].json` AND triggers a fresh FCPXML run.

**Title cards as runtime tool weren't proposed proactively.** The v3 paper cut included two interstitials in Act 1; the final edit had seven across all three acts. Five new title cards (most replacing spoken stats) came from Jeff's hand pass. v5.0 promotes title-card-as-shortener to a named editorial pattern in `SKILL-edit.md` so the Edit Agent proposes them in the rough cut.

**Research-sourced framing was Jeff's territory alone.** Two of the seven title cards ("Fewer than 1% of refugees resettled" and the U.S. Refugee Admissions Program suspension stats) were research-sourced — pulled from Jeff's own research, not the interview transcripts. The Edit Agent had no mechanism for this. v5.0 adds context-beat suggestions: the agent flags narrative gaps where external context would land harder, with `(research needed)` tags; Jeff fills in the actual content.

### Corrections Jeff Made

The big corrections cluster around four themes:

**Severity of trim.** Surviving quotes were trimmed ~75–80% on average. A few extreme cases: Alice #16 went 24s → 2.2s (-91%); late-Alice #45/#46 went 55s → ~3s combined (-95%). The agent's v2 trims were moderate; the final edit was aggressive. v5.0's runtime-recommendation field gives the agent room to propose tighter trims while preserving the wide-rough-cut visibility.

**Replacement of spoken stats with on-screen text.** Four places where the rough cut had a speaker delivering a statistic or a piece of context, the final replaced it with a title card. Title-card-as-shortener pattern.

**Cross-act material movement.** Five Jane fragments that were tagged but unselected in v3 (#54, #52, #87, #88, #91, #92, #93, #71) entered the final to fill Act 3 space the dropped seizure-medication beat had vacated. The Edit Agent didn't see those fragments as alternates because the brief had locked in the seizure-medication block. v5.0 brief-language softening lets future Edit Agent runs treat brief commitments as defaults to honor, not walls to defend.

**Sentence-level reorder.** Alice #11 played in the final with sentences in a different order than the source transcript. The agent never proposed this. v5.0 segment-level data model and the "quotes are clay" framing make this a first-class editorial move.

### Cardinal Rule Status

Zero violations across the entire pipeline. All 23 surviving quotes in the final edit are verbatim substrings of their source transcripts. Alice #11's sentence-level reorder is permitted (verbatim words, only order changed) — not a violation. Verified against per-speaker captioned XMLs and Jeff's final FCP edit.

### Rules That Emerged

The twelve lessons that drove the v5.0 release were extracted from this project (with confirmation by Jeff during the Phase 2 review). Summarized:

1. **Quotes are clay; the timeline is the work product.** Source quotes decompose into segments. The paper cut is a timeline of entries; each entry has `segments[]` referencing source quote + source segment + optional per-segment trim. New entries form when playback order ≠ source order or when segments come from multiple source quotes. Splitting is implicit.
2. **Brief is starting points, not constraints.** "must stay / immovable / locked in" → "currently planned to stay / load-bearing / tentatively committed."
3. **Title-card-as-shortener** as a named editorial pattern in the rough cut.
4. **Context-beat suggestions** — agent flags gaps where external research would help; doesn't do the research.
5. **Wide rough cut + per-quote runtime recommendation.** `must-keep / probable-keep / probable-cut / optional` toward 2× target; viewer toggle between full inventory and recommended-tight view.
6. **Multi-round Edit ↔ FCPXML loop.** Indefinite iteration; each round emits versioned outputs; agents stay separate to preserve the Opus/Sonnet model split.
7. **Transcription Agent at pipeline position 0.** Replaces prompt-driven Step 0; reads git-crypt'd AssemblyAI key.
8. **Universal versioning + dependency graph.** Per-file `-v[N]` suffix; `pipeline-state.json` tracks current versions and stale state.
9. **Model declarations in SKILL frontmatter; handoff footers with launch prompts.** Single source of truth — Jeff today, n8n tomorrow.
10. **FCPXML Agent handles multicam and single-clip footage.** Per-interview `clip_type` detection.
11. **Live HTML artifact as Edit Agent work surface.** Created at session start; bidirectional via `sendPrompt()`; auto-scrolls to current focus; full quote text inlined in chat on first reference.
12. **Creative Context Agent Phase 0 — Discovery.** Drive + Gmail searched at session start; candidates surfaced for approval before ingestion.

### Reference Value

Future projects most likely to benefit from referencing this example:

- **Any Nonprofit Fundraising / Fund-a-Need pitch.** The runtime calibration data here is the strongest fundraising-pitch evidence in the knowledge base. Compared to Pacer Center's nonprofit-fundraising profile (which was longer-form), International Institute represents the short-form event-appeal end of the spectrum.
- **Any project where the rough cut significantly exceeds target runtime.** The 4× overshoot here is the canonical example of when wide-inventory framing is right vs. when the agent should be more disciplined. The v5.0 runtime-recommendation layer is calibrated against this project.
- **Any project with research-sourced framing material.** The seven title cards in the final demonstrate how research and interview material weave together. Future Edit Agent runs proposing context-beat suggestions should reference how Jeff used the "Fewer than 1%" stat and the post-January-2025 policy stack to raise stakes.
- **Any project where the editorial intent revises substantially between brief and final cut.** Three brief-locked beats dropped here — a clean demonstration that brief commitments are starting points. Future Edit Agent runs should treat brief language with v5.0 softening in mind.
- **Any project considering sentence-level reorder.** Alice #11's reorder in this final is the canonical example of the v5.0 segment-level data model in practice. The verbatim words stayed; the segment order changed; the quote read better.
