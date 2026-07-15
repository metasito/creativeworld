#!/usr/bin/env python3
"""Cross-platform headless screenshot. Finds the browser for you (lib.browser_path).

  shot.py <url-or-path> <out.png> [--size 1280x800] [--vt 4000]

--vt is Chromium's --virtual-time-budget (ms): lets initial JS/animations run
before capture. NOTE: rAF barely advances under virtual time — for games and
animated pages use drive.py (real time) when chromedriver is available.
"""
import subprocess
import sys
from pathlib import Path

import lib


def shot(target, out, size="1280,800", vt=4000):
    browser = lib.browser_path()
    if not browser:
        sys.exit("no browser found — set $BROWSER or install Chrome/Chromium")
    url = target if "://" in target else Path(target).resolve().as_uri()
    cmd = [browser, "--headless", "--no-sandbox", "--disable-gpu",
           f"--screenshot={Path(out).resolve()}", f"--window-size={size}",
           f"--virtual-time-budget={vt}", url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not Path(out).exists():
        sys.exit(f"screenshot failed ({browser}):\n{r.stderr[-800:]}")
    print(f"saved {out} ({browser})")


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    size, vt = "1280,800", 4000
    if "--size" in args:
        i = args.index("--size")
        size = args[i + 1].replace("x", ",")
        args = args[:i] + args[i + 2:]
    if "--vt" in args:
        i = args.index("--vt")
        vt = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    shot(args[0], args[1], size, vt)


if __name__ == "__main__":
    main()
