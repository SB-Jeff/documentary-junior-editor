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

# Canonical section names -> tolerant substrings matched case-insensitively
_PARAM_SECTIONS = {
    "speaker_refs": ["media ref ids", "media refs", "media ref id"],
    "speaker_angles": ["angle ids", "angle id", "angles"],
    "reference_file": ["reference fcpxml", "reference file", "sample narrative",
                       "reference"],
    "library_location": ["library location", "library"],
    "event_name": ["event name", "event"],
    "format_ref": ["format reference", "format ref", "format"],
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

    refs_body = _find_section(sections, _PARAM_SECTIONS["speaker_refs"])
    angles_body = _find_section(sections, _PARAM_SECTIONS["speaker_angles"])
    ref_body = _find_section(sections, _PARAM_SECTIONS["reference_file"])
    lib_body = _find_section(sections, _PARAM_SECTIONS["library_location"])
    evt_body = _find_section(sections, _PARAM_SECTIONS["event_name"])
    fmt_body = _find_section(sections, _PARAM_SECTIONS["format_ref"])

    speaker_refs = _parse_kv_list(refs_body) if refs_body is not None else {}
    speaker_angles = _parse_kv_list(angles_body) if angles_body is not None else {}

    if not speaker_refs:
        raise ValueError(
            "Missing 'Media Ref IDs' in fcpxml-params.md. Expected a section "
            "like '## Media Ref IDs' followed by '- <Speaker>: r<N>' list items."
        )
    if not speaker_angles:
        raise ValueError(
            "Missing 'Angle IDs' in fcpxml-params.md. Expected a section like "
            "'## Angle IDs' followed by '- <Speaker>: <angleID>' list items."
        )

    # Every speaker with a ref must have an angle
    missing_angles = [s for s in speaker_refs if s not in speaker_angles]
    if missing_angles:
        raise ValueError(
            f"Angle IDs missing for speaker(s): {', '.join(missing_angles)}. "
            "Every speaker in 'Media Ref IDs' must have a matching entry in "
            "'Angle IDs'."
        )

    reference_file = _parse_scalar(ref_body) if ref_body is not None else ""
    if not reference_file:
        raise ValueError(
            "Missing 'Reference FCPXML' in fcpxml-params.md. Expected a section "
            "like '## Reference FCPXML' followed by the filename."
        )
    # Use just the basename — the script joins with xml_dir
    reference_file = os.path.basename(reference_file)

    return {
        "speaker_refs": speaker_refs,
        "speaker_angles": speaker_angles,
        "reference_file": reference_file,
        "library_location": _parse_scalar(lib_body) if lib_body is not None else "",
        "event_name": _parse_scalar(evt_body) if evt_body is not None else "",
        "format_ref": _parse_scalar(fmt_body) if fmt_body is not None else "",
    }


# ---------------------------------------------------------------------------
# trimmed-quotes.json loader
# ---------------------------------------------------------------------------

def load_quotes(path: str):
    """
    Load trimmed-quotes.json, drop interstitials (with a warning), and return
    the ordered list of quote dicts. Accepts either a top-level list or
    {"quotes": [...]}.
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

    return quotes


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
        {"num", "speaker", "part", "sequence", "original", "trimmed", "split",
         "startTC", "endTC"}

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
        "notes": "",
    }


# ---------------------------------------------------------------------------
# Output verification
# ---------------------------------------------------------------------------

def count_mc_clips(output_path: str) -> int:
    """Count <mc-clip> elements in the generated FCPXML via regex."""
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        return len(re.findall(r"<mc-clip\b", content))
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
        quotes_raw = load_quotes(args.quotes)
        if not quotes_raw:
            print("[build_fcpxml] no quotes to render after filtering interstitials",
                  file=sys.stderr)
            return EXIT_GENERIC

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
        source_fcpxmls = {}
        for speaker in params["speaker_refs"].keys():
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
