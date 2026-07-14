# CreativeWorld — Autonomous Creative Project Engine

An autonomous, self-improving system that continuously builds new creative projects — mini games, generative art, 3D pages, landing pages with wild effects — while squeezing maximum value out of a limited token budget ($20 Claude Pro plan).

**Motto: Squeeze as many tokens as you can.**

## Quick start

```bash
python3 engine/server.py          # realtime dashboard -> http://localhost:8787
python3 engine/board.py list      # the agile board in your terminal
```

Start a Claude Code session in this repo and say **"go"** (or `/boot`): the engine claims tasks, builds, verifies with screenshots, commits — and keeps going by itself until ~95% of the token window is used, then wraps up, naps until the window resets, and resumes.

## How it works

| Piece | What it does |
|---|---|
| `CLAUDE.md` | The constitution every session obeys: boot → work loop → budget protocol. |
| `state/` | Single source of truth: backlog, queue, token ledger, session journal, learnings. A fresh session resumes from these files alone. |
| `engine/track_tokens.py` | Reads the live session transcript (`~/.claude/projects/*/*.jsonl`) and maintains the weighted-token ledger. |
| `engine/budget_check.py` | Verdict: exit 0 CONTINUE · 3 WRAP_UP (>85%) · 4 STOP (>95%). `--preflight` is the free CI gate. |
| `engine/board.py` | Agile board CLI (claim/done/move/add/brief) — bookkeeping costs zero LLM tokens. |
| `engine/server.py` | Realtime dashboard: token gauge, kanban, project gallery, session journal. |
| `engine/drive.py` | Real-time headless-browser driver (WebDriver) to verify games/animations actually run. |
| `.claude/skills/` | The "team": `boot` (resume), `pm` (plan/ideate), `build-project` (builder), `wrap-up` (clean stop), `retro` (get better every day). |
| `projects/` | The output — each project is one self-contained `index.html`. |

## Token budget

The plan's real limits aren't queryable, so the engine estimates: weighted tokens (`output×5 + input + cache_write×1.25 + cache_read×0.1`) against `budget_per_window` in `state/tokens.json` (5h rolling window). When a real rate-limit hits, `track_tokens.py --limit-hit` calibrates the budget down to actual usage — the estimate improves every day.

## Full autonomy (GitHub Actions) — one-time setup

`.github/workflows/engine.yml` runs hourly: a free preflight gate exits instantly if the budget is spent; otherwise Claude boots and works the queue. To activate:

1. On your own machine run `claude setup-token` and copy the token.
2. GitHub repo → Settings → Secrets and variables → Actions → new secret **`CLAUDE_CODE_OAUTH_TOKEN`**.
3. Actions tab → enable workflows.

The cron also skips (free) whenever a commit landed in the last 45 minutes, so it never competes with a live session.

## Projects

Every project epic ships as `projects/<slug>/index.html` — dependency-free, screenshot-verified. Open them from the dashboard gallery.
