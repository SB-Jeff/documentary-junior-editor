# Pipeline Architecture Spec — v4.0

## Status: Draft
## Date: 2026-03-26
## Context: Issues identified during Dr. Pan Intro trimming session

---

## Problem Statement

The current pipeline separates the editing process into discrete, sequential agent sessions (Transcript → Tagging → Selection → Trim → FCPXML). In practice, the boundaries between selection and trimming are artificial — editorial decisions at the trim stage regularly surface problems that require changing the selection, and the inability to split quotes into independently orderable subclips limits the editor's ability to construct the narrative they hear in their head. Additionally, the agent has no visibility into the editor's real-time work in the artifact viewer, creating a communication bottleneck where the editor must manually export and paste state JSON to share their decisions.

Three interconnected issues need to be addressed:

1. **Subclip splitting** — quotes need to be splittable into independent subclips that can be individually reordered and interleaved with other quotes.
2. **Merging Selection and Trim** — selection and trimming need to happen in the same session, not sequentially.
3. **Real-time state visibility** — the agent needs to observe the editor's work in the artifact as it happens.

---

## Issue 1: Subclip Splitting

### The Problem

The current system treats each quote as an atomic unit. Splits (e.g., 6a/6b) exist only as trim annotations — metadata in the `initialTrims` object. They are not independent items in the viewer. You cannot grab #21a and #21b as separate cards, reorder them, or slot another quote between them.

### The Use Case

In the Dr. Pan edit, Jeff planned to intercut quotes #21 and #14 in the timeline:

- #21a: "The majority of our patients are female."
- #14: "There is a level of comfort and familiarity when you are with a female provider."
- #21b: "I feel passionate about working with other women to achieve those goals to feel the best you can in your own skin."

This creates a single cohesive thought from two separate interview moments. The current system can't represent this — the FCPXML Agent would lay down #21 and #14 as sequential full clips, and the editor would have to reconstruct the intercut manually in Final Cut Pro.

### Proposed Solution

When the editor splits a quote, the system should create actual independent entries in the quote list:

- **Data model:** A split produces new quote entries (e.g., `num: "21a"`, `num: "21b"`) that reference their parent (`parentNum: 21`) but are otherwise first-class items — they have their own sequence position, their own trim, and their own timecode range.
- **Viewer:** Split subclips appear as independent cards that can be dragged, reordered, and placed anywhere in the sequence. They carry a visual indicator (e.g., "21a" / "21b" badge, matching color) showing they came from the same parent.
- **Split action in the viewer:** The editor enters a "split mode" on a quote (similar to trim mode). They click between words to place a split point. Everything above becomes part A, everything below becomes part B. Multiple splits could produce A/B/C. Each part immediately appears as its own card.
- **Trim + split interaction:** Each subclip can be independently trimmed after splitting. The word-toggle trim editor works on the subclip's text, not the full original.
- **FCPXML output:** Each subclip becomes its own `<clip>` element with accurate timecode ranges derived from the original quote's timecodes. The FCPXML Agent already handles the a/b notation; it just needs subclips to arrive as separate entries in `trimmed-quotes.json` with their own sequence positions.

### Data Structure

```json
{
  "num": "21a",
  "parentNum": 21,
  "speaker": "Dr. Kristin Pan",
  "part": "A Different Kind of Care",
  "sequence": 10,
  "original": "I love working with women. I think that that is one thing that's unique for me...",
  "trimmed": "The majority of our patients are female",
  "split": true,
  "split_part": "a",
  "startTC": "00:18:10",
  "endTC": "00:18:16"
}
```

---

## Issue 2: Merging the Selection Agent and Trim Agent

### The Problem

The current pipeline runs selection and trimming as separate sessions with separate agents. The Selection Agent picks quotes and sequences them, saves `selection-state.json`, and hands off. The Trim Agent reads that file in a fresh session and trims each quote.

In practice, trimming and selection are deeply intertwined:

- Trimming a quote can reveal that it's redundant with a neighboring quote — the editor needs to deselect it, not just trim it.
- Trimming can change the flow enough that the sequence needs reordering — quotes that worked in one order don't work after trimming changes their entry/exit points.
- The editor may want to pull in a previously deselected quote to replace one that isn't working after trimming — this requires going back to the full quote pool, which the Trim Agent currently doesn't have access to.
- Splitting a quote (Issue 1) is an action that sits between selection and trimming — it changes the number of items in the sequence (a selection concern) and the content of each item (a trimming concern).

The artificial separation forces the editor to either: (a) complete all selection decisions before seeing any trims, or (b) go back and restart the Selection Agent session to make changes, losing trim work.

### Proposed Solution

Merge the Selection Agent and Trim Agent into a single **Edit Agent** that handles both selection and trimming in one session. The Edit Agent would:

- Have access to the full tagged quote pool (not just the selected quotes).
- Support selecting, deselecting, reordering, trimming, and splitting in any order.
- Present the paper cut as it evolves, with trims visible in context.
- Track the distinction between "selected" and "deselected" quotes so the editor can pull quotes back in at any time.

The Transcript Agent and Tagging Agent remain separate upstream steps — they produce the raw material. The Edit Agent consumes `tagged-quotes.json` and `act-structure.md` and produces the final `trimmed-quotes.json` for the FCPXML Agent.

### Pipeline (proposed)

```
Transcript Agent → Tagging Agent → Edit Agent → FCPXML Agent
                                    (selection + trimming + splitting)
```

### Skill Changes

- `SKILL-selection.md` and `SKILL-trim.md` merge into `SKILL-edit.md`.
- The new skill covers: initial selection recommendations, sequencing, trimming guidelines (including the cross-quote principles added in v3.0), splitting, and the full handoff to FCPXML.
- The Cardinal Rule (never paraphrase or edit words) carries over unchanged.
- The isolated context window rationale from the Trim Agent needs to be reconsidered — the Edit Agent will necessarily have a longer context. The Cardinal Rule will need to be reinforced through other means (e.g., verification steps, automated checks).

### Handoff Changes

- `selection-state.json` is no longer a handoff document between agents — it becomes internal state within the Edit Agent session (or is eliminated entirely).
- The Edit Agent produces `trimmed-quotes.json` directly, which is the only handoff the FCPXML Agent needs (along with `act-structure.md` and `fcpxml-params.md`).

---

## Issue 3: Real-Time Artifact State Visibility

### The Problem

The agent cannot see what the editor is doing in the artifact viewer. When the editor reorders quotes, toggles selections, or makes trims in the viewer, the agent's only visibility comes from the editor manually clicking "Save State," copying the JSON, and pasting it into the chat. This is slow, breaks the creative flow, and means the agent can't learn from or react to the editor's decisions as they happen.

In the Dr. Pan session, this bottleneck appeared repeatedly:

- The agent presented trim recommendations that didn't align with what the editor was seeing, because the agent couldn't observe the editor's prior changes.
- The editor had to stop editing, export state, paste it, wait for the agent to process it, then resume — disrupting the creative rhythm.
- The agent couldn't learn iteratively from the editor's choices because it only saw snapshots, not the process.

### Desired Behavior

The agent should be able to "watch" the artifact state in something close to real time:

- When the editor makes a change in the viewer (select, deselect, reorder, trim, split), the agent is aware of it without the editor needing to take any manual export action.
- The agent can react — e.g., "I see you deselected #14. That makes sense given #24 already covers the comfort beat. Want me to adjust my Act 2 recommendations?"
- The agent can learn from patterns — e.g., noticing that the editor consistently trims more aggressively than recommended, and adjusting future recommendations accordingly.

### Possible Approaches

**Option A: Artifact state sync via the component.** The React component periodically (or on change) writes its current state to a known location that the agent can read — e.g., a state file in the project folder, or a callback that updates a shared data structure. The agent polls or watches for changes.

**Option B: Bidirectional communication channel.** The artifact viewer and the agent share a communication channel (e.g., via MCP or a lightweight message bus). The viewer sends state-change events to the agent, and the agent can send updates back to the viewer (e.g., loading new trim recommendations without rewriting the file).

**Option C: Cowork-level integration.** The Cowork platform provides a mechanism for artifacts rendered in the preview panel to communicate state changes back to the agent session. This would be a platform-level feature, not something built into the individual artifact.

### Constraints

- The solution must not require the editor to take manual action to share state.
- The solution must not disrupt the editor's creative flow (no modal dialogs, no forced pauses).
- The agent should be able to observe but not override — the editor is always in control.
- Latency should be low enough that the agent's awareness feels conversational, not batched.

### Recommendation

Option C is the most robust long-term solution but depends on Cowork platform capabilities. Option A is implementable today as a stopgap — the React component could write state to a file on save, and the agent could read it. This wouldn't be truly real-time but would eliminate the copy-paste step. Option B is the ideal middle ground if MCP tooling supports it.

---

## Implementation Priority

1. **Merge Selection + Trim into Edit Agent** — this is the most impactful change for editorial quality and is achievable with skill changes alone (no platform dependencies).
2. **Subclip splitting** — requires viewer component changes and data model updates, but is self-contained within the project.
3. **Real-time state visibility** — the most valuable but most platform-dependent. Start with Option A (file-based sync) as a stopgap.

---

*Spec drafted during Dr. Pan Intro trimming session, 2026-03-26.*
