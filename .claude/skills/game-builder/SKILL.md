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

- Spatial connect-the-nodes builder (drag lit→dark to route power, surge timer = lose): one shared `nearestLightable()` (scan every unlit target × every lit source, pick the shortest legal link) powers BOTH the `?demo=1` autopilot AND `window.__surge.solve()` for free, and doubles as winnability proof — the demo self-advanced through GRID 5 in one 11s drive.py run (title `WIN 5`). Place nodes as a source-at-centre + jittered two-radius ring and gate links by a `maxLink = min(W,H)*0.42` distance so the mechanic is spatial, not just "tap all". A live dashed drag-preview coloured green/red by the same `canLink && !hasEdge` predicate makes legal moves instant-read. Capture the gallery shot at `--wait 3` (a mid-grid frame with a dark node left) — the demo's auto-advance means a late frame is just a fresh grid.
- Beat-sync polish for a tap game: run one rising `bpm=min(cap,base+elapsed*k)` clock in the loop, accumulate `beatAge+=dt` and fire `onBeat()` (spawn + metronome `click`) when it crosses `beatLen=60/bpm` — spawns then land ON the beat for free, and a pop with `beatAge<BEAT_WIN` (~0.19s) earns a doubled "BEAT" hit. Combo = `combo++; mult=1+floor(combo/4)`; a MISS (ping hit nothing) resets combo, which is what makes the streak feel earned. The `?demo=1` AI popping the bloom nearest the core each beat drove score 28→98 in a 10s real-time drive.py run (title mirrors `score:/lives:`), proving the combo climbs. Watch the title screen at 390px: a `&nbsp;`-forced one-line title (`clamp(38px,13vw,72px)`) overflows the right edge — use a normal space so it wraps to two centered lines.
- Adding a second hazard type to a scrolling dodge game (jellyfish alongside whirlpools): reuse the existing world-depth→screen mapping and `worldToScreen`, seed the new hazards on the same depth column, and CONCAT both hazard arrays for the `?demo` AI's nearest-threat scan (`state.whirls.concat(state.jellies)`) so the self-play still dodges everything and wins — otherwise the new hazard silently makes the demo lose. A sting = one-shot on contact via a per-hazard `cool` cooldown timer, drain a chunk of the resource, knock the player back along the contact normal, emit a burst of the same puff particles, `navigator.vibrate(30)`, and a brief full-screen `sting` flash timer. drive.py needs an absolute `file:///C:/.../index.html?demo` URL (a relative path 400s); `--wait 6 --shot x.png --js "return document.title" --wait 15 --js ...` captures a real-time mid-play frame AND confirms the demo reaches `WIN` in one run.
- Animated "energy trail" along a fixed beam/path: build pixel points + cumulative segment lengths once per render, then draw evenly-spaced photons at `d = (glow*speed)%gap; d<total; d+=gap` via a `posAt(d)` that walks the segments — `globalCompositeOperation='lighter'` + shadowBlur makes them read as flowing light with zero extra state. A "level-select grid" polish is cheapest as the existing progress dots upgraded to 46px `<button>`s (done/cur classes) wired to a shared `jumpTo(n)` that clears the overlay and re-runs setupLevel — reuse of the level machinery, no new screen.
- "Completion" polish (quench/steam, victory bursts) is best SEEN via the synchronous `window.__x.forceWin()` hook + a `drive.py --js "window.__x.forceWin(); return document.title;" --shot out.png --wait 0.3` — captures the effect at its peak before the win overlay slides up. Delay that overlay (e.g. `setTimeout(()=>winOv.classList.remove('hide'), 950)`) so the burst is actually visible instead of instantly covered. Soft steam = additive-free radial-gradient circles (`rgba(235,244,255,a)`→transparent) that rise (`vy` negative), grow (`r+=grow`), and fade (`life-=decay`); pair with a `blade.targetGlow=0.06` so the metal visibly cools while it steams.
- Drag-to-merge grid puzzles (2048-by-drag): a floating `#ghost` div at `position:fixed` following the pointer + `document.elementFromPoint` to resolve the drop cell is all the drag you need — no per-cell listeners. Factor the merge into `doMerge(src,dst)` so the `?demo=1` AI and `window.__merge.forceWin()` reuse it. Board tension comes from spawning 2 crystals per merge (net +1 cell) so the grid slowly floods; lose = board full AND `anyMoves()` false. A GREEDY demo that always fuses the *highest* available matching pair funnels mass upward and self-won to the tier-6 target (title `WIN`) — greedy-highest beats greedy-random for climbing merge trees. Diamond-shaped gems = a 45°-rotated rounded square with the label counter-rotated back.
- Weaving/dodge scroller (steer horizontally, thread gates, dodge void orbs): a spring toward a pointer target (`vx += (tx-x)*26*dt; vx *= pow(0.0008,dt)`) gives smooth momentum with tilt from `vx`. Score gates on the frame `g.y` crosses `rider.y` (a `scored` flag) so a fast rider can't double-count; the `?demo=1` AI just steers to the nearest un-scored gate's `cx` unless a void is within `r+46` and closing (`dd<150`), then flees to the far side — reached score 4 in a 9s drive, proving the loop. `globalCompositeOperation='lighter'` for ribbons/glow/sparks makes the whole aurora read; radial-gradient void with a thin stroke ring reads as a "hole" against it.
- Pulsing-hazard polish for gravity/aim games: store the supernova's pulse as `killR = r*(1 + 0.55*(0.5+0.5*sin(snPhase*spd+off)))` and advance `snPhase` in step() BEFORE the `!comet.moving` early-return so it keeps pulsing at rest; then reuse `snKillR()` for both collision AND the predicted-path guide so the aim line honestly stops at the hazard. A level-select "screen" can just be 64px `.lvl` buttons inside the existing title overlay (`startAt(n)` shared by Launch + pickers) — the overlay renders over live gameplay so a plain title screenshot already shows the hazard glowing behind it.
- Connect-the-nodes grid puzzles (drag a wire S→T): store the level as walls + src/tgt and get everything for free from one BFS — `?demo=1` feeds the BFS path cell-by-cell (~90ms/step) to prove winnability, and `window.__relay.solve()` sets path=BFS+win() for a synchronous hook. Guarding path edits with an `advTok` that `loadLevel` increments makes stale demo `setTimeout` steps no-op after a level advances, so the demo cleanly self-wins all 3 (title reaches `WIN 3`). For the gallery shot, drive with a SHORT `--wait` (~1.2s) — the demo's final win state hides the board, so a mid-route frame reads the mechanic far better.
- Auto-advancing `?demo=1` players (level N wins → advance to N+1): a `win()` that shows its overlay on a delay (e.g. 620ms) will re-show that stale overlay on the *next* level if the demo advances sooner — freezing the demo if `stepDemo` bails while the overlay is visible. Make the demo's post-win advance delay strictly longer than win()'s overlay delay so `nextLevel()` clears the stale timer. Proof of a solvable multi-level puzzle: one long `drive.py --wait` that reaches title `WIN <last>` on its own.
- Rotate-to-align ring puzzles: store each ring as a snapped step index and define "aligned" as index 0 (notch drawn at `rot - PI/2` so rot≡0 = under the top marker); then `solve()`/`forceWin()` = snap every `rot` to nearest `2π` multiple, and the demo = nudge the innermost unaligned ring's rot toward its nearest `2π`. Pick the dragged ring by radial band (`hypot` from center), rotate by the delta of `atan2` angles.
- Scrolling dodge games (kite/runner): keep the `?demo=1` AI dead simple — steer AWAY from the single nearest approaching hazard, else chase the nearest collectible; a subtle dead condition (`s.y-kite.y > td*0`) silently disabled avoidance and the demo died at 20%. With a time-based altitude win (alt += 100*dt/WIN_MS), a demo that reaches `alt:100` in one drive.py run (~WIN_MS+scroll) is the winnability proof — no separate forceWin needed for that.

- Reveal/sonar games: a too-good `?demo=1` AI (pop the bloom nearest the core every 0.28s) clears hazards faster than they spawn, so validation shots show an empty field — the loop is proven by title `score:N lives:3` climbing, but for a gallery shot you can't rely on demo to leave a hazard on screen. The sonar rings + glowing core still read the mechanic; don't burn tokens chasing a bloom in-frame.
- Climb/escape games (reach-the-top vs a draining meter): balance is the whole game — first pass was unwinnable (climb 56px/s vs air lasting ~13s). Tune by measuring: run `?demo=1` with an aim-far-above target (`ay=-0.6*H` so the spring stays saturated = "perfect play"), read `reached%`/`air%` from the title at 12s, then set DEPTH + drain so perfect play surfaces in ~18–20s with ~25% air left. A `?demo=1` that actually WINs on its own (title flips to `WIN … reached:100%`) is the proof the loop is winnable, not just alive.
- Grid/laser puzzles: store each mirror's *solution* orientation in the level def and start it at the opposite — then `?demo=1` (rotate any wrong mirror toward its `sol` each tick) and `window.__prism.solve()` (set all to `sol`) both fall out for free, so one `drive.py --js` loop can assert every level is solvable (`__prism.solve()` returned true × N). Trace the beam with a visited-`(cell,dir)` set to kill infinite bounce loops.
- Rhythm/timing games: drive a normalized 0..1 spark position (ping-pong `pos+=dir*speed*dt/1000`) and judge on `abs(pos-0.5)` vs a `zoneHalf()` derived from DOM widths — decouples hit logic from pixel layout so it works at any viewport. `?demo=1` can auto-strike near centre with a cooldown to prove the loop; still ship a `window.__forge.forceWin()` hook for the WIN path.
- Gravity/aim games: a `?demo=1` player aiming straight at a small goal rarely scores (wells bend the path). Prove the loop with strokes-in-title, and prove the WIN path with a synchronous `window.__comet._forceWin()` test hook a single `drive.py --js` can assert — don't rely on random demo play to reach game-over.
