#!/usr/bin/env python3
"""Regression tests for the v5.16 fixes (Valley Outreach 2026 close).

Run:  python3 scripts/test_v516_fixes.py
"""
import json, os, re, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_fcpxml as bf
import generate_fcpxml as gf
import validate_timecodes as vt

HERE = os.path.dirname(os.path.abspath(__file__))
checks = []
def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail)); print(("  ✓ " if cond else "  ✗ ") + name + (f" — {detail}" if detail and not cond else ""))

# 1. parse_act_structure prefers the canonical "### Act Labels" list
md = """# Approved Act Structure
### Structure
**Act 1 — Alpha:** stuff
**Act 2 — Beta:** stuff
### Act Labels (for all downstream agents — currently planned)
Use exactly these labels for quote tagging:
- The Community We Want to Create
- What It Takes
- The Future We Create Together
- Orphan (for quotes that don't fit any act)
### Editorial Notes
- blah
"""
with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
    f.write(md); mdp = f.name
labels = bf.parse_act_structure(mdp)
check("act-labels parser reads the canonical list (3 acts, Orphan dropped)",
      labels == ["The Community We Want to Create", "What It Takes", "The Future We Create Together"], str(labels))

# 2. _load_v5 keeps content cards as placeholders in playback order; adapt_quote carries `card`
pool = [{"num": 1, "speaker": "A", "part": "X", "startTC": "00:00:01:00", "endTC": "00:00:05:00",
         "segments": [{"idx": 0, "text": "one two three.", "startTC": "00:00:01:00", "endTC": "00:00:03:00"},
                      {"idx": 1, "text": "four five six.", "startTC": "00:00:03:00", "endTC": "00:00:05:00"}]}]
timeline = {"schema_version": 5, "entries": [
    {"entry_id": "T1", "type": "title_card", "text": "Kindness", "part": "X", "membership": "tight", "estimated_seconds": 3, "source_quote_id": None},
    {"entry_id": "1", "source_quote_id": 1, "speaker": "A", "part": "X", "membership": "tight",
     "segments": [{"source_segment_idx": 0}, {"source_segment_idx": 1}]},
    {"entry_id": "T2", "type": "interstitial", "text": "Two lines\nhere", "part": "X", "membership": "tight", "estimated_seconds": 4, "source_quote_id": None},
]}
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump(timeline, f); tlp = f.name
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump(pool, f); poolp = f.name
loaded = bf.load_quotes(tlp, source_pool=bf.load_source_pool(poolp))
q = loaded["quotes"]
check("cards kept in playback order as placeholders", [x.get("_card", {}).get("type") if x.get("_card") else "spoken" for x in q] == ["title_card", "spoken", "spoken", "interstitial"], str([x.get("num") for x in q]))
pcs = [bf.adapt_quote(x, i + 1) for i, x in enumerate(q)]
check("adapt_quote forwards the card payload", pcs[0].get("card", {}).get("text") == "Kindness" and pcs[3].get("card", {}).get("estimated_seconds") == 4)

# 3. create_section_divider: multi-line text keeps the newline in the text node but not in the name attribute
gap, off, ctr = gf.create_section_divider("Two lines\nhere", gf.FractionTime(0, 24000), "r2", 1, duration=gf._quantize_to_frame_duration(4.0))
title = gap.find("title")
check("card title name has no newline; text keeps it", "\n" not in title.get("name") and title.find(".//text-style").text == "Two lines\nhere")
check("card duration is frame-quantized 4s", gap.get("duration") == gf._quantize_to_frame_duration(4.0).to_string())

# 4. matcher: short interior fragment matches with the length-scaled cutoff
def cap(offset_frames, dur_frames, text):
    el = ET.fromstring(f'<caption offset="{offset_frames*1001}/24000s" duration="{dur_frames*1001}/24000s" name="c"><text><text-style ref="ts1">{text}</text-style></text></caption>')
    return gf.Caption(el)
caps = [cap(0, 48, "and it's a value and a family legacy of"), cap(48, 48, "what connection means, and what it means to"),
        cap(96, 48, "feel, like you belong, and what that means for every"), cap(144, 48, "single person, right? It's not just about some people belonging.")]
s_idx, e_idx, score = gf.find_captions_for_sentence("it means to feel like you belong", caps)
check("7-word interior fragment now matches (scaled cutoff)", s_idx is not None and 0.45 < score <= 0.55, f"score={score:.3f}")
s2, e2, sc2 = gf.find_captions_for_sentence("completely unrelated words about airplanes and cheese here", caps)
check("unrelated 9-word sentence still rejected at 0.55", s2 is None, f"score={sc2:.3f}")

# 5. hole-fill fallback: an unmatched middle sentence between two matched neighbours is emitted
caps2 = [cap(0, 48, "the first sentence is here and it is long enough"), cap(48, 48, "zzz qqq"), cap(96, 48, "the third sentence is here and it is long enough too")]
um, fb = [], []
segs = gf.find_captions_for_quote("The first sentence is here and it is long enough. Middle words nobody transcribed at all. The third sentence is here and it is long enough too.", caps2, gap_threshold_secs=0.5, unmatched_out=um, fallback_out=fb)
check("hole-fill fallback emits the middle hole and reports it as fallback, not truncation",
      len(fb) == 1 and um == [] and any(s[0] <= 1 <= s[1] for s in segs), f"segs={segs} um={um} fb={fb}")

# 6. validator sort: "82a"-style nums sort with their parent
key = lambda n: vt._sort_key({"num": n}, 0)
check("validator sorts 82 < 82a < 82b < 83", key(82) < key("82a") < key("82b") < key(83))

# 7. viewer tcToSeconds parses HH:MM:SS:FF (needs node)
tpl = open(os.path.join(HERE, "quotes_viewer_template.jsx")).read()
m = re.search(r"function tcToSeconds\(tc\) \{.*?\n\}", tpl, re.S)
try:
    out = subprocess.run(["node", "-e", m.group(0) + '\nconsole.log(JSON.stringify([tcToSeconds("00:01:11:00"), tcToSeconds("00:01:11:12"), tcToSeconds("01:02"), tcToSeconds("00:01:11")]))'], capture_output=True, text=True, timeout=20)
    vals = json.loads(out.stdout.strip())
    check("viewer tcToSeconds handles 4-, 3- and 2-part timecodes", abs(vals[0]-71) < 1e-6 and abs(vals[1]-(71+12/23.976)) < 1e-6 and vals[2] == 62 and vals[3] == 71, str(vals))
except Exception as exc:  # noqa: BLE001
    check("viewer tcToSeconds (node)", False, str(exc))

failed = [c for c in checks if not c[1]]
print(f"\n{'OK' if not failed else 'FAIL'} — {len(checks)-len(failed)}/{len(checks)} checks passed.")
sys.exit(1 if failed else 0)
