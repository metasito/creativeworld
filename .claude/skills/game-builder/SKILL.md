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

- Reveal/sonar games: a too-good `?demo=1` AI (pop the bloom nearest the core every 0.28s) clears hazards faster than they spawn, so validation shots show an empty field — the loop is proven by title `score:N lives:3` climbing, but for a gallery shot you can't rely on demo to leave a hazard on screen. The sonar rings + glowing core still read the mechanic; don't burn tokens chasing a bloom in-frame.
- Climb/escape games (reach-the-top vs a draining meter): balance is the whole game — first pass was unwinnable (climb 56px/s vs air lasting ~13s). Tune by measuring: run `?demo=1` with an aim-far-above target (`ay=-0.6*H` so the spring stays saturated = "perfect play"), read `reached%`/`air%` from the title at 12s, then set DEPTH + drain so perfect play surfaces in ~18–20s with ~25% air left. A `?demo=1` that actually WINs on its own (title flips to `WIN … reached:100%`) is the proof the loop is winnable, not just alive.
- Grid/laser puzzles: store each mirror's *solution* orientation in the level def and start it at the opposite — then `?demo=1` (rotate any wrong mirror toward its `sol` each tick) and `window.__prism.solve()` (set all to `sol`) both fall out for free, so one `drive.py --js` loop can assert every level is solvable (`__prism.solve()` returned true × N). Trace the beam with a visited-`(cell,dir)` set to kill infinite bounce loops.
- Rhythm/timing games: drive a normalized 0..1 spark position (ping-pong `pos+=dir*speed*dt/1000`) and judge on `abs(pos-0.5)` vs a `zoneHalf()` derived from DOM widths — decouples hit logic from pixel layout so it works at any viewport. `?demo=1` can auto-strike near centre with a cooldown to prove the loop; still ship a `window.__forge.forceWin()` hook for the WIN path.
- Gravity/aim games: a `?demo=1` player aiming straight at a small goal rarely scores (wells bend the path). Prove the loop with strokes-in-title, and prove the WIN path with a synchronous `window.__comet._forceWin()` test hook a single `drive.py --js` can assert — don't rely on random demo play to reach game-over.
