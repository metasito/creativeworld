---
name: art-generator
description: Generative-art specialist — build algorithmic/procedural visual pieces (particle fields, flow noise, organic growth, shader-style canvas art) as a single index.html. Use when the claimed task is about a generative ALGORITHM or ambient visual; NOT for games with scores or content-driven landing pages.
---

# Art Generator

Build one generative piece per the claimed task's acceptance criteria.

## Pre-Flight Checks (run these BEFORE writing code)

```bash
python engine/board.py brief                 # confirm the claimed task + acceptance
python engine/heartbeat.py show              # collision check: another agent on this project?
ls projects/<slug>/ 2>/dev/null              # existing art? read before overwriting
python -c "import sys;sys.path.insert(0,'engine');import lib;print(lib.browser_path() or 'NO BROWSER')"
```

## Implementation Guardrails

- Single file, inline JS, no libraries — the algorithm IS the artwork. Canvas 2D for ≤~5k elements; WebGL fragment shader beyond that (CPU per-pixel loops will not hold 60fps fullscreen).
- Determinism is mandatory: `?seed=N` drives a seeded PRNG (mulberry32 or xorshift — never bare `Math.random` for structure), so every screenshot is reproducible and comparisons are honest.
- Composition rules: unified palette (pick 3-5 colors, not rainbow noise), one readable macro-form emerging from micro-behavior, dark-background vignette beats flat white.
- Live pieces animate on `requestAnimationFrame` with delta-time; static pieces render once and stop (no idle CPU burn).
- Interaction (cursor/touch) is welcome but the piece must look striking with ZERO interaction — that is what the screenshot captures.
- Tiny title/hint overlay so a visitor gets it instantly.

## Validation Phase

```bash
python engine/shot.py "projects/<slug>/index.html?seed=7" projects/<slug>/shot.png   # canonical seed
python engine/shot.py "projects/<slug>/index.html?seed=8" /tmp/seed8.png             # different seed => different art
python engine/shot.py "projects/<slug>/index.html?seed=7" /tmp/seed7b.png            # same seed => same art
"<browser>" --headless --no-sandbox --disable-gpu --enable-logging=stderr --virtual-time-budget=4000 "<url>" 2>&1 | grep -i error
```

READ the screenshots: seed 7 twice must match; seed 8 must differ; the canonical shot must be striking (iterate max 3, then file a polish task). Animated pieces: also `drive.py --wait 8 --shot` for a real-time frame. Then checkpoint: `board.py done` → `build_dashboard.py` → commit `<task-id>: <what> (closes #N)`.

## Self-Improvement Protocol

Whenever you fix a bug, find an algorithm/palette pattern that elevated a piece, or a cheaper way to verify: append ONE line to Lessons Learned below (newest first, keep ≤15). Delete lines proven wrong. This file is the discipline's memory — leave it smarter than you found it.

## Lessons Learned

- 2026-07-15: swarm-follows-target pieces: the demo path must move SLOWER than the followers' max speed, or the canonical shot shows a lagging comet-tail instead of a swarm — slow the path period until followers converge within the `--wait` window (verify with a near-count in the demo title).
- 2026-07-15: same-seed md5 hash equality fails for ANIMATED pieces (capture lands on different frames) — verify determinism by eyeballing structure of the two shots, not hashes.
- 2026-07-15: drive.py takes a full URL only — pass `file:///C:/...?seed=7&demo=1` (relative paths give chromedriver HTTP 400); masks built from fixed geometry must be clearance-checked across aspect ratios (a lancet arch landed inside the rose ring at 1280x800 and its pane never filled).
- 2026-07-15: virtual-time shots capture animated pieces at t≈0 (buds closed, scene "off") — canonical shot.png for any animated piece must come from `drive.py --wait N --shot`; give pieces a `?demo=1` autoplay param so the real-time shot shows the piece fully alive.
- 2026-07-15: `shot.py` used to percent-encode `?seed=7` on file paths (as_uri), silently ignoring the seed — fixed in engine/shot.py; if seeds ever "stop working", check URL encoding first.
