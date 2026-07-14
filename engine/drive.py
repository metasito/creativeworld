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
import os
import subprocess
import sys
import time
import urllib.request

DRIVER = "http://127.0.0.1:9515"
BROWSER_CANDIDATES = [
    "/opt/pw-browsers/chromium",                                        # cloud container
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",           # windows chrome
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",    # windows edge
]


def browser_binary():
    for p in BROWSER_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("no known browser binary found; edit BROWSER_CANDIDATES in drive.py")


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(DRIVER + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read())["value"]


def main():
    args = sys.argv[1:]
    url = args[0]
    proc = subprocess.Popen(["chromedriver", "--port=9515", "--disable-build-check"],
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
