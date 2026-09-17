#!/usr/bin/env python3
"""edits_store.py — the quote viewer's on-disk edit/step model (v5.15).

The versioning model (agreed with Jeff, 2026-09-17; mockup
scripts/mockups/versioning-redesign-mockup-2026-09-17.html):

  * ONE main edit that is always saved. The viewer autosaves its working state
    to ``current.json``; the agent reads that same file each turn.
  * STEPS are the annotated history of an edit — read-only snapshots written by
    the agent as the work moves act to act ("Claude: Act 1 proposal",
    "Jeff: Act 1 revision"). Jeff's step closes automatically when he hands
    off ("let's move to Act 2"); the agent's proposal lands as the next step.
    Steps are append-only: never rewritten, never deleted.
  * "Save as" forks the current state into a named ALTERNATIVE edit with its
    own step history. The agent assists on whichever edit is open.

Layout (all under the project's handoffs folder)::

    handoffs/<slug>/edits/
      <edit>/
        edit.json        name, created_at, forked_from, is_main
        current.json     the always-saved working state (viewer + agent)
        steps/
          001-claude-first-assembly.json
          002-jeff-act-1-revision.json
          ...

This replaces ``editing-versions/`` (numbered rounds + named cuts +
``checkpoints/``) and ``viewer-state.json``. ``migrate()`` folds a legacy
layout into edits/ once, leaving the old files in place.

CLI (what SKILL-edit tells the agent to run)::

    python3 scripts/edits_store.py list     --root R --slug S
    python3 scripts/edits_store.py migrate  --root R --slug S
    python3 scripts/edits_store.py snapshot --root R --slug S [--edit main] --who jeff --label "Act 1 revision"
    python3 scripts/edits_store.py propose  --root R --slug S [--edit main] --entries proposal.json --label "Act 2 proposal" [--note "..."]
    python3 scripts/edits_store.py new      --root R --slug S --name "Tighter cut" [--from main]

``snapshot`` writes the open edit's current entries as the next step (skipped
when identical to the latest step, unless --force). ``propose`` writes a step
AND replaces current.json's entries (written_by: "agent") — the viewer polls
and adopts it. ``new`` forks an alternative edit from another edit's current
state.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MAIN = "main"
WHO_VALUES = ("jeff", "claude", "pipeline")


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def slugify(name: str) -> str:
    s = re.sub(r"['\"]", "", (name or "").strip().lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "edit"


def not_junk(paths):
    """Drop macOS AppleDouble sidecars (._foo.json) on exFAT/SMB volumes."""
    return [p for p in paths if not p.name.startswith("._")]


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def edits_dir(root: Path, slug: str) -> Path:
    return Path(root) / "handoffs" / slug / "edits"


def edit_dir(root: Path, slug: str, edit: str) -> Path:
    return edits_dir(root, slug) / edit


def _entries_equal(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ----------------------------------------------------------------------------
# reading
# ----------------------------------------------------------------------------

def read_edit_meta(root: Path, slug: str, edit: str):
    return _read_json(edit_dir(root, slug, edit) / "edit.json")


def read_current(root: Path, slug: str, edit: str):
    return _read_json(edit_dir(root, slug, edit) / "current.json")


def list_steps(root: Path, slug: str, edit: str):
    """Light manifest of an edit's steps, oldest first."""
    sdir = edit_dir(root, slug, edit) / "steps"
    if not sdir.is_dir():
        return []
    out = []
    for p in sorted(not_junk(sdir.glob("*.json"))):
        j = _read_json(p) or {}
        m = re.match(r"^(\d+)-([a-z]+)-(.*)$", p.stem)
        seq = j.get("seq") or (int(m.group(1)) if m else None)
        who = j.get("who") or (m.group(2) if m else None)
        label = j.get("label") or (m.group(3).replace("-", " ") if m else p.stem)
        out.append({
            "seq": seq,
            "who": who,
            "label": label,
            "created_at": j.get("created_at"),
            "note": j.get("note"),
            "entry_count": len(j.get("entries", [])),
            "stem": p.stem,
            "path": _rel(root, p),
        })
    out.sort(key=lambda s: (s["seq"] or 0, s["stem"]))
    return out


def list_edits(root: Path, slug: str):
    """Every edit of a project with its step manifest. Main first, then by
    creation time. Shape is what the viewer's /edits poll consumes."""
    root = Path(root)
    edir = edits_dir(root, slug)
    if not edir.is_dir():
        return []
    edits = []
    for d in sorted(p for p in edir.iterdir() if p.is_dir() and not p.name.startswith("._")):
        meta = _read_json(d / "edit.json") or {}
        cur = _read_json(d / "current.json") or {}
        edits.append({
            "slug": d.name,
            "name": meta.get("name") or d.name,
            "is_main": bool(meta.get("is_main", d.name == MAIN)),
            "created_at": meta.get("created_at"),
            "forked_from": meta.get("forked_from"),
            "current": {
                "path": _rel(root, d / "current.json") if (d / "current.json").exists() else None,
                "generated_at": cur.get("generated_at"),
                "written_by": cur.get("written_by"),
                "entry_count": len(cur.get("entries", [])),
            },
            "steps": list_steps(root, slug, d.name),
        })
    edits.sort(key=lambda e: (not e["is_main"], e["created_at"] or "", e["slug"]))
    return edits


# ----------------------------------------------------------------------------
# writing
# ----------------------------------------------------------------------------

def next_seq(root: Path, slug: str, edit: str) -> int:
    steps = list_steps(root, slug, edit)
    return (max((s["seq"] or 0) for s in steps) + 1) if steps else 1


def write_step(root: Path, slug: str, edit: str, who: str, label: str, entries,
               note=None, target_runtime_seconds=None, created_at=None, seq=None) -> Path:
    """Append a step. Never overwrites: seq is always the next number."""
    if who not in WHO_VALUES:
        raise ValueError(f"who must be one of {WHO_VALUES}, got {who!r}")
    seq = seq or next_seq(root, slug, edit)
    stem = f"{seq:03d}-{who}-{slugify(label)[:60]}"
    path = edit_dir(root, slug, edit) / "steps" / f"{stem}.json"
    if path.exists():
        raise FileExistsError(f"step already exists: {path}")
    return _write_json(path, {
        "schema_version": SCHEMA_VERSION,
        "kind": "edit-step",
        "project_slug": slug,
        "edit": edit,
        "seq": seq,
        "who": who,
        "label": label,
        "note": note,
        "created_at": created_at or now_iso(),
        "target_runtime_seconds": target_runtime_seconds,
        "entry_count": len(entries),
        "entries": entries,
    })


def write_current(root: Path, slug: str, edit: str, entries, written_by: str,
                  base: dict = None, **fields) -> Path:
    """Write current.json, preserving the viewer's other fields (focus, chat
    pointers, pending ops...) unless `base` is given. `written_by` is
    "viewer" or "agent"; the viewer adopts agent writes newer than its own."""
    cur = dict(base if base is not None else (read_current(root, slug, edit) or {}))
    cur.update({
        "schema_version": cur.get("schema_version", SCHEMA_VERSION),
        "kind": "edit-current",
        "project_slug": slug,
        "edit": edit,
        "generated_at": now_iso(),
        "written_by": written_by,
        "entries": entries,
    })
    cur.update(fields)
    return _write_json(edit_dir(root, slug, edit) / "current.json", cur)


def create_edit(root: Path, slug: str, name: str, entries, from_edit=None,
                from_step=None, is_main=False, who="jeff", first_label=None,
                target_runtime_seconds=None, edit_slug=None) -> str:
    """Create an edit dir with edit.json, current.json and its first step.
    Returns the edit slug. Refuses to clobber an existing edit."""
    eslug = edit_slug or (MAIN if is_main else slugify(name))
    d = edit_dir(root, slug, eslug)
    if (d / "edit.json").exists():
        raise FileExistsError(f"edit already exists: {eslug}")
    _write_json(d / "edit.json", {
        "schema_version": SCHEMA_VERSION,
        "kind": "edit",
        "project_slug": slug,
        "slug": eslug,
        "name": name,
        "is_main": is_main,
        "created_at": now_iso(),
        "forked_from": ({"edit": from_edit, "step": from_step} if from_edit else None),
    })
    write_current(root, slug, eslug, entries, written_by="viewer", base={},
                  target_runtime_seconds=target_runtime_seconds)
    label = first_label or (f"forked from {from_edit}" + (f" step {from_step}" if from_step else "")
                            if from_edit else "created")
    write_step(root, slug, eslug, who, label, entries,
               target_runtime_seconds=target_runtime_seconds)
    return eslug


def snapshot(root: Path, slug: str, edit: str, who: str, label: str, note=None,
             force=False):
    """Write current.json's entries as the next step. Returns the step path, or
    None when the entries are identical to the latest step (and not forced)."""
    cur = read_current(root, slug, edit)
    if not cur or not isinstance(cur.get("entries"), list):
        raise FileNotFoundError(f"no current.json for edit {edit!r}")
    steps = list_steps(root, slug, edit)
    if steps and not force:
        last = _read_json(Path(root) / steps[-1]["path"]) or {}
        if _entries_equal(last.get("entries"), cur["entries"]):
            return None
    return write_step(root, slug, edit, who, label, cur["entries"], note=note,
                      target_runtime_seconds=cur.get("target_runtime_seconds"))


def propose(root: Path, slug: str, edit: str, entries, label: str, who="claude",
            note=None):
    """The agent's proposal beat: append a step AND make it the current state
    (written_by "agent"). The viewer polls /edits and adopts it."""
    cur = read_current(root, slug, edit) or {}
    step = write_step(root, slug, edit, who, label, entries, note=note,
                      target_runtime_seconds=cur.get("target_runtime_seconds"))
    write_current(root, slug, edit, entries, written_by="agent",
                  agent_note=note, agent_step=step.stem)
    return step


# ----------------------------------------------------------------------------
# migration from the v5.13 layout
# ----------------------------------------------------------------------------

_ROUND_RE = re.compile(r"^(?:trimmed-quotes-)?v(\d+)\.json$")
_CKPT_RE = re.compile(r"^(\d+)[-_]([a-z]+)[-_](.+)$")


def _mtime_iso(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) \
            .isoformat(timespec="seconds").replace("+00:00", "Z")
    except OSError:
        return now_iso()


def migrate(root: Path, slug: str, handoffs_dir: Path = None, fallback_rounds=None):
    """Fold a legacy layout into edits/. Idempotent: does nothing when
    edits/main already exists. Old files are left in place.

      editing-versions/v<N>.json            -> steps of main ("Round N", pipeline)
      editing-versions/checkpoints/*.json   -> steps of main (who from filename)
      editing-versions/<named>.json         -> an alternative edit (one step)
      viewer-state.json                     -> main's current.json when it has entries
      fallback_rounds [(label, entries, target)] -> used when no editing-versions

    Returns a report dict; `created` is False when nothing was done.
    """
    root = Path(root)
    report = {"created": False, "main_steps": 0, "edits": [], "source": None, "notes": []}
    if (edit_dir(root, slug, MAIN) / "edit.json").exists():
        return report

    handoffs_dir = Path(handoffs_dir) if handoffs_dir else root / "handoffs" / slug
    canonical = root / "handoffs" / slug / "editing-versions"
    legacy = handoffs_dir / "editing-versions"
    ev = None
    if canonical.is_dir() and not_junk(list(canonical.glob("*.json"))):
        ev = canonical
    elif legacy.is_dir() and legacy.resolve() != canonical.resolve() \
            and not_junk(list(legacy.glob("*.json"))):
        ev = legacy
        report["notes"].append(f"legacy flat editing-versions used: {legacy}")

    main_steps = []   # (sort_key, who, label, entries, target, created_at)
    named = []        # (name, entries, target, created_at)
    target = None
    if ev is not None:
        report["source"] = str(ev)
        for p in not_junk(sorted(ev.glob("*.json"))):
            j = _read_json(p)
            if not isinstance(j, dict) or not isinstance(j.get("entries"), list):
                report["notes"].append(f"skipped unreadable {p.name}")
                continue
            target = target or j.get("target_runtime_seconds")
            m = _ROUND_RE.match(p.name)
            if m:
                n = int(m.group(1))
                main_steps.append((_mtime_iso(p), "pipeline", f"Round {n}",
                                   j["entries"], j.get("target_runtime_seconds"), _mtime_iso(p)))
            else:
                named.append((j.get("cut_name") or p.stem, j["entries"],
                              j.get("target_runtime_seconds"), _mtime_iso(p)))
        ck = ev / "checkpoints"
        if ck.is_dir():
            for p in not_junk(sorted(ck.glob("*.json"))):
                j = _read_json(p)
                if not isinstance(j, dict) or not isinstance(j.get("entries"), list):
                    continue
                m = _CKPT_RE.match(p.stem)
                who = (m.group(2) if m else "pipeline")
                who = {"agent": "claude", "jeff": "jeff", "claude": "claude"}.get(who, "pipeline")
                label = (m.group(3) if m else p.stem).replace("-", " ").replace("_", " ")
                main_steps.append((_mtime_iso(p), who, label, j["entries"],
                                   j.get("target_runtime_seconds"), _mtime_iso(p)))
    elif fallback_rounds:
        report["source"] = "fallback_rounds"
        for i, (label, entries, tgt) in enumerate(fallback_rounds):
            target = target or tgt
            main_steps.append((f"{i:06d}", "pipeline", label, entries, tgt, now_iso()))

    # Live working state (viewer-state.json) wins as main's current.
    vs = None
    for cand in (root / "handoffs" / slug / "viewer-state.json", handoffs_dir / "viewer-state.json"):
        j = _read_json(cand)
        if isinstance(j, dict) and isinstance(j.get("entries"), list) and j["entries"]:
            vs = j
            report["notes"].append(f"main current.json taken from {cand}")
            break

    if not main_steps and vs is None and not named:
        return report  # nothing to migrate; caller may create main from scratch

    main_steps.sort(key=lambda t: t[0])
    if main_steps:
        cur_entries = main_steps[-1][3]
    elif vs is not None:
        cur_entries = vs["entries"]
    else:
        cur_entries = []
    if vs is not None:
        cur_entries = vs["entries"]

    # main
    d = edit_dir(root, slug, MAIN)
    _write_json(d / "edit.json", {
        "schema_version": SCHEMA_VERSION, "kind": "edit", "project_slug": slug,
        "slug": MAIN, "name": "Main edit", "is_main": True,
        "created_at": now_iso(), "forked_from": None,
        "migrated_from": report["source"],
    })
    for i, (_, who, label, entries, tgt, created) in enumerate(main_steps, start=1):
        write_step(root, slug, MAIN, who, label, entries, target_runtime_seconds=tgt,
                   created_at=created, seq=i)
    base = {k: v for k, v in (vs or {}).items()
            if k not in ("kind", "schema_version", "generated_at")}
    write_current(root, slug, MAIN, cur_entries, written_by="viewer", base=base,
                  target_runtime_seconds=(vs or {}).get("target_runtime_seconds") or target)
    report["created"] = True
    report["main_steps"] = len(main_steps)

    # named cuts -> alternative edits
    for name, entries, tgt, created in named:
        eslug = slugify(name)
        if eslug == MAIN or (edit_dir(root, slug, eslug) / "edit.json").exists():
            eslug = f"{eslug}-{len(report['edits']) + 2}"
        create_edit(root, slug, name, entries, from_edit=MAIN, is_main=False,
                    who="jeff", first_label="saved cut (migrated)",
                    target_runtime_seconds=tgt, edit_slug=eslug)
        report["edits"].append(eslug)
    return report


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--root", required=True, help="project/SSD root containing handoffs/")
        p.add_argument("--slug", required=True, help="project slug")

    p = sub.add_parser("list", help="print edits + steps as JSON"); common(p)
    p = sub.add_parser("migrate", help="fold legacy editing-versions/ + viewer-state.json into edits/"); common(p)
    p = sub.add_parser("snapshot", help="write the open edit's current entries as the next step"); common(p)
    p.add_argument("--edit", default=MAIN)
    p.add_argument("--who", default="jeff", choices=WHO_VALUES)
    p.add_argument("--label", required=True)
    p.add_argument("--note", default=None)
    p.add_argument("--force", action="store_true", help="write even if identical to the latest step")
    p = sub.add_parser("propose", help="agent proposal: append a step AND replace current.json"); common(p)
    p.add_argument("--edit", default=MAIN)
    p.add_argument("--entries", required=True, help="JSON file: a list of entries, or an object with `entries`")
    p.add_argument("--label", required=True)
    p.add_argument("--who", default="claude", choices=WHO_VALUES)
    p.add_argument("--note", default=None)
    p = sub.add_parser("new", help="fork an alternative edit from another edit's current state"); common(p)
    p.add_argument("--name", required=True)
    p.add_argument("--from", dest="from_edit", default=MAIN)
    args = ap.parse_args(argv)

    root, slug = Path(args.root), args.slug
    if args.cmd == "list":
        print(json.dumps(list_edits(root, slug), indent=2))
    elif args.cmd == "migrate":
        rep = migrate(root, slug)
        print(json.dumps(rep, indent=2))
    elif args.cmd == "snapshot":
        path = snapshot(root, slug, args.edit, args.who, args.label, note=args.note, force=args.force)
        print(f"step: {path}" if path else "unchanged since the latest step — no step written")
    elif args.cmd == "propose":
        j = json.loads(Path(args.entries).read_text(encoding="utf-8"))
        entries = j["entries"] if isinstance(j, dict) else j
        if not isinstance(entries, list):
            sys.exit("--entries must be a JSON list or an object with an `entries` list")
        step = propose(root, slug, args.edit, entries, args.label, who=args.who, note=args.note)
        print(f"step: {step}\ncurrent.json updated (written_by: agent)")
    elif args.cmd == "new":
        cur = read_current(root, slug, args.from_edit)
        if not cur:
            sys.exit(f"no current.json for edit {args.from_edit!r}")
        steps = list_steps(root, slug, args.from_edit)
        eslug = create_edit(root, slug, args.name, cur.get("entries", []),
                            from_edit=args.from_edit,
                            from_step=(steps[-1]["seq"] if steps else None),
                            target_runtime_seconds=cur.get("target_runtime_seconds"))
        print(f"edit: {eslug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
