#!/usr/bin/env python3
"""Reality-check the budget estimate by ACTUALLY calling claude.

The weighted-token budget is a guess; the authoritative signal is the CLI
itself. When the estimate says STOP, one tiny haiku call settles it:
  - call works  -> the estimate was false; raise budget so work continues
  - limit error -> record the real hit + reset time (window.not_before)

Usage:  probe_limit.py
Exit:   0 = claude works, 4 = real limit hit, 2 = inconclusive (CLI error)
"""
import json
import shutil
import subprocess
import sys

import lib


def probe_and_calibrate():
    """Probe claude once and calibrate tokens.json from the result.

    Returns ('ok'|'limit'|'error', detail). Saves tokens.json on ok/limit.
    """
    claude = shutil.which("claude") or "claude"
    try:
        p = subprocess.run(
            [claude, "-p", "Reply with exactly: ok", "--model", "haiku"],
            cwd=str(lib.ROOT), capture_output=True, text=True, timeout=180)
        out = (p.stdout or "") + (p.stderr or "")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return "error", str(e)

    tokens = lib.load("tokens.json")
    lib.update_from_transcripts(tokens)

    if lib.looks_like_limit(out):
        reset = lib.parse_reset_time(out)
        lib.record_limit_hit(tokens, reset)
        lib.save("tokens.json", tokens)
        return "limit", lib.iso(reset) if reset else "no reset time in output"
    if p.returncode != 0:  # broken CLI/network, not a limit — don't calibrate
        return "error", f"rc={p.returncode}: {out[-200:].strip()}"

    s = lib.budget_summary(tokens)
    if s["pct"] >= s["stop_pct"]:
        # Still working at "STOP" — the budget is provably too low. Raise it so
        # usage lands just under the wrap-up line: the verdict flips back to
        # CONTINUE, work resumes, and the next STOP crossing probes again. Near
        # the ceiling the REAL CLI answer drives, and an actual limit hit
        # re-clamps the budget down to true spend (record_limit_hit).
        cfg = tokens["config"]
        old = cfg["budget_per_window"]
        cfg["budget_per_window"] = round(s["used"] * 100.0 / (s["wrap_up_pct"] - 1))
        tokens.setdefault("calibration", {}).setdefault("notes", []).append(
            f"{lib.iso(lib.now())}: probe OK at {s['pct']}% — "
            f"raised budget {old} -> {cfg['budget_per_window']}")
    lib.save("tokens.json", tokens)
    return "ok", f"claude answered at {s['pct']}% of budget"


def main():
    status, detail = probe_and_calibrate()
    print(json.dumps({"probe": status, "detail": detail}))
    sys.exit({"ok": 0, "limit": 4}.get(status, 2))


if __name__ == "__main__":
    main()
