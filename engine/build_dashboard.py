#!/usr/bin/env python3
"""Compose dashboard data from state/. Writes dashboard/data.json (also used live by server.py)."""
import json

import lib


def compose(live=False):
    tokens = lib.load("tokens.json")
    if live:
        lib.update_from_transcripts(tokens)
    backlog = lib.load("backlog.json")
    queue = lib.load("queue.json")
    sessions = lib.load("sessions.json")["sessions"]
    learnings = (lib.STATE / "learnings.md").read_text(encoding="utf-8").strip().splitlines()

    projects = []
    for e in backlog["epics"]:
        if e["kind"] != "project":
            continue
        slug = e.get("slug")
        shot = bool(slug and (lib.ROOT / "projects" / slug / "shot.png").exists())
        built = bool(slug and (lib.ROOT / "projects" / slug / "index.html").exists())
        projects.append({**e, "built": built, "shot": shot,
                         "url": f"/projects/{slug}/" if built else None})

    summary = lib.budget_summary(tokens)
    name, _ = lib.verdict(summary)
    return {
        "generated_at": lib.iso(lib.now()),
        "budget": {**summary, "verdict": name,
                   "history": tokens.get("history", [])[-20:]},
        "epics": backlog["epics"],
        "tasks": backlog["tasks"],
        "queue": queue,
        "projects": projects,
        "sessions": sessions[-10:],
        "learnings": [l[2:] for l in learnings if l.startswith("- ")][:8],
    }


def main():
    data = compose(live=False)
    out = lib.ROOT / "dashboard" / "data.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
