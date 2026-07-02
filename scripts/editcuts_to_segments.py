#!/usr/bin/env python3
"""Canonical `_editCuts` → `segments[]` converter for the Edit→FCPXML handoff.

WHY THIS EXISTS
---------------
The quote viewer's **Export to Final Cut** writes a v5 payload
(`trimmed-quotes-v[N]-tight.json`) whose entries carry character-range trims in
`_editCuts` — the shape the viewer's char-range trim editor produces. But
`scripts/build_fcpxml.py` reconstructs clips from the *other* v5 trim shape:
per-entry `segments[]` where each ref is
`{"source_segment_idx": i, "head_trim_words": h, "tail_trim_words": t}`.

Those two shapes never met in the pipeline, so on every export the Edit Agent
had to hand-convert `_editCuts` → `segments[]` before the FCPXML Agent could
build. That improvised step was fragile and undocumented, and it was seen to
break on two separate projects (h-s-ibew-2026, epicor-rf-fager).

This module is the durable, tested replacement for that improvisation. It is the
exact inverse of `build_quotes_viewer.migrate_entry_trims` (which goes
`segments[]` → `_editCuts`). The Edit Agent runs it as its export-fulfillment
step (see SKILL-edit.md, "Fulfilling an export request"); the output JSON is
consumed unchanged by `build_fcpxml.py`.

THE MID-SEGMENT LIMITATION (v5.7, still true)
---------------------------------------------
`head_trim_words` / `tail_trim_words` can only express a **single contiguous**
kept span per segment. The viewer lets the editor cut words from the *middle*
of a segment, leaving two or more disjoint kept pieces — which head/tail trims
cannot represent. This converter approximates such a cut with the **widest
contiguous span**: it keeps everything from the first kept word to the last kept
word (trimming only fully-cut words off the head and tail), which *retains* the
interior cut words. That is why the exported FCPXML can "play slightly wider"
than the viewer shows at those points — the documented, accepted v5.7 behavior.

For every entry where that happens, the converter records a **fidelity note**
naming the affected segment(s) and the interior words that FCPXML will retain,
so the Edit Agent can do a per-entry verbatim (Cardinal Rule 1) re-check and the
editor can refine the in/out in Final Cut Pro. epicor-rf-fager entries #68 and
#130 are the canonical real-world examples.

USAGE
-----
    python3 scripts/editcuts_to_segments.py \
        handoffs/<slug>/trimmed-quotes-v<N>-tight.json \
        --source-pool handoffs/<slug>/tagged-quotes-v<N>.json \
        -o handoffs/<slug>/trimmed-quotes-v<N>-tight.segments.json

Exit code is 0 on success (even with fidelity notes — they are expected, not
errors) and non-zero only on hard failures (unreadable input, a spoken entry
whose source quote is missing from the pool, an entry that converts to zero kept
segments). The fidelity report is printed to stderr and, with --report, written
to a file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Pure helpers — kept byte-for-byte compatible with build_quotes_viewer.py so
# the char coordinates in `_editCuts` are interpreted exactly as they were
# produced. full_text is the segments' text joined with a SINGLE space, and a
# "word" is a maximal run of non-whitespace (re.findall(r"\S+", ...)).
# ---------------------------------------------------------------------------

def _build_full_text_and_offsets(segments: list):
    """Return (full_text, [(seg_start, seg_end), ...]) for the source segments.

    Mirrors build_quotes_viewer.migrate_entry_trims: join segment texts with a
    single space and track each segment's [start, end) char span in the join.
    Spans are returned in segment-list order (parallel to `segments`).
    """
    full_text = " ".join(seg.get("text", "") for seg in segments)
    spans = []
    pos = 0
    for i, seg in enumerate(segments):
        text = seg.get("text", "")
        spans.append((pos, pos + len(text)))
        pos += len(text)
        if i < len(segments) - 1:
            pos += 1  # the single-space separator
    return full_text, spans


def _normalize_cuts(cuts, text_len: int):
    """Clamp, drop-empty, sort and merge overlapping/adjacent cut ranges."""
    norm = []
    for c in cuts or []:
        try:
            s, e = int(c[0]), int(c[1])
        except (TypeError, ValueError, IndexError):
            continue
        s = max(0, min(s, text_len))
        e = max(0, min(e, text_len))
        if e > s:
            norm.append([s, e])
    norm.sort()
    merged = []
    for s, e in norm:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def _kept_ranges_from_cuts(cuts, text_len: int):
    """Complement of `cuts` within [0, text_len) — the ranges that are KEPT."""
    kept = []
    pos = 0
    for s, e in cuts:
        if pos < s:
            kept.append((pos, s))
        pos = max(pos, e)
    if pos < text_len:
        kept.append((pos, text_len))
    return kept


def _overlaps_kept(a: int, b: int, kept_ranges) -> bool:
    """True if [a, b) overlaps any kept range."""
    for ks, ke in kept_ranges:
        if max(ks, a) < min(ke, b):
            return True
    return False


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def editcuts_to_segments(entry: dict, source_quote: dict):
    """Convert one entry's `_editCuts` into a `segments[]` list.

    Returns (segment_refs, fidelity_notes):
      segment_refs   — list of {"source_segment_idx", "head_trim_words"?,
                       "tail_trim_words"?} in source-segment order, one per
                       segment that keeps at least one word. Zero-valued trims
                       are omitted for readability (build_fcpxml defaults them
                       to 0).
      fidelity_notes — list of str, one per segment whose kept material could
                       not be represented exactly (an interior/mid-segment cut).
                       Empty when the conversion is exact.

    A word is a maximal non-whitespace run. It is "kept" if it overlaps any kept
    char range, and "cut" only if it lies entirely inside the cuts. The kept
    span emitted per segment is the WIDEST contiguous span — first kept word
    through last kept word — so interior cut words are retained (see module
    docstring). Raises ValueError only on structural problems the caller can act
    on.
    """
    segments = source_quote.get("segments") or []
    if not segments:
        raise ValueError(
            f"source quote {source_quote.get('num')!r} has no segments[]; "
            "the source pool must be segment-decomposed."
        )

    full_text, spans = _build_full_text_and_offsets(segments)
    cuts = _normalize_cuts(entry.get("_editCuts"), len(full_text))
    kept_ranges = _kept_ranges_from_cuts(cuts, len(full_text))

    refs = []
    notes = []
    for seg, (seg_start, seg_end) in zip(segments, spans):
        seg_text = full_text[seg_start:seg_end]
        word_spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", seg_text)]
        if not word_spans:
            continue  # empty segment contributes nothing

        kept_flags = [
            _overlaps_kept(seg_start + ws, seg_start + we, kept_ranges)
            for ws, we in word_spans
        ]
        kept_idx = [i for i, k in enumerate(kept_flags) if k]
        if not kept_idx:
            continue  # segment fully cut → dropped from the entry

        first, last = kept_idx[0], kept_idx[-1]
        head = first
        tail = len(word_spans) - 1 - last

        ref = {"source_segment_idx": seg.get("idx")}
        if head:
            ref["head_trim_words"] = head
        if tail:
            ref["tail_trim_words"] = tail
        refs.append(ref)

        # Interior cut = a fully-cut word sitting between the first and last kept
        # word. head/tail trims cannot drop it, so FCPXML will retain it.
        interior = [i for i in range(first, last + 1) if not kept_flags[i]]
        if interior:
            words = [seg_text[ws:we] for ws, we in word_spans]
            retained = " ".join(words[i] for i in interior)
            notes.append(
                f"segment idx {seg.get('idx')}: mid-segment cut not "
                f"representable by head/tail word-trims — FCPXML will retain "
                f"{len(interior)} interior word(s) the viewer cut "
                f"(“{retained}”); the clip plays slightly wider here. "
                f"Verify verbatim (Cardinal Rule 1) and refine the in/out in "
                f"Final Cut Pro."
            )

    return refs, notes


def _lookup_source(pool: dict, sid):
    """Resolve a source quote by id, tolerating int/str coupling."""
    if sid is None:
        return None
    if sid in pool:
        return pool[sid]
    try:
        return pool.get(int(sid))
    except (ValueError, TypeError):
        return None


def convert_payload(payload: dict, pool: dict):
    """Convert an exported viewer payload in place-ish, returning (out, report).

    `payload` is the parsed `trimmed-quotes-v[N]-tight.json`. `pool` is keyed by
    source_quote_id (int and str), e.g. from build_fcpxml.load_source_pool.

    Returns (out_payload, report) where report is:
      {
        "entries_total", "entries_spoken", "entries_converted",
        "entries_passthrough", "entries_dropped",
        "affected": [{"entry_id", "source_quote_id", "notes": [...]}],
        "dropped":  [{"entry_id", "source_quote_id", "reason"}],
      }
    Spoken entries that already carry a usable `segments[]` are passed through
    untouched (idempotent). Non-spoken entries (title cards, interstitials,
    context beats) are passed through untouched.
    """
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("payload has no 'entries' list — not a v5 export?")

    out_entries = []
    report = {
        "entries_total": len(entries),
        "entries_spoken": 0,
        "entries_converted": 0,
        "entries_passthrough": 0,
        "entries_dropped": 0,
        "affected": [],
        "dropped": [],
    }

    for entry in entries:
        if not isinstance(entry, dict):
            out_entries.append(entry)
            continue

        sid = entry.get("source_quote_id")
        is_spoken = sid is not None
        if not is_spoken:
            out_entries.append(entry)  # non-spoken structural entry
            continue

        report["entries_spoken"] += 1

        # Already segment-shaped and usable → pass through (idempotent).
        existing = entry.get("segments")
        if isinstance(existing, list) and any(
            isinstance(s, dict) and "source_segment_idx" in s for s in existing
        ):
            report["entries_passthrough"] += 1
            out_entries.append(entry)
            continue

        source = _lookup_source(pool, sid)
        if source is None:
            raise ValueError(
                f"entry {entry.get('entry_id')!r} references source_quote_id "
                f"{sid!r} which is not in the source pool. Pass the matching "
                "tagged-quotes-v[N].json via --source-pool."
            )

        refs, notes = editcuts_to_segments(entry, source)

        if not refs:
            # Every segment was fully cut — nothing to build. Drop it loudly
            # rather than let build_fcpxml hard-fail on an empty entry.
            report["entries_dropped"] += 1
            report["dropped"].append({
                "entry_id": entry.get("entry_id"),
                "source_quote_id": sid,
                "reason": "all segments fully cut by _editCuts (0 kept words)",
            })
            continue

        new_entry = dict(entry)
        new_entry["segments"] = refs
        out_entries.append(new_entry)
        report["entries_converted"] += 1
        if notes:
            report["affected"].append({
                "entry_id": entry.get("entry_id"),
                "source_quote_id": sid,
                "notes": notes,
            })

    out = dict(payload)
    out["entries"] = out_entries
    return out, report


# ---------------------------------------------------------------------------
# Reporting + CLI
# ---------------------------------------------------------------------------

def format_report(report: dict) -> str:
    lines = []
    lines.append(
        f"Converted {report['entries_converted']} spoken entr"
        f"{'y' if report['entries_converted'] == 1 else 'ies'} "
        f"(passthrough {report['entries_passthrough']}, "
        f"dropped {report['entries_dropped']}, "
        f"total entries {report['entries_total']})."
    )
    if report["dropped"]:
        lines.append("")
        lines.append("DROPPED (all segments cut — needs attention):")
        for d in report["dropped"]:
            lines.append(
                f"  - entry {d['entry_id']} (source #{d['source_quote_id']}): "
                f"{d['reason']}"
            )
    if report["affected"]:
        lines.append("")
        lines.append(
            f"FIDELITY NOTES — {len(report['affected'])} entr"
            f"{'y' if len(report['affected']) == 1 else 'ies'} with mid-segment "
            "cuts (FCPXML plays slightly wider; re-check verbatim, refine in FCP):"
        )
        for a in report["affected"]:
            lines.append(f"  entry {a['entry_id']} (source #{a['source_quote_id']}):")
            for n in a["notes"]:
                lines.append(f"    - {n}")
    else:
        lines.append("No mid-segment approximations — conversion is exact.")
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Convert a viewer-exported _editCuts payload into a v5 "
                    "segments[] payload that build_fcpxml.py consumes."
    )
    ap.add_argument("cut_file", help="trimmed-quotes-v[N]-tight.json (viewer export)")
    ap.add_argument("--source-pool", required=True,
                    help="tagged-quotes-v[N].json (segment-decomposed source pool)")
    ap.add_argument("-o", "--output",
                    help="output JSON path (default: <cut_file>.segments.json)")
    ap.add_argument("--report", help="optional path to write the fidelity report")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress the report on stderr (still written with --report)")
    args = ap.parse_args(argv)

    # Reuse build_fcpxml's pool loader so the pool shape matches exactly what
    # the downstream build reads. Import lazily so the pure functions above stay
    # importable without the FCPXML deps present.
    import importlib.util
    from pathlib import Path
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "build_fcpxml", str(here / "build_fcpxml.py")
    )
    bfx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bfx)

    with open(args.cut_file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    pool = bfx.load_source_pool(args.source_pool)

    out, report = convert_payload(payload, pool)

    out_path = args.output or (args.cut_file.rsplit(".json", 1)[0] + ".segments.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    text = format_report(report)
    if not args.quiet:
        print(text, file=sys.stderr)
    print(out_path)  # stdout = the path, so callers can capture it
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
