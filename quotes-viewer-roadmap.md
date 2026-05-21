# Quote Viewer Roadmap

Single source of truth for quote viewer change requests, consumed by the separate
Claude Code project that owns viewer development (`scripts/quotes_viewer_template.jsx`
and supporting scripts).

The Editing Coach Agent files entries here from Cowork editorial sessions when
override-log patterns or session conversations surface friction points that point at
the viewer rather than the Edit Agent. Per-project Coach instances may write to a
project-scoped copy in `handoffs/[project-slug]/quotes-viewer-roadmap.md`; those
entries migrate to this master file at project close (during the Skill Review
Agent's sync phase).

Each entry follows this micro-structure:

```markdown
### [Short descriptive title]
**Source project:** [project-name(s)]
**Problem:** [The friction in Jeff's words]
**Proposed change:** [What the viewer should do differently]
**Priority:** [P0 blocking / P1 high-friction / P2 nice-to-have]
**Status:** [Filed / In progress / Shipped]
```

The Claude Code viewer project reads this file as its work queue. As items ship,
update the Status field to `Shipped` and reference the commit / PR.

---

## Open items (filed)

### Tweak-log persistence — dump override log on session end
**Source project:** 2026 Nanos Boston brand-video (May 2026), and surfaced during
v5.4 architecture work.
**Problem:** When the Edit Agent's quote viewer session ends, the pending-tweaks
panel (the "Talk to agent" log of overrides Jeff made against the Edit Agent's
proposed cut) lives only in browser state. Jeff hits "Send" and the tweaks flow into
the Edit Agent's chat as a one-shot batch, after which the structured log is gone.
This means the Editing Coach Agent has no persisted input to analyze post-session;
Coach has to fall back to the visible viewer state, Jeff's memory, and the
rough/tight diff in `trimmed-quotes-v[N].json`. Fallback works for Nanos but loses
the iteration pattern data (e.g., promote-then-demote pairs on the same entry, which
indicate uncertainty).
**Proposed change:** At session end (or on every Send), the viewer writes the
pending-tweaks list as `handoffs/[project-slug]/tweak-log-v[N].json` directly to
disk via `window.cowork.callMcpTool('mcp__workspace__bash', ...)`. Schema: each
entry is a structured object with `entry_id`, `change_type` (status_flip / trim /
reorder / drop / split / comment), `before` state, `after` state, `timestamp`, and
optional `note` (if Jeff added free-text via the Comment-on-this button). Preserves
iteration order so reversal pairs are reconstructible.
**Priority:** P0 blocking — without this, the Editing Coach Agent operates in
degraded fallback mode on every project.
**Status:** Shipped — viewer writes `handoffs/[slug]/tweak-log-v[N].json` on Send
and Export via `callBash` (no-op outside Cowork). `applyLocalEdit` now records
structured `{seq, entry_id, change_type, before, after, timestamp, note,
description}` ops; log carries top-level `commentary`/`baseline`/`generated_at`.
Schema matches SKILL-editing-coach.md's documented input. Verified end-to-end in a
browser build (status_flip + reorder captured with before/after).

### Tight-candidate state distinct from must-keep
**Source project:** 2026 Nanos Boston brand-video (May 2026).
**Problem:** Jeff is currently using `must-keep` as a workspace toggle, not as a
conviction signal. Because the Tight Cut view filters to `must-keep` only, Jeff
promotes `probable-keep` quotes to `must-keep` so they appear in the Tight view,
then re-evaluates the expanded Tight cut and demotes the ones that didn't earn the
promotion. This contaminates the override log (many promotions are workspace
toggles, not editorial conviction) and produces the promote-then-demote reversal
pattern that's hard for Coach to interpret correctly.
**Proposed change:** Add a third recommendation state — `tight-candidate` — distinct
from `must-keep`. Edit Agent populates it during the rough cut for quotes it judges
borderline-essential. Tight Cut view filters to `must-keep + tight-candidate`. Jeff
promotes/demotes between `probable-keep`, `tight-candidate`, and `must-keep` as
three meaningful states rather than two-with-a-workaround. Keeps the must-keep
signal clean.
**Priority:** P1 high-friction — works around an active editorial pain point; ships
alongside the SKILL-edit.md `tight_priority` change below for full benefit.
**Status:** Filed

### Tight_priority ranking inside probable-keeps (skill-side + viewer-side)
**Source project:** 2026 Nanos Boston brand-video (May 2026).
**Problem:** The Edit Agent hands Jeff a flat pile of `probable-keep` quotes with
no ranking inside the pile. Jeff has to figure out which ones earn promotion to
Tight, which manifests as the must-keep-as-workspace workaround above.
**Proposed change:** Two-part. (1) SKILL-edit.md change: Edit Agent populates a
`tight_priority` field on each `probable-keep` entry (high / medium / low), ranking
which ones it judges most likely to earn promotion to Tight. (2) Viewer change:
expose `tight_priority` as a visible badge on each probable-keep card; allow
sorting by tight_priority within an act. Combined with the tight-candidate state
above, this lets Jeff scan ranked candidates rather than discover them by
experimentation.
**Priority:** P1 high-friction — the viewer half is paired with the tight-candidate
state.
**Status:** Filed (skill-side change is Editing Coach's territory; coordinate the
viewer-side change with the next SKILL-edit.md update).

### Drag-to-reorder in Edit view is broken (regression)
**Source project:** Surfaced during v5.5 work session (2026-05-21), reflecting on
the post-Nanos Editing Coach design conversation. Confirmed by Jeff.
**Problem:** The drag-to-reorder affordance in the Edit view is not working. The
CHANGELOG v5.3 entry explicitly describes drag-and-drop reorder via the left-edge
drag handle as working ("not the whole card — fixes the text-selection-hijack
failure mode"). Current state diverges from documented state. Without working
drag-to-reorder, Jeff has to use the ↑/↓ move buttons exclusively, which is slow
for any non-trivial reordering and discourages exploration of alternative
sequences.
**Proposed change:** Diagnose and fix. Likely candidates: event-handler regression
during a recent template rebuild, drag-and-drop library version mismatch, or
the left-edge drag handle's event binding was lost. Verify against the v5.3
CHANGELOG description of the intended behavior.
**Priority:** P0 blocking — core editing affordance broken; degrades the entire
Edit view experience.
**Status:** Filed

### Interstitials between quotes — regression
**Source project:** Surfaced during v5.5 work session (2026-05-21). Per Jeff:
"Add back the ability to add interstitials between quotes."
**Problem:** The ability to add interstitials (title cards, context beats,
B-roll cues) between quotes in the Edit view is no longer present. This was
working in a prior version. Without this, Jeff cannot satisfy Cardinal Rule 2
(Narrative Coherence) directly in the viewer — the rule explicitly requires
proposing interstitial text when transitions break, and the viewer is supposed
to be where editorial changes happen ("the Viewer Is the Source of Truth" per
SKILL-edit.md). Currently interstitial work has to happen by chatting with the
Edit Agent and asking it to bake them back into the viewer.
**Proposed change:** Restore the interstitial affordance — likely an "+
interstitial" button between adjacent entries in the Edit view, opening a
small editor for the interstitial text + duration estimate. The interstitial
should persist as a distinct entry type in `trimmed-quotes-v[N].json` (entry
type field: "quote" | "title_card" | "interstitial" | "context_beat"). The
underlying data model already supports this per SKILL-edit.md's title-card
and context-beat references; the viewer just needs the UI.
**Priority:** P0 blocking — blocks the viewer from being a complete surface for
Cardinal Rule 2 compliance; forces work-arounds through chat.
**Status:** Filed

### Quote Library — filter out quotes already in the timeline
**Source project:** Surfaced during v5.5 work session (2026-05-21). Per Jeff:
"In the quote library be able to filter out quotes that already appear in the
timeline."
**Problem:** The Quote Library currently shows every catalogued quote without
distinguishing which are already pulled into the active cut and which remain
unused. When the cut is forming and Jeff is looking for material that hasn't
landed yet (orphans worth considering, missing beats), he has to mentally
cross-reference the Edit view against the Library. High friction at exactly
the moment Jeff is doing the "what am I missing" pass.
**Proposed change:** Add a filter toggle to the Quote Library view: "Hide
quotes in current cut." When enabled, hides any quote whose `source_quote_id`
appears as a `source_quote_id` on any timeline entry in the active round +
sub-cut (Rough or Tight, whichever is currently selected). Default: off
(show all). Toggle state persists across sessions via localStorage in the
viewer.
**Priority:** P1 high-friction — meaningfully improves the "find unused
material" workflow during reduction passes.
**Status:** Filed

### Quote Library — re-tag act assignment
**Source project:** Surfaced during v5.5 work session (2026-05-21). Per Jeff:
"In the quote library add the ability to change how the quote was tagged,
i.e. change from Act 1 to Act 2 and so on."
**Problem:** Act reassignment is currently available only from the Edit view
(per SKILL-edit.md: "act-reassign dropdown" on each quote card). When Jeff
is browsing the Quote Library and spots a mis-tag, he has to switch to the
Edit view, find the quote there (only possible if it's currently in the
cut), reassign it, then switch back. For quotes not currently in the cut,
the reassign isn't even possible without first pulling the quote into the
cut.
**Proposed change:** Add the same act-reassign dropdown to each quote card
in the Quote Library view. Behavior identical to the Edit view's dropdown
— change persists to the quote's act tag in the source pool. Update is
visible immediately in both views.
**Priority:** P1 high-friction — closes a parity gap that forces unnecessary
view-switching.
**Status:** Filed

### Quote Library — search
**Source project:** Surfaced during v5.5 work session (2026-05-21). Per Jeff:
"In the quote library view, add a search function."
**Problem:** Quote Libraries at project scale (Nanos had 373 quotes across
10 speakers) are hard to navigate without text search. Currently Jeff can
filter by speaker and act, but finding a specific remembered phrase or
keyword requires scrolling.
**Proposed change:** Add a search input at the top of the Quote Library
view. Real-time filter that matches against quote verbatim text (the
primary field) and optionally rationale text. Case-insensitive, no regex
required. Search applies AFTER existing speaker/act filters (composable).
Empty search = no filter. Search state does NOT persist across sessions
(it's transient by nature).
**Priority:** P1 high-friction — the value scales with project size; Nanos
(373 quotes) and beyond will feel this more than smaller projects.
**Status:** Filed

---

*Maintained as part of the `documentary-junior-editor` skill set. Coach writes here;
the Claude Code viewer project reads here.*
*Current as of: 2026-05-21*
