#!/usr/bin/env python3
"""GitHub sync for the board: real issues per task, closed on ship. Stdlib only.

Token comes from $GITHUB_TOKEN or state/secrets.json {"github_token": ...}
(git-ignored). Without a token (or a github remote) every call is a silent
no-op, so the engine keeps working token-free — commit-link traceability
from T26 stays the fallback.

Usage as a module (board.py):
  ensure_task_issue(t, epic_title)  on claim -> creates "[Tn] title", stores number
  close_task_issue(t, comment)      on done  -> closes #N with a comment

CLI:
  github.py sync    # backfill issues for open tasks, close issues of done tasks
"""
import json
import re
import urllib.error
import urllib.request

import lib

API = "https://api.github.com"
LABEL_COLORS = {"size:S": "c2e0c6", "size:M": "fbca04", "size:L": "d93f0b",
                "engine": "1d76db", "dashboard": "5319e7", "project": "0e8a16"}


def token():
    import os
    t = os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    try:
        return json.loads((lib.STATE / "secrets.json").read_text())["github_token"]
    except Exception:
        return None


def repo_path():
    url = lib.repo_url()
    return url.split("github.com/", 1)[1] if url else None


def enabled():
    return bool(token() and repo_path())


def api(method, path, data=None):
    """One GitHub API call. Returns parsed JSON or raises urllib.error.HTTPError."""
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": "Bearer " + token(),
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "creativeworld-engine"})
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read()
        return json.loads(body) if body else {}


def ensure_labels(names):
    for n in names:
        try:
            api("POST", f"/repos/{repo_path()}/labels",
                {"name": n, "color": LABEL_COLORS.get(n, "ededed")})
        except urllib.error.HTTPError as e:
            if e.code != 422:  # 422 = already exists
                raise


def task_labels(t, epic_title):
    kind = re.sub(r"[^a-z]+", "-", (epic_title or "").lower()).strip("-")
    labels = [f"size:{t.get('size', 'S')}"]
    labels.append(kind if kind in ("engine", "dashboard") else "project")
    return labels


def ensure_task_issue(t, epic_title=""):
    """Create the GitHub issue for a task (idempotent). Mutates t['issue']."""
    if not enabled():
        return None
    if str(t.get("issue") or "").strip():
        return t["issue"]
    labels = task_labels(t, epic_title)
    ensure_labels(labels)
    body = (f"**Task** `{t['id']}` · size {t.get('size', '?')} · epic {epic_title or t.get('epic', '?')}\n\n"
            f"**Acceptance**\n{t.get('acceptance') or '—'}\n\n"
            f"_Filed automatically by the CreativeWorld engine._")
    issue = api("POST", f"/repos/{repo_path()}/issues",
                {"title": f"[{t['id']}] {t['title']}", "body": body, "labels": labels})
    t["issue"] = str(issue["number"])
    return t["issue"]


def close_task_issue(t, comment=None):
    """Close a task's issue with an optional comment. Safe no-op without one."""
    if not enabled() or not str(t.get("issue") or "").strip():
        return False
    n = str(t["issue"]).lstrip("#")
    if comment:
        api("POST", f"/repos/{repo_path()}/issues/{n}/comments", {"body": comment})
    api("PATCH", f"/repos/{repo_path()}/issues/{n}",
        {"state": "closed", "state_reason": "completed"})
    return True


def ship_comment(t):
    """Close-comment linking the real commit that shipped the task, if pushed."""
    sha = lib.commits_by_task().get(t["id"])
    base = lib.repo_url()
    if sha and base:
        return f"Shipped in {base}/commit/{sha}."
    return "Shipped (commit link lands on next push)."


def pull(b):
    """GitHub -> board: issue closed there marks the task done; size-label edits
    update the task's size. Board wins conflicts: a task actively claimed
    (in_progress) is never auto-closed from GitHub. Returns list of changes."""
    if not enabled():
        return []
    changed = []
    for t in b["tasks"]:
        iss = str(t.get("issue") or "").strip()
        if not iss or t["status"] == "done":
            continue
        try:
            info = api("GET", f"/repos/{repo_path()}/issues/{iss}")
        except Exception:
            continue  # offline / deleted issue — board stays the truth
        for lb in (l["name"] for l in info.get("labels", [])):
            if lb.startswith("size:") and lb[5:] in ("S", "M", "L") and lb[5:] != t.get("size"):
                t["size"] = lb[5:]
                changed.append(f"{t['id']}: size -> {t['size']} (GitHub label)")
        if info.get("state") == "closed":
            if t["status"] == "in_progress":
                changed.append(f"{t['id']}: issue #{iss} closed on GitHub but task is claimed — board wins")
            else:
                t["status"] = "done"
                changed.append(f"{t['id']}: -> done (issue #{iss} closed on GitHub)")
    return changed


def sync():
    """Backfill: open tasks get real issues; done tasks with issues get closed."""
    if not enabled():
        print("github sync disabled (no token or remote)")
        return
    b = lib.load("backlog.json")
    for c in pull(b):  # GitHub -> board first, so backfill sees fresh statuses
        print("  " + c)
    epics = {e["id"]: e["title"] for e in b["epics"]}
    made = closed = 0
    for t in b["tasks"]:
        try:
            if t["status"] in ("next", "in_progress", "review") and not t.get("issue"):
                ensure_task_issue(t, epics.get(t["epic"], t["epic"]))
                print(f"  opened #{t['issue']} for {t['id']}: {t['title']}")
                made += 1
            elif t["status"] == "done" and t.get("issue"):
                info = api("GET", f"/repos/{repo_path()}/issues/{str(t['issue']).lstrip('#')}")
                if info.get("state") == "open":
                    close_task_issue(t, ship_comment(t))
                    print(f"  closed #{t['issue']} for {t['id']}")
                    closed += 1
        except Exception as e:
            print(f"  ! {t['id']}: {e}")
    lib.save("backlog.json", b)
    print(f"sync done: {made} opened, {closed} closed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        sync()
    else:
        print(__doc__)
