# CreativeWorld — Autonomous Creative Project Engine

An autonomous, self-improving system that continuously builds new creative projects — mini games, generative art, 3D rendering pages, landing pages with wild effects (e.g. a phone that decomposes into its internal layers on scroll) — while squeezing maximum value out of a limited token budget.

**Motto: Squeeze as many tokens as you can.**

## Core ideas

- **Autonomous project factory**: the engine picks creative topics, plans them, and builds them end-to-end. The more creative, the better.
- **Dashboard**: a simple web dashboard showing
  - token usage (consumed / remaining, with history)
  - the task queue: what's being worked on now and what's queued next
  - per-project status, like a project manager's view of a team
- **Budget awareness**: runs on the $20 Claude plan. The engine must stop cleanly at ~95% token usage, persist all state, and resume fresh with full context when the token window resets.
- **State persistence**: everything (queue, task status, project progress, learnings) is stored on disk so a fresh session can pick up exactly where the last one stopped.
- **Agile team simulation**: tasks are categorized and scheduled like a real team — agents pick up tasks, work them, and merge results; a PM view in the dashboard shows what's happening in each project.
- **Self-improvement**: the engine also works on its own dashboard and tooling — it should get better every day, like an engine that improves itself.
- **Skills-first token optimization**: define and use Claude Code skills aggressively so repeated workflows cost as few tokens as possible.

## Status

Bootstrap commit — planning in progress via ultraplan.
