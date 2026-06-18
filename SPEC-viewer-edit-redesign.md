# SPEC — Quote Viewer + Edit Agent Redesign (act-by-act live partner)

Status: approved design, pre-build. Source of truth for the `viewer-edit-redesign` branch.
Origin: 2026-06-18 design/interview session with Jeff (see memory `viewer_edit_redesign_2026_06_18`).
Supersedes the Tight/Loose/Library terminology in the v5.9 viewer and the multi-session
Edit-Agent flow in `SKILL-edit.md`.

---

## 1. Purpose

Turn the quote viewer from a throwaway Cowork chat artifact into a **persistent, agent-readable
local app**, and turn the Edit Agent from an open-loop "drops a finished cut you reverse-audit"
into an **act-by-act live partner** that proposes first and shows its reasoning (including what it
left out). The redesign fixes the three editorial complaints (miscategorized / omitted /
over-trimmed quotes) — all of which were traced to silent agent judgment in an open loop, not bad
upstream data.

Mirrors Jeff's own from-scratch method (memory `jeff_editorial_method`).

---

## 2. Core concepts

- **Act-by-act.** Work proceeds one act at a time (a doc is ~3 acts + an Intro). The act tabs
  (`All / Intro / Act 1 / Act 2 / Act 3`) are the structure; there is **no step indicator** — the
  "Categorize → Build → Refine" phases map onto the views, not onto buttons.
- **Agent proposes, Jeff disposes.** The agent always makes the real call first (pre-sorts the
  Library by act, pre-builds an over-inclusive Timeline, flags low-confidence categorizations);
  Jeff corrects. The asymmetry is the training signal the Editing Coach learns from.
- **Three tiers, subtractive** — see §4. The Library keeps every quote forever; nothing is ever
  destroyed.
- **Trimming is a separate axis** from the tiers: a trimmed quote stays in the Timeline (just plays
  shorter); trims are reversible.

---

## 3. Data contract

### 3.1 Existing (keep) — from `build_quotes_viewer.py` / `sample_viewer_data.json`
- `PROJECT_TITLE`, `PROJECT_META { slug, ssd_root, target_seconds, act_labels[], speakers[] }`
- `SOURCE_QUOTES[]`: `{ num, originalNum, speaker, speakerSlug, role, quote, startTC, endTC,
  part (act label), rationale, is_orphan, segments[] }`
- Trims today are character-range over the quote text; segments[] carry per-segment TCs.
- Current membership: `entry.membership ∈ {tight, loose}`; Library = source quotes with no active
  entry; `Library ⊇ Loose ⊇ Tight`.

### 3.2 Tier remap (relabel, do not rebuild the membership engine)
- `tight`  → **Timeline** (the working cut)
- `loose`  → **Cuts** (removed from the Timeline, recoverable; starts empty)
- Library  → **Quote Library** (every quote; the Library *view* shows all tiers)
Containment is unchanged: `Library ⊇ Cuts ⊇ Timeline` in set terms, but the UI treats Timeline and
Cuts as the two placements and the Library as the permanent superset.

### 3.3 Required extensions (new wiring)
- **Act titles + roadmaps + premise.** Today only bare `act_labels` ("Act 1") reach the viewer.
  The Creative Context handoffs (`act-structure-v[N].md`, `creative-brief-summary-v[N].md`) carry
  the descriptive title ("Business Challenge") and the per-act narrative roadmap and the premise.
  Add to `PROJECT_META`: `acts: [{ label, title, roadmap }]` and `premise`. Build script must read
  these from the Creative Context handoffs (or accept them in the JSON).
- **Agent rejection notes.** Each Library (not-used) quote may carry `agent_note` — why it was left
  out ("overlaps #3/#9"). Populated by the Edit Agent.
- **Split lineage.** A split produces sibling entries with a shared `split_src` (e.g. `5a`/`5b` →
  `split_src: "5"`) so **Rejoin** can stitch them back verbatim.
- **Saved cuts (deliverables).** A named save = a snapshot of the Timeline arrangement +
  trims + tier assignments, stored as `editing-versions/<name>.json` (extends the existing
  `editing-versions/v[N].json`). Multiple named deliverables per project (long cut, social shorts)
  coexist; Open loads one; Save offers "save changes to this cut" (overwrite) and "save as new".

---

## 4. The three tiers (subtractive model)

- **Quote Library** — every catalogued quote, the permanent inventory. The Library *view* is
  organized by act and is BOTH the categorize surface (verify/fix buckets) AND the rejected-quotes
  home (left-out quotes show the agent's `agent_note`). Each quote shows a status badge
  (`In timeline` / `In cuts` / `Not used`).
- **Timeline** — the working cut. Pulling a quote from the Library lands it here. Starts
  over-inclusive (agent-built); Jeff winnows down.
- **Cuts** — recoverable bin. Starts empty; fills with quotes cut from the Timeline. Restore →
  Timeline; Discard → back to the not-used Library (NOT a delete).

Top view tabs, in workflow order: **Quote Library → Timeline → Cuts.**

---

## 5. UI component inventory (the canonical interface — all of this ships)

Top bar: project name · **Save** (save changes to this cut / save as new named cut) · **Open**
(reopen a saved cut) · **Export to Final Cut**.
Act nav row: `All / Intro / Act 1 / Act 2 / Act 3` (left-aligned).
Sub-header: active act title inline — `Act 3 · Results & Impact · [Creative context ▾]`.
Creative context dropdown: **act-scoped** — on All shows premise + all act roadmaps; on a single
act shows only that act's roadmap. Sourced from Creative Context agent.
Agent panel: the agent's current proposal/reasoning, with the **staleness cue** (§6.4).
View filter: `Quote Library / Timeline / Cuts` + **interview/speaker** dropdown.
Mode (Timeline view only): segmented **Review | Edit**; in Edit, secondary **Open all / Collapse
all**.
Search (Library view): text search + **"exclude quotes already in the Timeline"** toggle.

Timeline · Edit-mode card: **drag handle** (reorder *within* an act only), speaker (no quote
number), header **Cut** + **Edit**; expanded = inline editable box (select text + **Delete** to
trim → strikethrough; typing blocked = verbatim), **Reset trims** (only when trimmed), **Split
here** (at cursor), **Rejoin** (on split parts, with a "Split of #N" tag + shared left-edge).
Collapsed card shows the quote **as it plays** (trimmed text hidden, no strikethrough).
Timeline · Review-mode: clean serif read of the cut, trimmed text hidden, grouped by titled act;
agent **seam-flags** inline (§6.6).
Quote Library card: compact clickable **act pill** (recategorize — Library only) *before* the
status badge; speaker; quote text; `agent_note` if not used; **Add to Timeline** action.
Cuts card: **Restore** / **Discard**.
All view: whole cut grouped by titled act headers; in Review mode you read the film end to end.

---

## 6. The six resolved design decisions

1. **"Cut" / "Cuts" kept** — natural editor language; the film is the "Timeline"/deliverable name,
   never "the cut", so no collision.
2. **Rejoin** — split parts share a subtle left-edge + "Split of #N" tag; each has a Rejoin button
   that merges the verbatim words back into the single source quote.
3. **Discard kept** — clears a quote out of the Cuts bin back to the not-used Library; NOT a
   delete. The Library keeps everything always → no destructive action, no confirm dialogs.
4. **Staleness cue** — agent panel shows "✓ Up to date with your edits"; the moment Jeff edits
   after the agent's last message it flips to amber "↻ You've changed things since I last looked —
   ask me and I'll catch up." Sending a message clears it. Honest, not fake real-time. (The agent
   reads viewer state when it is its turn — i.e. attached to each of Jeff's messages.)
5. **Shared quote handle (numbers hidden)** — agent→Jeff: natural-language reference + viewer
   auto-scrolls/highlights the card; Jeff→agent: per-card **"Point at this"** tags the exact quote
   into his message. Numeric IDs stay under the hood (hover fallback).
6. **Narrative coherence (Cardinal Rule 2)** — surfaced as agent **seam-flags inside Review mode**
   (orphan pronoun, abrupt jump, already-made point), each with a suggested fix/bridge. Appears
   where Jeff reads, only when flagged.

---

## 7. Persistence & app shell

The viewer must survive task-switching and support named, recallable saved cuts — impossible on the
Cowork chat-artifact model (artifact is ephemeral; `sendPrompt` unavailable; persistence is a
brittle 3-tier fallback). Target: a **persistent local app** served in Chrome, sharing state with
the agent through files on disk.
- Saved cuts → `editing-versions/<name>.json` (named deliverables, not just v[N]).
- Export → packages the current Timeline and hands to the FCPXML Agent, which builds the `.fcpxml`
  from the media reference / angle IDs already extracted by FCPXML Params. The viewer does NOT
  generate XML itself (unchanged from today's Export contract).
- Agent reads the viewer's current state from disk on each of its turns (no copy-paste, no
  PDF-printing). Mechanism to be finalized in build (reuse/extend `viewer_save_server.py`).

---

## 8. Agent-side changes (`SKILL-edit.md` and friends)

- Replace the open-loop "generate full artifact → reverse-audit" flow with the **act-by-act loop**:
  per act the agent (a) presents its categorization + flags low-confidence ones, (b) builds an
  over-inclusive Timeline with visible reasons including **what it left out** (`agent_note`),
  (c) refines continuously (order/cut/trim/split) with Jeff.
- Remove the step-indicator framing; the views drive the workflow.
- Emit the staleness/seam-flag/point-at-this affordances' data.
- Preserve both Cardinal Rules verbatim.

---

## 9. Build phases

1. **This spec** (done).
2. **Viewer** — rebuild `quotes_viewer_template.jsx` + `build_quotes_viewer.py` to §4/§5/§6,
   wired to a real project's `tagged-quotes` JSON + Creative Context handoffs; verify in a browser
   build (`test_viewer_build.py` + preview MCP). Reuse the membership engine (relabel, don't
   rebuild).
3. **Persistence/app shell** — §7.
4. **Agent skill** — §8.
5. **Run the full loop on a real project**; iterate.

---

## 10. Open items / defaults for the build

- Act titles/roadmaps/premise wiring (§3.3) requires the build script to read Creative Context
  handoffs; if absent, fall back to bare `act_labels` and an empty roadmap (degrade gracefully).
- "Point at this" → exact data shape of the tag handed to chat: TBD in build (default: speaker +
  first six words + hidden id).
- Seam-flags: agent-emitted, stored per-Review-render; default off when the agent hasn't run.
- Saved-cut file naming/collision rules: TBD in build (default: slugify name; on collision, suffix).
