#!/usr/bin/env python3
"""
build_quotes_viewer.py — wrap the canonical .jsx template into a self-contained
HTML artifact, with per-project data baked in.

Reads:
  - scripts/quotes_viewer_template.jsx (the canonical React component)
  - One of:
      (a) A pre-assembled project data JSON file (--data option)
      (b) Auto-discovered files in the project handoffs folder
          (tagged-quotes-v*.json, trimmed-quotes-v*.json,
          editing-versions/v*.json, pipeline-state.json)

Writes:
  - The self-contained HTML viewer (React 18 + Babel-standalone + inline CSS)

Architecture:
  - Strips the ES `import` and `export default` from the template
  - Substitutes the DATA BLOCK constants (PROJECT_TITLE, PROJECT_META,
    SOURCE_QUOTES, ROUNDS, INITIAL_ROUND_INDEX, INITIAL_FOCUS)
  - Migrates timeline entries from the v5.0 segment-based shape to the
    character-range trim shape the new viewer uses
  - Wraps in <html><head>...</head><body><div id="root"></div><script>...</script></body></html>

Usage:
  python3 build_quotes_viewer.py \\
      --slug tccs-dr-pan-testimonials \\
      --ssd-root /Volumes/TCCS_2026/TCCS_2026 \\
      --output /Volumes/TCCS_2026/TCCS_2026/handoffs/tccs-dr-pan-testimonials/tccs-dr-pan-testimonials_quotes_view.html
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ============================================================================
# Data assembly
# ============================================================================

def tokens_of(text: str):
    return re.findall(r"\S+", text or "")


def find_substring_with_offset(haystack: str, needle: str, start_hint: int = 0):
    """Find needle in haystack starting at start_hint. Returns (start, end) or None."""
    if not needle:
        return None
    idx = haystack.find(needle, start_hint)
    if idx < 0:
        return None
    return (idx, idx + len(needle))


def migrate_entry_trims(entry: dict, source_quotes_by_num: dict) -> dict:
    """Convert v5.0 segment-based entry → new viewer's character-range entry.

    Old entry shape:
        {
            "entry_id": "e_002",
            "source_quote_id": 2,
            "speaker": "...",
            "part": "...",
            "runtime_recommendation": "...",
            "segments": [
                {"source_segment_idx": 0, "head_trim_words": 1},
                {"source_segment_idx": 2}
            ],
            "notes": "..."
        }

    New entry shape:
        {
            "entry_id": "2",                    # bare source num, no e_NNN
            "_subLabel": null,
            "source_quote_id": 2,
            "type": "spoken",
            "speaker": "...",
            "part": "...",
            "runtime_recommendation": "...",
            "_editCuts": [[start, end], ...],   # char ranges to cut
            "notes": "..."
        }
    """
    src = source_quotes_by_num.get(entry["source_quote_id"])
    if not src:
        return None

    # Build full original text (join all segments with single space, matching
    # what the new viewer's fullQuoteText does).
    full_text = " ".join(seg["text"] for seg in src["segments"])

    # Track character offset of each segment in full_text
    seg_offsets = {}
    pos = 0
    for i, seg in enumerate(src["segments"]):
        seg_offsets[seg["idx"]] = (pos, pos + len(seg["text"]))
        pos += len(seg["text"])
        if i < len(src["segments"]) - 1:
            pos += 1  # space separator

    # Build kept char ranges from entry's segments list + word trims
    kept_ranges = []
    for seg_ref in entry.get("segments", []):
        idx = seg_ref["source_segment_idx"]
        if idx not in seg_offsets:
            continue
        seg_start, seg_end = seg_offsets[idx]
        seg_text = full_text[seg_start:seg_end]
        head_trim = seg_ref.get("head_trim_words", 0)
        tail_trim = seg_ref.get("tail_trim_words", 0)

        # Compute the kept text inside this segment by skipping head_trim words
        # at the start and tail_trim words at the end
        tokens = tokens_of(seg_text)
        if not tokens:
            continue
        if head_trim + tail_trim >= len(tokens):
            continue  # nothing kept

        # Find the kept portion's char range within seg_text
        # Use regex to find each word's position in seg_text
        word_spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", seg_text)]
        if not word_spans:
            continue
        kept_word_start = word_spans[head_trim][0] if head_trim < len(word_spans) else len(seg_text)
        kept_word_end = word_spans[len(word_spans) - tail_trim - 1][1] if tail_trim < len(word_spans) else 0

        if kept_word_end <= kept_word_start:
            continue
        kept_ranges.append((seg_start + kept_word_start, seg_start + kept_word_end))

    # Merge adjacent kept ranges that are separated only by whitespace —
    # otherwise the segment-join spaces become spurious 1-char cuts.
    kept_ranges.sort()
    if kept_ranges:
        merged = [list(kept_ranges[0])]
        for kr in kept_ranges[1:]:
            last = merged[-1]
            if kr[0] <= last[1]:
                last[1] = max(last[1], kr[1])
            elif full_text[last[1]:kr[0]].strip() == "":
                # only whitespace between → merge
                last[1] = kr[1]
            else:
                merged.append(list(kr))
        kept_ranges = [tuple(r) for r in merged]

    # Cuts = complement of kept_ranges within full_text
    cuts = []
    if not kept_ranges:
        cuts.append([0, len(full_text)])
    else:
        pos = 0
        for kr_start, kr_end in kept_ranges:
            if pos < kr_start:
                cuts.append([pos, kr_start])
            pos = kr_end
        if pos < len(full_text):
            cuts.append([pos, len(full_text)])

    # Drop any pure-whitespace cuts (defensive — shouldn't happen after merge)
    cuts = [[s, e] for s, e in cuts if full_text[s:e].strip() != ""]

    # Migrate entry_id: e_NNN → bare source num (no e_ prefix, no padding)
    # Reasoning: under v5.0 punch list, entry IDs derive from source num.
    old_id = str(entry.get("entry_id", ""))
    if old_id.startswith("e_"):
        new_id = str(entry["source_quote_id"])
    else:
        new_id = old_id

    migrated = {
        "entry_id": new_id,
        "_subLabel": None,
        "source_quote_id": entry["source_quote_id"],
        "type": entry.get("type", "spoken"),
        "speaker": entry.get("speaker"),
        "part": entry.get("part"),
        "runtime_recommendation": entry.get("runtime_recommendation", "probable-keep"),
        "_editCuts": cuts,
        "notes": entry.get("notes", ""),
    }
    # Pass through the Edit Agent's tight-promotion ranking (high/medium/low) on
    # probable-keep entries so the viewer can badge + sort by it.
    if entry.get("tight_priority"):
        migrated["tight_priority"] = entry["tight_priority"]
    return migrated


def migrate_recommendations_two_tier(entries):
    """Normalize the recommendation field to the viewer's supported states.

    Supported: must-keep, tight-candidate (borderline-essential; shows in the
    Tight cut), probable-keep. Legacy probable-cut / optional collapse to
    probable-keep.
    """
    allowed = ("must-keep", "tight-candidate", "probable-keep")
    out = []
    for e in entries:
        rec = e.get("runtime_recommendation", "probable-keep")
        if rec not in allowed:
            note = e.get("notes", "") or ""
            note = (note + " ").strip() + f"[migrated: was '{rec}' → probable-keep]"
            e = {**e, "runtime_recommendation": "probable-keep", "notes": note}
        out.append(e)
    return out


def load_project_data_from_handoffs(slug: str, ssd_root: Path) -> dict:
    """Auto-discover project data files in the handoffs folder.

    Returns the assembled project data dict in the shape the new template expects.
    """
    handoffs = ssd_root / "handoffs" / slug
    if not handoffs.is_dir():
        raise SystemExit(f"Handoffs folder not found: {handoffs}")

    # Project metadata from pipeline-state.json
    ps_path = handoffs / "pipeline-state.json"
    if not ps_path.exists():
        raise SystemExit(f"pipeline-state.json missing at {ps_path}")
    ps = json.loads(ps_path.read_text())
    project_name = ps.get("project_name", slug)
    cc = ps.get("agents", {}).get("creative-context", {})
    act_labels_full = cc.get("act_labels", ["Act 1", "Act 2", "Act 3"])
    speakers = cc.get("speakers", [])
    target_seconds = 120
    # Best-effort: look for target_runtime_seconds in any trimmed-quotes file
    for f in handoffs.glob("trimmed-quotes-v*.json"):
        try:
            j = json.loads(f.read_text())
            if "target_runtime_seconds" in j:
                target_seconds = j["target_runtime_seconds"]
                break
        except Exception:
            pass

    # Source quotes: tagged-quotes-v[latest].json + orphans aggregated from speaker files
    source_quotes = []
    orphans = []
    tagged_files = sorted(handoffs.glob("tagged-quotes-v*.json"))
    if tagged_files:
        tq = json.loads(tagged_files[-1].read_text())
        if isinstance(tq, list):
            source_quotes = [q for q in tq if not q.get("is_orphan")]
            orphans = [q for q in tq if q.get("is_orphan")]
        elif isinstance(tq, dict) and "quotes" in tq:
            source_quotes = [q for q in tq["quotes"] if not q.get("is_orphan")]
            orphans = [q for q in tq["quotes"] if q.get("is_orphan")]

    # If orphans aren't in tagged-quotes, try to pull from per-speaker orphan
    # files (lynette-tagged-quotes-v1.json structure varies). Fallback: extract
    # from existing viewer HTML data block if present.
    if not orphans:
        viewer_html = handoffs / f"{slug}_quotes_view.html"
        if viewer_html.exists():
            html = viewer_html.read_text(errors="ignore")
            m = re.search(r"window\.__VIEWER_DATA__\s*=\s*(\{.*?\});\s*</script>", html, re.DOTALL)
            if m:
                try:
                    d = json.loads(m.group(1))
                    if not source_quotes:
                        source_quotes = d.get("source_quotes", [])
                    orphans = d.get("orphan_quotes", []) or []
                except Exception:
                    pass

    # Mark orphans
    for o in orphans:
        o["is_orphan"] = True
    combined_quotes = list(source_quotes) + list(orphans)

    # Rounds: prefer editing-versions/v*.json, fallback to trimmed-quotes-v*.json
    rounds = []
    editing_versions_dir = handoffs / "editing-versions"
    if editing_versions_dir.is_dir():
        round_files = sorted(editing_versions_dir.glob("v*.json"),
                             key=lambda p: int(re.search(r"v(\d+)", p.name).group(1)))
    else:
        round_files = sorted(handoffs.glob("trimmed-quotes-v*.json"),
                             key=lambda p: int(re.search(r"v(\d+)", p.name).group(1)))

    for f in round_files:
        try:
            j = json.loads(f.read_text())
        except Exception as e:
            print(f"Skipping {f.name}: {e}", file=sys.stderr)
            continue
        round_num = j.get("round", int(re.search(r"v(\d+)", f.name).group(1)))
        entries = j.get("entries", [])
        rounds.append({
            "round_number": round_num,
            "round_label": f"Round {round_num}",
            "version": f.stem,
            "_raw_entries": entries,
        })

    return {
        "project_name": project_name,
        "slug": slug,
        "ssd_root": str(ssd_root),
        "act_labels": act_labels_full,
        "speakers": speakers,
        "target_seconds": target_seconds,
        "source_quotes": combined_quotes,
        "rounds": rounds,
    }


def assemble_data_block(data: dict) -> dict:
    """Convert auto-discovered data into the shape the template's data block expects.

    Migrates timeline entries from segment-based v5.0 shape to character-range
    shape, and collapses four-tier recommendations to two-tier.
    """
    by_num = {q["num"]: q for q in data["source_quotes"]}
    migrated_rounds = []
    for r in data["rounds"]:
        migrated_entries = []
        for e in r["_raw_entries"]:
            if e.get("source_quote_id") is None:
                # Non-spoken entry (title card / interstitial / context beat)
                migrated_entries.append({
                    "entry_id": str(e.get("entry_id", "")),
                    "_subLabel": None,
                    "source_quote_id": None,
                    "type": e.get("type", "spoken"),
                    "part": e.get("part", ""),
                    "runtime_recommendation": e.get("runtime_recommendation", "probable-keep"),
                    "_editCuts": [],
                    "notes": e.get("notes", ""),
                    "text": e.get("text", ""),
                })
                continue
            mig = migrate_entry_trims(e, by_num)
            if mig:
                migrated_entries.append(mig)
        migrated_entries = migrate_recommendations_two_tier(migrated_entries)
        migrated_rounds.append({
            "round_number": r["round_number"],
            "round_label": r["round_label"],
            "version": r["version"],
            "timeline": migrated_entries,
        })

    project_meta = {
        "slug": data["slug"],
        "ssd_root": data["ssd_root"],
        "target_seconds": data["target_seconds"],
        # Keep only real act labels (Orphan filtered out — orphans live as flag
        # on quotes, not as an act). Preserve order.
        "act_labels": [a for a in data["act_labels"] if a != "Orphan"],
        "speakers": data["speakers"],
    }

    return {
        "PROJECT_TITLE": data["project_name"],
        "PROJECT_META": project_meta,
        "SOURCE_QUOTES": data["source_quotes"],
        "ROUNDS": migrated_rounds,
        "INITIAL_ROUND_INDEX": max(0, len(migrated_rounds) - 1),
        "INITIAL_FOCUS": None,
    }


# ============================================================================
# Template substitution + HTML wrap
# ============================================================================

def js_literal(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def substitute_data_block(template_src: str, data_block: dict) -> str:
    """Replace canonical data-block placeholders with project data."""
    # Use lambda replacements to avoid Python regex's backslash-escape interpretation
    # on JSON output containing \uXXXX sequences.
    out = template_src

    out = re.sub(
        r'^const PROJECT_TITLE = "[^"]*";',
        lambda _: f'const PROJECT_TITLE = {json.dumps(data_block["PROJECT_TITLE"])};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # PROJECT_META: replace the full constant block
    out = re.sub(
        r'^const PROJECT_META = \{.*?\n\};',
        lambda _: f'const PROJECT_META = {js_literal(data_block["PROJECT_META"])};',
        out,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )

    # SOURCE_QUOTES: replace empty list with real data
    out = re.sub(
        r'^const SOURCE_QUOTES = \[\];',
        lambda _: f'const SOURCE_QUOTES = {js_literal(data_block["SOURCE_QUOTES"])};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # ROUNDS: replace empty list
    out = re.sub(
        r'^const ROUNDS = \[\s*//[^\n]*\n\];',
        lambda _: f'const ROUNDS = {js_literal(data_block["ROUNDS"])};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # INITIAL_ROUND_INDEX
    out = re.sub(
        r'^const INITIAL_ROUND_INDEX = \d+;',
        lambda _: f'const INITIAL_ROUND_INDEX = {data_block["INITIAL_ROUND_INDEX"]};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # INITIAL_FOCUS
    focus = data_block.get("INITIAL_FOCUS")
    focus_literal = "null" if focus is None else json.dumps(focus)
    out = re.sub(
        r'^const INITIAL_FOCUS = null;',
        lambda _: f'const INITIAL_FOCUS = {focus_literal};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    return out


def strip_module_syntax(template_src: str) -> str:
    """Strip ES import and convert export default → bare function for in-browser Babel."""
    # Strip the import line
    out = re.sub(
        r'^import \{[^}]+\} from "react";\s*\n',
        "",
        template_src,
        count=1,
        flags=re.MULTILINE,
    )
    # Convert export default function → function
    out = re.sub(
        r'^export default function QuotesView\(\)',
        "function QuotesView()",
        out,
        count=1,
        flags=re.MULTILINE,
    )
    return out


VIEWER_CSS = """
:root {
  --bg: #fafaf9;
  --surface: #ffffff;
  --surface-2: #f5f5f4;
  --border: #e7e5e4;
  --border-strong: #d6d3d1;
  --text: #1c1917;
  --text-muted: #57534e;
  --text-subtle: #78716c;
  --accent: #0369a1;
  --accent-soft: #e0f2fe;
  --accent-strong: #075985;
  --must: #059669;
  --must-soft: #d1fae5;
  --tight: #0d9488;
  --tight-soft: #ccfbf1;
  --probable: #2563eb;
  --probable-soft: #dbeafe;
  --warn: #d97706;
  --warn-soft: #fef3c7;
  --danger: #dc2626;
  --danger-soft: #fee2e2;
  --highlight: #fde68a;
  --shadow: 0 1px 2px rgba(0,0,0,.04), 0 4px 12px rgba(0,0,0,.05);
  color-scheme: light;
  font: 14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); }
body { padding-bottom: 80px; }
button { font: inherit; cursor: pointer; }
kbd { background: #fff; border: 1px solid #ddd; border-radius: 3px; padding: 0 4px; font-size: 11px; }

.viewer { min-height: 100vh; }

/* === Header (two-tone: gray top, white bottom) ===
   Backgrounds are full-bleed; inner wrappers centered to align with .main. */
.hdr { position: sticky; top: 0; z-index: 50; background: var(--surface); }
.hdr-row1 {
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}
.hdr-row1-inner {
  display: flex; align-items: center; gap: 14px;
  padding: 12px 20px;
  max-width: 1100px;
  margin: 0 auto;
}
.hdr-row2 {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.hdr-row2-inner {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 20px;
  flex-wrap: wrap;
  max-width: 1100px;
  margin: 0 auto;
}
.hdr-title { font-size: 15px; font-weight: 600; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.round-select {
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  padding: 4px 26px 4px 10px; font: inherit; font-size: 12px; color: var(--text);
  height: 28px; cursor: pointer; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2378716c' fill='none' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 8px center;
}

/* Mode toggle (tab pattern with bold accent underline + faint dividers) */
.mode-toggle { display: inline-flex; gap: 0; }
.mode-toggle button {
  background: transparent; border: 0;
  border-bottom: 3px solid transparent;
  border-radius: 0;
  padding: 8px 18px; font-size: 13px; color: var(--text-muted); font-weight: 500;
  position: relative; transition: color .15s, border-color .15s;
}
.mode-toggle button:hover { color: var(--text); }
.mode-toggle button + button::before {
  content: ""; position: absolute; left: -1px; top: 25%; bottom: 25%;
  width: 1px; background: var(--border);
}
.mode-toggle button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 700;
}

/* Unsynced pill */
.unsynced-pill {
  background: var(--warn-soft); border: 1px solid var(--warn);
  border-radius: 999px; padding: 3px 10px;
  font-size: 11px; color: var(--warn); font-weight: 600;
  margin-left: auto; cursor: pointer;
}
.unsynced-pill:hover { background: var(--warn); color: white; }

/* Filter groups (outlined containers, no fill) */
.filter-group {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: transparent;
}
.filter-group .group-label {
  color: var(--text-subtle); margin-right: 4px;
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;
}
.chip {
  background: transparent; border: 1px solid transparent;
  color: var(--text-muted); padding: 3px 10px;
  border-radius: 999px; font-size: 12px; cursor: pointer;
  transition: all 0.15s;
}
.chip:hover { background: var(--surface-2); color: var(--text); }
.chip.active { background: var(--text); color: white; border-color: var(--text); }

/* Cut block */
.cut-block {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 3px 4px 3px 10px;
  margin-left: auto;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: transparent;
}
.cut-toggle { display: inline-flex; gap: 2px; }
.cut-toggle button {
  background: transparent; border: 0;
  padding: 4px 12px; border-radius: 4px;
  font-size: 12px; color: var(--text-muted); font-weight: 500;
}
.cut-toggle button:hover:not(.active) { background: var(--surface-2); }
.cut-toggle button.active.rough { background: var(--probable-soft); color: var(--probable); }
.cut-toggle button.active.tight { background: var(--must-soft); color: var(--must); }
.cut-metric { font-size: 12px; color: var(--text); font-variant-numeric: tabular-nums; padding-left: 10px; border-left: 1px solid var(--border); }
.cut-metric .val { font-weight: 600; }
.cut-metric-rough .val { color: var(--probable); }
.cut-metric-tight .val { color: var(--must); }
.cut-export {
  background: var(--accent); color: white; border: 1px solid var(--accent);
  border-radius: 6px; padding: 5px 14px; font-size: 12px; font-weight: 500;
  margin-left: 4px;
}
.cut-export:hover { background: var(--accent-strong); border-color: var(--accent-strong); }

/* === Main pane === */
.main { padding: 20px; max-width: 1100px; margin: 0 auto; }
.act-section { margin-bottom: 32px; }
.act-header {
  display: flex; align-items: baseline; gap: 12px; padding: 8px 0; margin-bottom: 12px;
  border-bottom: 2px solid var(--border-strong);
}
.act-title { font-size: 18px; font-weight: 600; margin: 0; }
.act-sub { color: var(--text-muted); font-size: 13px; }

/* === Library toolbar (hide-in-cut toggle + search) === */
.lib-toolbar {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid var(--border);
}
.lib-hide-toggle {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--text-muted); cursor: pointer; user-select: none;
}
.lib-hide-toggle input { cursor: pointer; }
.lib-hide-count {
  font-size: 10px; font-weight: 600; color: var(--must); background: var(--must-soft);
  border-radius: 999px; padding: 1px 8px; margin-left: 2px;
}
.lib-search {
  flex: 1; min-width: 200px; max-width: 420px; font: inherit; font-size: 13px;
  border: 1px solid var(--border-strong); border-radius: 8px; padding: 7px 12px;
  background: var(--surface); color: var(--text);
}
.lib-search:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.lib-search-meta { font-size: 11px; color: var(--text-subtle); }

/* === Library cards === */
.lib-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; margin-bottom: 10px; box-shadow: var(--shadow);
}
.lib-card.orphan { background: var(--surface-2); border-style: dashed; }
.lib-card.in-tl { border-left: 4px solid var(--must); }
.card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.qid {
  font-weight: 600; font-variant-numeric: tabular-nums; color: var(--text);
  background: var(--surface-2); padding: 2px 8px; border-radius: 4px; font-size: 13px;
}
.qid.split { background: var(--probable-soft); color: var(--probable); }
.speaker-tag { font-size: 11px; padding: 2px 8px; border-radius: 999px; font-weight: 500; }
.act-tag-static {
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: var(--surface-2); color: var(--text-muted);
}
.tc { color: var(--text-subtle); font-size: 11px; font-variant-numeric: tabular-nums; font-family: ui-monospace,Menlo,monospace; }
.in-tl-pill {
  font-size: 10px; padding: 2px 8px; border-radius: 999px;
  background: var(--must-soft); color: var(--must); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.orphan-pill {
  font-size: 10px; padding: 2px 8px; border-radius: 999px;
  background: var(--surface-2); color: var(--text-muted); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.lib-card .quote-text { color: var(--text); line-height: 1.55; margin: 8px 0 10px; }
.lib-card .rationale {
  color: var(--text-muted); font-size: 12.5px; margin-top: 8px;
  padding-top: 8px; border-top: 1px dashed var(--border);
}
.rationale-label { color: var(--text-subtle); font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; margin-right: 4px; }

.lib-actions, .tl-actions {
  display: flex; gap: 6px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);
}
.btn {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px;
  padding: 5px 11px; font-size: 12px; color: var(--text); transition: all 0.15s;
}
.btn:hover { background: var(--surface); border-color: var(--border-strong); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--accent); border-color: var(--accent); color: white; }
.btn-primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
.btn-primary:disabled { background: var(--must-soft); color: var(--must); border-color: var(--must-soft); opacity: 1; cursor: default; }
.btn-comment {
  background: var(--probable-soft); border-color: var(--probable-soft); color: var(--probable);
}
.btn-comment:hover { background: var(--probable); border-color: var(--probable); color: white; }
.btn-danger { color: var(--danger); }
.btn-danger:hover { background: var(--danger-soft); border-color: var(--danger); color: var(--danger); }

/* === Timeline cards (v4.0.1-style) === */
.tl-card {
  display: flex; gap: 0; padding: 0; margin-bottom: 10px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  overflow: visible;
  box-shadow: var(--shadow);
}
.tl-card.dragging { opacity: 0.4; }
.tl-card.drag-over { box-shadow: 0 -3px 0 0 var(--accent), var(--shadow); }
.tl-drag { touch-action: none; }
.tl-card.is-must-keep { border-left: 4px solid var(--must); }
.tl-card.is-tight-candidate { border-left: 4px solid var(--tight); }
.tl-card.is-probable-keep { border-left: 4px solid var(--probable); }
.tl-card.focus-flash { animation: focusHL 1.6s ease-out; }
@keyframes focusHL {
  0% { background: var(--highlight); }
  100% { background: var(--surface); }
}
.tl-drag {
  display: flex; align-items: stretch; padding: 0 6px;
  cursor: grab; color: var(--text-subtle);
  background: var(--surface-2); border-right: 1px solid var(--border);
  user-select: none;
  border-top-left-radius: 7px; border-bottom-left-radius: 7px;
}
.tl-drag:active { cursor: grabbing; }
.tl-drag svg { margin: auto; }
.tl-body { flex: 1; padding: 14px 16px; min-width: 0; }
.tl-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.tl-move-btns { display: inline-flex; gap: 2px; }
.tl-move-btn {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 4px;
  padding: 2px 6px; font-size: 11px; color: var(--text-muted);
  font-family: ui-monospace, Menlo, monospace; cursor: pointer; line-height: 1;
}
.tl-move-btn:hover:not(:disabled) { background: var(--surface); color: var(--text); border-color: var(--border-strong); }
.tl-move-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.tl-scissors {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 4px;
  padding: 3px 6px; font-size: 12px; cursor: pointer; color: var(--text-muted);
  display: inline-flex; align-items: center; gap: 4px;
}
.tl-scissors:hover { background: var(--probable-soft); border-color: var(--probable); color: var(--probable); }

.act-tag-wrap { position: relative; display: inline-block; }
.act-tag-btn {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; cursor: pointer;
  background: var(--surface-2); color: var(--text-muted);
  border: 1px solid transparent;
}
.act-tag-btn:hover { border-color: var(--border-strong); }
.act-tag-btn .caret { opacity: 0.5; font-size: 9px; margin-left: 2px; }
.reassign-pop {
  position: absolute; z-index: 30; margin-top: 4px; left: 0;
  background: var(--surface); border: 1px solid var(--border-strong); border-radius: 6px;
  box-shadow: var(--shadow); padding: 4px; min-width: 160px;
}
.reassign-pop button {
  display: block; width: 100%; text-align: left;
  background: transparent; border: 0; padding: 6px 10px; border-radius: 4px;
  font-size: 12px; color: var(--text);
}
.reassign-pop button:hover { background: var(--surface-2); }

.rec-badge {
  font-size: 11px; padding: 2px 9px; border-radius: 4px; font-weight: 700; cursor: pointer;
  text-transform: uppercase; letter-spacing: 0.04em; border: 0;
  transition: all 0.15s;
}
.rec-badge.must-keep { background: var(--must-soft); color: var(--must); }
.rec-badge.must-keep:hover { background: var(--must); color: white; }
.rec-badge.tight-candidate { background: var(--tight-soft); color: var(--tight); }
.rec-badge.tight-candidate:hover { background: var(--tight); color: white; }
.rec-badge.probable-keep { background: var(--probable-soft); color: var(--probable); }
.rec-badge.probable-keep:hover { background: var(--probable); color: white; }

/* tight_priority badge (on probable-keep cards when the Edit Agent ranked them) */
.tp-badge { font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.tp-badge.tp-high { background: #fee2e2; color: #b91c1c; }
.tp-badge.tp-medium { background: #fef3c7; color: #b45309; }
.tp-badge.tp-low { background: #f1f5f9; color: #64748b; }
.tp-sort-toggle {
  background: transparent; border: 1px solid var(--border-strong); border-radius: 6px;
  padding: 4px 10px; font-size: 12px; color: var(--text-muted);
}
.tp-sort-toggle:hover:not(.active) { background: var(--surface-2); color: var(--text); }
.tp-sort-toggle.active { background: var(--probable-soft); color: var(--probable); border-color: var(--probable); }

.tl-quote { color: var(--text); line-height: 1.55; font-size: 14px; margin: 6px 0 0; }
.tl-quote-cut { color: var(--danger); text-decoration: line-through; opacity: 0.65; }
.tl-quote-hint {
  font-size: 11px; color: var(--text-subtle); margin-top: 4px;
  display: inline-block; cursor: pointer; user-select: none;
}
.tl-quote-hint:hover { color: var(--text); }
.tl-notes {
  color: var(--text-muted); font-size: 12px; margin-top: 10px;
  padding-top: 8px; border-top: 1px dashed var(--border); font-style: italic;
}
.tl-notes-label { color: var(--text-subtle); font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 4px; font-style: normal; }

/* === Interstitial / title-card / context-beat cards === */
.tl-interstitial { border-left: 4px solid var(--warn); background: var(--warn-soft); }
.tl-interstitial .tl-drag { background: rgba(217,119,6,0.10); border-right-color: rgba(217,119,6,0.25); }
.ins-type-badge {
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  padding: 2px 8px; border-radius: 4px; background: var(--warn); color: white;
}
.ins-edit-row { display: flex; gap: 8px; align-items: flex-start; margin: 8px 0 0; }
.ins-text {
  flex: 1; min-height: 42px; resize: vertical; font: inherit; font-size: 14px; line-height: 1.5;
  background: var(--surface); border: 1px solid var(--border-strong); border-radius: 6px;
  padding: 8px 10px; color: var(--text);
}
.ins-text:focus { outline: none; border-color: var(--warn); box-shadow: 0 0 0 2px var(--warn-soft); }
.ins-secs { display: inline-flex; align-items: center; gap: 2px; font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.ins-secs input {
  width: 48px; font: inherit; font-size: 13px; text-align: right;
  border: 1px solid var(--border-strong); border-radius: 4px; padding: 4px 6px; margin: 0 2px;
  background: var(--surface); color: var(--text);
}
.ins-research { font-size: 11px; color: var(--warn); font-weight: 600; margin-top: 8px; }

/* "+ interstitial" insertion slot between timeline cards */
.ins-slot { display: flex; justify-content: center; margin: -2px 0 8px; min-height: 16px; }
.ins-add-btn {
  background: transparent; border: 1px dashed var(--border-strong); border-radius: 999px;
  color: var(--text-subtle); font-size: 11px; padding: 2px 12px; opacity: 0.55; transition: all 0.15s;
}
.ins-add-btn:hover { opacity: 1; border-color: var(--warn); color: var(--warn); background: var(--warn-soft); }
.ins-add {
  width: 100%; max-width: 620px; margin: 4px auto 10px;
  background: var(--surface); border: 1px solid var(--warn); border-radius: 8px;
  padding: 12px; box-shadow: var(--shadow);
}
.ins-add-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.ins-add-type {
  flex: 1; font: inherit; font-size: 12px; padding: 5px 8px;
  border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); color: var(--text);
}
.ins-add-text {
  width: 100%; min-height: 56px; resize: vertical; font: inherit; font-size: 14px; line-height: 1.5;
  border: 1px solid var(--border-strong); border-radius: 6px; padding: 8px 10px; color: var(--text);
  box-sizing: border-box;
}
.ins-add-text:focus { outline: none; border-color: var(--warn); box-shadow: 0 0 0 2px var(--warn-soft); }
.ins-add-actions { display: flex; gap: 6px; margin-top: 8px; }

/* Interstitials in Review view */
.review-interstitial {
  margin: 12px auto; padding: 10px 14px; max-width: 80%;
  background: var(--warn-soft); border: 1px dashed var(--warn); border-radius: 8px; text-align: center;
}
.ri-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--warn); }
.ri-text { font-size: 15px; color: var(--text); margin-top: 4px; font-style: italic; }

/* Trim + split panels */
.trim-panel, .split-panel {
  margin-top: 10px; padding: 12px; background: var(--surface-2);
  border-radius: 6px; border: 1px solid var(--border);
}
.trim-hint, .split-hint { font-size: 11px; color: var(--text-subtle); margin: 0 0 8px; }
.trim-text {
  font-size: 14px; line-height: 1.55; padding: 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
  user-select: text; -webkit-user-select: text; cursor: text;
}
.trim-cut { color: var(--danger); text-decoration: line-through; opacity: 0.6; }
.trim-actions, .split-actions { display: flex; gap: 6px; margin-top: 10px; }
.split-text {
  font-size: 14px; line-height: 1.85; padding: 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
}
.split-marker {
  display: inline-block; cursor: pointer; padding: 0 3px; margin: 0 1px;
  color: var(--border-strong); border-radius: 3px; user-select: none;
}
.split-marker:hover { background: var(--probable-soft); color: var(--probable); }
.split-marker.active { background: var(--probable); color: white; font-weight: 700; }
.split-counter { font-size: 11px; color: var(--text-subtle); margin: 8px 0; }

/* === Review === */
.review-tabs {
  display: flex; gap: 18px; justify-content: center; flex-wrap: wrap;
  border-bottom: 1px solid var(--border); margin-bottom: 16px;
}
.review-tab {
  background: transparent; border: 0; border-bottom: 2px solid transparent;
  padding: 8px 4px; margin-bottom: -1px; font-size: 13px; color: var(--text-muted);
  cursor: pointer; transition: all 0.15s;
}
.review-tab.active { color: var(--text); border-color: var(--text); font-weight: 500; }
.review-tab .count { color: var(--text-subtle); font-size: 11px; margin-left: 4px; }
.review-act { margin-bottom: 28px; max-width: 700px; margin-left: auto; margin-right: auto; }
.review-act h2 { font-size: 20px; margin: 0 0 12px; padding-bottom: 6px; border-bottom: 2px solid var(--text); display: inline-block; }
.review-act h2 .meta { color: var(--text-muted); font-size: 12px; margin-left: 10px; font-weight: 400; }
.review-block { margin-bottom: 14px; }
.review-block .speaker {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--text-subtle); margin-bottom: 4px;
}
.review-text { font-size: 16px; line-height: 1.65; color: var(--text); }

/* === Empty === */
.empty {
  text-align: center; padding: 60px 20px; color: var(--text-muted);
  border: 2px dashed var(--border); border-radius: 8px; background: var(--surface);
}
.empty h3 { margin: 0 0 8px; font-size: 16px; color: var(--text); }

/* === Send-to-agent panel === */
.send-panel {
  position: fixed; bottom: 16px; right: 16px;
  width: 380px; max-height: 70vh;
  background: var(--surface); border: 1px solid var(--border-strong);
  border-radius: 10px; box-shadow: 0 8px 30px rgba(0,0,0,.18);
  display: flex; flex-direction: column;
  overflow: hidden; z-index: 90;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.send-panel.collapsed { width: auto; }
/* When there are pending tweaks AND the panel is collapsed, emphasize the
   panel so it functions as the single "you have unsent work" indicator
   (replacing the redundant header pill). */
.send-panel.has-pending.collapsed {
  border-color: var(--warn);
  box-shadow: 0 4px 18px rgba(217, 119, 6, 0.28), 0 1px 2px rgba(0,0,0,.05);
}
.send-panel.collapsed .sp-body { display: none; }
.send-panel.collapsed .sp-foot { display: none; }
.sp-head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; cursor: pointer; user-select: none;
  font-size: 13px; border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.send-panel.collapsed .sp-head { border-bottom: 0; }
.sp-title { font-weight: 600; }
.sp-count {
  background: var(--warn); color: white;
  border-radius: 999px; padding: 1px 8px;
  font-size: 11px; font-weight: 700; min-width: 22px; text-align: center;
}
.sp-count.zero { background: var(--surface-2); color: var(--text-muted); }
.sp-toggle { margin-left: auto; color: var(--text-muted); font-size: 13px; }
.sp-body { padding: 12px 14px; overflow: auto; flex: 1; min-height: 0; }
.sp-section { margin-bottom: 14px; }
.sp-section-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.sp-section-title { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-subtle); font-weight: 600; }
.sp-optional { color: var(--text-subtle); font-size: 10px; }
.sp-discard {
  margin-left: auto; background: none; border: 0; padding: 0;
  color: var(--text-subtle); font-size: 11px; cursor: pointer;
}
.sp-discard:hover:not(:disabled) { color: var(--danger); text-decoration: underline; }
.sp-discard:disabled { opacity: 0.35; cursor: not-allowed; }
.sp-ops { list-style: none; padding: 0; margin: 0; font-size: 12px; }
.sp-ops li { padding: 6px 0; border-bottom: 1px solid var(--border); line-height: 1.45; color: var(--text); }
.sp-ops li:last-child { border-bottom: 0; }
.sp-ops li::before { content: "→ "; color: var(--text-subtle); }
.sp-ops li.empty { color: var(--text-subtle); font-style: italic; }
.sp-ops li.empty::before { content: ""; }
.sp-textarea {
  width: 100%; resize: vertical; min-height: 70px; max-height: 200px;
  font: inherit; font-size: 13px; line-height: 1.5;
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 12px; color: var(--text); margin: 0; box-sizing: border-box;
}
.sp-textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.sp-hint { font-size: 10px; color: var(--text-subtle); margin-top: 6px; }
.sp-foot {
  padding: 10px 14px; border-top: 1px solid var(--border);
  display: flex; gap: 8px; align-items: center;
}
.sp-send {
  background: var(--accent); color: white; border: 1px solid var(--accent);
  border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 500;
}
.sp-send:hover:not(:disabled) { background: var(--accent-strong); border-color: var(--accent-strong); }
.sp-send:disabled { background: var(--surface-2); color: var(--text-subtle); border-color: var(--border); cursor: not-allowed; }
.sp-status { font-size: 11px; color: var(--text-subtle); }
.sp-status.ok { color: var(--must); font-weight: 500; }
.sp-status.warn { color: var(--warn); font-weight: 500; }
.sp-version { margin-left: auto; font-family: ui-monospace, Menlo, monospace; font-size: 10px; color: var(--text-subtle); }
"""


def wrap_html(component_src: str, project_title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{project_title} — Quote Viewer</title>
<style>
{VIEWER_CSS}
</style>
<script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body>
<div id="root"></div>
<script type="text/babel" data-presets="react">
const {{ useState, useCallback, useRef, useEffect }} = React;

{component_src}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(React.createElement(QuotesView));
</script>
</body>
</html>
"""


# ============================================================================
# Main
# ============================================================================

def main():
    p = argparse.ArgumentParser(description="Build documentary-junior-editor quote viewer HTML.")
    p.add_argument("--slug", help="Project slug (folder name under handoffs/)")
    p.add_argument("--ssd-root", help="Project SSD root path", default=None)
    p.add_argument("--data", help="Pre-assembled project data JSON (alternative to --slug)")
    p.add_argument("--template", default=None, help="Template .jsx path")
    p.add_argument("--output", help="Output HTML path")
    args = p.parse_args()

    here = Path(__file__).resolve().parent
    tpl_path = Path(args.template) if args.template else here / "quotes_viewer_template.jsx"
    if not tpl_path.exists():
        print(f"Template not found: {tpl_path}", file=sys.stderr)
        return 1

    template_src = tpl_path.read_text()

    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"Data file not found: {data_path}", file=sys.stderr)
            return 1
        data_block = json.loads(data_path.read_text())
        slug = data_block.get("PROJECT_META", {}).get("slug") or "project"
    else:
        if not args.slug or not args.ssd_root:
            print("Provide either --data, or both --slug and --ssd-root", file=sys.stderr)
            return 1
        raw = load_project_data_from_handoffs(args.slug, Path(args.ssd_root))
        data_block = assemble_data_block(raw)
        slug = raw["slug"]

    out_path = Path(args.output) if args.output else None
    if out_path is None:
        ssd_root = data_block["PROJECT_META"].get("ssd_root") or args.ssd_root
        if not ssd_root:
            print("Cannot infer output path; provide --output", file=sys.stderr)
            return 1
        out_path = Path(ssd_root) / "handoffs" / slug / f"{slug}_quotes_view.html"

    # Substitute data, strip module syntax, wrap
    substituted = substitute_data_block(template_src, data_block)
    component_src = strip_module_syntax(substituted)
    html = wrap_html(component_src, data_block["PROJECT_TITLE"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
