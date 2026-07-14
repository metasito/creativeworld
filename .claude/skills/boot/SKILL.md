---
name: boot
description: Fresh-session resume for the CreativeWorld engine. Restores full working context from state files only, claims a task, and starts the work loop. Use at the start of every session or when asked to "go".
---

# Boot

1. `python3 engine/board.py brief` — ONE command gives budget verdict, the task to resume (with handoff), the next queue, and the last session note. Obey the verdict (CONTINUE / WRAP_UP / STOP per CLAUDE.md Budget protocol).
2. If it printed RESUME, continue that task from its handoff. Otherwise `python3 engine/board.py claim`.
3. If `next` has fewer than 5 tasks, invoke the `pm` skill before working.
4. Do NOT read old transcripts, git log, or files unrelated to the claimed task. State files are the whole truth.
5. Enter the work loop from CLAUDE.md: one task → verify in Chromium → `board.py done` → `track_tokens.py` → `build_dashboard.py` → commit (+push if remote) → `budget_check.py` → next task.
6. Keep the session going autonomously: after each checkpoint, continue immediately; when budget says STOP, invoke the `wrap-up` skill and nap (hourly wakeups running only `budget_check.py`) until it says CONTINUE, then boot again.
