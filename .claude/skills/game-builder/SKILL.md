---
name: game-builder
description: Mobile-game specialist — build a touch-first web game (arcade, puzzle, physics toy with win/lose state) as a single index.html that plays on Android and iPhone. Use when the claimed task's epic is a GAME (has a game loop, score, or player input); NOT for passive art or landing pages.
---

# Game Builder

Build one touch-first mobile web game per the claimed task's acceptance criteria.

## Pre-Flight Checks (run these BEFORE writing code)

```bash
python engine/board.py brief                 # confirm the claimed task + acceptance
python engine/heartbeat.py show              # another agent mid-task on this project? if yes, STOP
ls projects/<slug>/ 2>/dev/null              # existing work? read it before overwriting
python -c "import sys;sys.path.insert(0,'engine');import lib;print(lib.browser_path() or 'NO BROWSER')"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8787/api/state   # 200 = live server for drive.py
```

If NO BROWSER: stop and report — a game cannot ship unverified.

## Implementation Guardrails

- One `index.html`, inline CSS/JS, zero network (no CDNs, fonts, fetch). Single strong mechanic > three weak ones.
- Touch-first (CLAUDE.md Direction): pointer events only (`pointerdown/move/up`, never hover-gated), `touch-action:none` on the play surface, targets ≥44px, `<meta name="viewport" content="width=device-width, initial-scale=1">`, portrait-friendly.
- Game loop on `requestAnimationFrame` with delta-time (never assume 60Hz). Animate transform/opacity only; canvas for particle-heavy scenes.
- Must have: instant-read title/hint overlay, score or progress, a fail/win state, restart without reload.
- Test hooks are mandatory: `?demo=1` runs an autopilot player AND mirrors live state into `document.title` (score, game-over) so the driver can assert the loop really runs.
- Audio (if any): WebAudio created on first pointer event (mobile autoplay rules), never required for play.

## Validation Phase (a game is not done until SEEN working)

```bash
python engine/shot.py projects/<slug>/index.html projects/<slug>/shot.png            # desktop 1280x800
python engine/shot.py projects/<slug>/index.html /tmp/mobile.png --size 390x844      # phone width
# real-time play test (rAF barely advances under virtual time — static shots lie):
python engine/drive.py "http://localhost:8787/projects/<slug>/?demo=1" --wait 10 --js "return document.title" --shot projects/<slug>/shot.png
# console errors:
"<browser>" --headless --no-sandbox --disable-gpu --enable-logging=stderr --virtual-time-budget=4000 "file://.../index.html" 2>&1 | grep -i error
```

READ both screenshots. Assert `document.title` changed (score moved / game-over fired). If chromedriver is missing, shot.py is the fallback but note it in the handoff. Then checkpoint: `board.py done` → `build_dashboard.py` → commit `<task-id>: <what> (closes #N)`.

## Self-Improvement Protocol

Whenever you fix a bug, hit a platform quirk, or find a pattern that made the game better or cheaper to build: append ONE line to Lessons Learned below (newest first, keep ≤15). Delete lines proven wrong. This file is the discipline's memory — leave it smarter than you found it.

## Lessons Learned

- (placeholder — first real lesson replaces this line)
