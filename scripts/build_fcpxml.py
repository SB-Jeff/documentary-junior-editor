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

from generate_fcpxml import parse_source_fcpxml, generate_fcpxml  # noqa: E402


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_MISSING_INPUT = 2
EXIT_BAD_PARAMS = 3
EXIT_NO_CAPTION = 4
EXIT_GEN_ERROR = 5


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

    label_re = re.compile(
        r"^\s*#+\s*((?:Act|Part|Section)\s*[^#\n]*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    labels = [m.group(1).strip() for m in label_re.finditer(text)]
    return labels


# ---------------------------------------------------------------------------
# Source caption file lookup
# ---------------------------------------------------------------------------

def find_speaker_fcpxml(speaker: str, xml_dir: Path):
    """
    Locate a source caption .fcpxml for a given speaker. Tries exact match,
    case-insensitive match, then first/last-name substring match. Returns the
    Path to the matching file or raises FileNotFoundError with a diagnostic.
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

    # Substring match on first or last name
    parts = speaker.split()
    tokens = [t.lower() for t in parts if t]
    for p in fcpxmls:
        stem_lower = p.stem.lower()
        if any(t and t in stem_lower for t in tokens):
            return p

    candidates_tried.append(f"case-insensitive stem match in {xml_dir}")
    if tokens:
        candidates_tried.append(
            f"substring match on {tokens} in {xml_dir}"
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
    FCPXML via regex. Name preserved for backward compat with main()'s
    success-line print; the count is now total spine clips, not just
    multicam.
    """
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
            label_set = {lbl.lower() for lbl in act_labels}
            unknown_parts = set()
            for q in quotes_raw:
                part = (q.get("part") or "").strip()
                if part and part.lower() not in label_set:
                    # Also accept partial matches
                    if not any(part.lower() in lbl or lbl in part.lower()
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
            generate_fcpxml(
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
        if n_clips == 0:
            print(
                "[build_fcpxml] warning: generated FCPXML contains 0 mc-clip "
                "elements. No quotes matched their source captions.",
                file=sys.stderr,
            )
            # Not fatal — still report the file — but surface the condition.

        print(
            f"Generated FCPXML with {n_clips} clips; "
            f"total duration {total_dur}; output: {args.output}"
        )
        return EXIT_OK

    except FileNotFoundError as fe:
        print(f"[build_fcpxml] missing input during {stage}: {fe}", file=sys.stderr)
        return EXIT_MISSING_INPUT
    except Exception as e:
        print(f"[build_fcpxml] unhandled error during {stage}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return EXIT_GENERIC


if __name__ == "__main__":
    sys.exit(main())
