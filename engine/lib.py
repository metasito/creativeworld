"""Shared helpers for the CreativeWorld engine. Stdlib only."""
import contextlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"

# Known headless-capable browsers, first hit wins. Override with $BROWSER.
BROWSER_CANDIDATES = [
    "/opt/pw-browsers/chromium",                                      # cloud container
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",         # windows chrome
    str(Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",  # windows edge
    "/usr/bin/chromium-browser", "/usr/bin/chromium", "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",   # macOS
]


def browser_path():
    """Path to a headless-capable browser on THIS machine, or None.

    $BROWSER wins if set; otherwise first existing candidate. Central so
    drive.py / shot.py / skills stay platform-agnostic (cloud vs Windows vs mac).
    """
    env = os.environ.get("BROWSER")
    if env and Path(env).exists():
        return env
    for p in BROWSER_CANDIDATES:
        if Path(p).exists():
            return p
    return None
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


LOCK = STATE / ".engine.lock"


@contextlib.contextmanager
def state_lock(timeout=10.0, stale=60.0):
    """Cross-process mutex for read-modify-write on state files.

    Multiple agents (interactive session + autopilot + dashboard server) mutate
    the same JSON; without this, two concurrent claims/saves lose updates.
    O_EXCL lockfile with retry; locks older than `stale` seconds are broken
    (a crashed holder must not deadlock the engine forever)."""
    deadline = time.time() + timeout
    fd = None
    while fd is None:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - LOCK.stat().st_mtime > stale:
                    LOCK.unlink()
                    continue
            if time.time() > deadline:
                raise TimeoutError(f"state lock busy > {timeout}s: {LOCK}")
            time.sleep(0.1)
    try:
        yield
    finally:
        os.close(fd)
        with contextlib.suppress(OSError):
            LOCK.unlink()


def load(name):
    return json.loads((STATE / name).read_text(encoding="utf-8"))


def save(name, data):
    """Atomic write: tmp file + os.replace, so a reader/crash never sees a torn file."""
    path = STATE / name
    tmp = path.parent / f"{path.name}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for _ in range(40):  # Windows: replace can briefly fail while a reader has it open
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


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
    """Return ({session_id: weighted_total}, earliest_usage_dt, earliest_in_span_dt).

    earliest is across ALL usage; earliest_in_span is the oldest usage that
    passed the `since` filter (drives the rolling-window reset estimate).
    Dedupes by message id (streaming rewrites the same message with growing
    usage), keeping the max weighted value per id.
    """
    per_session = {}
    earliest = in_span = None
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
            if in_span is None or dt < in_span:
                in_span = dt
            mid = msg.get("id") or ts
            by_msg[mid] = max(by_msg.get(mid, 0), weighted(usage, weights))
        if by_msg:
            per_session[f.stem] = round(sum(by_msg.values()))
    return per_session, earliest, in_span


def total_usage():
    """All-time weighted usage across this project's transcripts. Monotonic, so
    task cost = total_at_done - total_at_claim survives window rolls. With two
    agents working at once the bystander's tokens bleed in — treat as ceiling."""
    tokens = load("tokens.json")
    per_session, _, _ = scan_transcripts(tokens["config"]["weights"])
    return round(sum(per_session.values()))


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
    per_session, earliest, _ = scan_transcripts(weights, since=since)
    if win.get("started_at") is None:
        # Window starts at the first usage seen after the previous window ended.
        not_before = parse_iso(win["not_before"]) if win.get("not_before") else None
        start = earliest if earliest else now()
        if not_before and start < not_before:
            start = not_before
        win["started_at"] = iso(start)
        per_session, _, _ = scan_transcripts(weights, since=parse_iso(win["started_at"]))
    by = win.setdefault("by_session", {})
    for sid, total in per_session.items():
        by[sid] = max(by.get(sid, 0), total)  # max: recounts never shrink, other containers' entries survive
    calibrate_floor_from_history(tokens)
    return tokens


def calibrate_floor_from_history(tokens):
    """Budget can never be below usage we PROVED achievable: any past window that
    spent more than the budget WITHOUT a real limit hit shows the true ceiling is
    at least that spend. Idempotent; runs on every transcript update."""
    cfg = tokens["config"]
    floor = max((h["used"] for h in tokens.get("history", [])
                 if not h.get("limit_hit")), default=0)
    if floor > cfg["budget_per_window"]:
        old = cfg["budget_per_window"]
        cfg["budget_per_window"] = floor
        tokens.setdefault("calibration", {}).setdefault("notes", []).append(
            f"{iso(now())}: auto-raised budget {old} -> {floor} "
            "(a past window overran it with no real limit hit)")
    return tokens


def burn_series(weights, window_hours, buckets=12):
    """Weighted usage bucketed into `buckets` equal time slices over the trailing
    window_hours (oldest first). Feeds the budget-panel burn sparkline. Dedupes by
    message id (streaming rewrites the same message) keeping the max per id; a
    message's timestamp is constant across rewrites so its bucket never moves."""
    span_start = now() - timedelta(hours=window_hours)
    slice_s = window_hours * 3600.0 / buckets
    sums = [0.0] * buckets
    root = project_transcript_dir()
    files = root.glob("*.jsonl") if root else TRANSCRIPTS.glob("*/*.jsonl")
    for f in files:
        by_mid = {}
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
            if dt < span_start:
                continue
            idx = min(max(int((dt - span_start).total_seconds() // slice_s), 0), buckets - 1)
            mid = msg.get("id") or ts
            w = weighted(usage, weights)
            cur = by_mid.get(mid)
            if cur is None or w > cur[1]:
                by_mid[mid] = (idx, w)
        for idx, w in by_mid.values():
            sums[idx] += w
    return [round(s) for s in sums]


def budget_summary(tokens):
    """Budget verdict input. The REAL subscription cap behaves like a trailing
    window, so `used` is the max of (a) the anchored engine window — keeps
    history/bars meaningful — and (b) the TRAILING window_hours sum over
    transcripts, which is boundary-drift-proof (see the 04:22Z incident where
    an anchored 'fresh' window showed 457k while the true session was 5x in).
    """
    cfg = tokens["config"]
    win_used = round(sum(tokens["window"].get("by_session", {}).values()))
    used, roll_used, roll_end = win_used, None, None
    rate, eta_h, spark = None, None, None
    if cfg.get("weights"):  # rolling needs transcript access (tests may omit it)
        span_start = now() - timedelta(hours=cfg["window_hours"])
        per, _, first_in = scan_transcripts(cfg["weights"], since=span_start)
        roll_used = round(sum(per.values()))
        spark = burn_series(cfg["weights"], cfg["window_hours"])
        if first_in:
            roll_end = first_in + timedelta(hours=cfg["window_hours"])
            hours = max((now() - first_in).total_seconds() / 3600.0, 0.1)
            rate = round(roll_used / hours)
        used = max(win_used, roll_used)
    budget = cfg["budget_per_window"]
    if rate and used < budget:
        eta_h = round((budget - used) / rate, 1)
    pct = 100.0 * used / budget if budget else 0.0
    binding = "trailing" if (roll_used is not None and roll_used > win_used) else "window"
    # Displayed reset = the anchored engine window end (started_at + window_hours):
    # a STABLE, counting-DOWN target that by_session actually clears at. The old code
    # showed roll_end (oldest-trailing-msg + window_hours) here, but that oldest msg
    # slides forward as it ages out, so resets_at was pinned to ~now and never counted
    # down — which made the whole panel look broken.
    end = window_end(tokens)
    # Nap target is separate: when the TRAILING measure is binding, relief comes as
    # the oldest spend ages out of the trailing window (roll_end), not at the anchored
    # reset. Kept apart so display stays honest while naps track the real constraint.
    nap_end = roll_end if (binding == "trailing" and roll_end) else end
    return {
        "used": used,
        "window_used": win_used,
        "rolling_used": roll_used,
        "binding": binding,
        "budget": budget,
        "pct": round(pct, 1),
        "rate_per_hour": rate,
        "eta_hours": eta_h,
        "burn_spark": spark,
        "window_started_at": tokens["window"].get("started_at"),
        "resets_at": iso(end) if end else None,
        "seconds_to_reset": max(0, int((end - now()).total_seconds())) if end else None,
        "nap_until": iso(nap_end) if nap_end else None,
        "nap_seconds": max(0, int((nap_end - now()).total_seconds())) if nap_end else None,
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
