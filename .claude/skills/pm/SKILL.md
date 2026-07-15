---
name: pm
description: Project-manager role — groom the CreativeWorld backlog. Invents new creative project ideas, slices them into tasks, prioritizes the queue. Use when the next-queue is thin (<5 tasks) or when asked to plan.
---

# PM (sprint planning)

1. Read `state/backlog.json` epic titles + `state/learnings.md` (short) — nothing else.
2. If fewer than 2 unbuilt project epics exist, invent new ones. Rules for ideas:
   - Maximally creative and varied: mini games, generative/interactive art, 3D CSS/WebGL scenes, physics toys, audio-reactive pages, wild landing-page effects, weird UI experiments.
   - Never repeat a concept already in the epics list. Prefer ideas that look impressive as a screenshot.
   - Must be buildable as a single dependency-free `index.html` (S/M sized).
   - Mobile-games era (CLAUDE.md Direction, issue #24): once all pre-2026-07-15 epics have shipped, every new project epic is a touch-first mobile game playable on Android and iPhone.
   - `python3 engine/board.py add-epic project "<Title>" -- "<one-line concept>" --slug <slug>`
3. Slice: every active project epic needs a v1 task (M) and optionally a polish task (S, backlog). Meta-epics (Engine E1, Dashboard E2) should always have at least one improvement task filed — the engine gets better every day.
   - `python3 engine/board.py add <epic-id> <S|M> "<title>" -- "<verifiable acceptance criteria>"`
4. Prioritize: `python3 engine/board.py move <id> next` until ~10 tasks are in next. Mix: mostly creative work, ~1 in 4 self-improvement. Reorder by editing `state/queue.json` `next` array if needed.
5. Commit state changes with message `pm: groomed backlog`.
