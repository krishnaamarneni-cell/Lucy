"""
Lucy's ambient awareness.

get_world_state() returns a dict of everything Lucy should know about
her current situation. This gets passed into every LLM call so she can
respond with context instead of starting from a blank slate.

Design principles:
- Everything is best-effort. If a data source fails, we omit it rather
  than crash the whole function.
- Everything is cheap to collect (no external API calls except weather,
  which is cached).
- The output is a plain dict that's easy to format for the LLM or display
  in the dashboard.
"""

import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

LUCY_DIR = Path.home() / "Lucy"

# Weather is cached to avoid hitting the API on every LLM call
_weather_cache: dict[str, Any] = {"data": None, "fetched_at": 0}
_WEATHER_TTL_SECONDS = 900  # 15 minutes

# Process start time so we can compute Lucy's uptime
_LUCY_START_TIME = time.time()


# ---------------------------------------------------------------------------
# Individual data sources
# ---------------------------------------------------------------------------

def _get_time_info() -> dict:
    """Current time, day, date, and a human time-of-day label."""
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    elif 17 <= hour < 21:
        time_of_day = "evening"
    elif 21 <= hour < 24:
        time_of_day = "late evening"
    else:
        time_of_day = "late night"

    return {
        "time": now.strftime("%H:%M"),
        "time_12h": now.strftime("%-I:%M %p"),
        "day_of_week": now.strftime("%A"),
        "date_pretty": now.strftime("%B %-d, %Y"),
        "time_of_day": time_of_day,
        "iso": now.isoformat(),
    }


def _run(cmd: list[str], cwd: Path | None = None, timeout: float = 2.0) -> str:
    """Run a command and return its stdout, or empty string on any failure."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _get_git_info() -> dict:
    """Current branch, last commit message, minutes since, uncommitted count."""
    info: dict = {}

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=LUCY_DIR)
    if branch:
        info["branch"] = branch

    last_msg = _run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=LUCY_DIR,
    )
    if last_msg:
        info["last_commit"] = last_msg

    last_time = _run(
        ["git", "log", "-1", "--pretty=%ct"],
        cwd=LUCY_DIR,
    )
    if last_time:
        try:
            last_unix = int(last_time)
            minutes_ago = int((time.time() - last_unix) / 60)
            info["minutes_since_last_commit"] = minutes_ago
        except ValueError:
            pass

    # Count uncommitted files
    status_out = _run(["git", "status", "--porcelain"], cwd=LUCY_DIR)
    if status_out is not None:
        lines = [l for l in status_out.splitlines() if l.strip()]
        info["uncommitted_files"] = len(lines)

    return info


def _get_system_info() -> dict:
    """Battery, uptime, load — basic host info."""
    info: dict = {}

    # System uptime via /proc/uptime (Linux / WSL)
    try:
        with open("/proc/uptime") as f:
            seconds = float(f.read().split()[0])
            info["host_uptime_hours"] = round(seconds / 3600, 1)
    except (OSError, ValueError):
        pass

    # Battery via Windows from WSL
    try:
        ps_cmd = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_Battery).EstimatedChargeRemaining",
        ]
        result = subprocess.run(
            ps_cmd, capture_output=True, text=True, timeout=3.0
        )
        out = result.stdout.strip()
        if out and out.isdigit():
            info["battery_percent"] = int(out)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Load average (first 1-min load)
    try:
        load = os.getloadavg()[0]
        info["load_1min"] = round(load, 2)
    except (OSError, AttributeError):
        pass

    return info


def _get_lucy_info() -> dict:
    """Lucy's own state: mode, uptime, recent activity."""
    info: dict = {}

    # Mode
    try:
        from brain.mode import get_mode
        info["mode"] = get_mode()
    except Exception:
        pass

    # Lucy's process uptime
    uptime_sec = time.time() - _LUCY_START_TIME
    info["uptime_minutes"] = round(uptime_sec / 60, 1)

    # Recent activity from the event bus
    try:
        from brain import events
        recent = events.get_history(limit=5)
        if recent:
            info["recent_events"] = [
                {"kind": e["kind"], "timestamp": e["timestamp"]}
                for e in recent
            ]
            # Find the last non-api event
            meaningful = [e for e in recent if not e["kind"].startswith("api.")]
            if meaningful:
                last = meaningful[-1]
                try:
                    t = datetime.fromisoformat(last["timestamp"])
                    seconds_ago = int((datetime.now() - t).total_seconds())
                    info["last_activity_seconds_ago"] = seconds_ago
                    info["last_activity_kind"] = last["kind"]
                except Exception:
                    pass
    except Exception:
        pass

    return info


def _get_weather_info() -> dict:
    """Current weather, cached for 15 minutes."""
    global _weather_cache
    now = time.time()

    # Return cached value if still fresh
    if (
        _weather_cache["data"]
        and (now - _weather_cache["fetched_at"]) < _WEATHER_TTL_SECONDS
    ):
        return _weather_cache["data"]

    info: dict = {}
    try:
        # Reuse existing weather module if present
        from brain.tools.weather import get_current_weather  # type: ignore
        result = get_current_weather()
        if isinstance(result, dict):
            info = result
        elif isinstance(result, str):
            info = {"summary": result}
    except Exception:
        # Fallback: hit wttr.in directly (free, no API key, Delaware by default)
        try:
            import urllib.request
            url = "https://wttr.in/Delaware?format=j1"
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                current = data["current_condition"][0]
                info = {
                    "location": "Delaware",
                    "temp_f": int(current.get("temp_F", 0)),
                    "condition": current.get("weatherDesc", [{}])[0].get("value", ""),
                    "feels_like_f": int(current.get("FeelsLikeF", 0)),
                }
        except Exception:
            info = {}

    _weather_cache = {"data": info, "fetched_at": now}
    return info


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_world_state() -> dict:
    """
    Returns everything Lucy should know about her current situation.

    This function is defensive: if any individual data source fails, it
    is silently omitted. The only guarantee is that 'now' is always present.
    """
    state: dict = {"now": _get_time_info()}

    git_info = _get_git_info()
    if git_info:
        state["git"] = git_info

    sys_info = _get_system_info()
    if sys_info:
        state["system"] = sys_info

    lucy_info = _get_lucy_info()
    if lucy_info:
        state["lucy"] = lucy_info

    weather = _get_weather_info()
    if weather:
        state["weather"] = weather

    return state


def format_for_prompt(state: dict | None = None) -> str:
    """
    Turn the world state dict into plain English that Lucy's LLM can read
    as context. This goes into her system prompt.
    """
    if state is None:
        state = get_world_state()

    lines = []

    # Time
    now = state.get("now", {})
    if now:
        lines.append(
            f"It is {now.get('time_12h', '')} on {now.get('day_of_week', '')}, "
            f"{now.get('date_pretty', '')} ({now.get('time_of_day', '')})."
        )

    # Git
    git = state.get("git", {})
    if git:
        parts = []
        if "branch" in git:
            parts.append(f"On git branch '{git['branch']}'.")
        if "last_commit" in git and "minutes_since_last_commit" in git:
            mins = git["minutes_since_last_commit"]
            if mins < 60:
                time_phrase = f"{mins} minutes ago"
            elif mins < 1440:
                time_phrase = f"{mins // 60} hours ago"
            else:
                time_phrase = f"{mins // 1440} days ago"
            parts.append(f"Last commit: \"{git['last_commit']}\" ({time_phrase}).")
        if git.get("uncommitted_files", 0) > 0:
            parts.append(f"{git['uncommitted_files']} uncommitted file(s).")
        if parts:
            lines.append(" ".join(parts))

    # Lucy
    lucy = state.get("lucy", {})
    if lucy:
        parts = []
        if "mode" in lucy:
            parts.append(f"Lucy is in {lucy['mode']} mode.")
        if "uptime_minutes" in lucy:
            mins = lucy["uptime_minutes"]
            if mins < 60:
                parts.append(f"Lucy has been awake for {int(mins)} minutes.")
            else:
                parts.append(f"Lucy has been awake for {round(mins/60, 1)} hours.")
        if "last_activity_kind" in lucy and "last_activity_seconds_ago" in lucy:
            secs = lucy["last_activity_seconds_ago"]
            if secs < 60:
                parts.append(f"Last activity: {lucy['last_activity_kind']} ({secs}s ago).")
        if parts:
            lines.append(" ".join(parts))

    # System
    sys = state.get("system", {})
    if sys:
        parts = []
        if "battery_percent" in sys:
            parts.append(f"Battery {sys['battery_percent']}%.")
        if "host_uptime_hours" in sys:
            parts.append(f"Host uptime {sys['host_uptime_hours']}h.")
        if parts:
            lines.append(" ".join(parts))

    # Weather
    weather = state.get("weather", {})
    if weather:
        parts = []
        if "temp_f" in weather and "condition" in weather:
            loc = weather.get("location", "local area")
            parts.append(
                f"Weather in {loc}: {weather['temp_f']}°F, {weather['condition']}."
            )
        elif "summary" in weather:
            parts.append(f"Weather: {weather['summary']}.")
        if parts:
            lines.append(" ".join(parts))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI for quick testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    state = get_world_state()
    print("=== Raw state ===")
    print(_json.dumps(state, indent=2, default=str))
    print()
    print("=== Formatted for prompt ===")
    print(format_for_prompt(state))
