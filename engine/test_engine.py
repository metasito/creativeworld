#!/usr/bin/env python3
"""Engine smoke test — run before committing engine changes. Exit 0 = safe.

Exercises the board lifecycle (epic -> task -> claim -> done -> queue sync),
atomic save + state lock, and budget math, all on a throwaway STATE dir.
Zero network: GitHub sync and transcript scans are stubbed out.
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib  # noqa: E402


def main():
    tmp = Path(tempfile.mkdtemp(prefix="cw-test-"))
    real_state, real_lock, real_usage = lib.STATE, lib.LOCK, lib.total_usage
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

        print("engine smoke test: OK")
    finally:
        lib.STATE, lib.LOCK, lib.total_usage = real_state, real_lock, real_usage
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
