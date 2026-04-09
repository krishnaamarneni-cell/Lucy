"""
Lucy's learning journal.

Every time Lucy asks her mentor for help, we log the full interaction here.
Think of it as a junior developer's notebook — she writes down what she
asked, what her mentor did, and what she learned.

Stored as JSONL (one JSON object per line) at memory/learning_journal.jsonl.
This format is easy to append to, easy to read line-by-line, and future
sessions can query it for similar past tasks.
"""

import json
from datetime import datetime
from pathlib import Path

JOURNAL_PATH = Path.home() / "Lucy" / "memory" / "learning_journal.jsonl"


def log_mentor_session(user_request: str, mentor_result: dict, note: str = "") -> None:
    """
    Record a mentor session in Lucy's learning journal.

    Args:
        user_request: What the user originally asked Lucy.
        mentor_result: The dict returned by brain.mentor.ask_mentor().
        note: Optional extra context (e.g., "first time seeing this topic").
    """
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_request": user_request,
        "mentor_task": mentor_result.get("task", ""),
        "workspace": mentor_result.get("workspace", ""),
        "output": mentor_result.get("output", ""),
        "success": mentor_result.get("success", False),
        "duration_s": mentor_result.get("duration_s", 0),
        "error": mentor_result.get("error", ""),
        "note": note,
    }

    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_journal(limit: int = 20) -> list:
    """Return the most recent journal entries (newest first)."""
    if not JOURNAL_PATH.exists():
        return []
    with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return list(reversed(entries))[:limit]


def find_similar(query: str, limit: int = 3) -> list:
    """
    Dumb keyword-match for now. Later this becomes vector similarity search.
    Returns the most recent entries where the query words appear in the
    user_request or mentor_task.
    """
    if not JOURNAL_PATH.exists():
        return []
    query_words = set(query.lower().split())
    matches = []
    with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            text = (entry.get("user_request", "") + " " +
                    entry.get("mentor_task", "")).lower()
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                matches.append((score, entry))
    matches.sort(key=lambda x: (x[0], x[1]["timestamp"]), reverse=True)
    return [m[1] for m in matches[:limit]]


def journal_stats() -> dict:
    """Quick summary: how many sessions, success rate, total time spent."""
    if not JOURNAL_PATH.exists():
        return {"total": 0, "successful": 0, "failed": 0, "total_seconds": 0}
    total = successful = 0
    total_seconds = 0.0
    with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            total += 1
            if entry.get("success"):
                successful += 1
            total_seconds += entry.get("duration_s", 0)
    return {
        "total": total,
        "successful": successful,
        "failed": total - successful,
        "total_seconds": round(total_seconds, 1),
    }
