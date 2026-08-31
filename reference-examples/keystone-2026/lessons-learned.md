# Lessons Learned — Keystone 2026 Gala Video
## Completed: August 31, 2026
## Project Type: Nonprofit Fundraising (gala; evergreen-by-design)
## Subjects: 2 (Brandy — protagonist, food-shelf-client-turned-resource-navigator; Adero — President & CEO, limited-entry authority voice)

> Third `Nonprofit Fundraising` example (after Pacer Center and International
> Institute), and the strongest evidence yet on two questions: gala runtime
> (finals land ~4–5 min) and how much of a hard backstory a mission-driven
> fundraising piece should carry (answer: only the part the org's service
> resolves).

### Project Summary

Gala film for Keystone Community Services (St. Paul food shelf + resource
navigation, since 1939). Brandy once walked two miles with her daughter and a
flatbed dolly to Keystone's food shelf — humiliated, out of options — and now
works at Keystone answering calls from people in the exact situation she was
in. First project run fully on the v5.13 act-by-act live-partner flow with the
cold-read critic. The rough pipeline explored her full deep backstory (abuse,
addiction, recovery — at Jeff's explicit direction) plus a client-suggested
photo full-circle device; the final kept neither, and the reasons why are this
project's main contribution to the knowledge base.

### Act Structure (approved) vs. final shape

Approved: Answering the Call (intro) → The Hardest Summer → A Chance to Catch
My Breath → Full Circle, with the deep backstory in play and the photo device
as spine. Final (4:26): present-day navigator + listening/empathy thesis →
first-person reveal ("I really sat outside… This is my story") → "Brandi's
Story" card → flashback compressed to the point of contact (7-years scope line,
diagnosis/SSDI fact card, food crisis, therapist-referral card, the walk) →
welcome and relief → bridge proof → the climb (Brooklyn's push → volunteering →
cert → choosing Keystone, with a fact card + Adero's praise) → "living comeback
story" → ends on "This is my why." No ask in the film.

### What Worked Well

- **The wide rough cut did its job perfectly.** Every clip in the final came
  from the tagged pool; zero orphans pulled; zero digging. Exploring the deep
  backstory fully is what let Jeff SEE it didn't belong — the exploration was
  process, not waste.
- **The act-by-act cadence + cold-read critic.** Three fresh-eyes critiques
  caught real breaks pre-presentation (orphan pronouns, false endings, a
  photo-block continuity trap, daughter-count arithmetic). Notably, the beats
  the critics could never fully fix (the partners/kids chronology) are exactly
  what Jeff ultimately cut — repeated coherence-patching is a cut signal.
- **The first-person reveal won.** The #145 door built in-session ("I really
  sat outside… This is my story") became the final's hinge, chosen over the
  CEO's external reveal. When both exist, the subject's own reveal wins.
- **Live viewer partnership**: Jeff's reductions, restores, and re-tags arrived
  as clean correction signal; checkpoint-versioning meant nothing was ever
  lost across two server deaths and a version-role swap.

### What Was Difficult

- **The FCPXML export shipped three defect classes to FCP** before coming
  clean: a negative-duration clip from a mis-anchored caption match, a
  "corrected" swap that played wrong material, and off-frame-boundary times
  from an unquantized fallback duration. All from one root cause — camera-clock
  (time-of-day) caption offsets forcing full-range fuzzy matching. Guards now
  exist at build AND verify (committed with this example).
- **Content cards still aren't rendered in FCPXML** (W2/C6) — and the final
  treatment RELIES on fact cards, so Jeff hand-built all four. Priority up.
- **The viewer's act pill** re-shelves the Library card but not the timeline
  entry (by design, agent reconciles at bake) — read as a bug mid-session.

### Corrections Jeff Made (the record that matters)

1. **Mission-scope the story.** The deep backstory was cut to one fact card:
   "it got too far away from what Keystone actually does and how it helps
   people" — and it was "too much to cover" and "convoluted" (head-scratching
   chronology). Start the flashback at the point of contact with the org; the
   crisis you keep is the one the org answers.
2. **Meth framing** (mid-session): she turned to meth for the ENERGY to keep
   working and caring for her kids — not to mask pain. The energy-to-provide
   framing is the dignified, accurate one.
3. **Photo device cut**: "a little forced and perhaps too nuanced" for a short
   fundraising piece. One full-circle device max in short-form; prefer the one
   that needs no explaining (she works the desk she once stood at).
4. **No ask in the film**: "leave the specific ask to the speakers/presenters
   at the event. It's cleaner and also preserves this edit as a more evergreen
   piece." The film demonstrates; the event solicits.
5. **Word-level cuts are FCP territory** (explicit directive): breath- and
   single-word-level economy "is a judgment you can only make when hearing the
   clip" — out of scope for paper-cut sessions. Promoted to SKILL-edit.md.
6. **Fact-card register**: Jeff's four cards are neutral-informational; the
   hardest fact (diagnosis/SSDI) went on a card, not in her mouth. Narrative
   slide copy did not survive.

### Cardinal Rule Status

**Zero violations** across all emissions: 102/102 spoken entries verbatim at
emit; `_editCuts`→segments conversion exact; Jeff's FCP-level word cuts are
trims, not alterations. One transcript-attribution flag was WRONG (the one-word
"Summer." guessed as interviewer echo — it's Brandy): attribution flags on
one-word utterances are guesses and should be labeled as such.

### Rules That Emerged

1. **Mission-scope the flashback** *(1st sighting — advice, not pre-filter)*:
   the backstory a fundraising film keeps is the part the org's service
   resolves; open at the point of contact. Corollary sighting for the
   three-occurrence discipline, alongside Crisis Nursery (stigma the nursery
   answers) and International Institute (displacement the Institute answers).
2. **One full-circle device max in short-form** *(1st)*.
3. **The film demonstrates; the event solicits** *(1st — candidate "evergreen
   gala" project-type variant: no dated references, no baked-in ask)*.
4. **Word-level cuts are FCP territory** *(explicit directive — added to
   SKILL-edit.md Trimming Guidelines this commit)*.
5. **Gala runtime calibration point #2**: 24:36 rough → 4:26 final (82%
   reduction; International Institute was 76%). Finals land ~4–5 minutes.

### Reference Value

Future projects that should reference this example:
- **Any single-protagonist fundraising film where the subject's hardship
  exceeds the org's mission** — look at what was tagged vs. what survived, and
  Jeff's mission-scope rationale.
- **Evergreen event films** — the ask-exported-to-the-room structure.
- **Any project tempted by a plant-and-payoff device** — the photo device's
  full life cycle (client-suggested → built two ways → cut as forced).
- **Runtime planning for gala pieces** — the 82% reduction curve.

What to look at specifically: `Final_Edit.txt` (43 beats + 4 cards);
`handoffs/keystone-2026/edit-agent-lessons-v1.md` on the project SSD for the
full debrief Q&A; the three-treatment backstory history (full-voice → slides+VO
beat sheet → one fact card) in the project's editing-versions checkpoints.
