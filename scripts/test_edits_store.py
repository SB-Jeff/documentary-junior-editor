#!/usr/bin/env python3
"""Regression tests for edits_store.py (the v5.15 edit/step model).

    python3 scripts/test_edits_store.py

Covers: legacy migration (rounds + checkpoints + named cuts + viewer-state),
idempotence, snapshot skip-if-unchanged, propose (step + agent-written
current), fork (new edit), and the list manifest shape the viewer polls.
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("edits_store", HERE / "edits_store.py")
es = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(es)


def _ent(n, part="Act 1"):
    return {"entry_id": str(n), "source_quote_id": n, "type": "spoken", "part": part,
            "membership": "tight", "_editCuts": [], "notes": "", "why": ""}


def _legacy_project(root: Path, slug="proj"):
    ev = root / "handoffs" / slug / "editing-versions"
    (ev / "checkpoints").mkdir(parents=True)
    def w(p, obj, t):
        p.write_text(json.dumps(obj)); os.utime(p, (t, t))
    t0 = time.time() - 1000
    w(ev / "v1.json", {"round": 1, "entries": [_ent(1)], "target_runtime_seconds": 300}, t0)
    w(ev / "checkpoints" / "001-jeff-act1-reduction.json", {"entries": [_ent(1), _ent(2)]}, t0 + 10)
    w(ev / "checkpoints" / "002-agent-act2-proposal.json", {"entries": [_ent(1), _ent(2), _ent(3)]}, t0 + 20)
    w(ev / "v2.json", {"round": 2, "entries": [_ent(1), _ent(2), _ent(3), _ent(4)]}, t0 + 30)
    w(ev / "tighter-cut.json", {"round": 2, "cut_name": "Tighter Cut", "entries": [_ent(2)]}, t0 + 40)
    (ev / "._v9.json").write_text("junk")  # AppleDouble sidecar must be ignored
    w(root / "handoffs" / slug / "viewer-state.json",
      {"kind": "viewer-live-state", "generated_at": "2026-09-01T00:00:00Z",
       "focus": {"view": "timeline"}, "pending_ops": [{"seq": 1}],
       "entries": [_ent(1), _ent(2), _ent(3), _ent(4), _ent(5)]}, t0 + 50)
    return slug


def check_migrate(tmp):
    root = Path(tmp); slug = _legacy_project(root)
    rep = es.migrate(root, slug)
    assert rep["created"], rep
    assert rep["main_steps"] == 4, rep
    assert rep["edits"] == ["tighter-cut"], rep
    steps = es.list_steps(root, slug, "main")
    assert [s["label"] for s in steps] == ["Round 1", "act1 reduction", "act2 proposal", "Round 2"], steps
    assert [s["who"] for s in steps] == ["pipeline", "jeff", "claude", "pipeline"], steps
    assert [s["seq"] for s in steps] == [1, 2, 3, 4]
    cur = es.read_current(root, slug, "main")
    assert cur["kind"] == "edit-current" and cur["edit"] == "main"
    assert len(cur["entries"]) == 5, "viewer-state.json (live work) must win as main's current"
    assert cur["focus"] == {"view": "timeline"}, "viewer fields preserved"
    assert cur["written_by"] == "viewer"
    alt = es.list_edits(root, slug)
    assert [e["slug"] for e in alt] == ["main", "tighter-cut"], alt
    assert alt[0]["is_main"] and not alt[1]["is_main"]
    assert alt[1]["forked_from"] == {"edit": "main", "step": None}
    assert alt[1]["current"]["entry_count"] == 1
    assert alt[1]["steps"][0]["label"] == "saved cut (migrated)"
    # idempotent
    rep2 = es.migrate(root, slug)
    assert not rep2["created"]
    assert len(es.list_steps(root, slug, "main")) == 4
    # legacy files untouched
    assert (root / "handoffs" / slug / "editing-versions" / "v2.json").exists()


def check_migrate_nothing(tmp):
    root = Path(tmp)
    (root / "handoffs" / "empty").mkdir(parents=True)
    rep = es.migrate(root, "empty")
    assert not rep["created"] and not es.list_edits(root, "empty")
    rep = es.migrate(root, "empty", fallback_rounds=[("Round 1", [_ent(1)], 120)])
    assert rep["created"] and rep["source"] == "fallback_rounds"
    assert es.read_current(root, "empty", "main")["target_runtime_seconds"] == 120


def check_snapshot(tmp):
    root = Path(tmp); slug = "s"
    es.create_edit(root, slug, "Main edit", [_ent(1)], is_main=True, who="claude",
                   first_label="first assembly")
    assert es.snapshot(root, slug, "main", "jeff", "Act 1 revision") is None, \
        "identical to the latest step → no duplicate step"
    es.write_current(root, slug, "main", [_ent(1), _ent(2)], written_by="viewer")
    p = es.snapshot(root, slug, "main", "jeff", "Act 1 revision", note="move to act 2")
    assert p and p.name == "002-jeff-act-1-revision.json", p
    j = json.loads(p.read_text())
    assert j["who"] == "jeff" and j["seq"] == 2 and j["entry_count"] == 2 and j["note"] == "move to act 2"
    forced = es.snapshot(root, slug, "main", "jeff", "again", force=True)
    assert forced.name.startswith("003-jeff-again")
    try:
        es.write_step(root, slug, "main", "nobody", "x", [])
    except ValueError:
        pass
    else:
        raise AssertionError("bad `who` accepted")


def check_propose_and_fork(tmp):
    root = Path(tmp); slug = "p"
    es.create_edit(root, slug, "Main edit", [_ent(1)], is_main=True, who="claude", first_label="first")
    es.write_current(root, slug, "main", [_ent(1)], written_by="viewer", focus={"view": "cuts"})
    step = es.propose(root, slug, "main", [_ent(1), _ent(9)], "Act 2 proposal", note="braided")
    assert step.name == "002-claude-act-2-proposal.json"
    cur = es.read_current(root, slug, "main")
    assert cur["written_by"] == "agent" and len(cur["entries"]) == 2
    assert cur["focus"] == {"view": "cuts"}, "viewer fields survive an agent write"
    assert cur["agent_step"] == step.stem
    # fork
    eslug = es.create_edit(root, slug, "Tighter cut", cur["entries"], from_edit="main", from_step=2)
    assert eslug == "tighter-cut"
    meta = es.read_edit_meta(root, slug, eslug)
    assert meta["forked_from"] == {"edit": "main", "step": 2} and not meta["is_main"]
    st = es.list_steps(root, slug, eslug)
    assert len(st) == 1 and st[0]["label"] == "forked from main step 2" and st[0]["who"] == "jeff"
    try:
        es.create_edit(root, slug, "Tighter cut", [], from_edit="main")
    except FileExistsError:
        pass
    else:
        raise AssertionError("duplicate edit slug accepted")
    lst = es.list_edits(root, slug)
    assert [e["slug"] for e in lst] == ["main", "tighter-cut"]
    assert lst[0]["current"]["written_by"] == "agent"
    assert lst[0]["steps"][-1]["path"].endswith("steps/002-claude-act-2-proposal.json")


def check_cli(tmp):
    import subprocess
    root = Path(tmp); slug = _legacy_project(root)
    def run(*a):
        return subprocess.run([sys.executable, str(HERE / "edits_store.py"), *a],
                              capture_output=True, text=True)
    r = run("migrate", "--root", str(root), "--slug", slug); assert r.returncode == 0, r.stderr
    r = run("snapshot", "--root", str(root), "--slug", slug, "--who", "jeff", "--label", "Act 1 revision")
    assert r.returncode == 0 and "step:" in r.stdout, r
    prop = root / "prop.json"; prop.write_text(json.dumps({"entries": [_ent(7)]}))
    r = run("propose", "--root", str(root), "--slug", slug, "--entries", str(prop), "--label", "Act 2 proposal")
    assert r.returncode == 0 and "written_by: agent" in r.stdout, r
    r = run("new", "--root", str(root), "--slug", slug, "--name", "Social 30s")
    assert r.returncode == 0 and "edit: social-30s" in r.stdout, r
    r = run("list", "--root", str(root), "--slug", slug); assert r.returncode == 0
    lst = json.loads(r.stdout)
    assert lst[0]["slug"] == "main" and {e["slug"] for e in lst} == {"main", "tighter-cut", "social-30s"}, lst
    assert len(lst[0]["steps"]) == 6, [s["label"] for s in lst[0]["steps"]]


def main():
    checks = [check_migrate, check_migrate_nothing, check_snapshot, check_propose_and_fork, check_cli]
    failed = 0
    for c in checks:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                c(tmp); print(f"  ok   {c.__name__}")
            except Exception as e:  # noqa: BLE001
                failed += 1; print(f"  FAIL {c.__name__}: {e}")
    print("edits_store tests:", "FAILED" if failed else "all passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
