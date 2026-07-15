#!/usr/bin/env python3
"""Compose dashboard data from state/. Writes dashboard/data.json (also used live by server.py)."""
import json
from datetime import datetime, timezone

import lib


def compose(live=False):
    tokens = lib.load("tokens.json")
    if live:
        lib.update_from_transcripts(tokens)
    backlog = lib.load("backlog.json")
    queue = lib.load("queue.json")
    sessions = lib.load("sessions.json")["sessions"]
    learnings = (lib.STATE / "learnings.md").read_text(encoding="utf-8").strip().splitlines()
    try:
        activity = lib.load("activity.json")
    except Exception:
        activity = {"engine_status": "idle", "current_task": None, "current_action": None,
                    "agent": None, "updated": None, "log": []}

    # real token cost per epic = sum of its done tasks' measured costs
    cost_by_epic = {}
    for t in backlog["tasks"]:
        if t.get("cost"):
            cost_by_epic[t["epic"]] = cost_by_epic.get(t["epic"], 0) + t["cost"]

    projects = []
    for e in backlog["epics"]:
        if e["kind"] != "project":
            continue
        slug = e.get("slug")
        idx = (lib.ROOT / "projects" / slug / "index.html") if slug else None
        shot = bool(slug and (lib.ROOT / "projects" / slug / "shot.png").exists())
        built = bool(idx and idx.exists())
        updated = lib.iso(datetime.fromtimestamp(idx.stat().st_mtime, tz=timezone.utc)) if built else None
        projects.append({**e, "built": built, "shot": shot, "updated": updated,
                         "cost": cost_by_epic.get(e["id"], 0),
                         "url": f"/projects/{slug}/" if built else None})

    # Wire each task to the real commit that shipped it (named "<id>: ...").
    commits = lib.commits_by_task()
    tasks = [{**t, "commit": commits.get(t["id"])} for t in backlog["tasks"]]

    summary = lib.budget_summary(tokens)
    name, _ = lib.verdict(summary)
    return {
        "generated_at": lib.iso(lib.now()),
        "repo_url": lib.repo_url(),
        "budget": {**summary, "verdict": name,
                   "history": tokens.get("history", [])[-20:]},
        "epics": backlog["epics"],
        "tasks": tasks,
        "queue": queue,
        "projects": projects,
        "sessions": sessions[-10:],
        "learnings": [l[2:] for l in learnings if l.startswith("- ")][:8],
        "activity": {**activity, "log": activity.get("log", [])[-12:]},
    }


def main():
    data = compose(live=False)
    out = lib.ROOT / "dashboard" / "data.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
