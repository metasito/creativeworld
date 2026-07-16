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
from datetime import timedelta

import heartbeat
import lib
import probe_limit

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


def run_agent(dry):
    """Launch one headless agent cycle. Returns (returncode, output_tail).

    The output is captured (and echoed live) so we can detect the real usage
    limit the Claude CLI prints when the subscription window is exhausted.
    """
    if dry:
        print("[dry-run] would launch:", CLAUDE, "-p <prompt>")
        time.sleep(1)
        return 0, ""
    # headless + unattended: the loop needs git/python/chrome with no prompts, so it
    # runs with skipped permissions inside this repo. Only run autopilot on a repo you trust.
    cmd = [CLAUDE, "-p", PROMPT, "--dangerously-skip-permissions", "--max-turns", "120"]
    try:
        proc = subprocess.Popen(cmd, cwd=str(lib.ROOT), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
    except FileNotFoundError:
        sys.exit("claude CLI not found on PATH — install it or add to PATH")
    lines = []
    for line in proc.stdout:  # tee: keep it visible AND scannable for a limit message
        sys.stdout.write(line)
        sys.stdout.flush()
        lines.append(line)
    proc.wait()
    return proc.returncode, "".join(lines[-500:])


def nap(until_dt, label, once):
    """Sleep until until_dt (re-checking at most hourly). Returns False if --once."""
    secs = max(60, int((until_dt - lib.now()).total_seconds()) + 60)  # +60s safety buffer
    set_status("napping", f"{label} — waking {lib.iso(until_dt)} (~{secs // 60}m)")
    print(f"napping {secs}s until {lib.iso(until_dt)} — {label}")
    if once:
        return False
    time.sleep(min(secs, 3600))
    return True


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
        # 0. Dashboard kill-switch: honor a "stop" flag before spending anything.
        if lib.control().get("autopilot") == "stop":
            set_status("paused", "stopped from dashboard — waiting for Start")
            print("autopilot paused (dashboard flag) — re-checking in 30s")
            if once:
                break
            time.sleep(30)
            continue

        tokens = lib.load("tokens.json")
        lib.update_from_transcripts(tokens)
        lib.save("tokens.json", tokens)
        s = lib.budget_summary(tokens)

        # 1. Hard gate: a real limit hit set not_before — never resume before it.
        nb = tokens["window"].get("not_before")
        if nb and lib.now() < lib.parse_iso(nb):
            if not nap(lib.parse_iso(nb), f"limit cooldown {s['pct']}%", once):
                break
            continue

        # 2. Soft gate: the (estimated) budget says wrap up / stop for this window.
        #    STOP is only an estimate — probe reality before napping on it: if
        #    claude still answers, the budget was false (probe recalibrates it up
        #    and we keep working); if a real limit answers, not_before is set and
        #    the hard gate above naps until the true reset.
        name, _ = lib.verdict(s)
        if name == "STOP" and not dry:
            status, detail = probe_limit.probe_and_calibrate()
            _run_heartbeat(["log", f"STOP estimate probed: {status} — {detail}"])
            print(f"STOP estimate probed: {status} — {detail}")
            if status in ("ok", "limit"):
                continue
        if name != "CONTINUE":
            nap_at = s.get("nap_until") or s.get("resets_at")
            reset = lib.parse_iso(nap_at) if nap_at else lib.now() + timedelta(hours=1)
            if not nap(reset, f"budget {name} {s['pct']}%", once):
                break
            continue

        # 3. Work one cycle, then let the REAL CLI limit be authoritative.
        set_status("working", f"budget {s['pct']}% — launching agent")
        print(f"budget CONTINUE {s['pct']}% — launching agent")
        rc, out = run_agent(dry)
        _run_heartbeat(["log", "agent cycle finished"])

        reset = lib.parse_reset_time(out)
        if lib.looks_like_limit(out) or (rc != 0 and reset):
            tokens = lib.load("tokens.json")
            lib.update_from_transcripts(tokens)
            if reset is None:  # limit hit but no timestamp — over-nap one window, re-check
                reset = lib.now() + timedelta(hours=tokens["config"]["window_hours"])
            lib.record_limit_hit(tokens, reset)
            lib.save("tokens.json", tokens)
            _run_heartbeat(["log", f"REAL usage limit hit — napping until {lib.iso(reset)}"])
            print(f"LIMIT HIT — napping until {lib.iso(reset)}")
            if not nap(reset, "real usage limit", once):
                break
            continue

        if rc != 0:  # non-limit failure: brief backoff so we don't hot-loop
            print(f"agent exited {rc} (no limit detected) — backing off 120s")
            _run_heartbeat(["log", f"agent error rc={rc} — 120s backoff"])
            if once:
                break
            time.sleep(120)
            continue

        if once:
            break
    set_status("idle")


if __name__ == "__main__":
    main()
