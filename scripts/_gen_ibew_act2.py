#!/usr/bin/env python3
"""Append the over-inclusive Act 2 (Done Right) build to Jeff's 'Narrative 1' cut.

Narrative 1 lives at handoffs/h-s-ibew-2026/editing-versions/narrative-1.json in
the VIEWER's runtime shape (_editCuts char-ranges). We preserve its 32 Jobs
entries exactly and append Act 2 entries converted to that same shape via the
build's own migrate_entry_trims(). Also merges Act 2 not-used notes + seam-flags
into edit-agent-notes-v1.json (flat handoffs/, where the build reads notes)."""
import json
import importlib.util
from pathlib import Path

SSD = Path("/Volumes/H+S IBEW 2026/H+S IBEW 2026")
H = SSD / "handoffs"
NARR = H / "h-s-ibew-2026" / "editing-versions" / "narrative-1.json"

# import the build module to reuse migrate_entry_trims
spec = importlib.util.spec_from_file_location(
    "bqv", Path(__file__).resolve().parent / "build_quotes_viewer.py")
bqv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bqv)

src = json.load(open(H / "tagged-quotes-v1.json"))
by = {q["num"]: q for q in src}
dr_nums = {q["num"] for q in src if q.get("part") == "Done Right"}
ALL = "ALL"

# --- Act 2 timeline (Done Right), beat-grouped, all tight ---
# None entry = the law-beat context-beat interstitial.
act2 = [
    (67, [0, 1, 3, 4, 5, 6]),   # Jeff — genuine vs. commercialized (OPENER)
    # Beat A — plan-first
    (11, ALL),                   # Andrew — figure it out first, build second
    (68, [0, 3, 4, 7]),          # Jeff — thought out, do it once, done right
    (12, ALL),                   # Andrew — vetting land/community
    (48, ALL),                   # Andrew — other states could learn
    (81, ALL),                   # Jeff — pay more to do it right the first time
    # Beat B — craft
    (8, ALL),                    # Andrew — prefab, not stick-built
    (7, ALL),                    # Andrew — collaborative, smartest people
    (50, ALL),                   # Andrew — Amazon of energy
    # Beat C — environment
    (15, ALL),                   # Andrew — water is MN's concern (setup)
    (16, ALL),                   # Andrew — car-wash rebuttal
    (17, ALL),                   # Andrew — winter car-wash riff
    (19, ALL),                   # Andrew — power / grid
    (77, ALL),                   # Jeff — Rosemount firsthand (water/energy)
    (78, ALL),                   # Jeff — self-imposed delays, new pipeline, adding to grid
    (79, ALL),                   # Jeff — union MN vs. non-union refinery
    (150, ALL),                  # Rachel — Texas cooling comparison
    (147, ALL),                  # Rachel — huge nature person
    (144, ALL),                  # Rachel — water recycling
    (151, ALL),                  # Rachel — green state
    (117, ALL),                  # Brittany — others abusive, MN trying
    (13, ALL),                   # Andrew — we take our landscape
    (14, ALL),                   # Andrew — puts environment-carers at ease
    (18, ALL),                   # Andrew — complaints come via AI/social media
    (20, ALL),                   # Andrew — research it, get involved
    # Beat D — the law (interstitial first)
    None,                        # context-beat: 2025 MN law facts
    (69, ALL),                   # Jeff — laws set terms + manage across life
    (70, ALL),                   # Jeff — aren't parasites in the community
    (72, ALL),                   # Jeff — forced to abide
    (71, ALL),                   # Jeff — MN has a standard / 80%
    (120, ALL),                  # Brittany — feel safe knowing it's a law
    (119, ALL),                  # Brittany — law holds companies accountable
    (118, ALL),                  # Brittany — permitting / monitoring
    (101, ALL),                  # Gavin — could model the country
    (155, ALL),                  # Rachel — a higher standard
    (152, ALL),                  # Rachel — law protects the environment
]

# --- Act 2 not-used notes ---
act2_notes = {
    21: "Left out — duplicate of #11 ('figure it out first, build later').",
    22: "Left out — on-site energy generation; overlaps #19/#50, more abstract.",
    23: "Left out — 'on the horizon' future-tense; vague vs. the concrete rebuttals.",
    45: "Left out — 'MN makes sense, Fortune 500 here'; overlaps the why-Minnesota thesis.",
    46: "Left out — 'MN vets things out'; duplicates #12.",
    47: "Left out — 'space available, environmentally'; overlaps #13.",
    49: "Left out — 'speed to market isn't best'; overlaps #11.",
    66: "Left out — 'data centers are positive, a step above'; overlaps #67, weaker.",
    74: "Left out — 'think it over once more' audience address; softer than the firsthand proof.",
    75: "Left out — 'pushing the envelope the right way'; overlaps #67/#81.",
    76: "Left out — 'people are limited to their own experience'; meta-commentary, no beat.",
    80: "Left out — 'haven't worked in another state'; overlaps #79's MN-vs-elsewhere proof.",
    102: "Left out — 'as long as standards are in place'; duplicates #101, weaker.",
    121: "Left out — 'turning a corner, paving the way'; overlaps #117.",
    145: "Left out of Done Right — safety meetings / morale; reads as Act 1 site-quality.",
    148: "Left out — OFF-MESSAGE ('doesn't really change how I feel') per the brief; use Rachel's on-message takes.",
    153: "Left out — 'things are becoming nature-friendly'; vague, thinner than #147/#150.",
}

act2_seam_flags = [
    {"before_entry_id": "77", "kind": "forward-reference",
     "message": "Jeff #77 opens by referencing 'laws passed here in Minnesota' before the law beat (Beat D) and its interstitial have introduced them.",
     "suggestion": "Head-trim #77 to start at 'Firsthand experience working on a Rosemount data center,' or move the law beat ahead of this firsthand-environment beat."},
]


def seg_entry(num, segs):
    q = by[num]
    idxs = [s["idx"] for s in q["segments"]] if segs == ALL else segs
    raw = {
        "entry_id": str(num),
        "source_quote_id": num,
        "speaker": q["speaker"],
        "part": q["part"],
        "membership": "tight",
        "segments": [{"source_segment_idx": i} for i in idxs],
        "notes": "",
    }
    migrated = bqv.migrate_entry_trims(raw, by)
    assert migrated is not None, f"migration failed for #{num}"
    return migrated


interstitial = {
    "entry_id": "T1",
    "_subLabel": None,
    "source_quote_id": None,
    "type": "context_beat",
    "speaker": "TEXT",
    "part": "Done Right",
    "membership": "tight",
    "_editCuts": [],
    "intent": "The 2025 Minnesota data-center law — the specific provisions (water-use permitting, energy accountability, the standard that lets the state set terms and manage the project across its life) that none of the subjects can state on camera. Lands ahead of the law beat.",
    "research_needed": True,
    "estimated_seconds": 6,
    "notes": "",
}

act2_entries = []
placed = set()
for item in act2:
    if item is None:
        act2_entries.append(interstitial)
        continue
    num, segs = item
    act2_entries.append(seg_entry(num, segs))
    placed.add(num)

# coverage: every Done Right quote is placed or noted
noted = set(act2_notes)
uncovered = dr_nums - placed - noted
assert not uncovered, f"Uncovered Done Right quotes: {sorted(uncovered)}"
assert not (placed & noted), f"Both placed and noted: {sorted(placed & noted)}"
assert not (noted - dr_nums), f"Notes ref non-DoneRight: {sorted(noted - dr_nums)}"

# --- Append to Narrative 1, preserving Jeff's 32 Jobs entries exactly ---
narr = json.load(open(NARR))
orig_count = len(narr["entries"])
assert orig_count == 32 and all(e.get("part") == "Jobs" for e in narr["entries"]), \
    f"Narrative 1 unexpected: {orig_count} entries"
narr["entries"] = narr["entries"] + act2_entries
json.dump(narr, open(NARR, "w"), indent=2)

# --- Merge notes into edit-agent-notes-v1.json (flat handoffs/) ---
NOTES = H / "edit-agent-notes-v1.json"
sidecar = json.load(open(NOTES))
sidecar["by_num"].update({str(k): v for k, v in act2_notes.items()})
existing_flag_ids = {f["before_entry_id"] for f in sidecar.get("seam_flags", [])}
for f in act2_seam_flags:
    if f["before_entry_id"] not in existing_flag_ids:
        sidecar.setdefault("seam_flags", []).append(f)
json.dump(sidecar, open(NOTES, "w"), indent=2)

print(f"Act 2 placed={len(placed)} interstitial=1 not-used={len(act2_notes)} (DoneRight total={len(dr_nums)})")
print(f"Narrative 1: {orig_count} Jobs + {len(act2_entries)} Act 2 = {len(narr['entries'])} entries")
print("Wrote narrative-1.json + merged edit-agent-notes-v1.json")
