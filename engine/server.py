#!/usr/bin/env python3
"""Realtime dashboard server. Stdlib only.

  python3 engine/server.py [port]   ->  http://localhost:8787

Routes:
  /            -> dashboard/index.html
  /api/state   -> live JSON (state files + live transcript scan), no caching
  /projects/*  -> the creative projects
"""
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import build_dashboard
import lib


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(lib.ROOT), **kw)

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
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
