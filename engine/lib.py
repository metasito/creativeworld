"""Shared helpers for the CreativeWorld engine. Stdlib only."""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
TRANSCRIPTS = Path(os.environ.get("CLAUDE_TRANSCRIPTS_DIR", Path.home() / ".claude" / "projects"))


def load(name):
    return json.loads((STATE / name).read_text(encoding="utf-8"))


def save(name, data):
    (STATE / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def weighted(usage, weights):
    return (
        usage.get("input_tokens", 0) * weights["input"]
        + usage.get("output_tokens", 0) * weights["output"]
        + usage.get("cache_creation_input_tokens", 0) * weights["cache_write"]
        + usage.get("cache_read_input_tokens", 0) * weights["cache_read"]
    )


def scan_transcripts(weights, since=None):
    """Return ({session_id: weighted_total}, earliest_usage_dt).

    Dedupes by message id (streaming rewrites the same message with growing
    usage), keeping the max weighted value per id.
    """
    per_session = {}
    earliest = None
    for f in TRANSCRIPTS.glob("*/*.jsonl"):
        by_msg = {}
        for line in f.open(encoding="utf-8"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message") or {}
            usage = msg.get("usage")
            ts = d.get("timestamp")
            if not usage or not ts:
                continue
            dt = parse_iso(ts)
            if earliest is None or dt < earliest:
                earliest = dt
            if since and dt < since:
                continue
            mid = msg.get("id") or ts
            by_msg[mid] = max(by_msg.get(mid, 0), weighted(usage, weights))
        if by_msg:
            per_session[f.stem] = round(sum(by_msg.values()))
    return per_session, earliest


def window_end(tokens):
    started = tokens["window"].get("started_at")
    if not started:
        return None
    return parse_iso(started) + timedelta(hours=tokens["config"]["window_hours"])


def roll_window_if_expired(tokens):
    """If the 5h window has passed, archive it to history and reset. Returns True if rolled."""
    end = window_end(tokens)
    if end is None or now() < end:
        return False
    win = tokens["window"]
    used = sum(win.get("by_session", {}).values())
    tokens["history"].append({
        "started_at": win["started_at"],
        "used": round(used),
        "budget": tokens["config"]["budget_per_window"],
    })
    tokens["history"] = tokens["history"][-50:]
    tokens["window"] = {"started_at": None, "by_session": {}, "not_before": iso(end)}
    return True


def update_from_transcripts(tokens):
    """Merge live transcript usage into tokens['window']. Mutates tokens."""
    roll_window_if_expired(tokens)
    win = tokens["window"]
    weights = tokens["config"]["weights"]
    since = parse_iso(win["started_at"]) if win.get("started_at") else None
    per_session, earliest = scan_transcripts(weights, since=since)
    if win.get("started_at") is None:
        # Window starts at the first usage seen after the previous window ended.
        not_before = parse_iso(win["not_before"]) if win.get("not_before") else None
        start = earliest if earliest else now()
        if not_before and start < not_before:
            start = not_before
        win["started_at"] = iso(start)
        per_session, _ = scan_transcripts(weights, since=parse_iso(win["started_at"]))
    by = win.setdefault("by_session", {})
    for sid, total in per_session.items():
        by[sid] = max(by.get(sid, 0), total)  # max: recounts never shrink, other containers' entries survive
    return tokens


def budget_summary(tokens):
    cfg = tokens["config"]
    used = round(sum(tokens["window"].get("by_session", {}).values()))
    budget = cfg["budget_per_window"]
    pct = 100.0 * used / budget if budget else 0.0
    end = window_end(tokens)
    return {
        "used": used,
        "budget": budget,
        "pct": round(pct, 1),
        "window_started_at": tokens["window"].get("started_at"),
        "resets_at": iso(end) if end else None,
        "seconds_to_reset": max(0, int((end - now()).total_seconds())) if end else None,
        "wrap_up_pct": cfg["wrap_up_pct"],
        "stop_pct": cfg["stop_pct"],
    }


def verdict(summary):
    if summary["pct"] >= summary["stop_pct"]:
        return "STOP", 4
    if summary["pct"] >= summary["wrap_up_pct"]:
        return "WRAP_UP", 3
    return "CONTINUE", 0
