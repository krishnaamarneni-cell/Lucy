"""
Lucy's event bus.

Every time Lucy does something interesting (thinks, speaks, calls mentor,
changes mode, runs a tool), she publishes an event here. The dashboard
subscribes to this stream so you can watch everything in real time.

Events are kept in a bounded deque in memory plus broadcast to any
async WebSocket subscribers.
"""

import asyncio
import json
import time
from collections import deque
from datetime import datetime
from typing import Any


# Rolling history of recent events (for late subscribers and debugging)
_MAX_HISTORY = 200
_history: deque[dict] = deque(maxlen=_MAX_HISTORY)

# Live subscribers — asyncio queues that each WebSocket client owns
_subscribers: list[asyncio.Queue] = []


def _make_event(kind: str, data: dict[str, Any] | None = None) -> dict:
    return {
        "id": int(time.time() * 1000),
        "timestamp": datetime.now().isoformat(),
        "kind": kind,
        "data": data or {},
    }


def publish(kind: str, data: dict[str, Any] | None = None) -> dict:
    """
    Publish an event. Called synchronously from anywhere in Lucy.

    Examples of kinds:
      - "status.awake"
      - "status.sleeping"
      - "voice.listening"
      - "voice.transcribed"  data={"text": "..."}
      - "voice.speaking"     data={"text": "..."}
      - "mentor.calling"     data={"task": "..."}
      - "mentor.result"      data={"output": "..."}
      - "mode.changed"       data={"from": "read", "to": "ask"}
      - "tool.called"        data={"tool": "weather", "args": {...}}
      - "action.denied"      data={"reason": "...", "action": "..."}
      - "error"              data={"message": "..."}
    """
    event = _make_event(kind, data)
    _history.append(event)
    # Broadcast to all live subscribers, non-blocking
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # Subscriber is falling behind — drop the event for that one only
            pass
    return event


def get_history(limit: int = 50) -> list[dict]:
    """Return the most recent events (newest last)."""
    items = list(_history)
    return items[-limit:]


def subscribe() -> asyncio.Queue:
    """Register a new subscriber queue. The caller must call unsubscribe()."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove a subscriber queue."""
    try:
        _subscribers.remove(q)
    except ValueError:
        pass


def subscriber_count() -> int:
    return len(_subscribers)
