#!/usr/bin/env python3
"""viewer_save_server.py — tiny localhost helper that lets the quote viewer
persist files when it is opened in a plain browser tab (outside Cowork).

Why this exists
---------------
The viewer runs browser-first (see the kickoff brief). Inside Cowork it writes
files via ``window.cowork.callMcpTool``; that path is dead in a normal browser
tab, so working-round saves and the tweak log used to silently evaporate.

This helper is the robust persistence tier: run it once from the project (or
SSD) root, and the viewer POSTs ``{path, content}`` to it. It writes the file
to the correct location automatically — no manual file placement, no Downloads
clutter, works in every browser. If the helper is NOT running, the viewer
degrades to a plain download, so a save is never lost either way.

Security
--------
- Binds to 127.0.0.1 only (never reachable off this machine).
- Only paths *under* ``handoffs/`` are writable, and only ``.json`` files.
- Absolute paths, ``..`` traversal, and symlink escapes are rejected — every
  resolved target must stay inside ``<root>/handoffs``.

Usage
-----
    python3 scripts/viewer_save_server.py [--root DIR] [--port 8765]

``--root`` defaults to the current working directory; run it from the directory
that contains ``handoffs/`` (the project / SSD root the viewer was built for).
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8765
MAX_BODY = 16 * 1024 * 1024  # 16 MB — generous for a cut/tweak-log JSON


class SaveHandler(BaseHTTPRequestHandler):
    # Set on the server instance in main(); the resolved, allowed root.
    root: Path = Path.cwd().resolve()

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
        if self.path.rstrip("/") in ("/ping", "/health"):
            self._json(200, {"ok": True, "service": "viewer-save-server",
                             "root": str(self.root)})
        else:
            self._json(404, {"ok": False, "error": "not found"})

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
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port to listen on (default: {DEFAULT_PORT})")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / "handoffs").is_dir():
        sys.stderr.write(
            f"warning: {root}/handoffs does not exist yet — it will be created "
            f"on first save. Make sure --root is the project/SSD root.\n")

    SaveHandler.root = root
    server = ThreadingHTTPServer(("127.0.0.1", args.port), SaveHandler)
    sys.stderr.write(
        f"[viewer-save-server] listening on http://127.0.0.1:{args.port}\n"
        f"[viewer-save-server] root: {root}\n"
        f"[viewer-save-server] writable sandbox: {root}/handoffs/**.json\n"
        f"[viewer-save-server] leave this running while you work in the viewer; "
        f"Ctrl-C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[viewer-save-server] stopped.\n")
        server.shutdown()


if __name__ == "__main__":
    main()
