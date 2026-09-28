# Lessons Learned — Valley Outreach 2026 Values Video
## Completed: round 1 locked 2026-09-28 (FCP final pending)
## Project Type: Organization Values / Culture Film (first of this type in the knowledge base)
## Subjects: 6 — Jess (Director of Communications & Development; frames the film), Russ (volunteer — Kindness), Kris (Client Support Services, 17 yrs — Connection), Mia (food shelf coordinator — Equity), Eurell (StyleXchange program manager — Collaboration), Mirella (donor + board member — Trust)

> Not a client story. Jeff: "an organizational exposé that highlights their values and how
> they guide the work they do. It's meant to highlight the solidness of the foundation. For
> the purposes of this video, that foundation and pure intent is the reason that people
> should continue to support via donations or volunteering." Evergreen; no crisis spine; no
> baked-in ask (the event solicits); no clients on camera (client request). Deliverables:
> one premiere + five per-value vignette cutdowns for the Oct 24 mixer.

### Project Summary
Six interviews shot 2026-09-23; ran the whole pipeline (transcription → creative context →
orchestrated fan-out → synthesis → act-by-act edit → FCPXML) in ONE Claude Code session on
2026-09-28 — the v5.15 viewer-versioning acceptance test. The interview guide (Jeff's, client-
approved) already carried the three acts: The Community We Want to Create / What It Takes /
The Future We Create Together. Round-1 tight cut: 32 entries (26 spoken + 6 title cards),
~5:37 speech; Act 1 Jess-only ~0:54, five value mini-acts ~4:04, Act 3 ~0:37.

### Act Structure (approved) vs. what Jeff cut
Proposed with a separate Intro; Jeff folded it into Act 1 ("an intro is part of Act 1 unless
we agree upon it up front"). Act 1 became Jess alone: welcome → "always a crisis for someone"
→ five-values card → "our values aren't just words". Act 2 = five mini-acts, each opened by a
card, one speaker each, in the approved order Kindness → Connection → Equity → Collaboration →
Trust. Act 3 = two Jess lines, ending forward on "they can thrive".

### What Worked Well
- **Act-by-act live partner loop on v5.15**: 21 steps, every proposal adopted live (once the
  agent stopped opening its own viewer tab); Jeff's restores/cuts were clean signal.
- **The cold-read critic**, especially once repeated flags were treated as cut signals
  (Collaboration and Trust came in cleaner on the second read than earlier acts).
- **Surfacing the floor on request** (Mirella): a ranked list + one recommendation, "add them
  all back threaded, I'll prune" → Jeff kept exactly one. Cheap in the viewer; pure signal.
- **Orchestrator fan-out in-session** (7 subagents, ~8 min, validation + TC gate clean).
- **Content cards now render in FCPXML** — fixed in-session after Jeff reported it from FCP.

### What Was Difficult
- **The rejected Intro**: three trimmed Russ fragments; a head-trim orphaned "it"; "nobody
  talks about values" played before the values existed. The critic flagged the "it"; the
  agent rationalized it. → cut-signal rule (SKILL-edit v5.16).
- **Equity as a program report** (delivery 3×/week, global food section) next to Kindness and
  Connection, which Jeff had cut as the speaker's lived relationship to the value. Rebuilt
  from the lived lines. Deliberately NOT a rule — handled by the two dialogue moments.
- **Kris's father story** kept as "the one backstory the org resolves" (Keystone lens); Jeff:
  too personal for an organizational video — the story was about her family, not the
  organization. → relevance rule.
- **Two viewer instances** (agent's preview tab + Jeff's Chrome) clobbered `current.json`;
  fixed by rule + step-sequence adoption + instance warning.
- **One Kris clip** ("it means to feel like you belong", 7 words) missed the caption matcher
  at 0.535 vs 0.55 → length-scaled threshold + hole-fill fallback.

### Corrections Jeff Made (the record that matters)
1. No separate Intro unless agreed up front; strictly three acts.
2. Don't assemble an opening from cross-speaker fragments; open on a whole thought.
3. Edit for the whole film, not the act — Act 1 doesn't need "we can show it"; Act 2 is the proof.
4. Trim-then-cut is normal; don't ask about it.
5. The roadmap is the best guess at the time; adjust it against the material.
6. Personal history that isn't about the organization is out (father/alcoholism story).
7. A value segment is the person living the value, one idea per line, ~40–60 s, ends on the
   strongest line — not a list of what the org built. (Observed across all five of his cuts.)
8. Repeated critic flags on a line = cut it (parking-lot line "makes no sense in the edit").
9. For the Trust beat he restored five lines to hear them and kept only the one that names the
   donor's doubt (the fraud climate) and answers it.
10. Debrief posture: don't create restrictive rules from a one-off project type; use dialogue.

### Cardinal Rule Status
Zero violations: every entry `_editCuts` → segments conversion verified verbatim; the
agent's only text changes were trims and splits. One transcription-side flag: Mirella's
on-camera name is rendered "Mireya Rangel" by ASR — spelling to confirm before titles.

### Reference Value
- **Any Organization Values / Culture film** (nonprofit or company): the mini-act shape (card
  → one speaker → 3–5 lived lines → strongest line last), the Jess-only frame, and the
  "foundation is the reason to support" thesis with no ask.
- **Any project with no reference example**: the two dialogue moments were born here.
- **Runtime shape**: ~5:37 round-1 speech against a 4–5 min target (Jeff cut ~1:00 off the
  agent's assemblies per act on average).

### Files
- `transcripts/` — the six raw transcripts. `Final_Edit.txt` — pending Jeff's FCP final
  (export the finished XML; derive verbatim-as-played from its captions, as Keystone did).
- Project SSD: `handoffs/valley-outreach-2026/` (all handoffs, 21 edit steps,
  `edit-agent-lessons-v1.md` = the debrief agenda with decisions, `drafts/edit-session-
  corrections.md` = the timestamped raw log).
