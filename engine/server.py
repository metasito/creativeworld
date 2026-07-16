#!/usr/bin/env python3
"""Realtime dashboard server. Stdlib only.

  python3 engine/server.py [port]   ->  http://localhost:8787

Routes:
  /            -> dashboard/index.html
  /api/state   -> live JSON (state files + live transcript scan), no caching
  /projects/*  -> the creative projects
"""
import json
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import board
import build_dashboard
import lib

RESTART = threading.Event()


def watch_engine(httpd, interval=2.0):
    """Re-exec the server when any engine/*.py changes — a long-running process
    otherwise serves stale imports silently (bit us: compose edits invisible)."""
    def stamps():
        return {p: p.stat().st_mtime for p in (lib.ROOT / "engine").glob("*.py")}
    before = stamps()
    while True:
        time.sleep(interval)
        try:
            if stamps() != before:
                print("engine/*.py changed -> restarting server")
                RESTART.set()
                httpd.shutdown()
                return
        except OSError:
            pass  # file mid-write; retry next tick


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(lib.ROOT), **kw)

    def do_POST(self):
        route = self.path.rstrip("/")
        if route not in ("/api/task", "/api/task/update", "/api/autopilot"):
            self.send_error(404)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if route == "/api/autopilot":
                state = "run" if body.get("run") else "stop"
                lib.set_control("autopilot", state)  # own state_lock inside
                out, code = {"ok": True, "autopilot": state}, 200
                resp = json.dumps(out).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return
            with lib.state_lock():  # whole read-modify-write is one transaction
                b = lib.load("backlog.json")
                if route == "/api/task/update":
                    t = board.update_task(b, body["id"], status=body.get("status"),
                                          handoff=body.get("handoff"), pr=body.get("pr"),
                                          issue=body.get("issue"), order=body.get("order"))
                    out, code = {"ok": True, "task": t["id"], "status": t["status"]}, 200
                else:
                    title = body["title"].strip()
                    assert title, "title required"
                    size = body.get("size", "S")
                    assert size in ("S", "M", "L"), "bad size"
                    epic = body.get("epic", "")
                    if body.get("new_epic"):
                        ne = body["new_epic"]
                        epic = board.create_epic(b, "project", ne["title"], ne.get("description", ""),
                                                 slug=ne.get("slug") or None)["id"]
                    assert any(e["id"] == epic for e in b["epics"]), f"unknown epic {epic}"
                    t = board.create_task(b, epic, size, title, body.get("acceptance", ""),
                                          status="next", top=body.get("top", True))
                    out, code = {"ok": True, "task": t["id"], "epic": epic}, 200
        except Exception as e:
            out, code = {"ok": False, "error": str(e)}, 400
        resp = json.dumps(out).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def do_GET(self):
        if self.path.rstrip("/") == "/api/state":
            try:
                body = json.dumps(build_dashboard.compose(live=True)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            except Exception as e:  # keep the dashboard alive on any state hiccup
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/":
            self.path = "/dashboard/index.html"
        super().do_GET()

    def log_message(self, *a):
        pass  # quiet


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print(f"CreativeWorld dashboard -> http://localhost:{port}")
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=watch_engine, args=(httpd,), daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return
    finally:
        httpd.server_close()
    if RESTART.is_set():
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])


if __name__ == "__main__":
    main()
