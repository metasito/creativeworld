#!/usr/bin/env python3
"""Budget verdict. Exit 0=CONTINUE, 3=WRAP_UP, 4=STOP.

Usage:
  budget_check.py               # live: scan transcripts, persist, verdict
  budget_check.py --preflight   # CI gate: committed tokens.json only, no transcript scan
"""
import json
import sys

import lib


def main():
    preflight = "--preflight" in sys.argv
    tokens = lib.load("tokens.json")
    if preflight:
        if lib.roll_window_if_expired(tokens):
            print(json.dumps({"verdict": "CONTINUE", "reason": "window reset"}))
            sys.exit(0)
    else:
        lib.update_from_transcripts(tokens)
        lib.save("tokens.json", tokens)
    summary = lib.budget_summary(tokens)
    name, code = lib.verdict(summary)
    print(json.dumps({"verdict": name, **summary}))
    sys.exit(code)


if __name__ == "__main__":
    main()
