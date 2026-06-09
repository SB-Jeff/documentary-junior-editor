#!/usr/bin/env python3
"""Pre-handoff QA gate for the quote viewer (kickoff brief P4).

Every historical blank-page failure was an input-contract violation. This is
the runnable regression gate that pins each one so it can't silently come back.
Run it before handing a viewer build off:

    python3 scripts/test_viewer_build.py

It exits non-zero (and prints what failed) on any regression, so it can sit in
a build/QA step. Checks:

  1. The known-good fixture builds, compiles JSX, and mounts (#root present).
  2. Missing act_labels                -> build FAILS loud (blank-page #1).
  3. String-form speakers              -> build FAILS loud (speaker-color crash).
  4. Empty orphan pool                 -> builds, and ships the explicit P5
                                          "no orphans" empty-state (not nothing).
  5. String source_quote_id            -> coerced to int and linked (Bug 6);
                                          strings used to link to nothing.
  6. validate_project_metadata         -> unit-checks the contract directly.

Fixtures live in scripts/test-fixtures/. The negative fixtures (one per
historical failure mode) are committed alongside the good baseline.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "test-fixtures"
BUILD = HERE / "build_quotes_viewer.py"

# Import the build script as a module so we can unit-test its pure helpers.
_spec = importlib.util.spec_from_file_location("build_quotes_viewer", BUILD)
bqv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bqv)


def _build(fixture: str, out: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILD), "--data", str(FIX / fixture), "--output", out],
        capture_output=True, text=True,
    )


# --- Checks -----------------------------------------------------------------

def check_good_fixture(tmp):
    out = str(Path(tmp) / "good.html")
    r = _build("sample_viewer_data.json", out)
    assert r.returncode == 0, f"good fixture build failed:\n{r.stderr[-400:]}"
    html = Path(out).read_text()
    assert 'id="root"' in html, "no #root mount node in output"
    assert "React.createElement" in html, "JSX was not compiled to JS"
    assert len(html) > 150_000, f"output suspiciously small ({len(html):,} bytes)"


def check_missing_act_labels(tmp):
    r = _build("negative_missing_act_labels.json", str(Path(tmp) / "x.html"))
    assert r.returncode != 0, "build should FAIL on empty act_labels, but succeeded"
    assert "act_labels" in r.stderr, \
        f"failure should name act_labels:\n{r.stderr[-400:]}"


def check_string_speakers(tmp):
    r = _build("negative_string_speakers.json", str(Path(tmp) / "x.html"))
    assert r.returncode != 0, "build should FAIL on string speakers, but succeeded"
    assert "speakers" in r.stderr, \
        f"failure should name speakers:\n{r.stderr[-400:]}"


def check_empty_orphans(tmp):
    out = str(Path(tmp) / "noorphans.html")
    r = _build("negative_empty_orphans.json", out)
    assert r.returncode == 0, f"empty-orphan build failed:\n{r.stderr[-400:]}"
    html = Path(out).read_text()
    assert "No orphans found in this pool" in html, \
        "P5 explicit empty-state marker missing from the build"


def check_string_source_quote_id(_tmp):
    raw = json.load(open(FIX / "negative_string_source_quote_id.json"))
    raw = {k: v for k, v in raw.items() if not k.startswith("_")}
    raw.update(slug="strid-test", ssd_root="/tmp", target_seconds=0,
               project_name="String-ID Test")

    by_num = {2: raw["source_quotes"][0]}
    assert bqv.lookup_source_quote(by_num, "2") is not None, \
        'lookup_source_quote(by_num, "2") returned None — string id did not coerce'

    db = bqv.assemble_data_block(raw)
    entries = db["ROUNDS"][0]["timeline"]
    assert len(entries) == 1, \
        f"expected 1 migrated entry (string id linked), got {len(entries)}"
    sid = entries[0]["source_quote_id"]
    assert isinstance(sid, int) and sid == 2, \
        f"source_quote_id not coerced to int 2: {sid!r}"


def check_validate_unit(_tmp):
    # Valid metadata passes.
    bqv.validate_project_metadata(
        {"act_labels": ["Act 1"], "speakers": [{"name": "X", "slug": "x"}]}, "unit")
    # Each violation raises BuildContractError.
    for bad in (
        {"act_labels": [], "speakers": [{"name": "X", "slug": "x"}]},
        {"act_labels": ["Act 1"], "speakers": ["X"]},
        {"act_labels": ["Act 1"], "speakers": [{"name": "X"}]},  # slug missing
    ):
        try:
            bqv.validate_project_metadata(bad, "unit")
        except bqv.BuildContractError:
            continue
        raise AssertionError(f"validate_project_metadata did not reject {bad!r}")


CHECKS = [
    ("good fixture builds + mounts", check_good_fixture),
    ("missing act_labels fails loud", check_missing_act_labels),
    ("string speakers fails loud", check_string_speakers),
    ("empty orphan pool ships empty-state", check_empty_orphans),
    ("string source_quote_id is coerced", check_string_source_quote_id),
    ("validate_project_metadata contract", check_validate_unit),
]


def main():
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in CHECKS:
            try:
                fn(tmp)
            except Exception as e:  # noqa: BLE001 — report any failure clearly
                failures.append((name, str(e)))
                print(f"  ✗ {name}\n      {e}")
            else:
                print(f"  ✓ {name}")

    print()
    if failures:
        print(f"FAILED — {len(failures)}/{len(CHECKS)} check(s) failed. "
              f"Do not hand off this build.")
        return 1
    print(f"OK — all {len(CHECKS)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
