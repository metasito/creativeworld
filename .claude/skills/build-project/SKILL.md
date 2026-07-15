---
name: build-project
description: Builder role — implement a creative project task end-to-end (scaffold, build, verify with screenshot, register). Use whenever the claimed task belongs to a project epic.
---

# Build a creative project

1. Create `projects/<slug>/index.html` — single file, inline CSS/JS, no CDNs/fonts/network. Target: visually striking in the first second, works at desktop + 390px mobile width. Mobile-game era projects (CLAUDE.md Direction): touch-first — pointer events (no hover-only interactions), `<meta name="viewport">`, portrait-friendly layout, touch targets ≥44px.
2. Quality bar: 60fps animations (transform/opacity only, requestAnimationFrame for canvas), one strong idea executed well beats three half-ideas. Include a tiny title/hint overlay so a visitor instantly gets it.
3. Verify for real with headless Chromium (cloud: `/opt/pw-browsers/chromium`; Windows: `"C:\Program Files\Google\Chrome\Application\chrome.exe"`):
   `<browser> --headless --no-sandbox --disable-gpu --screenshot=projects/<slug>/shot.png --window-size=1280,800 --virtual-time-budget=4000 "file://$PWD/projects/<slug>/index.html"`
   Read the screenshot. If it doesn't look striking, iterate (max 3 iterations, then file a polish task instead). For mobile games, also verify a portrait shot: repeat with `--window-size=390,844` into `projects/<slug>/shot-mobile.png`.
4. For interactive/animated pages the static screenshot lies (virtual time barely advances rAF). Use the real-time driver instead:
   `python3 engine/drive.py "http://localhost:8787/projects/<slug>/?demo=1" --wait 10 --js "return document.title" --shot projects/<slug>/shot.png`
   Convention: give games a `?demo=1` autopilot mode and mirror live state into `document.title` under demo, so `--js` can assert the loop really runs (score changes, game-over fires).
5. Check the browser console for errors: rerun with `--enable-logging=stderr 2>&1 | grep -i error` if anything looks off.
6. Register: `python3 engine/board.py epic-status <epic-id> shipped` when v1 is accepted, then the standard checkpoint (done → track → build_dashboard → commit).
