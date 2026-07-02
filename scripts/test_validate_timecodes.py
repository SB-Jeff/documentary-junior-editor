#!/usr/bin/env python3
"""Regression gate for the timecode-sanity validator (validate_timecodes.py).

Pins the epicor-rf-fager failure mode (collapsed startTC==endTC runs that
shipped from the Transcript stage undetected to FCPXML export) plus the two
other degenerate classes the gate exists to catch. Run it before trusting the
gate:

    python3 scripts/test_validate_timecodes.py

Exits non-zero (and prints what failed) on any regression. Fixtures live in
scripts/test-fixtures/ alongside the viewer fixtures.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "test-fixtures"
MOD = HERE / "validate_timecodes.py"

_spec = importlib.util.spec_from_file_location("validate_timecodes", MOD)
vtc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vtc)


def _kinds(issues):
    return {i.kind for i in issues}


def _fails(issues):
    return [i for i in issues if i.severity == "FAIL"]


def _warns(issues):
    return [i for i in issues if i.severity == "WARN"]


# --- Checks -----------------------------------------------------------------

def check_clean_passes():
    issues, err = vtc.validate_file(str(FIX / "tc_clean.json"))
    assert err is None, f"clean fixture errored: {err}"
    assert not issues, f"clean fixture produced issues: {[str(i) for i in issues]}"


def check_collapsed_run_fails():
    """The epicor Doug case: a run of startTC==endTC must FAIL at quote AND
    segment level, with the escalated run finding present."""
    issues, err = vtc.validate_file(str(FIX / "tc_collapsed_run.json"))
    assert err is None, f"errored: {err}"
    kinds = _kinds(issues)
    assert "collapsed_quote_run" in kinds, "missing escalated quote-run FAIL"
    assert "collapsed_segment_run" in kinds, "missing escalated segment-run FAIL"
    assert _fails(issues), "collapsed run must produce FAILs"


def check_segment_outside_and_ordering_fails():
    issues, err = vtc.validate_file(str(FIX / "tc_segment_and_monotonic.json"))
    assert err is None, f"errored: {err}"
    kinds = _kinds(issues)
    assert "segment_outside_quote" in kinds, "missing segment-outside-quote FAIL"
    assert "nonmonotonic_segment" in kinds, "missing non-monotonic segment FAIL"
    assert "inverted_tc" in kinds, "missing inverted (endTC<startTC) FAIL"


def check_isolated_collapse_is_warn():
    """A single collapsed TC in an otherwise-healthy speaker flags (WARN),
    it does not fail the gate — matches 'flags/fails on runs'."""
    quotes = []
    for i in range(1, 11):
        collapsed = (i == 5)
        s = f"00:{i:02d}:00"
        e = s if collapsed else f"00:{i:02d}:04"
        quotes.append({
            "num": i, "speaker": "Solo", "startTC": s, "endTC": e,
            "segments": [{"idx": 0, "text": "t", "startTC": s, "endTC": e}],
        })
    issues = vtc.validate_quotes(quotes, "inline")
    assert not _fails(issues), f"isolated collapse should not FAIL: {[str(i) for i in _fails(issues)]}"
    assert any(i.kind == "collapsed_quote_tc" for i in _warns(issues)), \
        "isolated collapse should still WARN"


def check_promoted_orphan_ordering_is_warn():
    """A high-num quote with an earlier TC (promoted orphan) warns, not fails —
    quote numbering is not guaranteed chronological once editing begins."""
    quotes = [
        {"num": 1, "speaker": "A", "startTC": "00:05:00", "endTC": "00:05:04",
         "segments": [{"idx": 0, "text": "t", "startTC": "00:05:00", "endTC": "00:05:04"}]},
        {"num": 2, "speaker": "A", "startTC": "00:02:00", "endTC": "00:02:04",
         "segments": [{"idx": 0, "text": "t", "startTC": "00:02:00", "endTC": "00:02:04"}]},
    ]
    issues = vtc.validate_quotes(quotes, "inline")
    assert not _fails(issues), "promoted-orphan ordering should not FAIL"
    assert any(i.kind == "nonmonotonic_quote" for i in _warns(issues)), \
        "out-of-order quote should WARN"


def check_unparseable_and_missing():
    quotes = [{"num": 1, "speaker": "A", "startTC": "garbage", "endTC": "00:01:00",
               "segments": []}]
    issues = vtc.validate_quotes(quotes, "inline")
    assert any(i.kind == "unparseable_tc" for i in _fails(issues)), \
        "unparseable TC must FAIL"
    _, err = vtc.validate_file(str(FIX / "does_not_exist.json"))
    assert err is not None, "missing file should report an error"


def check_parser_matches_forms():
    assert vtc.tc_to_seconds("00:01:02") == 62
    assert vtc.tc_to_seconds("01:02") == 62
    assert abs(vtc.tc_to_seconds("00:00:01:12") - (1 + 12 * 1001.0 / 24000.0)) < 1e-6
    assert vtc.tc_to_seconds("") is None
    assert vtc.tc_to_seconds("nope") is None


CHECKS = [
    ("clean fixture passes", check_clean_passes),
    ("collapsed run FAILs (epicor Doug)", check_collapsed_run_fails),
    ("segment-outside / ordering / inverted FAIL", check_segment_outside_and_ordering_fails),
    ("isolated collapse is a WARN", check_isolated_collapse_is_warn),
    ("promoted-orphan ordering is a WARN", check_promoted_orphan_ordering_is_warn),
    ("unparseable / missing handled", check_unparseable_and_missing),
    ("TC parser matches all forms", check_parser_matches_forms),
]


def main():
    failures = []
    for name, fn in CHECKS:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — report any failure clearly
            failures.append((name, str(e)))
            print(f"  ✗ {name}\n      {e}")
        else:
            print(f"  ✓ {name}")

    print()
    if failures:
        print(f"FAILED — {len(failures)}/{len(CHECKS)} check(s) failed.")
        return 1
    print(f"OK — all {len(CHECKS)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
