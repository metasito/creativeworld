#!/usr/bin/env python3
"""Autopilot — the always-on autonomous worker. Invests all available tokens.

Loop:
  1. Budget check (free). If tokens available -> launch a headless Claude agent
     that boots, works ONE task, verifies, commits+pushes.
  2. If budget spent -> nap until the window resets, then resume.
Writes a live heartbeat (state/activity.json) the dashboard shows in real time.

Run once and leave it:
  python engine/autopilot.py                 # forever
  python engine/autopilot.py --once          # a single cycle (for testing)
  python engine/autopilot.py --dry-run       # never call claude; simulate

Requires the `claude` CLI on PATH (headless mode).
"""
import shutil
import subprocess
import sys
import time

import heartbeat
import lib

CLAUDE = shutil.which("claude") or "claude"
PROMPT = (
    "You are the CreativeWorld autopilot agent, running headless with no user. "
    "Invoke the boot skill and work exactly ONE task from the queue per CLAUDE.md: "
    "claim it, build it, verify it for real, then run the checkpoint "
    "(board.py done, track_tokens, build_dashboard) and commit+push. "
    "Use engine/heartbeat.py to report status: at start `heartbeat.py status working "
    "--task <id> --action <what> --agent autopilot`, log key steps with `heartbeat.py log`, "
    "and if budget_check says WRAP_UP/STOP invoke the wrap-up skill and finish. "
    "Keep it token-cheap. Do not start a second task."
)


def budget_state():
    tokens = lib.load("tokens.json")
    lib.update_from_transcripts(tokens)
    lib.save("tokens.json", tokens)
    s = lib.budget_summary(tokens)
    name, _ = lib.verdict(s)
    return name, s


def run_agent(dry):
    if dry:
        heartbeat.main_noargs = None
        print("[dry-run] would launch:", CLAUDE, "-p <prompt>")
        time.sleep(1)
        return 0
    # headless + unattended: the loop needs git/python/chrome with no prompts, so it
    # runs with skipped permissions inside this repo. Only run autopilot on a repo you trust.
    cmd = [CLAUDE, "-p", PROMPT, "--dangerously-skip-permissions", "--max-turns", "120"]
    try:
        return subprocess.run(cmd, cwd=str(lib.ROOT)).returncode
    except FileNotFoundError:
        sys.exit("claude CLI not found on PATH — install it or add to PATH")


def set_status(status, action=None):
    argv = ["status", status, "--agent", "autopilot"]
    if action:
        argv += ["--action", action]
    _run_heartbeat(argv)


def _run_heartbeat(argv):
    old = sys.argv
    sys.argv = ["heartbeat.py"] + argv
    try:
        heartbeat.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old


def main():
    once = "--once" in sys.argv
    dry = "--dry-run" in sys.argv
    print(f"autopilot up · claude={CLAUDE} · once={once} dry={dry}")
    while True:
        name, s = budget_state()
        if name == "CONTINUE":
            set_status("working", f"budget {s['pct']}% — launching agent")
            print(f"budget CONTINUE {s['pct']}% — launching agent")
            run_agent(dry)
            _run_heartbeat(["log", "agent cycle finished"])
        else:
            secs = (s.get("seconds_to_reset") or 300) + 30
            set_status("napping", f"budget {name} {s['pct']}% — napping ~{secs//60}m until reset")
            print(f"budget {name} {s['pct']}% — napping {secs}s until reset {s['resets_at']}")
            if once:
                break
            time.sleep(min(secs, 1800))
            continue
        if once:
            break
    set_status("idle")


if __name__ == "__main__":
    main()
