"""
Lucy's Google Calendar integration.
Read events, create events, check availability.
"""

import datetime
from brain.google_auth import get_calendar_service

CALENDAR_TRIGGERS = [
    "calendar", "meeting", "meetings", "schedule",
    "appointment", "event", "events", "busy",
    "free time", "available", "what's today",
    "any meetings", "my schedule", "this week",
]


def needs_calendar(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in CALENDAR_TRIGGERS)


def get_today_events() -> str:
    service = get_calendar_service()
    now = datetime.datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0).isoformat() + "Z"
    end = now.replace(hour=23, minute=59, second=59).isoformat() + "Z"

    events = service.events().list(
        calendarId="primary", timeMin=start, timeMax=end,
        singleEvents=True, orderBy="startTime"
    ).execute().get("items", [])

    if not events:
        return "No meetings or events today. Your day is clear."

    lines = ["**Today's schedule:**\n"]
    for e in events:
        start_time = e["start"].get("dateTime", e["start"].get("date", ""))
        if "T" in start_time:
            time_str = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00")).strftime("%-I:%M %p")
        else:
            time_str = "All day"
        summary = e.get("summary", "(no title)")
        location = e.get("location", "")
        loc_str = f" — {location}" if location else ""
        lines.append(f"- **{time_str}** {summary}{loc_str}")

    lines.append(f"\n*{len(events)} events today*")
    return "\n".join(lines)


def get_week_events() -> str:
    service = get_calendar_service()
    now = datetime.datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0).isoformat() + "Z"
    end = (now + datetime.timedelta(days=7)).replace(hour=23, minute=59, second=59).isoformat() + "Z"

    events = service.events().list(
        calendarId="primary", timeMin=start, timeMax=end,
        singleEvents=True, orderBy="startTime"
    ).execute().get("items", [])

    if not events:
        return "No events this week. You're free all week."

    lines = ["**This week's schedule:**\n"]
    current_day = ""
    for e in events:
        start_time = e["start"].get("dateTime", e["start"].get("date", ""))
        if "T" in start_time:
            dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            day = dt.strftime("%A, %B %-d")
            time_str = dt.strftime("%-I:%M %p")
        else:
            day = start_time
            time_str = "All day"

        if day != current_day:
            lines.append(f"\n**{day}**")
            current_day = day

        summary = e.get("summary", "(no title)")
        lines.append(f"- {time_str} — {summary}")

    lines.append(f"\n*{len(events)} events this week*")
    return "\n".join(lines)


def create_event(summary: str, date_str: str, time_str: str = "", duration_min: int = 60) -> str:
    service = get_calendar_service()

    try:
        if time_str:
            start_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + datetime.timedelta(minutes=duration_min)
            event = {
                "summary": summary,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/New_York"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/New_York"},
            }
        else:
            event = {
                "summary": summary,
                "start": {"date": date_str},
                "end": {"date": date_str},
            }

        created = service.events().insert(calendarId="primary", body=event).execute()
        return f"Event created: **{summary}** on {date_str} {time_str}. [Open in Calendar]({created.get('htmlLink', '')})"
    except Exception as e:
        return f"Couldn't create event: {str(e)}"


def handle_calendar(text: str) -> str:
    t = text.lower()
    import re

    # Create event: "create meeting at 2pm" or "schedule call tomorrow at 3pm"
    create_match = any(w in t for w in ["schedule", "create", "add event", "new event", "book", "set up", "create a meeting"])
    if create_match:
        # Try to extract details
        import datetime as _dt
        
        # Extract time
        time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', t)
        time_str = ""
        if time_match:
            hour = int(time_match.group(1))
            minute = time_match.group(2) or "00"
            ampm = time_match.group(3) or ""
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            time_str = f"{hour:02d}:{minute}"

        # Extract date
        today = _dt.date.today()
        if "tomorrow" in t:
            date_str = (today + _dt.timedelta(days=1)).isoformat()
        elif "monday" in t:
            days_ahead = (0 - today.weekday() + 7) % 7 or 7
            date_str = (today + _dt.timedelta(days=days_ahead)).isoformat()
        elif "tuesday" in t:
            days_ahead = (1 - today.weekday() + 7) % 7 or 7
            date_str = (today + _dt.timedelta(days=days_ahead)).isoformat()
        elif "wednesday" in t:
            days_ahead = (2 - today.weekday() + 7) % 7 or 7
            date_str = (today + _dt.timedelta(days=days_ahead)).isoformat()
        elif "thursday" in t:
            days_ahead = (3 - today.weekday() + 7) % 7 or 7
            date_str = (today + _dt.timedelta(days=days_ahead)).isoformat()
        elif "friday" in t:
            days_ahead = (4 - today.weekday() + 7) % 7 or 7
            date_str = (today + _dt.timedelta(days=days_ahead)).isoformat()
        else:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', t)
            if date_match:
                date_str = date_match.group(1)
            else:
                date_str = today.isoformat()

        # Extract event name
        summary = text
        for prefix in ["schedule", "create", "add event", "new event", "book", "set up", "create a meeting", "create meeting"]:
            if t.startswith(prefix):
                summary = text[len(prefix):].strip()
                break
        # Remove time/date parts from summary
        summary = re.sub(r'(?:at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', '', summary, flags=re.IGNORECASE)
        summary = re.sub(r'(?:on\s+\d{4}-\d{2}-\d{2})', '', summary, flags=re.IGNORECASE)
        summary = re.sub(r'(?:tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)', '', summary, flags=re.IGNORECASE)
        summary = summary.strip().strip(',').strip()
        if not summary:
            summary = "Meeting"

        if time_str:
            return create_event(summary, date_str, time_str)
        else:
            return create_event(summary, date_str)

    if any(w in t for w in ["this week", "week", "next 7"]):
        return get_week_events()

    if any(w in t for w in ["today", "any meeting", "my schedule", "what\'s on"]):
        return get_today_events()

    # Default: today's events
    return get_today_events()
