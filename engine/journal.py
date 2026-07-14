#!/usr/bin/env python3
"""Append a session entry to state/sessions.json. Zero LLM tokens.

Usage:
  journal.py start "what this session is doing"
  journal.py end "what shipped" --because "budget 95%" --resume "board.py brief; T13 next"
"""
import sys

import lib


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("start", "end"):
        sys.exit(__doc__)
    data = lib.load("sessions.json")
    sessions = data["sessions"]

    def opt(flag, default=""):
        return args[args.index(flag) + 1] if flag in args else default

    if args[0] == "start":
        sessions.append({"started": lib.iso(lib.now()), "ended": None, "did": args[1],
                         "stopped_because": None, "resume_with": ""})
        print(f"journal: session #{len(sessions)} started")
    else:
        last = sessions[-1]
        if last.get("ended"):  # no open session — file a closed one rather than clobbering
            sessions.append({"started": lib.iso(lib.now()), "ended": None, "did": "", "stopped_because": None, "resume_with": ""})
            last = sessions[-1]
        last["ended"] = lib.iso(lib.now())
        last["did"] = args[1]
        last["stopped_because"] = opt("--because", "session end")
        last["resume_with"] = opt("--resume", "python3 engine/board.py brief")
        print("journal: session closed")

    data["sessions"] = sessions[-50:]
    lib.save("sessions.json", data)


if __name__ == "__main__":
    main()
