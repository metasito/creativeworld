#!/usr/bin/env python3
"""One-shot per-task checkpoint: close a task, refresh tokens + dashboard, print the budget verdict.

Collapses the four-command checkpoint (board.py done -> track_tokens.py ->
build_dashboard.py -> budget_check.py) into a SINGLE command. That is one Python
start-up and one tool round-trip instead of four, and the transcript is scanned
once for the whole checkpoint instead of once per script — the cheapest way to
close out a task. Commit stays separate (it needs a message).

Usage:
  checkpoint.py <task-id> [ship note...]   # done + refresh + verdict
  checkpoint.py --no-done                  # unfinished task: just refresh + verdict

Exit code mirrors budget_check.py: 0=CONTINUE, 3=WRAP_UP, 4=STOP.
"""
import json
import sys

import lib
import board
import build_dashboard


def _write_dashboard():
    data = build_dashboard.compose(live=False)  # state on disk is already fresh
    out = lib.ROOT / "dashboard" / "data.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    args = [a for a in sys.argv[1:] if a != "--no-done"]
    do_done = "--no-done" not in sys.argv[1:]

    # One transcript scan for the whole checkpoint; persist so downstream reads agree.
    tokens = lib.load("tokens.json")
    lib.update_from_transcripts(tokens)
    lib.save("tokens.json", tokens)

    if do_done:
        if not args:
            sys.exit("usage: checkpoint.py <task-id> [ship note...]")
        tid, note = args[0], " ".join(args[1:])
        b = lib.load("backlog.json")
        t = board.update_task(b, tid, status="done", handoff=note)
        if t.get("cost"):
            print(f"done {tid} · cost ~{t['cost']:,} weighted tokens [{t['size']}]")
        else:
            print(f"done {tid}")
        if t.get("issue"):
            print(f"  commit with: {tid}: <what shipped> (closes #{t['issue']})")

    _write_dashboard()

    summary = lib.budget_summary(lib.load("tokens.json"))
    name, code = lib.verdict(summary)
    print(f"budget: {name} {summary['pct']}% of {summary['budget']} · resets {summary['resets_at']}")
    if summary.get("rate_per_hour"):
        eta = (f" · cap in ~{summary['eta_hours']}h" if summary.get("eta_hours") is not None
               else " · over cap")
        print(f"burn: {summary['rate_per_hour']:,} tok/h{eta}")
    sys.exit(code)


if __name__ == "__main__":
    main()
