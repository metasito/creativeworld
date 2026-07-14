#!/usr/bin/env python3
"""Update state/tokens.json from live transcripts and print a budget summary.

Usage:
  track_tokens.py               # scan, persist, print summary
  track_tokens.py --limit-hit   # a real rate-limit was hit: calibrate budget down to actual usage
"""
import json
import sys

import lib


def main():
    tokens = lib.load("tokens.json")
    lib.update_from_transcripts(tokens)
    summary = lib.budget_summary(tokens)

    if "--limit-hit" in sys.argv:
        cfg = tokens["config"]
        tokens["calibration"]["limit_hits"].append({
            "at": lib.iso(lib.now()),
            "window_used": summary["used"],
            "old_budget": cfg["budget_per_window"],
        })
        if summary["used"] > 0:
            cfg["budget_per_window"] = summary["used"]  # the real ceiling is what we actually spent
        summary = lib.budget_summary(tokens)

    lib.save("tokens.json", tokens)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
