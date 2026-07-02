#!/usr/bin/env python3
"""Deterministic timecode-sanity gate for tagged-quotes JSON.

Catches the collapsed / degenerate-timecode class that shipped undetected
through the epicor-rf-fager project: Doug Duvall's quotes had
`startTC == endTC` on 86 of 87 quotes and Bryce's on 14 of 46, originating
at the Transcript/Transcription stage. It surfaced only when the FCPXML
export verify failed five stages later (zero-length clip windows). This
script moves the check to the source so bad TCs fail loud where they are
introduced, not at export.

Per speaker, it flags/fails on:

  (a) runs of `startTC == endTC` at the quote AND segment level
      (a zero-duration quote/segment is unusable in FCPXML),
  (b) non-monotonic `startTC` within a speaker (a later quote/segment
      that starts strictly before an earlier one — the transcript is
      chronological, so this means a corrupt TC),
  (c) segment TCs that fall outside their parent quote's [startTC, endTC]
      window.

It also fails on unparseable TCs and inverted (`endTC < startTC`) TCs,
which are the same degenerate class.

Usage:

    python3 scripts/validate_timecodes.py <tagged-quotes.json> [more.json ...]
    python3 scripts/validate_timecodes.py 'handoffs/<slug>/*tagged-quotes-v*.json'

Options:
    --warn-only   Never exit non-zero (report only). For the Edit Agent's
                  session-start precondition: surface the warning, let Jeff
                  decide.
    --strict      Promote every WARN (isolated collapsed TC) to a FAIL.
    --json        Emit a machine-readable JSON report to stdout instead of
                  the human summary.
    --quiet       Suppress the per-file OK lines; print only problems + summary.
    --run-threshold N       Consecutive collapsed TCs that constitute a
                            failing "run" (default 3).
    --collapse-fraction F   Fraction of a speaker's quotes/segments collapsed
                            that fails regardless of run length (default 0.25).

Exit codes: 0 = clean (or --warn-only), 2 = validation FAIL, 1 = could not run.

Homes (see the skill docs):
  - SKILL-orchestrator.md  Phase 3, step 5 — fail loud before handoff.
  - SKILL-transcript.md    Completeness Check — self-check before emit.
  - SKILL-edit.md          Phase 1 input precondition — warn at session start.
"""

import argparse
import glob
import json
import sys
from pathlib import Path

# Tolerance (in seconds) for the segment-inside-quote-window check, to absorb
# the small rounding slop that exists between a quote's TC and its own
# segments' TCs (both come from the same transcript, but may round differently).
WINDOW_TOLERANCE_SECS = 1.0

# A startTC/endTC pair whose seconds differ by less than this is treated as
# "collapsed" (zero duration). Real quotes/segments always span more than a
# few frames; a sub-100ms span is the degenerate signature.
COLLAPSE_EPSILON_SECS = 0.10


def tc_to_seconds(tc_str):
    """Parse a timecode string into float seconds, or None if unparseable.

    Mirrors `_tc_string_to_seconds` in generate_fcpxml.py so this gate and the
    downstream FCPXML matcher agree on exactly what "parseable" means. Tolerant
    of:
        "HH:MM:SS"      — 3-part (most common in tagged-quotes JSON)
        "HH:MM:SS:FF"   — 4-part FCP timecode (frames at 23.98 fps)
        "HH:MM:SS.fff"  — decimal seconds
        "MM:SS" / "SS"  — short forms
    """
    if not tc_str:
        return None
    s = str(tc_str).strip()
    if not s:
        return None
    decimal = 0.0
    if "." in s:
        last_colon = s.rfind(":")
        last_dot = s.rfind(".")
        if last_dot > last_colon:
            try:
                decimal = float("0." + s[last_dot + 1:])
                s = s[:last_dot]
            except ValueError:
                pass
    # Drop-frame separator ';' is equivalent to ':' for parsing purposes.
    parts = s.replace(";", ":").split(":")
    try:
        ints = [int(p) for p in parts]
    except ValueError:
        return None
    if len(ints) == 4:
        h, m, sec, frames = ints
        return h * 3600 + m * 60 + sec + frames * (1001.0 / 24000.0)
    elif len(ints) == 3:
        h, m, sec = ints
        return h * 3600 + m * 60 + sec + decimal
    elif len(ints) == 2:
        m, sec = ints
        return m * 60 + sec + decimal
    elif len(ints) == 1:
        return ints[0] + decimal
    return None


class Issue:
    """One validation finding. severity is 'FAIL' or 'WARN'."""

    def __init__(self, severity, kind, speaker, where, message):
        self.severity = severity
        self.kind = kind
        self.speaker = speaker
        self.where = where
        self.message = message

    def as_dict(self):
        return {
            "severity": self.severity,
            "kind": self.kind,
            "speaker": self.speaker,
            "where": self.where,
            "message": self.message,
        }

    def __str__(self):
        return f"  [{self.severity}] {self.speaker} · {self.where}: {self.message}"


def _extract_quotes(data):
    """Return the list of quote objects from a loaded tagged-quotes payload.

    Accepts the array form (Transcript per-speaker + Synthesis combined output)
    and the viewer-data object form ({"SOURCE_QUOTES": [...]}) so the same gate
    can spot-check either.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("SOURCE_QUOTES", "quotes", "tagged_quotes"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(
        "unrecognized tagged-quotes shape: expected a top-level array of "
        "quotes or an object with a SOURCE_QUOTES/quotes array"
    )


def _speaker_of(quote):
    return (
        quote.get("speaker")
        or quote.get("speakerSlug")
        or "(unknown speaker)"
    )


def _quote_label(quote):
    num = quote.get("num", quote.get("originalNum", "?"))
    return f"quote #{num}"


def _sort_key(quote, file_order_idx):
    """Source order within a speaker: originalNum (per-speaker numbering)
    falls back to num, then to file order. Non-int values sort last but keep
    file order among themselves."""
    for field in ("originalNum", "num"):
        v = quote.get(field)
        if isinstance(v, int):
            return (0, v, file_order_idx)
    return (1, 0, file_order_idx)


def validate_quotes(quotes, source_label, run_threshold=3,
                    collapse_fraction=0.25):
    """Validate a list of quote objects. Returns a list[Issue].

    Groups by speaker, then applies the three per-speaker checks plus the
    unparseable / inverted TC checks. Purely deterministic — no I/O.
    """
    issues = []

    # Group quotes by speaker, preserving file order for stable tie-breaking.
    by_speaker = {}
    for i, q in enumerate(quotes):
        by_speaker.setdefault(_speaker_of(q), []).append((i, q))

    for speaker, indexed in by_speaker.items():
        ordered = sorted(indexed, key=lambda pair: _sort_key(pair[1], pair[0]))
        quote_objs = [q for _, q in ordered]

        # --- Quote-level pass ------------------------------------------------
        collapsed_flags = []       # bool per quote (quote-level TC collapsed)
        quote_starts = []          # parsed startTC seconds (or None) per quote

        for q in quote_objs:
            label = _quote_label(q)
            s_raw, e_raw = q.get("startTC"), q.get("endTC")
            s, e = tc_to_seconds(s_raw), tc_to_seconds(e_raw)
            quote_starts.append(s)

            # unparseable
            if s is None or e is None:
                bad = []
                if s is None:
                    bad.append(f"startTC={s_raw!r}")
                if e is None:
                    bad.append(f"endTC={e_raw!r}")
                issues.append(Issue(
                    "FAIL", "unparseable_tc", speaker, label,
                    f"unparseable timecode ({', '.join(bad)})"))
                collapsed_flags.append(False)
                continue

            # collapsed (zero-duration) quote TC
            if abs(e - s) < COLLAPSE_EPSILON_SECS:
                collapsed_flags.append(True)
            else:
                collapsed_flags.append(False)
                # inverted (endTC strictly before startTC)
                if e < s - COLLAPSE_EPSILON_SECS:
                    issues.append(Issue(
                        "FAIL", "inverted_tc", speaker, label,
                        f"endTC ({e_raw}) is before startTC ({s_raw})"))

        issues += _collapse_findings(
            speaker, "quote", collapsed_flags,
            [_quote_label(q) for q in quote_objs],
            run_threshold, collapse_fraction)

        # non-monotonic startTC across quotes (skip Nones already reported)
        prev = None
        prev_label = None
        for q, s in zip(quote_objs, quote_starts):
            if s is None:
                continue
            label = _quote_label(q)
            if prev is not None and s < prev - COLLAPSE_EPSILON_SECS:
                # WARN, not FAIL: a legitimately promoted orphan gets a high
                # `num` but keeps its original (earlier) TC, so quote order by
                # number is not guaranteed chronological once editing begins.
                # A garbage-TC track still surfaces here (and via collapse /
                # unparseable FAILs). Use --strict at the Transcript source
                # stage, where numbering IS pure transcript order.
                issues.append(Issue(
                    "WARN", "nonmonotonic_quote", speaker, label,
                    f"startTC ({q.get('startTC')}) is before the previous "
                    f"quote's startTC ({prev_label}) — expected if this is a "
                    f"promoted orphan; a corrupt TC otherwise"))
            prev, prev_label = s, q.get("startTC")

        # --- Segment-level pass ---------------------------------------------
        seg_collapsed_flags = []
        seg_labels = []
        for q in quote_objs:
            qs = tc_to_seconds(q.get("startTC"))
            qe = tc_to_seconds(q.get("endTC"))
            segs = q.get("segments") or []
            prev_seg = None
            prev_seg_label = None
            for seg in segs:
                idx = seg.get("idx", "?")
                seg_label = f"{_quote_label(q)} seg[{idx}]"
                ss_raw, se_raw = seg.get("startTC"), seg.get("endTC")
                ss, se = tc_to_seconds(ss_raw), tc_to_seconds(se_raw)

                if ss is None or se is None:
                    bad = []
                    if ss is None:
                        bad.append(f"startTC={ss_raw!r}")
                    if se is None:
                        bad.append(f"endTC={se_raw!r}")
                    issues.append(Issue(
                        "FAIL", "unparseable_tc", speaker, seg_label,
                        f"unparseable segment timecode ({', '.join(bad)})"))
                    seg_collapsed_flags.append(False)
                    seg_labels.append(seg_label)
                    continue

                # collapsed segment
                seg_collapsed_flags.append(abs(se - ss) < COLLAPSE_EPSILON_SECS)
                seg_labels.append(seg_label)

                # inverted segment
                if se < ss - COLLAPSE_EPSILON_SECS:
                    issues.append(Issue(
                        "FAIL", "inverted_tc", speaker, seg_label,
                        f"segment endTC ({se_raw}) before startTC ({ss_raw})"))

                # (c) segment outside its quote's window
                if qs is not None and ss < qs - WINDOW_TOLERANCE_SECS:
                    issues.append(Issue(
                        "FAIL", "segment_outside_quote", speaker, seg_label,
                        f"segment startTC ({ss_raw}) is before its quote's "
                        f"startTC ({q.get('startTC')})"))
                if qe is not None and se > qe + WINDOW_TOLERANCE_SECS:
                    issues.append(Issue(
                        "FAIL", "segment_outside_quote", speaker, seg_label,
                        f"segment endTC ({se_raw}) is after its quote's "
                        f"endTC ({q.get('endTC')})"))

                # non-monotonic segment startTC within the quote
                if prev_seg is not None and ss < prev_seg - COLLAPSE_EPSILON_SECS:
                    issues.append(Issue(
                        "FAIL", "nonmonotonic_segment", speaker, seg_label,
                        f"segment startTC ({ss_raw}) is before the previous "
                        f"segment's startTC ({prev_seg_label})"))
                prev_seg, prev_seg_label = ss, ss_raw

        issues += _collapse_findings(
            speaker, "segment", seg_collapsed_flags, seg_labels,
            run_threshold, collapse_fraction)

    return issues


def _collapse_findings(speaker, level, flags, labels, run_threshold,
                       collapse_fraction):
    """Turn a list of per-item 'collapsed' booleans into Issues.

    An isolated collapsed TC is a WARN. It escalates to FAIL when either a
    maximal consecutive run reaches `run_threshold`, or the collapsed fraction
    for this speaker+level reaches `collapse_fraction`. This is what makes the
    epicor case (Doug 86/87, Bryce 14/46) fail while a lone edge case only warns.
    """
    out = []
    total = len(flags)
    n_collapsed = sum(1 for f in flags if f)
    if n_collapsed == 0:
        return out

    # Longest consecutive run.
    longest = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        longest = max(longest, cur)

    fraction = n_collapsed / total if total else 0.0
    is_run = longest >= run_threshold
    is_fraction = fraction >= collapse_fraction
    severity = "FAIL" if (is_run or is_fraction) else "WARN"

    # Per-item findings (so the operator sees exactly which ones).
    for f, label in zip(flags, labels):
        if f:
            out.append(Issue(
                severity, f"collapsed_{level}_tc", speaker, label,
                f"{level} startTC == endTC (zero-duration)"))

    # Summary finding when it escalated to a run/systemic failure.
    if severity == "FAIL":
        reason = []
        if is_run:
            reason.append(f"run of {longest} consecutive")
        if is_fraction:
            reason.append(f"{n_collapsed}/{total} = {fraction:.0%}")
        out.append(Issue(
            "FAIL", f"collapsed_{level}_run", speaker, f"{level} level",
            f"collapsed {level} timecodes ({'; '.join(reason)}) — this is the "
            f"source-stage TC bug; re-run the Transcript/Transcription stage "
            f"for {speaker}"))
    return out


def validate_file(path, run_threshold=3, collapse_fraction=0.25):
    """Load and validate one file. Returns (issues, error_message_or_None)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return [], f"file not found: {path}"
    except json.JSONDecodeError as exc:
        return [], f"invalid JSON: {exc}"
    try:
        quotes = _extract_quotes(data)
    except ValueError as exc:
        return [], str(exc)
    if not quotes:
        return [], "no quotes found (empty array)"
    return validate_quotes(quotes, str(path), run_threshold,
                           collapse_fraction), None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Deterministic timecode-sanity gate for tagged-quotes JSON.")
    parser.add_argument("paths", nargs="+",
                        help="tagged-quotes JSON file(s) or glob(s)")
    parser.add_argument("--warn-only", action="store_true",
                        help="report only; never exit non-zero")
    parser.add_argument("--strict", action="store_true",
                        help="promote isolated collapsed-TC WARNs to FAIL")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit a JSON report instead of the human summary")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress per-file OK lines")
    parser.add_argument("--run-threshold", type=int, default=3,
                        help="consecutive collapsed TCs that fail (default 3)")
    parser.add_argument("--collapse-fraction", type=float, default=0.25,
                        help="collapsed fraction that fails (default 0.25)")
    args = parser.parse_args(argv)

    # Expand globs (and dedupe while preserving order).
    files = []
    seen = set()
    for p in args.paths:
        matches = sorted(glob.glob(p)) if any(c in p for c in "*?[") else [p]
        if not matches:
            matches = [p]  # let validate_file report the not-found
        for m in matches:
            if m not in seen:
                seen.add(m)
                files.append(m)

    report = {"files": [], "summary": {}}
    total_fail = total_warn = 0
    run_errors = []

    for path in files:
        issues, err = validate_file(path, args.run_threshold,
                                    args.collapse_fraction)
        if err:
            run_errors.append((path, err))
            report["files"].append({"file": path, "error": err})
            continue
        if args.strict:
            for iss in issues:
                if iss.severity == "WARN":
                    iss.severity = "FAIL"
        fails = [i for i in issues if i.severity == "FAIL"]
        warns = [i for i in issues if i.severity == "WARN"]
        total_fail += len(fails)
        total_warn += len(warns)
        report["files"].append({
            "file": path,
            "fail": len(fails),
            "warn": len(warns),
            "issues": [i.as_dict() for i in issues],
        })

        if not args.as_json:
            if issues:
                print(f"{path}: {len(fails)} FAIL, {len(warns)} WARN")
                for iss in issues:
                    print(iss)
            elif not args.quiet:
                print(f"{path}: OK — timecodes sane")

    report["summary"] = {
        "files_checked": len(files),
        "run_errors": len(run_errors),
        "total_fail": total_fail,
        "total_warn": total_warn,
    }

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        if run_errors:
            print("\nCould not check:")
            for path, err in run_errors:
                print(f"  [ERROR] {path}: {err}")
        print(f"\nSummary: {len(files)} file(s), {total_fail} FAIL, "
              f"{total_warn} WARN, {len(run_errors)} unreadable")

    # A run error (bad/missing file) is a hard failure too — the gate could not
    # confirm sanity. --warn-only suppresses exit codes entirely.
    if args.warn_only:
        return 0
    if run_errors:
        return 1
    return 2 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
