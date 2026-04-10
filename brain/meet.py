"""
Lucy's Google Meet integration.
Create meetings with Google Meet links, share links via email.
"""

import datetime
from brain.google_auth import get_calendar_service
from brain.gmail import send_email
from brain.contacts import search_contact

MEET_TRIGGERS = [
    "google meet", "meet link", "video call", "video meeting",
    "create a meeting", "schedule a meet", "meeting link",
    "zoom", "conference call",
]


def needs_meet(text: str) -> bool:
    t = text.lower()
    if any(trigger in t for trigger in MEET_TRIGGERS):
        return True
    if "meet" in t and any(w in t for w in ["create", "schedule", "set up", "link", "send"]):
        return True
    return False


def create_meet(summary: str = "Meeting", date_str: str = "", time_str: str = "",
                duration_min: int = 60, attendees: list = None) -> dict:
    """Create a calendar event with Google Meet link."""
    service = get_calendar_service()
    import re

    today = datetime.date.today()

    if not date_str:
        date_str = today.isoformat()
    elif "tomorrow" in date_str:
        date_str = (today + datetime.timedelta(days=1)).isoformat()

    if not time_str:
        time_str = "14:00"

    # Parse time
    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or "0")
        ampm = time_match.group(3) or ""
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        time_str = f"{hour:02d}:{minute:02d}"

    start_dt = datetime.datetime.fromisoformat(f"{date_str}T{time_str}:00")
    end_dt = start_dt + datetime.timedelta(minutes=duration_min)

    event = {
        "summary": summary,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/New_York"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/New_York"},
        "conferenceData": {
            "createRequest": {
                "requestId": f"lucy-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    if attendees:
        event["attendees"] = [{"email": a} for a in attendees]

    try:
        created = service.events().insert(
            calendarId="primary", body=event, conferenceDataVersion=1
        ).execute()

        meet_link = ""
        conf = created.get("conferenceData", {})
        for ep in conf.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri", "")
                break

        return {
            "success": True,
            "event_id": created.get("id", ""),
            "link": created.get("htmlLink", ""),
            "meet_link": meet_link,
            "summary": summary,
            "start": start_dt.isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_meet(text: str) -> str:
    t = text.lower()
    import re

    # Extract time
    time_match = re.search(r'at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', t)
    time_str = time_match.group(1) if time_match else ""

    # Extract date
    today = datetime.date.today()
    if "tomorrow" in t:
        date_str = (today + datetime.timedelta(days=1)).isoformat()
    elif any(day in t for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        for day_name, day_num in days.items():
            if day_name in t:
                days_ahead = (day_num - today.weekday() + 7) % 7 or 7
                date_str = (today + datetime.timedelta(days=days_ahead)).isoformat()
                break
    else:
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', t)
        date_str = date_match.group(1) if date_match else today.isoformat()

    # Extract meeting name
    summary = "Meeting"
    for pattern in [r'(?:create|schedule|set up)\s+(?:a\s+)?(?:meeting|meet|call)\s+(?:with\s+)?(?:about\s+)?(.+?)(?:\s+at\s+|\s+on\s+|\s+tomorrow|$)',
                    r'(?:meeting|meet|call)\s+(?:with\s+)?(?:about\s+)?(.+?)(?:\s+at\s+|\s+on\s+|$)']:
        name_match = re.search(pattern, t)
        if name_match:
            summary = name_match.group(1).strip()
            if summary:
                break

    # Extract email addresses for attendees
    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)

    # Check for contact names to resolve to emails
    attendees = list(emails)
    for name_pattern in ["with", "send to", "share with", "invite"]:
        if name_pattern in t:
            after = t.split(name_pattern)[-1].strip()
            # Remove time/date parts
            after = re.sub(r'at\s+\d.*', '', after).strip()
            after = re.sub(r'on\s+\d.*', '', after).strip()
            after = re.sub(r'tomorrow.*', '', after).strip()
            if after and "@" not in after:
                # Try to find this person in contacts
                contact_result = search_contact(after)
                contact_email = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', contact_result)
                if contact_email:
                    attendees.append(contact_email.group(0))

    result = create_meet(summary, date_str, time_str, attendees=attendees if attendees else None)

    if result["success"]:
        lines = [f"**Meeting created: {result['summary']}**\n"]
        lines.append(f"- **When:** {result['start']}")
        if result["meet_link"]:
            lines.append(f"- **Google Meet link:** {result['meet_link']}")
        lines.append(f"- [Open in Calendar]({result['link']})")

        if attendees:
            lines.append(f"- **Attendees:** {', '.join(attendees)}")

        # If user asked to send the link to someone
        if any(w in t for w in ["send", "share"]) and attendees:
            for addr in attendees:
                send_email(addr, f"Meeting: {result['summary']}", 
                          f"Hi,\n\nHere's the Google Meet link for our meeting:\n\n{result['meet_link']}\n\nTime: {result['start']}\n\nBest,\nKrishna")
            lines.append(f"\n✅ Meeting link sent to {', '.join(attendees)}")

        return "\n".join(lines)
    else:
        return f"Couldn't create meeting: {result['error']}"
