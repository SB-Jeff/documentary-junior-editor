# Claude Code Prompt — Quote Viewer Development

This file holds the launch prompt for starting a Claude Code session focused on
quote viewer development. Copy the block under "Launch prompt" into a new Claude
Code session pointed at `~/Desktop/documentary-junior-editor/`.

Each session works through one or more items from `quotes-viewer-roadmap.md`.
The roadmap is the source of truth for what to build; this prompt sets up the
context Claude Code needs to do it well.

---

## Before the first session — one-time per Mac

1. Install Claude Code if you haven't already.
2. Confirm the canonical skill repo is cloned at `~/Desktop/documentary-junior-editor/`
   and is on the `main` branch with no uncommitted changes (`git status` should
   be clean before each session).
3. Confirm you can run the viewer locally if there's a dev server / build
   command (check `scripts/` for any build helpers).

---

## Launch prompt — copy into a new Claude Code session

```
You are working on the quote viewer for the documentary-junior-editor
pipeline. The codebase is at ~/Desktop/documentary-junior-editor/.
The canonical viewer template is scripts/quotes_viewer_template.jsx
— a React component compiled into a self-contained HTML artifact that
runs inside Anthropic's Cowork environment.

Your work queue is quotes-viewer-roadmap.md at the repo root. Read it
first. Each entry has a Problem, Proposed change, Priority, and Status.
Work items from highest priority down (P0 → P1 → P2). Update each
entry's Status as work progresses ("Filed" → "In progress" → "Shipped").

## Pipeline context (read once, then refer back as needed)

The viewer is the Edit Agent's primary work surface in the documentary
editing pipeline. Read SKILL.md for the full pipeline overview. The
Edit Agent specifically (SKILL-edit.md) describes what the viewer must
support — selection, trimming, sentence-level reorder, splitting,
interstitials, status badges, the Send-to-agent feedback panel.

The Editing Coach Agent (SKILL-editing-coach.md) reads the viewer's
override log (the "Talk to agent" pending tweaks list) and turns
patterns into SKILL-edit.md updates. Several roadmap items exist
specifically to make Coach's job easier — most importantly tweak-log
persistence (P0). Read SKILL-editing-coach.md to understand what
Coach expects from the viewer.

## Cardinal Rules — these are absolute

Two pipeline-wide rules apply to your work too. Both are documented in
SKILL.md but worth stating here because the viewer is where editorial
decisions become permanent:

1. **Verbatim quotes.** The viewer must never enable paraphrasing or
   editing of quote text. Trim (cut from head/tail/middle), reorder
   segments, split into sub-quotes — all fine. Changing the actual
   words is forbidden. If a UI affordance you're tempted to add would
   let Jeff alter words, do not add it.

2. **Narrative coherence.** The viewer must support, not obstruct, the
   Edit Agent's ability to satisfy narrative coherence. Interstitials,
   reorder, drop-and-restore — these are coherence-supporting tools and
   must remain functional. The "interstitials between quotes" roadmap
   item exists because the viewer currently can't satisfy this rule
   directly.

## What's in scope for viewer work

- scripts/quotes_viewer_template.jsx and any companion scripts in
  scripts/ that build, generate, or test the viewer
- Roadmap entries in quotes-viewer-roadmap.md
- Updates to SKILL-edit.md if a viewer change requires updating what
  the Edit Agent tells Jeff about the viewer (e.g., new affordance to
  document). Coordinate via roadmap entry's Notes field — don't
  unilaterally rewrite SKILL-edit.md without flagging it.
- CHANGELOG.md when you ship a release
- Tests for the viewer if a test framework exists

## What's NOT in scope

- Other SKILL files (SKILL-creative-context.md, SKILL-transcript.md,
  SKILL-synthesis.md, SKILL-fcpxml.md, etc.) — these belong to their
  respective agent owners
- The reference-examples/ folder — owned by Skill Review Agent
- The handoffs/ pattern — pipeline state is the agent system's concern
- Editing Coach or Skill Review skill files — owned by the Cowork
  editorial sessions

If a roadmap item requires changes outside scope, surface the
dependency to Jeff before making the change.

## How to work each item

1. Read the roadmap entry.
2. If anything is unclear (which user gesture triggers a behavior, what
   the exact data shape should be, what acceptable performance looks
   like), ask Jeff before implementing — don't guess.
3. Look at the current code to understand what's there and where the
   change lands.
4. Propose the implementation approach (in 1-3 sentences) and ask Jeff
   to confirm before writing significant code.
5. Implement.
6. Test manually in the rendered viewer if possible. If a test
   framework exists, add tests.
7. Update the roadmap entry's Status to "In progress" when you start,
   "Shipped" when committed.
8. Commit with a descriptive message referencing the roadmap entry.
9. Move to the next P0 (or next P1 if P0s are done).

## Commit pattern

```
viewer: [short imperative description]

Roadmap item: [entry title]
[What changed and why, in 2-4 lines]
```

Push to origin/main when Jeff approves. Pulled into next editing
session via the standard project setup workflow.

## Don't try to do everything in one session

The roadmap is long and will grow. Pick 1-3 items per session based
on priority and how related they are. Ship small, ship often, let
Jeff see incremental wins.

## When the session is done

1. Confirm all started items reached either "Shipped" or are explicitly
   handed back to "Filed" with a note explaining the blocker.
2. Run git status — confirm no orphan changes.
3. Summarize what shipped, what's still in progress, what blockers
   surfaced. Note any new roadmap entries discovered during the work
   (Jeff confirms before they land in the roadmap).
4. Remind Jeff to git push if not already done.

Start by reading SKILL.md, then quotes-viewer-roadmap.md, then ask me
what I want to focus on this session.
```

---

## After the session

When Claude Code finishes a session, the repo should have:
- Updated viewer code (`scripts/quotes_viewer_template.jsx` and possibly
  related scripts)
- Updated `quotes-viewer-roadmap.md` with Status field changes
- Maybe a CHANGELOG.md entry if the viewer release is significant enough
  to bump a version
- Clean git status if everything was committed and pushed

If you wrap up a session and the viewer code has changed, the next
documentary editing project that pulls the skill folder will pick up the
new viewer automatically — that's the whole point of keeping the viewer
template in the canonical skill repo.

## When to update this prompt file

Update this file when:
- The viewer codebase changes location or structure
- The pipeline architecture changes in ways that affect what the viewer
  needs to support (new Cardinal Rules, new data model)
- The roadmap format changes
- Patterns emerge that future sessions should know about

Don't update it for project-specific or one-off concerns. This is the
reusable launcher; per-session context goes into the session itself.

---

*Maintained as part of the `documentary-junior-editor` skill set.*
*Current as of: 2026-05-21*
