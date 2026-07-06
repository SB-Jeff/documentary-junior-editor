#!/usr/bin/env python3
"""One-shot generator: Edit Agent Act 1 (Jobs) over-inclusive build for H+S IBEW 2026.

Per Jeff's process: at the over-inclusive stage there are NO Cuts — every
plausible quote goes on the Timeline first; we cut down later. So all 33
plausible entries are membership=tight (Cuts empty). The 13 I'd previously
sidelined carry a 'Reduction candidate' note so my reasoning survives into the
cut-down step. Clearly-out material (backstory / duplicates / tangents) stays in
the Library as not-used with a by_num reason.

Writes editing-versions/v1.json (the open cut) + edit-agent-notes-v1.json.
Asserts every Jobs quote is accounted for (timeline | not-used note)."""
import json
from pathlib import Path

H = Path("/Volumes/H+S IBEW 2026/H+S IBEW 2026/handoffs")
src = json.load(open(H / "tagged-quotes-v1.json"))
by = {q["num"]: q for q in src}
jobs_nums = {q["num"] for q in src if q.get("part") == "Jobs"}

ALL = "ALL"  # sentinel: keep every segment of the source quote

# --- TIMELINE — beat-grouped, over-inclusive, ALL membership=tight ---
# (num, segment-selection). ALL = every segment.
timeline = [
    # Beat 1 — identity & what the union means
    (56, [0, 1, 2]),                  # Jeff — identity/origin (OPENER)
    (58, [1, 2, 3, 4, 5, 6, 7]),      # Jeff — grandmother union-placer legacy
    (60, [0, 1]),                     # Jeff — Barbara Henderson named
    (135, [0, 1]),                    # Rachel — brothers & sisters, community
    (92, [0, 1, 2]),                  # Gavin — "very well taken care of"
    (91, ALL),                        # Gavin — non-union→union pay drew me in
    (111, [0, 1, 2]),                 # Brittany — predictable wage / comforting
    (109, ALL),                       # Brittany — career-change backstory
    (110, ALL),                       # Brittany — learn a trade without paying
    (136, ALL),                       # Rachel — making more than my peers
    # Beat 2 — quality of the work
    (61, [1, 2]),                     # Jeff — safety above all else
    (6, ALL),                         # Andrew — safety's the number one thing
    (114, [0, 1, 2, 3]),              # Brittany — ground-up, trades, felt heard
    (113, [0]),                       # Brittany — "It was immaculate."
    (4, [0, 1]),                      # Andrew — paved walkways, food trucks
    (5, ALL),                         # Andrew — working conditions (alt)
    (62, ALL),                        # Jeff — cutting edge / test your skill
    # Beat 3 — scale & pay
    (2, [0, 1]),                      # Andrew — massive impact, puts people to work
    (96, [0, 1, 2]),                  # Gavin — 300-400 at Meta, all hands on deck
    (94, ALL),                        # Gavin — a home, consistent work
    (97, [1]),                        # Gavin — off the bench
    (9, [0, 1]),                      # Andrew — 58-60hr weeks, 2yrs salary
    (28, ALL),                        # Andrew — 100-300 payroll scale
    (34, [0, 1, 2]),                  # Andrew — 2000-hr pre-apprentice pipeline
    (112, ALL),                       # Brittany — got all my hours + trained next gen
    (73, [3, 4, 6]),                  # Jeff — livable wage, place to raise family
    # Beat 4 — knock down "temporary"
    (99, [0, 1, 2, 3]),               # Gavin — "two things can be true"
    (100, ALL),                       # Gavin — great for the union, lots of jobs
    (64, [0, 1, 3, 8]),               # Jeff — far from temporary / permanent staples
    (65, ALL),                        # Jeff — far from temporary (alt take)
    (116, [0, 1, 3]),                 # Brittany — "a career, a lifestyle"
    (142, ALL),                       # Rachel — maintenance = permanent jobs
    (44, [2, 3]),                     # Andrew — "in 10 years, same temporary discussion" (CLOSE)
]

# The 13 I'd previously leaned against — now on the Timeline, carrying a
# reduction-candidate note (renders on the Timeline card's Notes line).
candidate_notes = {
    91:  "Reduction candidate — Gavin's non-union→union pay origin; #92 ('taken care of') is the stronger signature.",
    109: "Reduction candidate — Brittany's career-change backstory; context more than a beat.",
    110: "Reduction candidate — 'learn a trade without paying thousands'; alt security angle to #111.",
    136: "Reduction candidate — 'making more than my peers'; security beat already covered by #92/#111.",
    6:   "Reduction candidate — Andrew 'safety's the number one thing'; Jeff #61 carries safety on-camera.",
    5:   "Reduction candidate — Andrew's paved-pathways conditions; duplicates #4.",
    62:  "Reduction candidate — Jeff 'cutting edge… test your skill'; leans Act 2 (Done Right) and opens mid-thought (needs a head trim).",
    94:  "Reduction candidate — Gavin 'a home, consistent work'; overlaps #96 on the boom.",
    28:  "Reduction candidate — Andrew payroll scale; Andrew already heavy in the scale beat. Keep if you want the payroll number on camera.",
    112: "Reduction candidate — Brittany 'got all my hours + trained the next gen'; overlaps the pipeline beat.",
    100: "Reduction candidate — Gavin 'great for the union'; generic summary, weaker than #99.",
    65:  "Reduction candidate — second 'far from temporary' take; duplicates #64, which lands 'permanent staples' cleaner.",
    142: "Reduction candidate — Rachel's maintenance=permanent; #99 + #64 + #116 already carry the temporary beat.",
}

# --- NOT-USED notes (render on Library cards) — clear-outs only ---
notes = {
    3:  "Left out — career-advancement/travel tangent; off the Act 1 beat.",
    10: "Left out — per-diem/travel detail; supporting texture, not load-bearing.",
    29: "Left out — cyclical-industry/travelers mechanics; inside-baseball.",
    30: "Left out — overlaps #96/#28 on scale (300 for 2-3 yrs), weaker delivery.",
    31: "Left out — apprenticeship-intake overlaps #34, which states the pipeline cleaner.",
    32: "Left out — 'the bench' wait-time detail; overlaps #34/#97.",
    33: "Left out — pre-apprentice explainer; #34 lands the same point tighter.",
    35: "Left out — local-union headcount math (500/300); too granular for the act.",
    36: "Left out — travelers-from-other-states logistics; off-beat.",
    37: "Left out — contractor labor-sourcing detail; contractor inside-baseball.",
    38: "Left out — Hunt union pride/loyalty; brand-y, not member-facing.",
    39: "Left out — labor-pool stability/credentialing; supporting, not a beat.",
    40: "Left out — 'call the union' partnership mechanics; procedural.",
    41: "Left out — temporary rebuttal (Hennepin Tech); overlaps #44, weaker button.",
    42: "Left out — backup-generators/Gore Group; overlaps #44 temporary rebuttal.",
    43: "Left out — smaller-data-center/vacant-buildings aside; tangent.",
    57: "Left out of the build — LA→MN relocation backstory; a candidate to pull up if you want more of Jeff's origin (flagging for your verify pass).",
    59: "Left out — unions-beyond-construction (seamstress) tangent; widens #58 too far.",
    63: "Left out of Jobs — volume-of-work pivots into community outreach; flagging as a likely Act 3 (Community Benefits) candidate — re-tag first.",
    93: "Left out of the build — Gavin's 'friends stuck between jobs' generational angle; a candidate to pull up (flagging for your verify pass).",
    95: "Left out — 'all jobs will be union in the boom'; speculative, thinner than #96.",
    98: "Left out of the build — Gavin 'the bench affects your income/family'; a candidate to pull up — it also sets up #97 'off the bench' (flagging for your verify pass).",
    103: "Left out — generic 'good idea, place to work'; #99/#100 carry Gavin's rebuttal.",
    115: "Left out of Jobs — phases-of-construction drifts into 'money locally'; likely Act 3 (Community Benefits) candidate — re-tag first.",
    122: "Left out — duplicate 'immaculate' (Iowa drive-up); #113 is the clean two-word verdict.",
    123: "Left out — duplicate 'immaculate' (Iowa coworkers); redundant with #113.",
    124: "Left out — 'no pushback / podcasts' research aside; off-topic for the act.",
    133: "Left out — White Bear Lake move backstory; identity covered by #135.",
    134: "Left out — liked-science/physics backstory; not a Jobs beat.",
    138: "Left out — generic 'opportunity to learn electrical'; thin vs. #135/#136.",
    139: "Left out — longer-jobs-help-apprenticeship hours detail; #34 carries pipeline.",
    140: "Left out — 'work goes up and down' day-to-day; no narrative function here.",
    141: "Left out — 'full parking lot' scale; overlaps #96, weaker delivery.",
    143: "Left out — underground/first-job logistics; backstory, not a beat.",
    154: "Left out — 'good instructors / sense of community'; overlaps #135 and the pipeline beat.",
}

# Cardinal-Rule-2 seam-flags found reading the assembled act
seam_flags = [
    {"before_entry_id": "34", "kind": "orphan-opener",
     "message": "#34 opens 'And we've just since changed it' — 'it' (the pre-apprentice entry rule) has no antecedent now that #33's setup is left out.",
     "suggestion": "Head-trim #34 to start at 'in St. Paul ... you are automatically entered ... if you work 2,000 hours as pre-apprentice,' or restore #33 just ahead of it for the setup."},
    {"before_entry_id": "97", "kind": "jargon-no-setup",
     "message": "Gavin's 'get everybody off the bench' is the first use of 'the bench' — viewers may not know it means union members waiting for work.",
     "suggestion": "A one-line text interstitial ('On the bench = union members between jobs'), or pull up #98, which explains the bench cost."},
]


def entry(num, seg_sel, note=""):
    q = by[num]
    seg_idxs = [s["idx"] for s in q["segments"]] if seg_sel == ALL else seg_sel
    return {
        "entry_id": str(num),
        "source_quote_id": num,
        "_subLabel": None,
        "type": "spoken",
        "speaker": q["speaker"],
        "part": q["part"],
        "membership": "tight",
        "segments": [{"source_segment_idx": i} for i in seg_idxs],
        "notes": note,
    }


entries = [entry(num, segs, candidate_notes.get(num, "")) for num, segs in timeline]

# --- Coverage assertion: every Jobs quote is timeline | noted ---
placed = {num for num, _ in timeline}
noted = set(notes)
uncovered = jobs_nums - placed - noted
assert not uncovered, f"Uncovered Jobs quotes: {sorted(uncovered)}"
assert not (placed & noted), f"Both placed and noted: {sorted(placed & noted)}"
assert not (noted - jobs_nums), f"Notes reference non-Jobs nums: {sorted(noted - jobs_nums)}"
assert len(placed) == len(timeline), "Duplicate num in timeline"

(H / "editing-versions").mkdir(exist_ok=True)
cut = {
    "schema_version": 5,
    "round": 1,
    "cut_name": "Act 1 — Jobs (over-inclusive)",
    "project_slug": "h-s-ibew-2026",
    "entries": entries,
}
json.dump(cut, open(H / "editing-versions" / "v1.json", "w"), indent=2)

sidecar = {"schema_version": 1, "by_num": {str(k): v for k, v in notes.items()},
           "seam_flags": seam_flags}
json.dump(sidecar, open(H / "edit-agent-notes-v1.json", "w"), indent=2)

print(f"timeline(tight)={len(timeline)}  cuts=0  not-used={len(notes)}  total_jobs={len(jobs_nums)}")
print(f"sum={len(timeline)+len(notes)} (must equal {len(jobs_nums)})")
print("Wrote editing-versions/v1.json + edit-agent-notes-v1.json")
