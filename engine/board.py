#!/usr/bin/env python3
"""Agile board CLI over state/backlog.json + state/queue.json. Zero LLM tokens.

Usage:
  board.py brief                          # one-command boot context
  board.py list
  board.py claim                          # top of queue -> in_progress
  board.py done <id> [note...]
  board.py move <id> <status>             # backlog|next|in_progress|review|done
  board.py handoff <id> <text...>
  board.py link <id> [--issue N] [--pr URL]   # tie a task to its GitHub issue/PR
  board.py add <epic> <size> <title> -- <acceptance>
  board.py add-epic <kind> <title> -- <description> [--slug SLUG]
  board.py epic-status <id> <status>
"""
import os
import sys

import lib

STATUSES = {"backlog", "next", "in_progress", "review", "done"}


def gh_safe(fn, *a, **kw):
    """Run a github-sync call without ever breaking board flow (offline, bad
    token, rate limit -> warn and move on; the board is the source of truth)."""
    try:
        import github
        if not github.enabled():
            return None
        return fn(github, *a, **kw)
    except Exception as e:
        print(f"  (github sync skipped: {e})")
        return None


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


def get_task(b, tid):
    """Lookup that raises (safe inside the long-lived server) instead of exiting."""
    for t in b["tasks"]:
        if t["id"] == tid:
            return t
    raise KeyError(tid)


def update_task(b, tid, status=None, handoff=None, pr=None, issue=None, order=None):
    """Edit a task from the dashboard: status/handoff/pr/issue + optional reorder.

    Importable — used by server.py's POST /api/task/update.
    """
    t = get_task(b, tid)
    if status is not None:
        assert status in STATUSES, f"status must be one of {STATUSES}"
        was = t["status"]
        t["status"] = status
        if status != was:  # mirror board moves onto GitHub + cost snapshots
            epics = {e["id"]: e["title"] for e in b["epics"]}
            if status == "in_progress":
                t.setdefault("cost_start", lib.total_usage())
                gh_safe(lambda gh: gh.ensure_task_issue(t, epics.get(t["epic"], t["epic"])))
            elif status == "done":
                if t.get("cost_start") is not None:
                    t["cost"] = max(0, lib.total_usage() - t.pop("cost_start"))
                gh_safe(lambda gh: gh.close_task_issue(t, gh.ship_comment(t)))
    if handoff is not None:
        t["handoff"] = handoff.strip()
    if pr is not None:
        t["pr"] = pr.strip()
    if issue is not None:
        t["issue"] = str(issue).strip().lstrip("#")
    touch(t)
    lib.save("backlog.json", b)
    q = sync_queue(b)
    if order:
        head = [x for x in order if x in q["next"]]
        q["next"] = head + [x for x in q["next"] if x not in head]
        lib.save("queue.json", q)
    return t


def touch(t):
    t["updated"] = lib.iso(lib.now())


def issue_line(t):
    """Human-readable GitHub traceability for a task: issue link + PR link."""
    base = lib.repo_url()
    iss = str(t.get("issue") or "").strip()
    if iss and base:
        left = f"issue: {base}/issues/{iss}"
    elif base:
        left = f"issue: none yet — open at {base}/issues/new"
    else:
        left = "issue: (no github remote)"
    pr = t.get("pr")
    return f"{left}" + (f" · pr: {pr}" if pr else "")


def create_task(b, epic, size, title, acceptance, status="backlog", top=False):
    """Create a task (importable — used by server.py's POST /api/task)."""
    n = b["next_ids"]["task"]
    b["next_ids"]["task"] = n + 1
    t = {"id": f"T{n}", "epic": epic, "title": title.strip(),
         "acceptance": acceptance.strip(), "size": size, "status": status,
         "handoff": "", "updated": lib.iso(lib.now())}
    b["tasks"].append(t)
    lib.save("backlog.json", b)
    q = sync_queue(b)
    if top and status == "next":
        q["next"] = [t["id"]] + [x for x in q["next"] if x != t["id"]]
        lib.save("queue.json", q)
    return t


def create_epic(b, kind, title, description, slug=None):
    """Create an epic (importable — used by server.py's POST /api/task)."""
    n = b["next_ids"]["epic"]
    b["next_ids"]["epic"] = n + 1
    e = {"id": f"E{n}", "title": title.strip(), "kind": kind, "status": "planned",
         "description": description.strip()}
    if slug:
        e["slug"] = slug
    b["epics"].append(e)
    lib.save("backlog.json", b)
    return e


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
        if s.get("rate_per_hour"):
            eta = f" · cap in ~{s['eta_hours']}h" if s.get("eta_hours") is not None else " · over cap"
            print(f"burn: {s['rate_per_hour']:,} tok/h (trailing {tokens['config']['window_hours']}h){eta}")
        changes = gh_safe(lambda gh: gh.pull(b)) or []
        if changes:
            lib.save("backlog.json", b)
            for c in changes:
                print(f"github: {c}")
        q = sync_queue(b)
        epics = {e["id"]: e for e in b["epics"]}
        if q["in_progress"]:
            t = find(b, q["in_progress"])
            print(f"RESUME {t['id']} [{t['size']}] ({epics[t['epic']]['title']}): {t['title']}")
            print(f"  acceptance: {t['acceptance']}")
            print(f"  handoff: {t['handoff'] or '(none)'}")
        else:
            print("no task in progress — run: python3 engine/board.py claim")
        depth = len(q["next"])
        warn = " — WARN: queue thin, run the pm skill" if depth < 5 else ""
        print(f"queue: {depth} task(s) in next{warn}")
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
        agent = os.environ.get("CW_AGENT", "unknown")
        if "--agent" in args:
            agent = args[args.index("--agent") + 1]
        # whole claim under the state lock: two concurrent claims must not both win
        with lib.state_lock():
            b = lib.load("backlog.json")
            q = lib.load("queue.json")
            if q.get("in_progress"):
                holder = next((x.get("claimed_by") for x in b["tasks"]
                               if x["id"] == q["in_progress"]), None)
                sys.exit(f"already in progress: {q['in_progress']} (WIP limit = 1"
                         + (f", claimed_by {holder}" if holder else "") + ")")
            if not q.get("next"):
                sys.exit("queue empty — run the pm skill")
            t = find(b, q["next"][0])
            t["status"] = "in_progress"
            t["claimed_by"] = agent
            t["cost_start"] = lib.total_usage()  # for real per-task cost at done
            touch(t)
            lib.save("backlog.json", b)
            sync_queue(b)
        epics = {e["id"]: e["title"] for e in b["epics"]}
        gh_safe(lambda gh: gh.ensure_task_issue(t, epics.get(t["epic"], t["epic"])))
        print(f"claimed {t['id']}: {t['title']} (agent: {agent})\nacceptance: {t['acceptance']}")
        print(f"  {issue_line(t)}")

    elif cmd == "done":
        t = find(b, args[1])
        t["status"] = "done"
        t["handoff"] = " ".join(args[2:])
        if t.get("cost_start") is not None:
            t["cost"] = max(0, lib.total_usage() - t.pop("cost_start"))
            print(f"  cost: ~{t['cost']:,} weighted tokens [{t['size']}]")
        touch(t)
        gh_safe(lambda gh: gh.close_task_issue(t, gh.ship_comment(t)))
        print(f"done {t['id']}")
        if t.get("issue"):
            print(f"  commit with: {t['id']}: <what shipped> (closes #{t['issue']})")

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

    elif cmd == "link":
        t = find(b, args[1])
        rest = args[2:]
        if "--issue" in rest:
            t["issue"] = rest[rest.index("--issue") + 1].strip().lstrip("#")
        if "--pr" in rest:
            t["pr"] = rest[rest.index("--pr") + 1].strip()
        touch(t)
        print(f"{t['id']} linked · {issue_line(t)}")

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
