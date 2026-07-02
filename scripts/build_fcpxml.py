#!/usr/bin/env python3
"""
build_fcpxml.py — CLI wrapper around generate_fcpxml.py for the Agent SDK pipeline.

Reads a trimmed paper-cut JSON (produced by the Edit Agent), a markdown params
file (produced by the FCPXML Params Agent), and an act-structure markdown file,
then calls into generate_fcpxml.py's library functions to emit an import-ready
FCPXML file for Final Cut Pro.

This wrapper exists so the FCPXML Agent can invoke generation via run_script
rather than producing the raw XML as model output (which hits the 32K output
token limit). All heavy lifting stays in generate_fcpxml.py.

Usage:
    build_fcpxml.py --quotes QUOTES.json --params PARAMS.md \
                    --act-structure ACTS.md --xml-dir DIR \
                    --output OUT.fcpxml --project-name "My Project"
"""

import argparse
import json
import os
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

# Import library functions from generate_fcpxml.py (same directory).
#
# generate_fcpxml.py imports openpyxl at module-load time for its Excel-reading
# main(). This wrapper never touches Excel, so we stub openpyxl out if it's not
# installed — prevents the wrapper from failing on environments where openpyxl
# isn't present. The stub is only used if the real module cannot be imported.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import openpyxl  # noqa: F401
except ImportError:
    import types
    _stub = types.ModuleType("openpyxl")
    _stub.load_workbook = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("openpyxl is not installed; build_fcpxml.py does not use it")
    )
    sys.modules["openpyxl"] = _stub

from generate_fcpxml import (  # noqa: E402
    parse_source_fcpxml,
    generate_fcpxml,
    normalize_label,
    _canonicalize_section,
)


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_MISSING_INPUT = 2
EXIT_BAD_PARAMS = 3
EXIT_NO_CAPTION = 4      # quote-text truncation: clip plays less than verbatim
EXIT_GEN_ERROR = 5
EXIT_SPEAKER_MISS = 6    # speaker(s) skipped or 0-clip output
EXIT_VERIFY_FAIL = 7     # --verify post-generation checks failed


# ---------------------------------------------------------------------------
# fcpxml-params.md parser
# ---------------------------------------------------------------------------

# Canonical section names -> tolerant substrings matched case-insensitively.
# Ordering matters within a list: the most specific match goes first so that
# e.g. "event uid" doesn't get swallowed by the generic "event" match.
_PARAM_SECTIONS = {
    "speaker_refs":     ["media ref ids", "media refs", "media ref id"],
    "speaker_angles":   ["angle ids", "angle id", "angles"],
    "asset_refs":       ["asset ref ids", "asset refs", "asset ref id"],
    "asset_names":      ["asset names", "asset name"],
    "clip_types":       ["clip types", "clip type"],
    "reference_file":   ["reference fcpxml", "reference file",
                         "sample narrative", "reference"],
    "library_location": ["library location", "library"],
    "event_uid":        ["event uid", "event uuid"],
    "event_name":       ["event name", "event"],
    "format_ref":       ["format reference", "format ref", "format"],
}


def _strip_markup(value: str) -> str:
    """Strip backticks, surrounding quotes, bold markers, and whitespace."""
    value = value.strip()
    value = value.strip("`")
    value = value.strip()
    # Remove leading/trailing ** bold markers
    value = re.sub(r"^\*+|\*+$", "", value).strip()
    # Remove surrounding quotes
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        value = value[1:-1]
    return value.strip()


def _split_sections(text: str):
    """
    Split the params markdown into (heading, body) pairs.

    Accepts headings in the form '#+ Title', '**Title**' on its own line, or
    'Title:' on its own line. Body runs from the line after the heading to
    the next heading (or EOF).
    """
    # Normalize line endings
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    heading_re = re.compile(r"^\s*(#+)\s*(.+?)\s*$")
    bold_heading_re = re.compile(r"^\s*\*\*(.+?)\*\*\s*:?\s*$")
    colon_heading_re = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /_-]{2,50})\s*:\s*$")

    sections = []
    current_heading = None
    current_body = []

    def flush():
        if current_heading is not None:
            sections.append((current_heading, "\n".join(current_body).strip()))

    for line in lines:
        m = heading_re.match(line)
        if m:
            flush()
            current_heading = m.group(2).strip()
            current_body = []
            continue
        m = bold_heading_re.match(line)
        if m:
            flush()
            current_heading = m.group(1).strip()
            current_body = []
            continue
        m = colon_heading_re.match(line)
        if m and current_heading is not None:
            # Looks like a "Key: Value" heading line — treat as new mini-section
            flush()
            current_heading = m.group(1).strip()
            current_body = []
            continue
        if current_heading is not None:
            current_body.append(line)
        # Lines before the first heading are ignored

    flush()
    return sections


def _find_section(sections, candidates):
    """Return the body of the first section whose heading matches any candidate."""
    for heading, body in sections:
        heading_norm = heading.lower().strip().rstrip(":")
        for cand in candidates:
            if cand in heading_norm:
                return body
    return None


def _parse_kv_list(body: str):
    """
    Parse list items of the form '- Name: value', '* Name: value', or
    '1. Name: value' into an ordered dict. Tolerant of extra whitespace and
    backticks around the value.
    """
    result = {}
    if not body:
        return result
    item_re = re.compile(
        r"^\s*(?:[-*+]|\d+\.)\s*(?P<key>[^:]+?)\s*:\s*(?P<val>.+?)\s*$"
    )
    for line in body.split("\n"):
        if not line.strip():
            continue
        m = item_re.match(line)
        if m:
            key = _strip_markup(m.group("key"))
            val = _strip_markup(m.group("val"))
            if key and val:
                result[key] = val
    return result


def _parse_md_table(body: str) -> list:
    """
    Parse a GitHub-flavored markdown table into a list of dicts keyed by
    column header. Returns [] if no recognizable table is found.

    Tolerant of:
      - leading and trailing pipes (`| col | col |`)
      - the header-separator row (`|---|---|`) — skipped automatically
      - extra whitespace and backtick/bold markup inside cells (stripped via
        _strip_markup)
      - rows with fewer columns than the header (missing cells become "")

    Example input:
        | Interview / speaker | Source filename       | clip_type   |
        |---------------------|-----------------------|-------------|
        | Alice Mupenzi       | Alice_Mupenzi.fcpxml  | multicam    |
        | Ben                 | Ben_interview.fcpxml  | single_clip |

    Returns:
        [
          {"Interview / speaker": "Alice Mupenzi",
           "Source filename": "Alice_Mupenzi.fcpxml",
           "clip_type": "multicam"},
          ...
        ]
    """
    if not body:
        return []

    rows = []
    headers = None
    sep_re = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")

    for raw in body.split("\n"):
        line = raw.strip()
        if not line or "|" not in line:
            if headers is not None and rows:
                # Blank line after the table body — stop scanning.
                break
            continue
        if sep_re.match(line):
            # Header-separator row; skip but expect data rows next.
            continue
        # Split on pipes, dropping a single leading or trailing empty cell
        # from `| a | b |` style tables.
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        cells = [_strip_markup(c) for c in cells]
        if headers is None:
            headers = cells
            continue
        # Pad short rows with empty strings so dict keys are stable.
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        row = dict(zip(headers, cells[: len(headers)]))
        rows.append(row)

    return rows


def _parse_scalar(body: str) -> str:
    """Extract a single non-empty value from a section body."""
    if not body:
        return ""
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Strip list markers if present
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        return _strip_markup(line)
    return ""


def _resolve_reference_file(value: str) -> str:
    """
    Resolve a reference-file path from fcpxml-params.md to the extracted
    .fcpxml filename that lives in xml_dir/ after Phase 0 extraction.

    Handles three input shapes (Phase 0 of SKILL-fcpxml.md is assumed to have
    run extract_fcpxml.py on the xml dir before this script is invoked):

    1. Bare .fcpxml filename ("Sample_narrative.fcpxml") → return as-is
    2. .fcpxmld package path ("Sample_narrative.fcpxmld") → strip the trailing
       "d" → "Sample_narrative.fcpxml"
    3. .fcpxmld/Info.fcpxml path ("Sample_narrative.fcpxmld/Info.fcpxml") →
       resolve to "Sample_narrative.fcpxml" (the file extract_fcpxml.py
       produces by renaming Info.fcpxml to match the package name)

    Calling os.path.basename() blindly on case 3 returns "Info.fcpxml" and
    loses the package name, which then breaks the downstream
    `xml_dir / params["reference_file"]` join in main(). This helper avoids
    that bug while still accepting all the path shapes the FCPXML Params Agent
    has been observed to emit.
    """
    value = value.strip().rstrip("/").rstrip("\\")
    # Case 3: <pkg>.fcpxmld/Info.fcpxml — collapse to <pkg>.fcpxml
    norm = value.replace("\\", "/")
    if norm.endswith("/Info.fcpxml"):
        parent = os.path.dirname(norm)
        pkg = os.path.basename(parent)
        if pkg.endswith(".fcpxmld"):
            return pkg[: -len(".fcpxmld")] + ".fcpxml"
        # Info.fcpxml without an .fcpxmld parent is unexpected; fall through
    # Case 2: bare .fcpxmld package (with or without directory prefix) →
    # convert to the extracted .fcpxml name
    base = os.path.basename(norm)
    if base.endswith(".fcpxmld"):
        return base[: -len(".fcpxmld")] + ".fcpxml"
    # Case 1 (or anything else) — return the basename verbatim
    return base


def parse_params_md(path: str) -> dict:
    """
    Parse fcpxml-params.md into the dict that generate_fcpxml() needs.

    Returns keys: speaker_refs, speaker_angles, reference_file, library_location,
    event_name, format_ref. Raises ValueError with a specific message when a
    required section is missing or inconsistent.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"fcpxml-params.md not found: {path}")

    sections = _split_sections(text)

    refs_body         = _find_section(sections, _PARAM_SECTIONS["speaker_refs"])
    angles_body       = _find_section(sections, _PARAM_SECTIONS["speaker_angles"])
    asset_refs_body   = _find_section(sections, _PARAM_SECTIONS["asset_refs"])
    asset_names_body  = _find_section(sections, _PARAM_SECTIONS["asset_names"])
    clip_types_body   = _find_section(sections, _PARAM_SECTIONS["clip_types"])
    ref_body          = _find_section(sections, _PARAM_SECTIONS["reference_file"])
    lib_body          = _find_section(sections, _PARAM_SECTIONS["library_location"])
    evt_body          = _find_section(sections, _PARAM_SECTIONS["event_name"])
    evt_uid_body      = _find_section(sections, _PARAM_SECTIONS["event_uid"])
    fmt_body          = _find_section(sections, _PARAM_SECTIONS["format_ref"])

    speaker_refs   = _parse_kv_list(refs_body) if refs_body is not None else {}
    speaker_angles = _parse_kv_list(angles_body) if angles_body is not None else {}
    asset_refs     = _parse_kv_list(asset_refs_body) if asset_refs_body is not None else {}
    asset_names    = _parse_kv_list(asset_names_body) if asset_names_body is not None else {}

    # ── Clip Types: parsed as a markdown table (v5+) ──────────────────────────
    # Backward-compatible default: if the section is missing entirely, treat
    # every speaker in 'Media Ref IDs' as multicam, and every speaker in
    # 'Asset Ref IDs' as single_clip. Legacy multicam-only params files keep
    # working unchanged.
    clip_types = {}
    if clip_types_body is not None:
        rows = _parse_md_table(clip_types_body)
        for row in rows:
            # The handoff format uses "Interview / speaker" but be tolerant of
            # near-variants (spacing, capitalisation, alt punctuation).
            speaker_key = None
            for k in row.keys():
                if re.search(r"speaker|interview|name", k, re.IGNORECASE):
                    speaker_key = k
                    break
            type_key = None
            for k in row.keys():
                if re.search(r"clip[_ ]?type|type", k, re.IGNORECASE):
                    type_key = k
                    break
            if not speaker_key or not type_key:
                continue
            speaker = row[speaker_key].strip()
            ctype = row[type_key].strip().lower()
            if not speaker:
                continue
            if ctype not in {"multicam", "single_clip", "single-clip"}:
                raise ValueError(
                    f"Unknown clip_type {row[type_key]!r} for speaker "
                    f"{speaker!r} in 'Clip Types' table. Expected "
                    "'multicam' or 'single_clip'."
                )
            clip_types[speaker] = "single_clip" if ctype.replace("-", "_") == "single_clip" else "multicam"

    # Apply the legacy default for any speaker not explicitly listed.
    for s in speaker_refs:
        clip_types.setdefault(s, "multicam")
    for s in asset_refs:
        clip_types.setdefault(s, "single_clip")

    # ── At least one speaker must be configured ──────────────────────────────
    if not speaker_refs and not asset_refs:
        raise ValueError(
            "Missing speaker configuration in fcpxml-params.md. Expected at "
            "least one of '## Media Ref IDs' (for multicam interviews) or "
            "'## Asset Ref IDs' (for single_clip interviews) with "
            "'- <Speaker>: r<N>' list items."
        )

    # ── Per-speaker validation by clip_type ──────────────────────────────────
    multicam_speakers = [s for s, t in clip_types.items() if t == "multicam"]
    single_clip_speakers = [s for s, t in clip_types.items() if t == "single_clip"]

    if multicam_speakers and not speaker_refs:
        raise ValueError(
            "Multicam speakers declared in 'Clip Types' "
            f"({', '.join(multicam_speakers)}) but no 'Media Ref IDs' section "
            "found. Each multicam speaker must have a media ref ID."
        )
    if multicam_speakers and not speaker_angles:
        raise ValueError(
            "Multicam speakers declared in 'Clip Types' "
            f"({', '.join(multicam_speakers)}) but no 'Angle IDs' section "
            "found. Each multicam speaker must have an angle ID."
        )

    for s in multicam_speakers:
        if s not in speaker_refs:
            raise ValueError(
                f"Multicam speaker {s!r} has no entry in 'Media Ref IDs'. "
                "Every multicam speaker must have a media ref ID."
            )
        if s not in speaker_angles:
            raise ValueError(
                f"Multicam speaker {s!r} has no entry in 'Angle IDs'. "
                "Every multicam speaker must have an angle ID."
            )

    for s in single_clip_speakers:
        if s not in asset_refs:
            raise ValueError(
                f"Single-clip speaker {s!r} has no entry in 'Asset Ref IDs'. "
                "Every single_clip speaker must have an asset ref ID."
            )
        if s not in asset_names:
            raise ValueError(
                f"Single-clip speaker {s!r} has no entry in 'Asset Names'. "
                "Every single_clip speaker must have an asset name."
            )

    reference_file = _parse_scalar(ref_body) if ref_body is not None else ""
    if not reference_file:
        raise ValueError(
            "Missing 'Reference FCPXML' in fcpxml-params.md. Expected a section "
            "like '## Reference FCPXML' followed by the filename."
        )
    # Resolve to the extracted .fcpxml filename in xml_dir. Handles bare
    # .fcpxml, bare .fcpxmld, and .fcpxmld/Info.fcpxml shapes — see the
    # _resolve_reference_file docstring for the bug this fixes.
    reference_file = _resolve_reference_file(reference_file)

    return {
        "speaker_refs":     speaker_refs,
        "speaker_angles":   speaker_angles,
        "asset_refs":       asset_refs,
        "asset_names":      asset_names,
        "clip_types":       clip_types,
        "reference_file":   reference_file,
        "library_location": _parse_scalar(lib_body) if lib_body is not None else "",
        "event_name":       _parse_scalar(evt_body) if evt_body is not None else "",
        "event_uid":        _parse_scalar(evt_uid_body) if evt_uid_body is not None else "",
        "format_ref":       _parse_scalar(fmt_body) if fmt_body is not None else "",
    }


# ---------------------------------------------------------------------------
# Source-pool loader (tagged-quotes-v[N].json) — needed for v5 schema
# ---------------------------------------------------------------------------

def load_source_pool(path: str) -> dict:
    """
    Load tagged-quotes-v[N].json (the v5 source pool) and return a dict keyed
    by `num` (i.e. `source_quote_id`). Each value is the raw source-quote
    dict — `speaker`, `part`, `startTC`, `endTC`, `segments[]`.

    Accepts both a top-level list (canonical) and an object with a `quotes`
    key (defensive — some intermediate Synthesis outputs have been seen in
    that shape).
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "quotes" in data:
        items = data["quotes"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(
            f"{path} must be a JSON list or an object with a 'quotes' key."
        )

    pool = {}
    for q in items:
        if not isinstance(q, dict):
            continue
        num = q.get("num")
        if num is None:
            continue
        # Preserve both str and int forms so str lookups from
        # source_quote_id work regardless of how the timeline emitted them.
        pool[str(num)] = q
        pool[num] = q
    return pool


def _apply_word_trims(text: str, head_trim_words: int, tail_trim_words: int) -> str:
    """
    Apply head/tail word trims to a segment's verbatim text.

    Snaps to whitespace-delimited word boundaries. Degenerate trims (head or
    tail greater than or equal to the word count) collapse to an empty
    string rather than raising, so the caller can decide whether to drop the
    segment or surface a warning.
    """
    if head_trim_words <= 0 and tail_trim_words <= 0:
        return text
    words = text.split()
    if head_trim_words and head_trim_words >= len(words):
        return ""
    if tail_trim_words and tail_trim_words >= len(words):
        return ""
    if head_trim_words:
        words = words[head_trim_words:]
    if tail_trim_words:
        words = words[:-tail_trim_words]
    return " ".join(words)


def _v5_entry_to_segment_quotes(
    entry: dict,
    pool: dict,
    seq_counter: list,
) -> list:
    """
    Expand a v5 spoken-quote entry into a list of v4-shaped quote dicts —
    **one per kept segment**, in playback order.

    This is the per-segment generation pass: every segment that survives
    after head/tail-word trims becomes its own v4-shaped dict, which
    downstream adapt_quote() → build_spine() turns into its own `<mc-clip>`
    (or `<asset-clip>` once clip_type branching lands). One v5 entry can
    therefore produce N spine clips for N kept segments. This matches the
    Phase 3 "per-segment clip count" verification in SKILL-fcpxml.md.

    `seq_counter` is a single-element list used as a mutable counter so the
    caller can keep a stable global ordering across all entries (Python
    closures can't rebind an integer from an inner scope cleanly).

    Skips (with a stderr warning) segments whose trims fully collapse the
    text. Raises ValueError on hard data errors (missing source quote,
    missing segment idx, no segments[] on source).
    """
    source_quote_id = entry.get("source_quote_id")
    if source_quote_id is None:
        raise ValueError(
            f"v5 spoken-quote entry {entry.get('entry_id')!r} has no "
            "source_quote_id"
        )

    source = pool.get(source_quote_id) or pool.get(str(source_quote_id))
    if source is None:
        raise ValueError(
            f"v5 entry {entry.get('entry_id')!r} references "
            f"source_quote_id {source_quote_id!r} which is not in the "
            "source pool. Provide the matching tagged-quotes-v[N].json via "
            "--source-pool."
        )

    source_segments = {s["idx"]: s for s in source.get("segments", [])}
    if not source_segments:
        raise ValueError(
            f"Source quote {source_quote_id!r} has no segments[]. The "
            "source pool must be segment-decomposed for v5 schema support."
        )

    speaker = entry.get("speaker") or source.get("speaker", "")
    part = entry.get("part") or source.get("part", "")
    entry_id = entry.get("entry_id", "")

    # Guard: a raw viewer export carries char-range `_editCuts` and no
    # `segments[]`. This script builds clips from `segments[]`, so such a file
    # must be converted first. Fail with an actionable message rather than the
    # cryptic "produced zero kept segments" error the empty loop would raise.
    entry_segments = entry.get("segments")
    if (not entry_segments) and entry.get("_editCuts") is not None:
        raise ValueError(
            f"Entry {entry_id!r} carries char-range `_editCuts` but no "
            "`segments[]`. This is a raw viewer export; convert it first with "
            "scripts/editcuts_to_segments.py "
            "(python3 scripts/editcuts_to_segments.py <cut_file> "
            "--source-pool <tagged-quotes-v[N].json> -o <converted.json>), "
            "then build from the converted file. See SKILL-edit.md "
            "\"Fulfilling an export request\"."
        )

    out = []
    for seg_ref in entry.get("segments", []):
        idx = seg_ref.get("source_segment_idx")
        seg = source_segments.get(idx)
        if seg is None:
            raise ValueError(
                f"Entry {entry_id!r} references segment idx {idx!r} which "
                f"is not present on source quote {source_quote_id!r}."
            )
        head = int(seg_ref.get("head_trim_words", 0) or 0)
        tail = int(seg_ref.get("tail_trim_words", 0) or 0)
        trimmed_text = _apply_word_trims(seg["text"], head, tail)
        if not trimmed_text:
            print(
                f"Warning: entry {entry_id!r} segment idx {idx} collapsed "
                f"to empty text after trims (head={head}, tail={tail}); "
                "skipping this segment.",
                file=sys.stderr,
            )
            continue

        seq_counter[0] += 1
        notes_bits = [f"entry={entry_id}", f"seg={idx}"]
        if head:
            notes_bits.append(f"head_trim={head}")
        if tail:
            notes_bits.append(f"tail_trim={tail}")
        notes = " ".join(notes_bits)

        out.append({
            "num": source_quote_id,
            "speaker": speaker,
            "part": part,
            "sequence": seq_counter[0],
            "original": seg["text"],
            "trimmed": trimmed_text,
            "startTC": seg.get("startTC", "") or source.get("startTC", ""),
            "endTC": seg.get("endTC", "") or source.get("endTC", ""),
            "notes": notes,
            # Preserve v5 links for downstream steps (clip_type branching,
            # resource-ID remap, act-boundary cards, UID multicam refs).
            "_v5_entry": entry,
            "_v5_source_quote": source,
            "_v5_segment_idx": idx,
            "_v5_segment": seg,
        })

    if not out:
        raise ValueError(
            f"Entry {entry_id!r} (source_quote_id {source_quote_id!r}) "
            "produced zero kept segments after applying trims. Check "
            "head_trim_words / tail_trim_words on its segments."
        )
    return out


# ---------------------------------------------------------------------------
# trimmed-quotes.json loader (schema-aware: v4 + v5)
# ---------------------------------------------------------------------------

def load_quotes(path: str, source_pool: dict = None) -> dict:
    """
    Load trimmed-quotes.json and normalize it into a structured dict that the
    rest of the pipeline consumes.

    Accepts three input shapes:

    1. **v5 schema** — `{"schema_version": 5, "round": N, "entries": [...]}`.
       Entries are heterogeneous: spoken-quote (has `source_quote_id` and
       `segments[]`), `title_card`, `interstitial`, `context_beat`.
       Spoken-quote entries are reconstructed against `source_pool`
       (required for v5) into v4-shaped quote dicts so the existing
       adapt_quote() / generate_fcpxml() flow can consume them. Non-spoken
       entries are returned separately under `non_spoken_entries` for
       higher-level handling (currently warned-and-skipped; proper
       title-card / interstitial / context-beat rendering lands in a later
       step of the schema rewrite).

    2. **v4 legacy object** — `{"quotes": [...]}`. Each item carries v4
       fields directly (`num`, `trimmed`, `original`, `sequence`, etc.).
       Interstitials (`type: "interstitial"`) are dropped with a warning —
       same behavior as the v4-only loader.

    3. **v4 legacy list** — a bare top-level JSON list of v4 quote dicts.

    Returns:
        {
          "schema_version": 4 | 5,
          "quotes": [<v4-shaped dict>, ...],   # spoken-quote material only
          "non_spoken_entries": [<v5 entry>, ...],  # title_card/interstitial/context_beat
          "metadata": {  # only populated for v5
            "round": int | None,
            "project_slug": str | None,
            "target_runtime_seconds": int | None,
            "estimated_runtime_seconds": int | None,
          },
        }

    Raises ValueError with a specific message when the schema is detected as
    v5 but `source_pool` was not provided, or when an entry references data
    not present in the pool.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ---- v5 schema detection ------------------------------------------------
    is_v5 = (
        isinstance(data, dict)
        and (
            data.get("schema_version") == 5
            or ("entries" in data and "quotes" not in data)
        )
    )

    if is_v5:
        return _load_v5(data, source_pool, path)

    # ---- v4 fallback --------------------------------------------------------
    return _load_v4(data, path)


def _load_v5(data: dict, source_pool: dict, path: str) -> dict:
    """Normalize a v5 timeline into the load_quotes() return shape."""
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError(
            f"{path} looks like v5 schema but has no 'entries' list."
        )

    if source_pool is None:
        raise ValueError(
            f"{path} is v5 schema (schema_version=5 or entries[]) but no "
            "source pool was provided. Pass --source-pool pointing at the "
            "matching tagged-quotes-v[N].json so segments can be looked up."
        )

    quotes = []
    non_spoken = []
    seq_counter = [0]  # mutable so _v5_entry_to_segment_quotes can bump it
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        if "source_quote_id" in entry:
            # Spoken-quote entry — expand into one v4-shaped dict per kept
            # segment. The list extension preserves playback order.
            quotes.extend(
                _v5_entry_to_segment_quotes(entry, source_pool, seq_counter)
            )
        elif entry.get("type") in {"title_card", "interstitial", "context_beat"}:
            non_spoken.append(entry)
        else:
            print(
                f"Warning: v5 entry at index {idx} has no source_quote_id "
                f"and an unrecognized type {entry.get('type')!r}; skipping.",
                file=sys.stderr,
            )

    # Non-spoken entries aren't yet rendered by this script — surface what
    # got dropped so the FCPXML Agent can flag the gap to the user.
    type_counts = {}
    for e in non_spoken:
        type_counts[e.get("type", "?")] = type_counts.get(e.get("type", "?"), 0) + 1
    if type_counts:
        print(
            "Warning: v5 non-spoken entries are not yet rendered by "
            f"build_fcpxml.py (counts: {type_counts}). Spine generated "
            "without them. Title-card / interstitial / context-beat "
            "rendering lands in a follow-up step of the v5 schema rewrite.",
            file=sys.stderr,
        )

    return {
        "schema_version": 5,
        "quotes": quotes,
        "non_spoken_entries": non_spoken,
        "metadata": {
            "round": data.get("round"),
            "project_slug": data.get("project_slug"),
            "target_runtime_seconds": data.get("target_runtime_seconds"),
            "estimated_runtime_seconds": data.get("estimated_runtime_seconds"),
        },
    }


def _load_v4(data, path: str) -> dict:
    """Normalize legacy v4 trimmed-quotes input into the load_quotes() return shape."""
    if isinstance(data, dict) and "quotes" in data:
        items = data["quotes"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(
            f"{path} must be a JSON list, an object with a 'quotes' key, or "
            "a v5 object with an 'entries' key (got "
            f"{type(data).__name__})."
        )

    quotes = []
    interstitials = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "interstitial":
            interstitials += 1
            continue
        quotes.append(item)

    if interstitials:
        print(
            f"Warning: Interstitials are not yet rendered by build_fcpxml.py "
            f"(count: {interstitials}). Spine generated without them.",
            file=sys.stderr,
        )

    # Sort by sequence if every quote has one, else preserve input order
    if quotes and all("sequence" in q for q in quotes):
        quotes.sort(key=lambda q: q["sequence"])

    return {
        "schema_version": 4,
        "quotes": quotes,
        "non_spoken_entries": [],
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# act-structure.md parser
# ---------------------------------------------------------------------------

def parse_act_structure(path: str):
    """
    Extract ordered act/part/section labels from act-structure.md. Returns a
    list of label strings in document order. Tolerant of multiple heading
    styles.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # C7: in addition to numbered "Act N"-style headings, standalone act
    # headings like "Intro" / "Prologue" / "Epilogue" are real acts too.
    # Note generate_fcpxml.create_section_divider renames "Opening" ->
    # "Intro" at display time; both spellings must parse here so the
    # rename stays consistent end-to-end. The \b keeps "Action items"
    # from matching "Act".
    # [ \t]* (NOT \s*) after the keyword: \s matches newlines, which lets a
    # bare heading like '## Intro' swallow the next body line into the label.
    label_re = re.compile(
        r"^[ \t]*#+[ \t]*((?:Act|Part|Section|Intro|Introduction|Opening"
        r"|Prologue|Epilogue|Conclusion|Outro)\b[ \t]*[^#\n]*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    labels = [m.group(1).strip() for m in label_re.finditer(text)]
    return labels


# ---------------------------------------------------------------------------
# Source caption file lookup
# ---------------------------------------------------------------------------

class AmbiguousSpeakerFileError(RuntimeError):
    """Raised when a speaker's name-token fallback matches >1 source file."""


def find_speaker_fcpxml(speaker: str, xml_dir: Path):
    """
    Locate a source caption .fcpxml for a given speaker. Tries exact match,
    case-insensitive stem match, then a name-token fallback. Returns the
    Path to the matching file, or raises FileNotFoundError (no match) /
    AmbiguousSpeakerFileError (more than one fallback match).

    B6 — the fallback matches name tokens against WORD-BOUNDARY tokens of
    the file stem (stem split on non-alphanumerics), not raw substrings, so
    'Ben' does not match 'Reuben_interview.fcpxml'. Files matching ALL of
    the speaker's name tokens are preferred over files matching only some
    (so 'Mike Stern' binds to 'Mike_Stern.fcpxml' even when
    'Jana_Stern.fcpxml' also exists). If the best tier still holds more
    than one candidate, this fails loudly instead of silently binding the
    first sorted hit.
    """
    candidates_tried = []

    exact = xml_dir / f"{speaker}.fcpxml"
    candidates_tried.append(str(exact))
    if exact.exists():
        return exact

    # Case-insensitive stem match
    target_lower = speaker.lower()
    fcpxmls = sorted(xml_dir.glob("*.fcpxml"))
    for p in fcpxmls:
        if p.stem.lower() == target_lower:
            return p

    # Name-token fallback: match speaker name tokens against the stem's
    # word tokens (word boundaries — split on non-alphanumerics).
    tokens = [t.lower() for t in speaker.split() if t]
    full_matches = []     # files whose stem contains ALL name tokens
    partial_matches = []  # files whose stem contains at least one token
    if tokens:
        for p in fcpxmls:
            stem_words = set(re.split(r"[^a-z0-9]+", p.stem.lower())) - {""}
            hit = [t for t in tokens if t in stem_words]
            if len(hit) == len(tokens):
                full_matches.append(p)
            elif hit:
                partial_matches.append(p)

    candidates = full_matches if full_matches else partial_matches
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        listing = ", ".join(p.name for p in candidates)
        raise AmbiguousSpeakerFileError(
            f"Speaker '{speaker}' matches more than one source caption "
            f"FCPXML in {xml_dir}: [{listing}]. Refusing to guess — rename "
            "the files (or the speaker in fcpxml-params.md) so exactly one "
            "file matches, e.g. '<Full Speaker Name>.fcpxml'."
        )

    candidates_tried.append(f"case-insensitive stem match in {xml_dir}")
    if tokens:
        candidates_tried.append(
            f"word-boundary token match on {tokens} in {xml_dir}"
        )

    raise FileNotFoundError(
        f"No source caption FCPXML found for speaker '{speaker}' in {xml_dir}. "
        f"Looked for: {candidates_tried}."
    )


# ---------------------------------------------------------------------------
# Quote adapter: JSON shape -> generate_fcpxml's paper_cuts dict shape
# ---------------------------------------------------------------------------

def adapt_quote(q: dict, fallback_seq: int) -> dict:
    """
    Convert a trimmed-quotes.json record to the dict shape that build_spine()
    and generate_fcpxml() consume.

    Source shape (this script's input):
        v4: {"num", "speaker", "part", "sequence", "original", "trimmed",
             "split", "startTC", "endTC"}
        v5-derived: same shape produced by _v5_entry_to_segment_quotes(),
            plus a populated "notes" string with entry/segment traceability
            (e.g. "entry=e_001 seg=0 head_trim=3"). The notes field is
            forwarded into the paper_cut so build_spine() / downstream
            logging can show which v5 entry+segment a clip came from.

    Target shape (generate_fcpxml.py consumes, matching read_paper_cut_tab):
        {"seq_num", "quote_num", "speaker", "section", "quote", "start_tc",
         "end_tc", "notes"}

    Uses the trimmed text as the quote (the trimmed version is what should
    drive caption matching for split/non-contiguous handling).
    """
    quote_text = q.get("trimmed") or q.get("original") or ""
    return {
        "seq_num": q.get("sequence", fallback_seq),
        "quote_num": q.get("num", fallback_seq),
        "speaker": q.get("speaker", ""),
        "section": q.get("part", ""),
        "quote": quote_text,
        "start_tc": q.get("startTC", ""),
        "end_tc": q.get("endTC", ""),
        "notes": q.get("notes", ""),
    }


# ---------------------------------------------------------------------------
# Output verification
# ---------------------------------------------------------------------------

def count_mc_clips(output_path: str) -> int:
    """
    Count spine clip elements (<mc-clip> + <asset-clip>) in the generated
    FCPXML. Name preserved for backward compat with main()'s success-line
    print; the count is total DIRECT spine clips, not just multicam.

    Counts spine children via XML parse rather than a whole-file regex —
    multicam `<media>` resources legitimately contain `<asset-clip>`
    elements inside their angles, which a raw regex over-counts.
    """
    try:
        root = ET.parse(output_path).getroot()
        spine = root.find(".//spine")
        if spine is None:
            return 0
        return sum(1 for el in spine if el.tag in ("mc-clip", "asset-clip"))
    except Exception:
        # Fall back to the legacy regex count if the XML doesn't parse.
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            mc = len(re.findall(r"<mc-clip\b", content))
            asset = len(re.findall(r"<asset-clip\b", content))
            return mc + asset
        except Exception:
            return 0


def extract_total_duration(output_path: str) -> str:
    """Pull the top-level sequence duration attribute from the output file."""
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        m = re.search(r"<sequence\b[^>]*\bduration=\"([^\"]+)\"", content)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "unknown"


def _frac_secs(s: str) -> float:
    """Parse an FCPXML rational time ('16016/24000s', '0s') to float seconds."""
    if not s:
        return 0.0
    s = s.strip().rstrip("s")
    if "/" in s:
        num, denom = s.split("/")
        return int(num) / int(denom)
    return float(s)


def _entry_key(paper_cut: dict, index: int) -> str:
    """
    Stable per-entry grouping key for a paper-cut dict.

    v5-derived quotes carry 'entry=<id> seg=<n>' in notes — group by the
    entry id so all kept segments of one timeline entry verify together.
    v4 quotes are their own entry (one quote == one entry).
    """
    m = re.search(r"entry=(\S+)", paper_cut.get("notes") or "")
    if m:
        return m.group(1)
    return f"q{paper_cut.get('quote_num', '?')}#{index}"


def verify_output(output_path: str, paper_cuts: list, params: dict,
                  act_labels: list, build_report: dict) -> tuple:
    """
    W1 — post-generation verification. Parses the emitted FCPXML and
    cross-checks it against the expected inputs + the build report.

    Returns (report_dict, ok). report_dict is JSON-serializable:

      {
        "output": str,
        "overall_pass": bool,
        "failures": [str, ...],          # human-readable failure reasons
        "totals": {"clips_in_xml", "clips_expected_from_build",
                   "spine_elements"},
        "per_speaker": {speaker: {"clips_in_xml", "expected_entries",
                                  "expected_segments", "segments_matched",
                                  "clip_type_expected", "clip_types_in_xml",
                                  "clip_type_ok"}},
        "per_entry": [{"entry", "speaker", "expected_segments",
                       "segments_matched", "emitted_clips", "ok"}],
        "truncations": [...],            # from the build (W3)
        "speaker_misses": [...],         # from the build (W3)
        "act_dividers": {"declared_acts", "expected_dividers",
                         "divider_titles_in_xml", "offsets_monotonic",
                         "titles_consistent_with_gaps", "ok"},
        "project": {"has_uid", "has_mod_date"},
      }
    """
    failures = []

    tree = ET.parse(output_path)
    root = tree.getroot()
    spine = root.find(".//spine")
    if spine is None:
        return ({"output": output_path, "overall_pass": False,
                 "failures": ["no <spine> element in output"]}, False)

    xml_clips = [el for el in spine if el.tag in ("mc-clip", "asset-clip")]
    divider_gaps = [el for el in spine
                    if el.tag == "gap" and el.find("title") is not None]

    report_clips = build_report.get("clips", [])
    truncations = build_report.get("truncations", [])
    speaker_misses = build_report.get("speaker_misses", [])

    # ── totals ────────────────────────────────────────────────────────────
    if len(xml_clips) != len(report_clips):
        failures.append(
            f"spine clip count mismatch: {len(xml_clips)} in XML vs "
            f"{len(report_clips)} recorded during build"
        )

    # ── per-clip pairing: XML clips are emitted in build order ────────────
    clip_types_cfg = params.get("clip_types", {})
    per_speaker = {}

    def _speaker_bucket(speaker):
        if speaker not in per_speaker:
            per_speaker[speaker] = {
                "clips_in_xml": 0,
                "expected_entries": 0,
                "expected_segments": 0,
                "segments_matched": 0,
                "clip_type_expected": clip_types_cfg.get(speaker, "multicam"),
                "clip_types_in_xml": [],
                "clip_type_ok": True,
            }
        return per_speaker[speaker]

    # Expected side, from the trimmed-quotes JSON (paper_cuts):
    entries = {}  # entry_key -> {"speaker", "indices": [paper_cut_index]}
    for idx, pc in enumerate(paper_cuts):
        key = _entry_key(pc, idx)
        ent = entries.setdefault(key, {"speaker": pc.get("speaker", ""),
                                       "indices": []})
        ent["indices"].append(idx)

    matched_indices = {c.get("paper_cut_index") for c in report_clips}
    clips_per_index = {}
    for c in report_clips:
        clips_per_index[c.get("paper_cut_index")] = \
            clips_per_index.get(c.get("paper_cut_index"), 0) + 1

    for key, ent in entries.items():
        b = _speaker_bucket(ent["speaker"])
        b["expected_entries"] += 1
        b["expected_segments"] += len(ent["indices"])
        b["segments_matched"] += sum(
            1 for i in ent["indices"] if i in matched_indices)

    # Actual side, pairing XML elements with build-report clips in order:
    for i, el in enumerate(xml_clips):
        if i >= len(report_clips):
            break
        rc = report_clips[i]
        speaker = rc.get("speaker", "")
        b = _speaker_bucket(speaker)
        b["clips_in_xml"] += 1
        b["clip_types_in_xml"].append(el.tag)
        expected_tag = ("asset-clip"
                        if clip_types_cfg.get(speaker, "multicam") == "single_clip"
                        else "mc-clip")
        if el.tag != expected_tag:
            b["clip_type_ok"] = False
            failures.append(
                f"clip {i} for speaker {speaker!r} is <{el.tag}> but params "
                f"Clip Types says it should be <{expected_tag}>"
            )

    for speaker, b in per_speaker.items():
        if b["expected_segments"] and b["segments_matched"] < b["expected_segments"]:
            failures.append(
                f"speaker {speaker!r}: only {b['segments_matched']} of "
                f"{b['expected_segments']} expected segments produced clips"
            )
        if b["expected_segments"] and b["clips_in_xml"] == 0:
            failures.append(
                f"speaker {speaker!r}: expected "
                f"{b['expected_segments']} segment(s) but emitted 0 clips"
            )

    # ── per-entry: expected segments vs emitted clips ─────────────────────
    per_entry = []
    for key, ent in entries.items():
        expected = len(ent["indices"])
        matched = sum(1 for i in ent["indices"] if i in matched_indices)
        emitted = sum(clips_per_index.get(i, 0) for i in ent["indices"])
        ok = matched == expected
        per_entry.append({
            "entry": key,
            "speaker": ent["speaker"],
            "expected_segments": expected,
            "segments_matched": matched,
            "emitted_clips": emitted,
            "ok": ok,
        })
        if not ok:
            failures.append(
                f"entry {key!r} ({ent['speaker']}): {matched} of {expected} "
                "segments produced clips"
            )

    # ── act dividers (C5 invariants, verified from the XML itself) ────────
    # Expected divider count = number of section CHANGES across the
    # paper-cut sequence after canonicalization against act_labels —
    # exactly the rule build_spine applies.
    expected_dividers = 0
    cur = None
    for pc in paper_cuts:
        section = pc.get("section", "")
        if act_labels:
            section = _canonicalize_section(section, act_labels)
        if section and section != cur:
            expected_dividers += 1
            cur = section

    offsets = [_frac_secs(g.get("offset", "0s")) for g in divider_gaps]
    offsets_monotonic = all(b > a for a, b in zip(offsets, offsets[1:]))
    titles_consistent = True
    for g in divider_gaps:
        g_start = _frac_secs(g.get("start", "0s"))
        g_dur = _frac_secs(g.get("duration", "0s"))
        t = g.find("title")
        t_off = _frac_secs(t.get("offset", "0s"))
        t_dur = _frac_secs(t.get("duration", "0s"))
        if abs(t_off - g_start) > 1e-9:
            titles_consistent = False
            failures.append(
                f"divider title offset {t.get('offset')} != enclosing gap "
                f"start {g.get('start')} (gap offset {g.get('offset')})"
            )
        if t_off + t_dur > g_start + g_dur + 1e-9:
            titles_consistent = False
            failures.append(
                f"divider title (offset {t.get('offset')}, duration "
                f"{t.get('duration')}) overruns its gap (start "
                f"{g.get('start')}, duration {g.get('duration')})"
            )
    if not offsets_monotonic:
        failures.append(
            f"act-divider gap offsets are not monotonically increasing: "
            f"{[g.get('offset') for g in divider_gaps]}"
        )
    if len(divider_gaps) != expected_dividers:
        failures.append(
            f"act-divider count mismatch: {len(divider_gaps)} title gaps in "
            f"XML vs {expected_dividers} expected from section changes"
        )

    act_dividers = {
        "declared_acts": len(act_labels),
        "expected_dividers": expected_dividers,
        "divider_titles_in_xml": len(divider_gaps),
        "offsets_monotonic": offsets_monotonic,
        "titles_consistent_with_gaps": titles_consistent,
        "ok": (offsets_monotonic and titles_consistent
               and len(divider_gaps) == expected_dividers),
    }

    # ── W3 carry-through ──────────────────────────────────────────────────
    if truncations:
        failures.append(
            f"{len(truncations)} truncation event(s): clips play less than "
            "the verbatim quote text (see 'truncations')"
        )
    if speaker_misses:
        failures.append(
            f"{len(speaker_misses)} speaker miss(es): quotes dropped (see "
            "'speaker_misses')"
        )
    if len(xml_clips) == 0:
        failures.append("output contains 0 spine clips")

    # ── project element hygiene (C1) ──────────────────────────────────────
    project_el = root.find(".//project")
    project_info = {
        "has_uid": project_el is not None and project_el.get("uid") is not None,
        "has_mod_date": (project_el is not None
                         and project_el.get("modDate") is not None),
    }
    if project_info["has_uid"] or project_info["has_mod_date"]:
        failures.append(
            "generated <project> carries uid/modDate — these must be "
            "omitted so FCP assigns fresh ones on import (C1)"
        )

    report = {
        "output": output_path,
        "overall_pass": not failures,
        "failures": failures,
        "totals": {
            "clips_in_xml": len(xml_clips),
            "clips_expected_from_build": len(report_clips),
            "spine_elements": len(list(spine)),
        },
        "per_speaker": per_speaker,
        "per_entry": per_entry,
        "truncations": truncations,
        "speaker_misses": speaker_misses,
        "act_dividers": act_dividers,
        "project": project_info,
    }
    return report, not failures


def print_verify_summary(report: dict):
    """Human-readable --verify summary on stdout."""
    status = "PASS" if report.get("overall_pass") else "FAIL"
    print(f"\n[verify] overall: {status}")
    totals = report.get("totals", {})
    print(f"[verify] spine clips: {totals.get('clips_in_xml')} in XML / "
          f"{totals.get('clips_expected_from_build')} expected from build")
    for speaker, b in sorted(report.get("per_speaker", {}).items()):
        print(f"[verify]   {speaker}: {b['clips_in_xml']} clips "
              f"({b['expected_entries']} entries / "
              f"{b['expected_segments']} segments expected, "
              f"{b['segments_matched']} matched), "
              f"clip_type={b['clip_type_expected']} "
              f"({'ok' if b['clip_type_ok'] else 'MISMATCH'})")
    ad = report.get("act_dividers", {})
    print(f"[verify] act dividers: {ad.get('divider_titles_in_xml')} in XML / "
          f"{ad.get('expected_dividers')} expected "
          f"(declared acts: {ad.get('declared_acts')}; "
          f"monotonic={ad.get('offsets_monotonic')}, "
          f"fit_gaps={ad.get('titles_consistent_with_gaps')})")
    n_trunc = len(report.get("truncations", []))
    n_miss = len(report.get("speaker_misses", []))
    print(f"[verify] truncations: {n_trunc}; speaker misses: {n_miss}")
    for f in report.get("failures", []):
        print(f"[verify] FAIL: {f}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the CLI."""
    p = argparse.ArgumentParser(
        prog="build_fcpxml.py",
        description=(
            "Generate an import-ready FCPXML file from a trimmed paper-cut "
            "JSON, a params markdown file, and source caption FCPXMLs."
        ),
    )
    p.add_argument("--quotes", required=True, help="Path to trimmed-quotes.json")
    p.add_argument("--params", required=True, help="Path to fcpxml-params.md")
    p.add_argument("--act-structure", required=True,
                   help="Path to act-structure.md")
    p.add_argument("--source-pool",
                   help=(
                       "Path to tagged-quotes-v[N].json (the v5 source pool). "
                       "Required when trimmed-quotes.json is v5 schema; "
                       "ignored for v4 legacy input."
                   ))
    p.add_argument("--xml-dir", required=True,
                   help="Directory containing source caption .fcpxml files")
    p.add_argument("--output", required=True, help="Output .fcpxml file path")
    p.add_argument("--project-name", required=True,
                   help="Project name used in the FCP project element")
    p.add_argument("--allow-partial", action="store_true",
                   help=(
                       "Exit 0 even when quotes were truncated (unmatched "
                       "sentences) or speakers were skipped. The warning "
                       "summary is still printed and the output file is "
                       "still written. Also downgrades --verify failures "
                       "to warnings."
                   ))
    p.add_argument("--verify", action="store_true",
                   help=(
                       "After generation, parse the emitted FCPXML and "
                       "write a JSON verification report next to the "
                       "output (<output_basename>.verify.json) plus a "
                       "human-readable summary to stdout. Exits "
                       f"{EXIT_VERIFY_FAIL} on verification failure unless "
                       "--allow-partial is set."
                   ))
    return p


def _require_exists(path: str, label: str):
    """Raise FileNotFoundError with a friendly message if path is missing."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{label} not found: {path}")


def main(argv=None) -> int:
    """Run the wrapper pipeline end-to-end. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    stage = "startup"
    try:
        stage = "input validation"
        _require_exists(args.quotes, "trimmed-quotes.json")
        _require_exists(args.params, "fcpxml-params.md")
        _require_exists(args.act_structure, "act-structure.md")
        xml_dir = Path(args.xml_dir)
        if not xml_dir.is_dir():
            raise FileNotFoundError(f"xml-dir not found or not a directory: {xml_dir}")

        stage = "parsing fcpxml-params.md"
        try:
            params = parse_params_md(args.params)
        except ValueError as ve:
            print(f"[build_fcpxml] params error: {ve}", file=sys.stderr)
            return EXIT_BAD_PARAMS

        stage = "loading trimmed-quotes.json"
        # Peek at the timeline file to decide whether the source pool is
        # required. v5 input needs the pool; v4 doesn't. Loading the pool
        # here (before load_quotes) means we surface a missing-pool error
        # against the source-pool path, not against the timeline path.
        source_pool = None
        if args.source_pool:
            _require_exists(args.source_pool, "tagged-quotes (source pool)")
            source_pool = load_source_pool(args.source_pool)

        try:
            timeline = load_quotes(args.quotes, source_pool=source_pool)
        except ValueError as ve:
            print(f"[build_fcpxml] timeline error: {ve}", file=sys.stderr)
            return EXIT_BAD_PARAMS

        quotes_raw = timeline["quotes"]
        if not quotes_raw:
            print(
                "[build_fcpxml] no spoken-quote entries to render "
                f"(schema_version={timeline['schema_version']}). "
                "Spine would be empty.",
                file=sys.stderr,
            )
            return EXIT_GENERIC

        if timeline["schema_version"] == 5:
            print(
                f"[build_fcpxml] v5 timeline: "
                f"{len(quotes_raw)} spoken-quote entries, "
                f"{len(timeline['non_spoken_entries'])} non-spoken entries "
                f"(round={timeline['metadata'].get('round')}, "
                f"project_slug={timeline['metadata'].get('project_slug')!r})",
                file=sys.stderr,
            )

        stage = "parsing act-structure.md"
        act_labels = parse_act_structure(args.act_structure)
        if act_labels:
            # C8: compare normalized forms (lowercase, dashes/underscores ->
            # spaces, punctuation stripped) so slug parts like 'act-1-addie'
            # match labels like 'Act 1 — Addie'. Same normalization as
            # generate_fcpxml._canonicalize_section.
            label_set = {normalize_label(lbl) for lbl in act_labels} - {""}
            unknown_parts = set()
            for q in quotes_raw:
                part = (q.get("part") or "").strip()
                part_norm = normalize_label(part)
                if part_norm and part_norm not in label_set:
                    # Also accept partial matches
                    if not any(part_norm in lbl or lbl in part_norm
                               for lbl in label_set):
                        unknown_parts.add(part)
            for part in unknown_parts:
                print(
                    f"Warning: quote part '{part}' does not match any act label "
                    f"in act-structure.md; using as-is for section divider.",
                    file=sys.stderr,
                )

        stage = "adapting quotes"
        paper_cuts = [
            adapt_quote(q, idx + 1) for idx, q in enumerate(quotes_raw)
        ]

        stage = "locating source caption files"
        # Locate one source FCPXML per configured speaker (multicam +
        # single_clip). Use clip_types as the authoritative speaker list so
        # we don't miss single_clip speakers that have no media_ref entry.
        # Sort for deterministic iteration so the same project always
        # produces the same merged-resources ID layout across runs.
        all_speakers = sorted(
            set(params["speaker_refs"].keys())
            | set(params["asset_refs"].keys())
            | set(params["clip_types"].keys())
        )
        source_fcpxmls = {}
        for speaker in all_speakers:
            src_path = find_speaker_fcpxml(speaker, xml_dir)
            source_fcpxmls[speaker] = parse_source_fcpxml(str(src_path), speaker)

        stage = "locating reference fcpxml"
        reference_path = xml_dir / params["reference_file"]
        if not reference_path.exists():
            raise FileNotFoundError(
                f"Reference FCPXML not found: {reference_path} "
                f"(from fcpxml-params.md 'Reference FCPXML')."
            )

        stage = "generating FCPXML"
        output_dir = Path(args.output).parent
        if output_dir and not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        try:
            build_report = generate_fcpxml(
                paper_cuts=paper_cuts,
                source_fcpxmls=source_fcpxmls,
                reference_path=str(reference_path),
                output_path=args.output,
                speaker_refs=params["speaker_refs"],
                speaker_angles=params["speaker_angles"],
                project_name=args.project_name,
                clip_types=params["clip_types"],
                asset_refs=params["asset_refs"],
                asset_names=params["asset_names"],
                # SKILL Phase 2.1.5 — canonical act labels drive
                # act-boundary title cards on every emission.
                act_labels=act_labels,
                # SKILL Phase 2.1.6 — library/event values from the
                # params md target the destination FCP library so multicam
                # UIDs are recognized as the existing library multicams
                # rather than re-imported as duplicates.
                library_location=params.get("library_location") or None,
                event_name=params.get("event_name") or None,
                event_uid=params.get("event_uid") or None,
                format_ref=params.get("format_ref") or None,
            )
        except Exception as ge:
            print(f"[build_fcpxml] generation failed: {ge}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return EXIT_GEN_ERROR

        stage = "verifying output"
        if not os.path.exists(args.output) or os.path.getsize(args.output) == 0:
            print(
                f"[build_fcpxml] output file missing or empty: {args.output}",
                file=sys.stderr,
            )
            return EXIT_GEN_ERROR

        n_clips = count_mc_clips(args.output)
        total_dur = extract_total_duration(args.output)
        build_report = build_report or {}
        truncations = build_report.get("truncations", [])
        speaker_misses = build_report.get("speaker_misses", [])
        zero_clips = (n_clips == 0)

        # ── W3: prominent integrity summary on stderr ────────────────────
        if truncations or speaker_misses or zero_clips:
            bar = "=" * 72
            print(f"\n{bar}", file=sys.stderr)
            print("[build_fcpxml] VERBATIM-INTEGRITY WARNINGS — the output "
                  "file WAS written,", file=sys.stderr)
            print("but it does not faithfully cover the input quotes:",
                  file=sys.stderr)
            if truncations:
                print(f"\n  TRUNCATED QUOTES ({len(truncations)}): the "
                      "emitted clips play LESS than the verbatim text",
                      file=sys.stderr)
                for t in truncations:
                    text = t.get("text", "")
                    preview = text if len(text) <= 80 else text[:80] + "..."
                    print(f"    - quote #{t.get('quote_num')} "
                          f"[{t.get('speaker')}] "
                          f"({t.get('kind')}"
                          f"{', ' + t['entry'] if t.get('entry') else ''}): "
                          f"\"{preview}\"", file=sys.stderr)
            if speaker_misses:
                print(f"\n  SKIPPED SPEAKERS ({len(speaker_misses)}): quotes "
                      "dropped entirely", file=sys.stderr)
                for m in speaker_misses:
                    print(f"    - quote #{m.get('quote_num')} "
                          f"[{m.get('speaker')}]: {m.get('reason')}",
                          file=sys.stderr)
            if zero_clips:
                print("\n  EMPTY SPINE: generated FCPXML contains 0 clip "
                      "elements. No quotes matched their source captions.",
                      file=sys.stderr)
            if args.allow_partial:
                print("\n  --allow-partial set: exiting 0 despite the above.",
                      file=sys.stderr)
            else:
                print("\n  Exiting non-zero (truncation -> exit "
                      f"{EXIT_NO_CAPTION}, speaker miss / empty spine -> "
                      f"exit {EXIT_SPEAKER_MISS}). Re-run with "
                      "--allow-partial to accept a partial build.",
                      file=sys.stderr)
            print(bar, file=sys.stderr)

        print(
            f"Generated FCPXML with {n_clips} clips; "
            f"total duration {total_dur}; output: {args.output}"
        )

        exit_code = EXIT_OK
        if truncations:
            exit_code = EXIT_NO_CAPTION
        elif speaker_misses or zero_clips:
            exit_code = EXIT_SPEAKER_MISS

        # ── W1: --verify ──────────────────────────────────────────────────
        if args.verify:
            stage = "running --verify"
            verify_report, verify_ok = verify_output(
                args.output, paper_cuts, params, act_labels, build_report
            )
            out_path = Path(args.output)
            report_path = out_path.parent / (out_path.stem + ".verify.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(verify_report, f, indent=2)
            print_verify_summary(verify_report)
            print(f"[verify] report written: {report_path}")
            if not verify_ok and exit_code == EXIT_OK:
                exit_code = EXIT_VERIFY_FAIL

        if exit_code != EXIT_OK and args.allow_partial:
            return EXIT_OK
        return exit_code

    except AmbiguousSpeakerFileError as ae:
        print(f"[build_fcpxml] ambiguous speaker file during {stage}: {ae}",
              file=sys.stderr)
        return EXIT_GENERIC
    except FileNotFoundError as fe:
        print(f"[build_fcpxml] missing input during {stage}: {fe}", file=sys.stderr)
        return EXIT_MISSING_INPUT
    except Exception as e:
        print(f"[build_fcpxml] unhandled error during {stage}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return EXIT_GENERIC


if __name__ == "__main__":
    sys.exit(main())
