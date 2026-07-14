"""Shared helpers for the CreativeWorld engine. Stdlib only."""
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
TRANSCRIPTS = Path(os.environ.get("CLAUDE_TRANSCRIPTS_DIR", Path.home() / ".claude" / "projects"))


def project_transcript_dir():
    """Transcript folder for THIS project only, or None to scan all (fallback).

    Claude Code names each project's transcript dir after its cwd with every
    non-alphanumeric char turned into '-' (e.g. C:\\Users\\me\\creativeworld ->
    C--Users-me-creativeworld). Scoping to it stops OTHER projects' sessions on
    the same machine from being counted against this engine's budget.
    """
    if not TRANSCRIPTS.exists():
        return None
    enc = re.sub(r"[^A-Za-z0-9]", "-", str(ROOT))
    exact = TRANSCRIPTS / enc
    if exact.is_dir():
        return exact
    low = enc.lower()  # drive-letter / cwd casing can differ from when dir was made
    for d in TRANSCRIPTS.iterdir():
        if d.is_dir() and d.name.lower() == low:
            return d
    return None


_REPO_URL = None


def repo_url():
    """Base GitHub URL for this repo (e.g. https://github.com/owner/name), or None.

    Parsed once from `git remote get-url origin`, handling both SSH
    (git@github.com:owner/name.git) and HTTPS remotes. Enables the board to link
    tasks to their GitHub issue/PR like a real team workflow.
    """
    global _REPO_URL
    if _REPO_URL is not None:
        return _REPO_URL or None
    _REPO_URL = ""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT,
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return None
    m = re.search(r"github\.com[:/]+([^/]+)/(.+?)(?:\.git)?/?$", url)
    if m:
        _REPO_URL = f"https://github.com/{m.group(1)}/{m.group(2)}"
    return _REPO_URL or None


_COMMITS_BY_TASK = None


def commits_by_task():
    """{task_id: short_sha} for every task that has a commit, from git history.

    Commits are named `<task-id>: <what shipped>` (see CLAUDE.md), so one git-log
    scan maps each task to the real commit that shipped it. This is what makes the
    dashboard's traceability links REAL — they point at a commit that actually
    exists on the pushed remote, not a placeholder. Newest-first, so the first
    match per id wins (the commit that marked it done). Cached per process.
    """
    global _COMMITS_BY_TASK
    if _COMMITS_BY_TASK is not None:
        return _COMMITS_BY_TASK
    out = {}
    try:
        log = subprocess.run(
            ["git", "log", "--format=%h %s"], cwd=ROOT,
            capture_output=True, text=True, timeout=10).stdout
    except Exception:
        _COMMITS_BY_TASK = out
        return out
    for line in log.splitlines():
        sha, _, subject = line.partition(" ")
        m = re.match(r"(T\d+):", subject)
        if m and m.group(1) not in out:
            out[m.group(1)] = sha
    _COMMITS_BY_TASK = out
    return out


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
    root = project_transcript_dir()
    files = root.glob("*.jsonl") if root else TRANSCRIPTS.glob("*/*.jsonl")
    for f in files:
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


# --- Real usage-limit detection -------------------------------------------
# The authoritative "tokens are out" signal is the Claude CLI itself: when the
# 5h subscription cap is hit it prints a limit message, usually with the exact
# Unix reset time (e.g. "Claude AI usage limit reached|1752604200"). We react to
# THAT instead of guessing from a weighted count vs. an estimated budget.
LIMIT_EPOCH_RE = re.compile(r"usage limit reached[^\d]{0,4}(\d{10,13})", re.I)
LIMIT_ISO_RE = re.compile(r"resets?(?:\s+at)?\s+(\d{4}-\d{2}-\d{2}T[\d:]+Z)", re.I)
LIMIT_HINT_RE = re.compile(
    r"usage limit reached|rate[_\s-]?limit|\b429\b|too many requests|overloaded", re.I)


def looks_like_limit(text):
    """True if agent output shows a real usage/rate limit was hit."""
    return bool(text and LIMIT_HINT_RE.search(text))


def parse_reset_time(text):
    """Extract the exact limit-reset datetime (UTC) from agent output, or None."""
    if not text:
        return None
    m = LIMIT_EPOCH_RE.search(text)
    if m:
        ts = int(m.group(1))
        if ts > 10_000_000_000:  # milliseconds -> seconds
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    m = LIMIT_ISO_RE.search(text)
    if m:
        try:
            return parse_iso(m.group(1))
        except ValueError:
            return None
    return None


def record_limit_hit(tokens, reset_dt):
    """A real usage limit was hit: calibrate the budget estimate down to what we
    actually spent, close the current window, and refuse to resume before
    reset_dt (stored as window.not_before so even a fresh boot waits)."""
    summary = budget_summary(tokens)
    cfg = tokens["config"]
    tokens.setdefault("calibration", {}).setdefault("limit_hits", []).append({
        "at": iso(now()),
        "window_used": summary["used"],
        "old_budget": cfg["budget_per_window"],
        "reset_at": iso(reset_dt) if reset_dt else None,
    })
    if summary["used"] > 0:
        cfg["budget_per_window"] = summary["used"]  # the real ceiling is what we spent
    win = tokens["window"]
    used = round(sum(win.get("by_session", {}).values()))
    tokens.setdefault("history", []).append({
        "started_at": win.get("started_at"),
        "used": used,
        "budget": cfg["budget_per_window"],
        "limit_hit": True,
    })
    tokens["history"] = tokens["history"][-50:]
    tokens["window"] = {"started_at": None, "by_session": {},
                        "not_before": iso(reset_dt) if reset_dt else None}
    return tokens
