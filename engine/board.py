#!/usr/bin/env python3
"""Agile board CLI over state/backlog.json + state/queue.json. Zero LLM tokens.

Usage:
  board.py brief                          # one-command boot context
  board.py list
  board.py claim                          # top of queue -> in_progress
  board.py done <id> [note...]
  board.py move <id> <status>             # backlog|next|in_progress|review|done
  board.py handoff <id> <text...>
  board.py add <epic> <size> <title> -- <acceptance>
  board.py add-epic <kind> <title> -- <description> [--slug SLUG]
  board.py epic-status <id> <status>
"""
import sys

import lib

STATUSES = {"backlog", "next", "in_progress", "review", "done"}


def sync_queue(b):
    q = lib.load("queue.json")
    inprog = [t["id"] for t in b["tasks"] if t["status"] == "in_progress"]
    nxt = [t for t in b["tasks"] if t["status"] == "next"]
    old_order = {tid: i for i, tid in enumerate(q.get("next", []))}
    nxt.sort(key=lambda t: old_order.get(t["id"], 999))
    q["in_progress"] = inprog[0] if inprog else None
    q["next"] = [t["id"] for t in nxt]
    lib.save("queue.json", q)
    return q


def find(b, tid):
    for t in b["tasks"]:
        if t["id"] == tid:
            return t
    sys.exit(f"no task {tid}")


def touch(t):
    t["updated"] = lib.iso(lib.now())


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "list"
    b = lib.load("backlog.json")

    if cmd == "brief":
        # One-command boot context: budget verdict + what to do next. Keep output tiny.
        tokens = lib.load("tokens.json")
        lib.update_from_transcripts(tokens)
        lib.save("tokens.json", tokens)
        s = lib.budget_summary(tokens)
        name, _ = lib.verdict(s)
        print(f"budget: {name} {s['pct']}% of {s['budget']} · resets {s['resets_at']}")
        q = sync_queue(b)
        epics = {e["id"]: e for e in b["epics"]}
        if q["in_progress"]:
            t = find(b, q["in_progress"])
            print(f"RESUME {t['id']} [{t['size']}] ({epics[t['epic']]['title']}): {t['title']}")
            print(f"  acceptance: {t['acceptance']}")
            print(f"  handoff: {t['handoff'] or '(none)'}")
        else:
            print("no task in progress — run: python3 engine/board.py claim")
        for tid in q["next"][:5]:
            t = find(b, tid)
            print(f"  next: {t['id']} [{t['size']}] {t['title']}")
        sess = lib.load("sessions.json")["sessions"]
        if sess:
            last = sess[-1]
            print(f"last session: {last['did']} · resume_with: {last['resume_with']}")
        return

    if cmd == "list":
        q = sync_queue(b)
        epics = {e["id"]: e["title"] for e in b["epics"]}
        for status in ["in_progress", "next", "review", "backlog", "done"]:
            ts = [t for t in b["tasks"] if t["status"] == status]
            if status == "next":
                ts.sort(key=lambda t: q["next"].index(t["id"]))
            if ts:
                print(f"== {status} ==")
                for t in ts:
                    h = f"  <- {t['handoff']}" if t.get("handoff") else ""
                    print(f"  {t['id']} [{t['size']}] ({epics[t['epic']]}) {t['title']}{h}")
        return

    if cmd == "claim":
        q = lib.load("queue.json")
        if q.get("in_progress"):
            sys.exit(f"already in progress: {q['in_progress']} (WIP limit = 1)")
        if not q.get("next"):
            sys.exit("queue empty — run the pm skill")
        t = find(b, q["next"][0])
        t["status"] = "in_progress"
        touch(t)
        print(f"claimed {t['id']}: {t['title']}\nacceptance: {t['acceptance']}")

    elif cmd == "done":
        t = find(b, args[1])
        t["status"] = "done"
        t["handoff"] = " ".join(args[2:])
        touch(t)
        print(f"done {t['id']}")

    elif cmd == "move":
        t = find(b, args[1])
        assert args[2] in STATUSES, f"status must be one of {STATUSES}"
        t["status"] = args[2]
        touch(t)
        print(f"{t['id']} -> {args[2]}")

    elif cmd == "handoff":
        t = find(b, args[1])
        t["handoff"] = " ".join(args[2:])
        touch(t)
        print(f"handoff saved on {t['id']}")

    elif cmd == "add":
        epic, size = args[1], args[2]
        rest = " ".join(args[3:])
        title, _, acceptance = rest.partition(" -- ")
        n = b["next_ids"]["task"]
        b["next_ids"]["task"] = n + 1
        b["tasks"].append({"id": f"T{n}", "epic": epic, "title": title.strip(),
                           "acceptance": acceptance.strip(), "size": size,
                           "status": "backlog", "handoff": "", "updated": lib.iso(lib.now())})
        print(f"added T{n}")

    elif cmd == "add-epic":
        kind = args[1]
        slug = None
        rest_args = args[2:]
        if "--slug" in rest_args:
            i = rest_args.index("--slug")
            slug = rest_args[i + 1]
            rest_args = rest_args[:i] + rest_args[i + 2:]
        rest = " ".join(rest_args)
        title, _, desc = rest.partition(" -- ")
        n = b["next_ids"]["epic"]
        b["next_ids"]["epic"] = n + 1
        e = {"id": f"E{n}", "title": title.strip(), "kind": kind, "status": "planned",
             "description": desc.strip()}
        if slug:
            e["slug"] = slug
        b["epics"].append(e)
        print(f"added E{n}")

    elif cmd == "epic-status":
        for e in b["epics"]:
            if e["id"] == args[1]:
                e["status"] = args[2]
                print(f"{e['id']} -> {args[2]}")
                break
        else:
            sys.exit(f"no epic {args[1]}")

    else:
        sys.exit(__doc__)

    lib.save("backlog.json", b)
    sync_queue(b)


if __name__ == "__main__":
    main()
