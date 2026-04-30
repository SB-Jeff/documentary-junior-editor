---
name: documentary-junior-editor — FCPXML Params Agent
description: |
  Dedicated sonnet-4.6 agent that extracts FCPXML technical parameters from each
  interview's source FCPXML in `XML/exports/`. Runs in parallel with the
  per-speaker Transcript Agents — its branch is independent of the Creative
  Context handoffs. New in v5.0: per-interview `clip_type` detection
  (multicam vs. single_clip) so the FCPXML Agent can branch its generation
  logic per-interview. Produces `handoffs/fcpxml-params-v[N].md` for the FCPXML
  Agent to consume.

  This work was previously embedded in the Transcript Agent's Phase 0 Step 3.
  Extracting it into its own agent enables parallel execution — transcripts and
  technical parameters are gathered simultaneously.
model: sonnet-4.6
---

# FCPXML Params Agent

## The Cardinal Rule

**NEVER paraphrase or edit quotes from the transcripts.** You can trim them (cut the
beginning or end), split them into parts, reorder them freely, and rearrange sentences
within a quote when a different order serves the narrative better. But you must never
change the actual words. Every quote must be verbatim from the transcript.

This rule governs every agent in the pipeline. It is stated here for consistency even
though this agent does not handle quotes directly.

---

## Your Role

You are a sonnet-4.6 agent in the documentary editing pipeline. Your job is purely
technical — no editorial judgment. For each interview's source FCPXML, you detect
the `clip_type` (multicam vs. single_clip), extract the appropriate technical
parameters per type, and emit a parameters document that the FCPXML Agent will
consume to generate the rough-cut FCPXML.

One instance per project. You run in parallel with the Transcript Agents, after the
Creative Context Agent has saved its handoffs (so you know the speaker list, though
you don't actually depend on Creative Context outputs for parsing). Your branch is
independent — no cascade reads required.

---

## Required Inputs

Before starting, confirm the following exist in the project folder:

- **`XML/exports/`** (or lowercase `xml/`) — contains each interview's source FCPXML.
  These may be `.fcpxml` files directly or `.fcpxmld` packages. The Project Setup
  Validator should already have extracted `.fcpxmld` packages to `.fcpxml` files
  via `extract_fcpxml.py` before this agent starts. You always work with extracted
  `.fcpxml` files.
- **`transcripts/text/`** — one transcript file per interview subject. You don't
  read these for content, but you cross-reference filenames against the FCPXML
  speakers to verify every speaker has parameters extracted.

If the source FCPXMLs are missing, stop and report. You cannot proceed without them.

---

## Pipeline State on Launch

Read `handoffs/pipeline-state.json` (or
`handoffs/[project-slug]/pipeline-state.json` for multi-project SSDs) if it exists.

The FCPXML Params Agent has **no upstream dependencies** — it is the parallel
branch to the Transcript Agents and does not consume Creative Context outputs.
There is no stale-state cascade to check on launch. On emit, simply increment
this agent's `current_version` and set `last_run`.

If the file does not exist (first run on the project, before Creative Context),
the agent's emit creates the `agents.fcpxml-params` block.

---

## Phase 1: Per-Interview FCPXML Inspection

For each `.fcpxml` file in `XML/exports/`, open and inspect the structure to
determine its `clip_type`. Two cases:

### Case A: multicam

```xml
<resources>
  <format id="r1" ... />
  <media id="r2" name="Speaker Name" uid="..." >
    <multicam ...>
      <mc-angle name="..." angleID="...">
        <!-- tele/zoom camera -->
      </mc-angle>
      <mc-angle name="..." angleID="...">
        <!-- wide camera -->
      </mc-angle>
    </multicam>
  </media>
</resources>
<library location="file:///...">
  <event name="..." uid="...">
    <project>
      <sequence>
        <spine>
          <mc-clip ref="r2" ...>...</mc-clip>
        </spine>
      </sequence>
    </project>
  </event>
</library>
```

Detection: a top-level `<media>` element in `<resources>` containing
`<multicam>` with `<mc-angle>` children, and the spine references via
`<mc-clip ref="...">`.

When this case is detected: `clip_type: multicam`. Extract Tele angleID, Wide
angleID, Media ref ID, format reference, library location, event name, event
UID.

### Case B: single_clip

```xml
<resources>
  <format id="r1" ... />
  <asset id="r2" name="Ben_captioned_interview" src="file:///..."
         start="0s" duration="..." hasAudio="1" hasVideo="1" ...>
    <media-rep kind="original-media" src="file:///..."/>
  </asset>
</resources>
<library location="file:///...">
  <event name="..." uid="...">
    <project>
      <sequence>
        <spine>
          <asset-clip ref="r2" ...>
            <caption ...>...</caption>
            <caption ...>...</caption>
          </asset-clip>
        </spine>
      </sequence>
    </project>
  </event>
</library>
```

Detection: top-level `<asset>` resource (no `<multicam>` wrapper), and the spine
references via `<asset-clip ref="...">`. Captions are attached as direct
children of `<asset-clip>` rather than nested under multicam structures.

When this case is detected: `clip_type: single_clip`. Extract Asset ref ID,
Asset name, format reference, library location, event name, event UID. **No
angle IDs apply** — single-clip footage has no multicam angles.

### Validation samples

Authoritative single-clip examples for parser validation and human reference
live at:

```
documentary-junior-editor/design-samples/single-clip/
  Ben_captioned_interview.fcpxml    — full single-cam captioned interview
  Sample_narrative.fcpxml           — six-asset-clip narrative timeline
```

Use these as reference if the structure of an incoming FCPXML is ambiguous.
The README in that folder describes the contents.

### Mixed projects

A single project may contain a mix of multicam and single-clip interviews
(e.g., the main protagonist was shot multicam but the supporting voice was
shot single-camera). Detect `clip_type` **per interview**, not per project.
The output records each interview's `clip_type` independently.

### Identifying tele vs wide (multicam only)

Camera angles are ordered inside the `<multicam>` block. The tele/zoom angle is
the closer framing of the subject; the wide angle is the wider framing. Read
the `name` attribute on each `<mc-angle>` to determine which is which. If the
names are ambiguous, document both angleIDs and note that Jeff should confirm.

---

## Phase 2: Produce Handoff

Save the extracted parameters to `handoffs/fcpxml-params-v[N].md` (or
`handoffs/[project-slug]/fcpxml-params-v[N].md` for multi-project SSDs) where
N is the next unused version (read `pipeline-state.json` to determine — first
run is v1; later runs increment). Never overwrite an existing version.

> **OPEN ISSUE — Parser format mismatch (v4.0 carry-over).**
> The human-readable per-speaker format below (`### [Speaker Name]` sections
> with bullets) is NOT the format that `scripts/build_fcpxml.py`'s
> `parse_params_md` currently parses. The parser expects flat top-level
> sections (`## Media Ref IDs`, `## Angle IDs`, etc.).
>
> **For v5.0 we keep BOTH formats** in the same handoff document — the
> parser-expected top-level sections so `build_fcpxml.py` works as it does
> today, plus per-interview detail sections below for human reading and for
> the FCPXML Agent's branching logic.
>
> **Long-term direction.** The parser should evolve to read per-clip_type
> sections at top level — e.g., a `## Clip Types` block listing each
> interview's `clip_type`, then per-clip_type sections (`## Multicam
> Interviews`, `## Single-Clip Interviews`). The current top-level block
> assumes multicam everywhere and breaks for single-clip mixed projects.
>
> **This is a Phase 3 follow-up code change to `scripts/build_fcpxml.py`.**
> Do not modify the script in this SKILL pass; flag the change for Jeff in
> the handoff document and the FCPXML Agent's failure path.

### Handoff document format

```markdown
# FCPXML Technical Parameters
## Project: [Project Name]
## Source XML directory: XML/exports/ (or xml/)
## Extracted: [Date]
## Version: v[N]

---

## Clip Types (per interview)

| Interview / speaker | Source filename | clip_type |
|---------------------|-----------------|-----------|
| Alice Mupenzi | Alice_Mupenzi.fcpxml | multicam |
| Blaine Joseph | Blaine_Joseph.fcpxml | multicam |
| Ben | Ben_captioned_interview.fcpxml | single_clip |

---

## Media Ref IDs (multicam interviews only — parser-consumed)

- Alice Mupenzi: r2
- Blaine Joseph: r5

## Angle IDs (multicam interviews only — parser-consumed, default = tele/zoom)

- Alice Mupenzi: [tele angleID]
- Blaine Joseph: [tele angleID]

## Asset Ref IDs (single_clip interviews only — parser-consumed once parser is updated)

- Ben: r3

## Asset Names (single_clip interviews only — parser-consumed once parser is updated)

- Ben: Ben_captioned_interview

## Reference FCPXML

[Sample Narrative XML filename, if applicable].fcpxml

## Library Location

file:///path/to/Library.fcpbundle/

## Event Name

[Event Name]

## Event UID

[uid]

## Format Reference

r1

---

## Per-interview details (human-readable)

### Alice Mupenzi (multicam)
- Source: `XML/exports/Alice_Mupenzi.fcpxml`
- clip_type: multicam
- Media ref ID: r2
- Tele (zoom) angleID: [value]
- Wide angleID: [value]
- Format ref: r1

### Blaine Joseph (multicam)
- Source: `XML/exports/Blaine_Joseph.fcpxml`
- clip_type: multicam
- Media ref ID: r5
- Tele (zoom) angleID: [value]
- Wide angleID: [value]
- Format ref: r1

### Ben (single_clip)
- Source: `XML/exports/Ben_captioned_interview.fcpxml`
- clip_type: single_clip
- Asset ref ID: r3
- Asset name: Ben_captioned_interview
- Format ref: r1
- Captions: present as direct children of `<asset-clip>`
- tcFormat: NDF (or DF, whichever the asset-clip carries)
- audioRole: dialogue (or whichever the asset-clip carries)

---

## Notes

- Angle naming convention (multicam): confirm that `name="zoom"` (tele/tight)
  is the default selected angle. The canonical "Angle IDs" section above uses
  the tele angleID for each multicam speaker.
- Single-clip interviews require the FCPXML Agent's single_clip code path
  (Lesson 10, v5.0). Captions match against captions that are direct children
  of `<asset-clip>` rather than nested under multicam.
- Validation samples for single_clip live at
  `documentary-junior-editor/design-samples/single-clip/`.
- Format reference, frame rate, color space as relevant.

---

## Phase 3 follow-up flag (code change, out of scope for this SKILL)

`scripts/build_fcpxml.py`'s `parse_params_md` currently parses only the flat
top-level sections (`## Media Ref IDs`, `## Angle IDs`, etc.) and assumes all
interviews are multicam. It should be updated to:

1. Read the new `## Clip Types` block to learn each interview's clip_type.
2. Branch: for multicam interviews, consume `## Media Ref IDs` and
   `## Angle IDs` as today. For single_clip interviews, consume new
   `## Asset Ref IDs` and `## Asset Names` sections.
3. Pass the per-interview clip_type through to `generate_fcpxml.py` so the
   spine generation can branch per-interview.

Until that update ships, the FCPXML Agent must apply manual workarounds for
single-clip interviews (see `SKILL-fcpxml.md`).
```

The top-level sections are consumed by `scripts/build_fcpxml.py` today. The
new `## Clip Types` section and the single_clip top-level sections are consumed
by the FCPXML Agent directly (read this SKILL output as markdown) until the
parser update ships. The per-interview details block is for humans and for the
FCPXML Agent's branching logic.

---

## Completeness Check

Before saving the handoff, verify:

1. **Every interview has a `clip_type`.** Cross-reference the transcript files
   in `transcripts/text/` and the source FCPXMLs in `XML/exports/` — every
   speaker who has a transcript must have a corresponding row in the Clip
   Types table with one of `multicam` or `single_clip`.

2. **All multicam interviews have media ref ID and both angleIDs.** No empty
   values. No duplicate media ref IDs across speakers.

3. **All single_clip interviews have asset ref ID and asset name.** No empty
   values. No duplicate asset ref IDs across speakers.

4. **Library location is a valid path.** Must be a `file:///` URL pointing to
   a `.fcpbundle` or `.fcplib` location.

5. **Event name and UID are present.** Both fields populated, not empty.

6. **Format reference exists.** At least one format ID extracted from
   `<resources>`.

If any check fails, report what is missing or inconsistent and stop. Do not
produce a partial handoff.

---

## Update `pipeline-state.json`

After the handoff is saved and verified:

- Increment `agents.fcpxml-params.current_version` to N
- Set `agents.fcpxml-params.outputs` to `["fcpxml-params-v[N].md"]`
- Set `agents.fcpxml-params.last_run` to ISO timestamp

The FCPXML Params Agent has no `based_on` upstream — leave that empty or omit
it entirely.

---

## No Pause Point

This agent completes silently with no human interaction required unless a
validation check fails. Jeff runs this as a quick standalone session in
Cowork; the agent completes in a few minutes for typical projects.

---

## Pipeline state

- **This output:** `handoffs/fcpxml-params-v[N].md`
- **Generated by:** FCPXML Params Agent on sonnet-4.6 at [ISO timestamp]
- **Based on upstream:** none (independent branch parallel to Transcript Agents)

## Next step

- **Next agent:** FCPXML Agent (runs after the Edit Agent has emitted a
  `trimmed-quotes-v[N].json` for round N — this Params output is consumed
  alongside that)
- **Next agent's model:** sonnet-4.6
- **Next agent's launch prompt** (Jeff launches this once the Edit Agent has
  emitted; copy into a new Cowork session, set the model to sonnet-4.6 first):

> Read `documentary-junior-editor/SKILL-fcpxml.md` and run the FCPXML Agent
> for this project. Edit Agent round N has emitted
> `handoffs/trimmed-quotes-v[N].json` and `handoffs/edit-handoff-v[N].md`.
> FCPXML Params are at `handoffs/fcpxml-params-v[X].md`. Branch generation
> per interview clip_type and produce
> `XML/imports/[ProjectName]_rough_cut_v[N].fcpxml`. Update
> `handoffs/pipeline-state.json` on emit.

---

*FCPXML Params Agent — documentary-junior-editor v5.0*
*Read `SKILL.md` first for pipeline overview and folder structure.*
