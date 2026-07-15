#!/usr/bin/env python3
"""Engine smoke test — run before committing engine changes. Exit 0 = safe.

Exercises the board lifecycle (epic -> task -> claim -> done -> queue sync),
atomic save + state lock, and budget math, all on a throwaway STATE dir.
Zero network: GitHub sync and transcript scans are stubbed out.
"""
import contextlib
import io
import shutil
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib  # noqa: E402


def run_brief(board):
    """Run `board.py brief` against the temp state dir, return its stdout."""
    out, argv = io.StringIO(), sys.argv
    sys.argv = ["board.py", "brief"]
    try:
        with contextlib.redirect_stdout(out):
            board.main()
    finally:
        sys.argv = argv
    return out.getvalue()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="cw-test-"))
    real_state, real_lock, real_usage = lib.STATE, lib.LOCK, lib.total_usage
    real_scan, real_now = lib.scan_transcripts, lib.now
    lib.STATE, lib.LOCK = tmp, tmp / ".engine.lock"
    lib.total_usage = lambda: 0          # no transcript scan in tests
    import board
    board.gh_safe = lambda *a, **kw: None  # no GitHub in tests
    try:
        lib.save("queue.json", {"in_progress": None, "next": [], "note": ""})
        b = {"next_ids": {"task": 1, "epic": 1}, "tasks": [], "epics": []}
        lib.save("backlog.json", b)

        # lifecycle: epic -> task -> in_progress -> done, queue stays in sync
        e = board.create_epic(b, "project", "Test Epic", "desc", slug="test-epic")
        t = board.create_task(b, e["id"], "S", "Test task", "does a thing",
                              status="next", top=True)
        assert lib.load("queue.json")["next"] == [t["id"]], "task not queued"
        board.update_task(b, t["id"], status="in_progress")
        assert lib.load("queue.json")["in_progress"] == t["id"], "claim not synced"
        board.update_task(b, t["id"], status="done", handoff="ok")
        b2 = lib.load("backlog.json")
        assert b2["tasks"][0]["status"] == "done", "done not persisted"
        q = lib.load("queue.json")
        assert q["in_progress"] is None and q["next"] == [], "queue not cleared"

        # lock: acquires, releases, cleans up its file
        with lib.state_lock():
            lib.save("backlog.json", b2)
        assert not lib.LOCK.exists(), "lockfile leaked"

        # budget math + verdict thresholds
        w = {"input": 1, "output": 5, "cache_write": 1.25, "cache_read": 0.1}
        assert lib.weighted({"input_tokens": 10, "output_tokens": 2}, w) == 20
        tk = {"config": {"budget_per_window": 100, "wrap_up_pct": 85, "stop_pct": 95,
                         "window_hours": 5},
              "window": {"started_at": None, "by_session": {"a": 96}}}
        s = lib.budget_summary(tk)
        assert s["pct"] == 96.0 and lib.verdict(s)[0] == "STOP"
        assert s["rate_per_hour"] is None and s["eta_hours"] is None, "burn rate needs weights"
        s["pct"] = 90.0
        assert lib.verdict(s)[0] == "WRAP_UP"
        s["pct"] = 50.0
        assert lib.verdict(s)[0] == "CONTINUE"

        # brief: burn-rate line + thin-queue WARN + RESUME, on fixture state
        frozen = lib.now()
        lib.now = lambda: frozen         # exact burn-rate math, no clock drift
        started = frozen - timedelta(hours=2)
        lib.scan_transcripts = lambda weights, since=None: ({"s1": 100000}, started, started)
        lib.save("tokens.json", {
            "config": {"budget_per_window": 1000000, "wrap_up_pct": 85,
                       "stop_pct": 95, "window_hours": 5, "weights": w},
            "window": {"started_at": lib.iso(started), "by_session": {}},
            "history": []})
        lib.save("sessions.json", {"sessions": [
            {"did": "test session", "resume_with": "board.py brief"}]})
        t2 = board.create_task(b2, e["id"], "S", "Brief resume task", "shows up",
                               status="next", top=True)
        board.create_task(b2, e["id"], "S", "Queued task", "waits", status="next")
        board.update_task(b2, t2["id"], status="in_progress", handoff="mid-way")
        out = run_brief(board)
        assert "budget: CONTINUE 10.0%" in out, f"bad verdict line:\n{out}"
        assert "burn: 50,000 tok/h (trailing 5h)" in out, f"no burn line:\n{out}"
        assert "cap in ~18.0h" in out, f"bad eta:\n{out}"
        assert f"RESUME {t2['id']} [S]" in out and "handoff: mid-way" in out, \
            f"no resume block:\n{out}"
        assert "queue: 1 task(s) in next" in out and "WARN: queue thin" in out, \
            f"no thin-queue warn:\n{out}"
        assert "last session: test session" in out, f"no session line:\n{out}"

        # brief: deep queue drops the WARN, empty claim hint, no burn w/o weights
        board.update_task(b2, t2["id"], status="done")
        for i in range(4):
            board.create_task(b2, e["id"], "S", f"Filler {i}", "queued", status="next")
        tk2 = lib.load("tokens.json")
        tk2["config"]["weights"] = {}    # no transcript access -> no burn line
        lib.save("tokens.json", tk2)
        out = run_brief(board)
        assert "burn:" not in out, f"burn line without weights:\n{out}"
        assert "no task in progress" in out, f"missing claim hint:\n{out}"
        assert "queue: 5 task(s) in next" in out and "WARN" not in out, \
            f"unexpected warn on deep queue:\n{out}"

        print("engine smoke test: OK")
    finally:
        lib.STATE, lib.LOCK, lib.total_usage = real_state, real_lock, real_usage
        lib.scan_transcripts, lib.now = real_scan, real_now
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
