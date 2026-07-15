#!/usr/bin/env python3
"""Drive a real headless Chromium via chromedriver (WebDriver REST, stdlib only).

Usage:
  drive.py <url> [--wait N] [--js "return document.title"] [--shot out.png]
                 [--click X,Y] [--move X,Y]

Runs the page in REAL time (unlike --virtual-time-budget screenshots), so
games/animations actually play. Actions run in argv order after page load.
"""
import base64
import json
import shutil
import subprocess
import sys
import time
import urllib.request

import lib

DRIVER = "http://127.0.0.1:9515"


def browser_binary():
    p = lib.browser_path()
    if not p:
        sys.exit("no browser found — set $BROWSER or install Chrome/Chromium")
    return p


def chromedriver_binary():
    """chromedriver from PATH or tools/, or a clear next step (not a traceback)."""
    for c in [shutil.which("chromedriver"),
              str(lib.ROOT / "tools" / "chromedriver.exe"),
              str(lib.ROOT / "tools" / "chromedriver")]:
        if c and shutil.which(c):
            return c
    sys.exit("chromedriver not found (PATH or tools/). Real-time driving needs it.\n"
             "Fallback for static pages: python engine/shot.py <url> <out.png>\n"
             "Get it: https://googlechromelabs.github.io/chrome-for-testing/ "
             "(match your Chrome version, drop the exe into tools/)")


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(DRIVER + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read())["value"]


def main():
    args = sys.argv[1:]
    url = args[0]
    proc = subprocess.Popen([chromedriver_binary(), "--port=9515", "--disable-build-check"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                req("GET", "/status")
                break
            except Exception:
                time.sleep(0.2)
        s = req("POST", "/session", {"capabilities": {"alwaysMatch": {"goog:chromeOptions": {
            "binary": browser_binary(),
            "args": ["--headless=new", "--no-sandbox", "--disable-gpu", "--window-size=1280,800"]}}}})
        sid = s["sessionId"]
        req("POST", f"/session/{sid}/url", {"url": url})

        i = 1
        while i < len(args):
            a = args[i]
            if a == "--wait":
                time.sleep(float(args[i + 1])); i += 2
            elif a == "--js":
                out = req("POST", f"/session/{sid}/execute/sync", {"script": args[i + 1], "args": []})
                print(json.dumps(out)); i += 2
            elif a == "--shot":
                png = req("GET", f"/session/{sid}/screenshot")
                open(args[i + 1], "wb").write(base64.b64decode(png))
                print(f"saved {args[i + 1]}"); i += 2
            elif a in ("--click", "--move"):
                x, y = map(int, args[i + 1].split(","))
                actions = [{"type": "pointerMove", "x": x, "y": y, "duration": 50}]
                if a == "--click":
                    actions += [{"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]
                req("POST", f"/session/{sid}/actions", {"actions": [{
                    "type": "pointer", "id": "m", "parameters": {"pointerType": "mouse"},
                    "actions": actions}]})
                i += 2
            else:
                sys.exit(f"unknown arg {a}")
        req("DELETE", f"/session/{sid}")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
