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
**Status:** Filed

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

---

*Maintained as part of the `documentary-junior-editor` skill set. Coach writes here;
the Claude Code viewer project reads here.*
*Current as of: 2026-05-21*
