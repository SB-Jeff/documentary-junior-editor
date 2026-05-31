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
**Status:** Shipped (viewer + build-script halves) — the rec badge now cycles three
states (must-keep → tight-candidate → probable-keep); the Tight cut filters to
must-keep + tight-candidate via a shared `inTightCut` predicate (used by Tight view,
export, runtime totals, and the Library hide-in-cut filter). New teal badge + card
styling. `build_quotes_viewer.py` no longer collapses `tight-candidate` to
probable-keep. Verified in a browser build (3-state cycle + Tight cut composition).
⚑ DEPENDENCY (out of viewer scope): the Edit Agent populating `tight-candidate`
during the rough cut requires a SKILL-edit.md change — that file is owned by the
Editing Coach. Until that lands, Jeff sets tight-candidate manually (which is exactly
the clean workspace state this item asked for). Flagged in skill-review-notes; NOT
editing SKILL-edit.md unilaterally.
❓ OPEN QUESTION (Jeff, 2026-05-21): suspects three tiers may be unnecessary — that
two (must-keep / probable-keep) might suffice. Will try the three-tier version in a
real session. **For the Editing Coach to evaluate after real use:** does the
tight-candidate tier measurably reduce the must-keep-as-workspace pattern (promote-
then-demote reversals in the tweak log)? If not, revert to two-tier — it's a clean
one-commit backout (2-state badge cycle + `inTightCut` = must-keep only).

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
**Status:** Filed — viewer half was built (badge + view-only sort) then **reverted on
Jeff's call (2026-05-21)**. ✋ DESIGN OBJECTION (Jeff): the cut is meant to be read
top-to-bottom as a narrative (Cardinal Rule 2). **Any sort by confidence pulls quotes
out of their intended playback order** — even a "view-only" sort is misleading and
fights the read-through. The HIGH/MED/LOW *sort* is rejected on these grounds.
Re-attempt only with a NON-reordering design (e.g. a passive ranking badge that never
changes card order, if it's wanted at all — Jeff did not request this; it was
Coach-filed off Nanos). The skill-side half (Edit Agent populating `tight_priority`)
was never built. Reverted commit removed the badge, the sort toggle, the build-script
passthrough, and the demo fixture values.

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
**Status:** Shipped — root cause: native HTML5 drag-and-drop is unreliable inside
Cowork's sandboxed artifact iframe. Reimplemented drag using pointer events
(`onPointerDown` + `setPointerCapture` + `onPointerMove`/`onPointerUp`), which work
in every context and are synthetically testable. **The whole card is the drag source**
(not just the small left-edge grip — grabbing the quote was the natural gesture and
the handle-only design made the feature undiscoverable), excluding buttons and the
trim/text editors; a 5px move threshold distinguishes a drag from a click and text
selection is suppressed mid-drag. Verified with real mouse drags in a browser
(body-drag reorders, buttons/trim still work, no text-selection hijack).
NOTE for Coach/SKILL-edit.md: SKILL-edit.md:1080
says drag reorders "within or across acts," but the implementation (both before and
after this fix) constrains drag to within an act; cross-act moves go through the
act-reassign dropdown. Flagging the doc/behavior discrepancy — not changing
SKILL-edit.md unilaterally.

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
**Status:** Shipped — restored the "+ interstitial" affordance (matches the button
SKILL-edit.md:932 documents) as slim insertion controls between every Edit-view
entry and at each act head. Opens an inline editor with a type selector
(interstitial / title_card / context_beat), text field, and duration estimate.
Non-spoken entries now have a dedicated amber card with editable text/intent +
duration (text editing is allowed — not a verbatim quote; Cardinal Rule 1 governs
spoken quotes only), reorder, act-reassign, rec badge, drop, comment. Review view
renders them inline in the narrative flow — attributed as their type (e.g.
"— TITLE CARD") with italic text to set them apart from verbatim quotes. Persists
via existing round serialization.
Verified end-to-end in a browser build (render, add, Review). No SKILL-edit.md change
needed — the data model already supported these entry types.

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
**Status:** Shipped — added a "Hide quotes in current cut" toggle to the Library
toolbar. Hides any source quote whose `num` appears as a `source_quote_id` on a
timeline entry in the active round, respecting the Rough/Tight cut (Tight uses the
shared `inTightCut` predicate). Default off; persisted per project in localStorage.
Verified in a browser build (8 in-cut quotes hidden, choice survives reload).

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
**Status:** Shipped — added the act-reassign dropdown to each (non-orphan) Library
card, reusing the `.reassign-pop` pattern. Source-quote act is lifted into viewer
working state (`sourceActOverrides` + `quoteActOf`) so the Library regroups
immediately. The change is logged as a `reassign_source_act` tweak so the Edit Agent
persists it canonically to the source pool — the viewer does NOT overwrite the
upstream `tagged-quotes` file. Timeline entries keep their own `part` (no silent
moves). Verified in a browser build (#3 re-tagged Act 1 → Act 2, regrouped, op
logged).

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
**Status:** Shipped — added a search input to the Library toolbar. Real-time,
case-insensitive substring match on verbatim quote text + rationale, composed
AFTER the speaker/act filters and the hide-in-cut filter. Shows a live match count;
transient (not persisted). Verified in a browser build (quote-text match, rationale
match, and composition with the speaker filter).

---

## Open items — hammer-ner-2026 batch (filed 2026-05-29)

> **Provenance note:** These six entries were reconstructed on 2026-05-29 in the viewer
> dev session from the launcher brief; the original Coach filing was not recovered on
> disk (no project-scoped roadmap, tweak-log, or lessons-learned survived in
> `handoffs/hammer-ner-2026/`). Open specifics that the brief deferred "to the entry"
> were settled directly with Jeff on 2026-05-29 and are recorded inline below.
> Entries 1–3 are one coherent redesign of how the viewer represents cut membership —
> built together. Items 4 and 5 are more separable.

### AUTHORITATIVE membership model — Tight / Loose / Library
**Source project:** hammer-ner-2026 (May 2026)
**Problem:** The viewer's current model — one timeline with a per-entry conviction tier
(`must-keep` / `tight-candidate` / `probable-keep`) plus a Rough/Tight *view* filter —
conflates "how convinced am I" with "is it in the cut." It produced the
must-keep-as-workspace contamination and the promote/demote churn. The mental model an
editor actually works in is membership, not conviction.
**Proposed change:** Replace conviction tiers + the Rough/Tight toggle with an
authoritative two-window membership model over three strata. **Tight** = the active
default working cut. **Loose** = a fuller reference cut, kept **LIVE** (re-derived from
current state, never frozen). **Library** = the full source pool. Three verbs move
entries between strata (see "Three persistent strata" below). Retire
`runtime_recommendation`, `REC_CYCLE`, the rec badge, `cutFilter`, and `inTightCut`
entirely. This supersedes and obviates the earlier `tight-candidate` work and its
cross-scope dependency (Edit Agent populating `tight-candidate`) — flag for Coach.
**Priority:** P0 — foundational; everything else builds on it.
**Status:** Shipped (with "Three persistent strata" below — one commit). Every timeline
entry now carries `membership: "tight" | "loose"`; `membershipOf(entry)` migrates legacy
data on load (must-keep + tight-candidate → tight; probable-keep → loose; non-spoken
structural entries → tight). Retired `runtime_recommendation`, `REC_CYCLE`, the clickable
rec badge, `cutFilter`, and `inTightCut` from the JSX; the build script's
`migrate_recommendations_two_tier` became `migrate_membership` (assigns membership, drops
`runtime_recommendation` from emitted entries). Verified in a browser build: migration
maps legacy recs, no console errors, build-script migration unit-tested.
⚑ Cross-scope flag for Coach (NOT edited here): the `tight-candidate` SKILL-edit.md
dependency is now obsolete — see the existing cross-scope section below.

### Three persistent strata an editor dances between
**Source project:** hammer-ner-2026 (May 2026)
**Problem:** Membership needs an unambiguous containment rule and unambiguous verbs, or
"drop" becomes destructive-by-accident and the windows drift out of sync.
**Proposed change:** Enforce **Library ⊇ Loose ⊇ Tight**. Tight is the hub. Verbs
(settled with Jeff 2026-05-29):
- **Cut** — Tight → Loose. The only one-level demotion; lives in the Tight window.
- **Add** — Loose → Tight, *and* Library → Tight (pulling a quote from the Library lands
  it straight in Tight). Upward movement always targets Tight.
- **Drop** — Tight or Loose → Library, all the way back (a one-level drop would just
  duplicate Cut, so there is no intermediate stop and no separate "banish" verb).

This gives Loose a clean meaning: *entries cut from Tight but not dropped.* The only way
into Loose is by cutting from Tight. Naming: strata Tight / Loose / Library (avoid
"archive" — collides with version history); verbs Cut / Add / Drop. Dropping from tight
demotes to **Library**, not Loose (resolves the brief's internal contradiction).
**Priority:** P0 — the data/containment detail behind the membership model.
**Status:** Shipped (with the membership model above — one commit). Verbs implemented in
each card's action row: **Cut → Loose** (tight cards, blue `btn-cut`), **Add Back → Tight**
(loose cards, green `btn-add`), **Drop → Library** (red `btn-drop`, relabeled from the old
"Drop entry"). Quote Library **Add** lands a quote straight in Tight (`membership:"tight"`).
Each membership move records a `set_membership` tweak-log op (before/after). Per Jeff
(2026-05-31), interstitials/title-cards/context-beats get the Cut/Add Back verbs too (not
pinned to Tight). Window toggle replaces Rough/Tight: **Tight** (default, green) shows
`membership==tight`; **Loose** (blue) shows tight ∪ loose; metric + Export sit in this
block; `inActiveWindow(e)` rewired through sourceIdsInCut, passesTimelineFilters, runtime
totals, the header toggle, export, and renderReview. Verified in a browser build: Tight
shows 6 / Loose shows 9 on the fixture, Cut/Add Back/Add move membership and log ops,
palette matches the approved mockup (green=Tight, blue=Loose, red=destructive).

### Unify Edit + Review into one page with per-card reveal
**Source project:** hammer-ner-2026 (May 2026)
**Problem:** Edit and Review are separate tabs; you can't read the cut clean and tweak
one quote in place without tab-switching and losing your place.
**Proposed change:** Collapse Edit and Review into one surface. Default = clean read
(Review styling). Any card flips to edit-in-place ("uncover the stone for that one
quote") while surrounding cards stay clean; multiple cards open at once; a global
all-on / all-off control.
**Priority:** P1.
**Status:** Filed.

### "Talk to agent" should send iteratively (send-and-keep-working)
**Source project:** hammer-ner-2026 (May 2026)
**Problem:** The "Talk to agent" panel is a single cumulative catalog sent once. You
can't fire off a scoped batch mid-session and keep working — the model is one-shot.
**Proposed change:** Per-send queue: accumulate tweaks → Send a scoped batch at any time
(no viewer rebuild, Jeff keeps working) → panel **clears** and accumulates fresh for the
next batch. **Send-and-keep-working only — NOT live in-place rebuild.** Decisions
settled with Jeff 2026-05-29:
- **Persistence:** keep one cumulative `handoffs/[slug]/tweak-log-v[N].json` (Option A),
  appending every batch into it with a `batch` number + timestamp on each op so batch
  boundaries are preserved. Coach reads one file (matches `SKILL-editing-coach.md`).
- **Per-batch intent note:** one free-text reasoning note per batch, entered at Send
  time and stored on the batch, so the reasoning travels with the ops it explains.
- **Retire "Comment on this":** the per-op comment button (and its `comment` op) is
  removed; per-batch notes replace it. ⚑ Cross-scope flag for Coach: this drops the
  per-entry "Comment on this" annotations that `SKILL-editing-coach.md` lists as a named
  pattern category — Coach's documented input changes. Not editing the Coach skill file
  from the viewer project.
**Priority:** P1.
**Status:** Filed.

### BUG: split function duplicates the quote instead of splitting it
**Source project:** hammer-ner-2026 (May 2026)
**Problem:** Splitting an entry clones the full `segments[]` onto both halves instead of
partitioning the segment range — you get two copies of the whole quote, not a head and a
tail.
**Proposed change:** Split should partition the segment range across the two entries
(head → A, tail → B) with the boundary trims set on each side, preserving verbatim
integrity. Self-contained; can ship independently of the membership rework.
**Priority:** P1.
**Status:** Filed.

### [SUPERSEDED] Replace rough/tight toggle + conviction tiers with subtractive refinement in place
**Source project:** earlier entry, pre-2026-05-29 (original text not recovered)
**Status:** Superseded in terminology by the AUTHORITATIVE membership model above
(rough → Loose, tight → Tight). Implement to the membership model where they differ.
Retained as a pointer only; no separate build item.

---

## Cross-scope dependencies — for Editing Coach / Skill Review

The viewer batch (v5.6, 2026-05-21) shipped the **viewer + build-script halves** of
two items that also need a **`SKILL-edit.md`** change. `SKILL-edit.md` is owned by the
Editing Coach, so the viewer project did NOT edit it. These are the open coordination
items:

1. **Edit Agent should populate `tight-candidate`** during the rough cut for
   borderline-essential quotes. The viewer now supports the state (badge cycle + Tight
   cut filter); until the Edit Agent emits it, Jeff sets it manually. Needs a
   `SKILL-edit.md` rule change (the documented system is currently two-tier:
   must-keep / probable-keep only).

(The `tight_priority` ranking item was built then reverted on Jeff's call — its sort
violates narrative reading order. See that roadmap entry above; no SKILL-edit.md work
is pending for it.)

Also flagged (doc/behavior discrepancy, no code change made): `SKILL-edit.md:1080`
says drag-to-reorder works "within or across acts," but the viewer constrains drag to
within an act (cross-act moves use the act-reassign dropdown). Reconcile the doc or
the behavior — surfaced for the skill owners to decide.

---

*Maintained as part of the `documentary-junior-editor` skill set. Coach writes here;
the Claude Code viewer project reads here.*
*Current as of: 2026-05-29*
