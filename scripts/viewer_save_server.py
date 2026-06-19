#!/usr/bin/env python3
"""viewer_save_server.py — the quote viewer's persistent local app shell.

Why this exists
---------------
The viewer runs browser-first. It used to live as a throwaway Cowork chat
artifact: ephemeral (gone on task-switch), ``sendPrompt`` unavailable, and
persistence was a brittle fallback. The redesign (SPEC §7) moves it to a
**persistent local app served in Chrome that shares state with the Edit Agent
through files on disk**. This one process is that shell.

What it does (M4 — persistent app shell)
----------------------------------------
1. **Serves the built viewer** at ``/`` (pass ``--serve path/to/index.html``).
   Open ``http://127.0.0.1:<port>/`` once in Chrome; the tab survives
   task-switching like any web app — no chat artifact to lose.
2. **Persists files** the viewer POSTs to ``/save`` (``{path, content}``):
   named saved cuts (``editing-versions/<name>.json``), the tweak log, exports,
   and — new in M4 — the viewer's **live working state**, autosaved on every
   edit to ``handoffs/<slug>/viewer-state.json``. That file is the channel the
   Edit Agent reads on each of its turns to see the current cut (no copy-paste,
   no PDF-printing — see SKILL-edit.md).
   If the helper is NOT running, the viewer degrades to a plain download, so a
   save is never lost either way.

Same-origin bonus: when the viewer is *served* by this process, its ``/save``
POSTs are same-origin, so persistence works with no CORS caveats.

Security
--------
- Binds to 127.0.0.1 only (never reachable off this machine).
- Only paths *under* ``handoffs/`` are writable (POST /save) or readable
  (GET /read), and only ``.json`` files.
- Absolute paths, ``..`` traversal, and symlink escapes are rejected — every
  resolved target must stay inside ``<root>/handoffs``.
- ``--serve`` exposes exactly ONE file (the built viewer) at ``/``; no
  directory listing. GET /read is limited to the same handoffs/**.json sandbox
  (used to poll the Edit Agent's read-acknowledgement).

Usage
-----
    python3 scripts/viewer_save_server.py [--root DIR] [--serve INDEX_HTML] [--port 8765]

``--root`` defaults to the current working directory; run it from the directory
that contains ``handoffs/`` (the project / SSD root the viewer was built for).
``--serve`` is the path to the built ``index.html`` to serve at ``/``; omit it
to run save-only (the viewer is served some other way, e.g. another tab).
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DEFAULT_PORT = 8765
MAX_BODY = 16 * 1024 * 1024  # 16 MB — generous for a cut/tweak-log JSON


class SaveHandler(BaseHTTPRequestHandler):
    # Set on the server instance in main(); the resolved, allowed root.
    root: Path = Path.cwd().resolve()
    # Optional: path to the built viewer index.html served at "/". None = save-only.
    serve_file: Path = None

    # --- CORS / preflight -------------------------------------------------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802 (http.server naming)
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path in ("/ping", "/health"):
            self._json(200, {"ok": True, "service": "viewer-save-server",
                             "root": str(self.root),
                             "serving": str(self.serve_file) if self.serve_file else None})
        elif path == "/read":
            self._read_json(parse_qs(parsed.query))
        elif path == "/list":
            self._list_cuts(parse_qs(parsed.query))
        elif path in ("", "/index.html") and self.serve_file is not None:
            self._serve_viewer()
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def _list_cuts(self, query):
        """List the saved-cut JSON files in a sandboxed handoffs/ directory.

        Lets the viewer's Open menu reflect what is actually on disk (named
        deliverables saved this session, in another tab, or by the pipeline) —
        not just the cuts baked into the page at build time. Returns a light
        manifest per file: stem + the labelling fields, parsed best-effort.
        """
        rel = (query.get("path") or [""])[0].strip().lstrip("/")
        if ".." in Path(rel).parts:
            self._json(403, {"ok": False, "error": "path traversal not allowed"})
            return
        allowed = (self.root / "handoffs").resolve()
        target = (self.root / rel).resolve()
        if allowed != target and allowed not in target.parents:
            self._json(403, {"ok": False, "error": "path must be under handoffs/"})
            return
        if not target.is_dir():
            self._json(200, {"ok": True, "cuts": []})  # no dir yet → nothing saved
            return
        cuts = []
        for p in sorted(target.glob("*.json")):
            stem = p.stem
            entry = {"stem": stem, "path": (Path(rel) / p.name).as_posix()}
            try:
                j = json.loads(p.read_text(encoding="utf-8"))
                entry["round"] = j.get("round")
                entry["cut_name"] = j.get("cut_name")
                entry["entry_count"] = len(j.get("entries", []))
            except (OSError, ValueError):
                pass  # still list it, just without metadata
            cuts.append(entry)
        self._json(200, {"ok": True, "cuts": cuts})

    def _read_json(self, query):
        """Return the contents of a sandboxed handoffs/**.json file.

        Lets the viewer poll the Edit Agent's read-acknowledgement
        (handoffs/<slug>/agent-cursor.json) so the staleness cue can clear itself
        when the agent has caught up. Same sandbox as writes: handoffs/**.json
        only. Missing file → 404 {ok:false} (the viewer treats that as
        "agent hasn't connected yet"), never an error.
        """
        rel = (query.get("path") or [""])[0]
        try:
            target = self._safe_target(rel)
        except ValueError as e:
            self._json(403, {"ok": False, "error": str(e)})
            return
        if not target.is_file():
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            content = target.read_text(encoding="utf-8")
            data = json.loads(content)
        except (OSError, ValueError) as e:
            self._json(500, {"ok": False, "error": f"read failed: {e}"})
            return
        self._json(200, {"ok": True, "data": data})

    def _serve_viewer(self):
        """Serve the single built viewer file at /. No directory access."""
        try:
            body = self.serve_file.read_bytes()
        except OSError as e:
            self._json(500, {"ok": False, "error": f"cannot read viewer: {e}"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # Always fetch the freshest build (the file is rewritten by the build script).
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        if self.path.rstrip("/") != "/save":
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._json(400, {"ok": False, "error": "bad Content-Length"})
            return
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"ok": False, "error": "empty or oversized body"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            self._json(400, {"ok": False, "error": f"invalid JSON body: {e}"})
            return

        rel = payload.get("path")
        content = payload.get("content")
        if not isinstance(rel, str) or not isinstance(content, str):
            self._json(400, {"ok": False,
                             "error": "expected {path: str, content: str}"})
            return

        try:
            target = self._safe_target(rel)
        except ValueError as e:
            self._json(403, {"ok": False, "error": str(e)})
            return

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            self._json(500, {"ok": False, "error": f"write failed: {e}"})
            return

        rel_out = target.relative_to(self.root).as_posix()
        sys.stderr.write(f"[viewer-save-server] wrote {rel_out} "
                         f"({len(content)} bytes)\n")
        self._json(200, {"ok": True, "path": rel_out, "bytes": len(content)})

    def _safe_target(self, rel: str) -> Path:
        """Resolve `rel` under root, enforcing the handoffs/ + .json sandbox."""
        rel = rel.strip().lstrip("/")
        if not rel:
            raise ValueError("empty path")
        if ".." in Path(rel).parts:
            raise ValueError("path traversal ('..') is not allowed")
        if not rel.endswith(".json"):
            raise ValueError("only .json files may be written")
        allowed = (self.root / "handoffs").resolve()
        target = (self.root / rel).resolve()
        # Must live inside <root>/handoffs (covers symlink escapes too).
        if allowed != target and allowed not in target.parents:
            raise ValueError("path must be under handoffs/")
        return target

    # Quiet the default per-request stderr logging; we log writes ourselves.
    def log_message(self, *_args):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".",
                    help="project/SSD root containing handoffs/ (default: cwd)")
    ap.add_argument("--serve", default=None, metavar="INDEX_HTML",
                    help="path to the built viewer index.html to serve at / "
                         "(omit to run save-only)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port to listen on (default: {DEFAULT_PORT})")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / "handoffs").is_dir():
        sys.stderr.write(
            f"warning: {root}/handoffs does not exist yet — it will be created "
            f"on first save. Make sure --root is the project/SSD root.\n")

    serve_file = None
    if args.serve:
        serve_file = Path(args.serve).resolve()
        if not serve_file.is_file():
            sys.stderr.write(f"error: --serve file not found: {serve_file}\n")
            return 2

    SaveHandler.root = root
    SaveHandler.serve_file = serve_file
    server = ThreadingHTTPServer(("127.0.0.1", args.port), SaveHandler)
    sys.stderr.write(
        f"[viewer-save-server] listening on http://127.0.0.1:{args.port}\n"
        f"[viewer-save-server] root: {root}\n"
        f"[viewer-save-server] writable sandbox: {root}/handoffs/**.json\n")
    if serve_file is not None:
        sys.stderr.write(
            f"[viewer-save-server] serving viewer: {serve_file}\n"
            f"[viewer-save-server] OPEN IN CHROME: http://127.0.0.1:{args.port}/\n")
    else:
        sys.stderr.write(
            "[viewer-save-server] save-only (no --serve); open the viewer separately\n")
    sys.stderr.write(
        f"[viewer-save-server] leave this running while you work in the viewer; "
        f"Ctrl-C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[viewer-save-server] stopped.\n")
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main() or 0)
