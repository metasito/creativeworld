# Learnings

Distilled lessons from retros. Newest first. Keep entries to one line each — this file is read on boot by the pm/retro skills.

- 2026-07-15: The real subscription cap is a ROLLING 5h window, not discrete engine windows — a "fresh" window hit the limit at 457k because earlier usage still counted; budget math must model trailing-5h (T38 filed).
- 2026-07-15: server.py is long-running — edits to modules it imports (build_dashboard, board, lib) are invisible until restart; verify-by-screenshot caught a silently stale API. Restart after engine edits.
- 2026-07-15: Two agents WILL collide on the same file (autopilot + interactive both took T17): check heartbeat/claimed_by before editing, and all state mutations now go through lib.state_lock.
- 2026-07-14: Cloud-container work is unreachable once a session moves machines — push to a remote EARLY; a repo without a remote is one container-reclaim away from losing everything.
- 2026-07-14: Virtual-time screenshots lie for rAF pages — use `engine/drive.py` (real-time WebDriver; needs chromedriver `--disable-build-check` with the bundled Chromium, and `--no-sandbox --disable-gpu` everywhere).
- 2026-07-14: URL test hooks are gold: `?p=` (pin scroll progress), `?demo=1` (autopilot + state mirrored into document.title), `?seed=` (deterministic art) make every project verifiable headlessly for pennies.
- 2026-07-14: Cost calibration — full bootstrap (engine + dashboard + 3 shipped projects) ≈ 1.23M weighted tokens; one M-sized single-file project ≈ 150–250k; an S task ≈ 40–80k.
- 2026-07-14 (bootstrap): Transcript JSONL at `~/.claude/projects/<proj>/<session>.jsonl` carries per-turn `usage`; weighted formula in tokens.json config approximates plan units — calibrate, don't trust.
