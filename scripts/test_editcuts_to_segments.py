#!/usr/bin/env python3
"""Regression tests for the _editCuts → segments[] converter.

Run:  python3 scripts/test_editcuts_to_segments.py

Exits non-zero (printing what failed) on any regression. The load-bearing test
is the ROUND TRIP: build_quotes_viewer.migrate_entry_trims turns segments[] into
_editCuts; editcuts_to_segments must turn them back into segments[] that keep the
same verbatim text. The two are inverses, so a drift in either side is caught
here. The other tests pin the mid-segment approximation, idempotency, the
fully-cut drop, and end-to-end consumption by build_fcpxml.
"""

import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, str(HERE / f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


conv = _load("editcuts_to_segments")
bqv = _load("build_quotes_viewer")
bfx = _load("build_fcpxml")


# --- fixtures ---------------------------------------------------------------

def source_quote():
    """A four-segment source quote, the shape tagged-quotes-v[N].json carries."""
    return {
        "num": 23,
        "speaker": "Dana Reyes",
        "part": "Philosophy",
        "startTC": "00:01:10",
        "endTC": "00:01:40",
        "segments": [
            {"idx": 0, "text": "So the first thing we did was rethink the whole process.",
             "startTC": "00:01:10", "endTC": "00:01:16"},
            {"idx": 1, "text": "And honestly it was terrifying at first.",
             "startTC": "00:01:16", "endTC": "00:01:21"},
            {"idx": 2, "text": "But it paid off within a quarter.",
             "startTC": "00:01:21", "endTC": "00:01:27"},
            {"idx": 3, "text": "That changed everything for the whole team.",
             "startTC": "00:01:27", "endTC": "00:01:40"},
        ],
    }


def _kept_text_from_refs(refs, source):
    """Apply segment refs the way build_fcpxml does and join the kept text."""
    by_idx = {s["idx"]: s for s in source["segments"]}
    out = []
    for r in refs:
        seg = by_idx[r["source_segment_idx"]]
        out.append(bfx._apply_word_trims(
            seg["text"],
            int(r.get("head_trim_words", 0) or 0),
            int(r.get("tail_trim_words", 0) or 0),
        ))
    return " ".join(t for t in out if t)


# --- tests ------------------------------------------------------------------

def test_round_trip_head_tail_only():
    """segments[] --migrate--> _editCuts --convert--> segments[] preserves text.

    Uses only head/tail trims + a fully-dropped middle segment (idx 1), the
    representable case, so the round trip must be EXACT (no fidelity notes).
    """
    src = source_quote()
    by_num = {23: src}
    old_entry = {
        "entry_id": "e_023",
        "source_quote_id": 23,
        "speaker": "Dana Reyes",
        "part": "Philosophy",
        "segments": [
            {"source_segment_idx": 0, "head_trim_words": 3},   # drop "So the first"
            {"source_segment_idx": 2},                          # whole
            {"source_segment_idx": 3, "tail_trim_words": 1},    # drop "team."
        ],
        "notes": "",
    }
    expected_text = _kept_text_from_refs(
        [{"source_segment_idx": 0, "head_trim_words": 3},
         {"source_segment_idx": 2},
         {"source_segment_idx": 3, "tail_trim_words": 1}], src)

    migrated = bqv.migrate_entry_trims(old_entry, by_num)
    assert "_editCuts" in migrated, "migrate did not produce _editCuts"

    refs, notes = conv.editcuts_to_segments(migrated, src)
    assert notes == [], f"unexpected fidelity notes on a head/tail-only cut: {notes}"
    got_text = _kept_text_from_refs(refs, src)
    assert got_text == expected_text, (
        f"round trip changed kept text:\n  expected: {expected_text!r}\n"
        f"  got:      {got_text!r}"
    )
    # idx 1 was never selected → must be absent from the reconstructed segments.
    assert 1 not in {r["source_segment_idx"] for r in refs}, \
        "dropped middle segment reappeared"


def test_mid_segment_cut_is_approximated_and_flagged():
    """An interior word cut can't be head/tail-trimmed → widest span + a note."""
    src = source_quote()
    # Segment 0: "So the first thing we did was rethink the whole process."
    #  words:     0  1   2     3    4   5   6     7      8    9     10
    # Cut ONLY the interior word "did" (index 5). full_text starts at char 0 for
    # segment 0, so locate "did" in the full text and cut exactly that span.
    full_text, spans = conv._build_full_text_and_offsets(src["segments"])
    i = full_text.index(" did ") + 1
    entry = {
        "entry_id": "23",
        "source_quote_id": 23,
        "_editCuts": [[i, i + len("did")]],
    }
    refs, notes = conv.editcuts_to_segments(entry, src)
    assert len(notes) == 1, f"expected exactly one fidelity note, got {notes}"
    assert "did" in notes[0], f"note should name the retained word: {notes[0]}"
    # Widest contiguous span = whole segment 0 (head=tail=0): the interior cut
    # word is RETAINED, so the kept text still contains "did" (plays wider).
    seg0_ref = [r for r in refs if r["source_segment_idx"] == 0][0]
    assert seg0_ref.get("head_trim_words", 0) == 0
    assert seg0_ref.get("tail_trim_words", 0) == 0
    assert "did" in _kept_text_from_refs([seg0_ref], src)


def test_head_and_tail_of_same_segment_no_note():
    """Cutting leading AND trailing words (but nothing interior) stays exact."""
    src = source_quote()
    full_text, _ = conv._build_full_text_and_offsets(src["segments"])
    # Segment 3: "That changed everything for the whole team."
    seg3 = "That changed everything for the whole team."
    base = full_text.index(seg3)
    # cut "That changed " (head) and " team." (tail), keep the middle contiguous.
    head_cut = [base, base + len("That changed ")]
    tail_start = base + seg3.index(" whole team.")
    tail_cut = [tail_start, base + len(seg3)]
    entry = {"entry_id": "23", "source_quote_id": 23, "_editCuts": [head_cut, tail_cut]}
    refs, notes = conv.editcuts_to_segments(entry, src)
    assert notes == [], f"pure head+tail cut should not flag: {notes}"
    seg3_ref = [r for r in refs if r["source_segment_idx"] == 3][0]
    assert seg3_ref.get("head_trim_words") == 2, seg3_ref
    assert seg3_ref.get("tail_trim_words") == 2, seg3_ref
    assert _kept_text_from_refs([seg3_ref], src) == "everything for the"


def test_idempotent_passthrough():
    """An entry that already has segments[] is passed through untouched."""
    src = source_quote()
    pool = {23: src, "23": src}
    already = {
        "entry_id": "23", "source_quote_id": 23,
        "segments": [{"source_segment_idx": 0, "head_trim_words": 3}],
    }
    payload = {"schema_version": 5, "entries": [already]}
    out, report = conv.convert_payload(payload, pool)
    assert report["entries_passthrough"] == 1
    assert report["entries_converted"] == 0
    assert out["entries"][0]["segments"] == already["segments"]


def test_fully_cut_entry_is_dropped():
    """If _editCuts remove every word, the entry is dropped (loudly), not built."""
    src = source_quote()
    pool = {23: src, "23": src}
    full_text, _ = conv._build_full_text_and_offsets(src["segments"])
    entry = {"entry_id": "23", "source_quote_id": 23,
             "_editCuts": [[0, len(full_text)]]}
    payload = {"schema_version": 5, "entries": [entry]}
    out, report = conv.convert_payload(payload, pool)
    assert report["entries_dropped"] == 1, report
    assert out["entries"] == [], "fully-cut entry should not survive conversion"


def test_non_spoken_entry_passthrough():
    """Title cards / interstitials (no source_quote_id) pass through untouched."""
    src = source_quote()
    pool = {23: src, "23": src}
    card = {"entry_id": "T1", "type": "title_card", "text": "Act One"}
    payload = {"schema_version": 5, "entries": [card]}
    out, report = conv.convert_payload(payload, pool)
    assert out["entries"][0] == card
    assert report["entries_spoken"] == 0


def test_end_to_end_build_fcpxml_consumes_converted_output():
    """The converted payload loads through build_fcpxml._load_v5 without the
    old 'produced zero kept segments' crash the raw export triggered."""
    src = source_quote()
    pool = {23: src, "23": src}
    raw = {
        "schema_version": 5, "round": 1, "project_slug": "demo",
        "entries": [{
            "entry_id": "23", "source_quote_id": 23, "type": "spoken",
            "membership": "tight",
            # keep segments 0 (head-trim) + 2, drop 1 and 3
            "_editCuts": None,  # filled below
        }],
    }
    # Build _editCuts from a real trim so the fixture is realistic.
    old = {"entry_id": "e_023", "source_quote_id": 23,
           "segments": [{"source_segment_idx": 0, "head_trim_words": 3},
                        {"source_segment_idx": 2}]}
    raw["entries"][0]["_editCuts"] = bqv.migrate_entry_trims(old, {23: src})["_editCuts"]

    out, _ = conv.convert_payload(raw, pool)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "converted.json"
        p.write_text(json.dumps(out), encoding="utf-8")
        loaded = bfx.load_quotes(str(p), source_pool=pool)
    assert loaded["schema_version"] == 5
    # 2 kept segments → 2 v4-shaped clip dicts.
    assert len(loaded["quotes"]) == 2, loaded["quotes"]
    assert {q["_v5_segment_idx"] for q in loaded["quotes"]} == {0, 2}


def test_raw_export_gives_clear_error_from_build_fcpxml():
    """A raw _editCuts-only export (no segments[]) must fail with an actionable
    message pointing at the converter — not the old cryptic zero-segments error."""
    src = source_quote()
    pool = {23: src, "23": src}
    raw = {"schema_version": 5, "entries": [{
        "entry_id": "23", "source_quote_id": 23, "type": "spoken",
        "_editCuts": [[0, 5]],
    }]}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "raw.json"
        p.write_text(json.dumps(raw), encoding="utf-8")
        try:
            bfx.load_quotes(str(p), source_pool=pool)
        except ValueError as e:
            assert "editcuts_to_segments" in str(e), \
                f"error should name the converter, got: {e}"
            return
    raise AssertionError("expected a ValueError for a raw _editCuts export")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except Exception as e:  # noqa: BLE001 - test harness surfaces all
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
