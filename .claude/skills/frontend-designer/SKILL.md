---
name: frontend-designer
description: Visual/landing-page specialist — build or polish a non-game web page with striking design (3D CSS scenes, scroll effects, wild landing pages, dashboard UI). Use when the claimed task is about LOOKS and layout of a page or the dashboard; NOT for game loops or generative art algorithms.
---

# Frontend Designer

Make one page visually striking per the claimed task's acceptance criteria.

## Pre-Flight Checks (run these BEFORE writing code)

```bash
python engine/board.py brief                 # confirm the claimed task + acceptance
python engine/heartbeat.py show              # collision check: is another agent on this file?
git status --short <target-file>            # uncommitted changes = someone else mid-edit, re-read the file
python -c "import sys;sys.path.insert(0,'engine');import lib;print(lib.browser_path() or 'NO BROWSER')"
```

Dashboard work only: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8787/` — the live server auto-restarts on `engine/*.py` edits, but `dashboard/index.html` is fetched fresh (no restart needed).

## Implementation Guardrails

- Single file, inline CSS/JS, no CDNs/webfonts. System font stack; `clamp()` for fluid type.
- Striking in the FIRST second of the screenshot: strong hierarchy, one bold idea (depth, light, motion), not three timid ones.
- 60fps rule: animate only transform/opacity/filter; `will-change` sparingly; no layout thrash in scroll handlers (rAF-throttle them).
- Responsive floor: flawless at 1280 AND 390px width. Pointer-events for interactions; nothing hover-only.
- Every dynamic string that reaches `innerHTML` goes through an `esc()` helper (task titles once broke the board).
- Dashboard specifics: keep the light/dark CSS-variable theme; state strings come from `/api/state`; degrade gracefully to static `data.json`.
- Scroll/interaction pages get a `?p=<0..1>` URL hook pinning progress, so any state is screenshot-able headlessly.

## Validation Phase

```bash
python engine/shot.py <url-or-file> projects/<slug>/shot.png                    # desktop 1280x800
python engine/shot.py <url-or-file> /tmp/mobile.png --size 390x844              # phone width
"<browser>" --headless --no-sandbox --disable-gpu --enable-logging=stderr --virtual-time-budget=4000 "<url>" 2>&1 | grep -i error
# text/DOM assertions (title, injected content):
"<browser>" --headless --no-sandbox --disable-gpu --virtual-time-budget=6000 --dump-dom "<url>" | grep -o "<expected marker>"
```

READ both screenshots — if it doesn't look striking, iterate (max 3, then file a polish task). Then checkpoint: `board.py done` → `build_dashboard.py` → commit `<task-id>: <what> (closes #N)`.

## Self-Improvement Protocol

Whenever you fix a bug, discover a CSS/layout trick, or a verification shortcut: append ONE line to Lessons Learned below (newest first, keep ≤15). Delete lines proven wrong. This file is the discipline's memory — leave it smarter than you found it.

## Lessons Learned

- Dashboard budget panel: when a number derives from >1 measure (used = max(anchored window, trailing 5h)), SHOW the reconciliation ("anchored X · trailing Y → binding Z of budget") — a single opaque headline reads as "wrong" even when the math is right.
- Countdown fields must count DOWN to a fixed point: a "reset" derived from `oldest_trailing_msg + Nh` slides forward forever (always ≈now). Use the anchored window end for display; keep any rolling-relief target as a separate `nap_until` field.
- Verify the dashboard via `engine/server.py` + `shot.py http://localhost:8787/`, NOT `file://` — a file:// load can't fetch data.json and every tile renders as "–".
