---
name: wrap-up
description: Clean stop for the CreativeWorld engine — persist all state, journal the session, commit, and prepare the nap. Use when budget_check says STOP (exit 4) or the session must end.
---

# Wrap up

1. Current task unfinished? `python3 engine/board.py handoff <id> "<exact next action, files touched, what's verified>"` — write it for a stranger with zero context.
2. `python3 engine/track_tokens.py` (use `--limit-hit` instead if a real rate-limit error occurred).
3. `python3 engine/journal.py end "<what shipped>" --because "<why stopped>" --resume "<next command/task>"` (and `journal.py start "<plan>"` at boot).
4. `python3 engine/build_dashboard.py`
5. Commit everything (`wrap-up: <summary>`); push if a remote exists. Nothing may remain uncommitted.
6. Nap: schedule an hourly wakeup whose ONLY action is `python3 engine/budget_check.py` — on exit 4 keep napping, on exit 0 invoke the `boot` skill. Tell the user in one line what shipped and when work resumes.
