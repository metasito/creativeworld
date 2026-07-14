---
name: retro
description: Retrospective role — distill lessons into learnings.md and file self-improvement tasks. Use after every ~5 completed tasks or when asked.
---

# Retro

1. Look at `state/sessions.json` (last 3 entries) and `state/tokens.json` history — nothing else.
2. Append 1-3 one-line lessons to `state/learnings.md` (newest first). Good lessons are operational: what wasted tokens, what verification caught, what made a project pop. Delete lines older than ~20 entries.
3. File improvement work: at least one task on Engine (E1) or Dashboard (E2) that would make the next session cheaper or the output better. `python3 engine/board.py add E1 S "<title>" -- "<acceptance>"`
4. If token estimates were badly off (task sizes vs actual), adjust size guidance in CLAUDE.md.
5. Commit with `retro: <n> lessons, <n> tasks filed`.
