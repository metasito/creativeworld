#!/usr/bin/env python3
"""The engine's live heartbeat -> state/activity.json, shown on the dashboard.

Usage:
  heartbeat.py status <working|napping|idle> [--task T14] [--action "text"] [--agent name]
  heartbeat.py log "message" [--agent name]
  heartbeat.py show
"""
import json
import sys

import lib

FILE = "activity.json"


def load():
    try:
        return lib.load(FILE)
    except Exception:
        return {"engine_status": "idle", "current_task": None, "current_action": None,
                "agent": None, "updated": None, "log": []}


def opt(args, flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    a = load()
    cmd = args[0]

    if cmd == "status":
        a["engine_status"] = args[1]
        a["current_task"] = opt(args, "--task", a.get("current_task"))
        a["current_action"] = opt(args, "--action", a.get("current_action"))
        a["agent"] = opt(args, "--agent", a.get("agent"))
        a["updated"] = lib.iso(lib.now())
        if args[1] == "idle":
            a["current_task"] = a["current_action"] = None
    elif cmd == "log":
        a["log"].append({"at": lib.iso(lib.now()), "agent": opt(args, "--agent", a.get("agent")),
                         "msg": args[1]})
        a["log"] = a["log"][-40:]
        a["updated"] = lib.iso(lib.now())
    elif cmd == "show":
        print(json.dumps(a, indent=2))
        return
    else:
        sys.exit(__doc__)

    lib.save(FILE, a)
    print(f"heartbeat: {a['engine_status']}" + (f" {a['current_task']}" if a.get("current_task") else ""))


if __name__ == "__main__":
    main()
