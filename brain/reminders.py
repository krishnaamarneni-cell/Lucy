import json
import os
import threading
import time
import re
import dateparser
from datetime import datetime, timedelta
import pytz

REMINDERS_FILE = os.path.expanduser("~/Lucy/memory/reminders.json")
TZ = pytz.timezone("America/New_York")
_speak_fn = None

WORD_NUMS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "sixty": 60
}

def normalize_numbers(text):
    """Convert word numbers to digits: 'two minutes' → '2 minutes'"""
    for word, num in WORD_NUMS.items():
        text = re.sub(rf'\b{word}\b', str(num), text, flags=re.IGNORECASE)
    return text

def set_speak(fn):
    global _speak_fn
    _speak_fn = fn

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE) as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f)

def extract_time_string(text):
    text = normalize_numbers(text)
    patterns = [
        r'in \d+ (minute|minutes|hour|hours|second|seconds)',
        r'at \d{1,2}(:\d{2})?\s*(am|pm|AM|PM)',
        r'at \d{1,2}\s*(am|pm|AM|PM)',
        r'tomorrow at \d{1,2}(:\d{2})?\s*(am|pm|AM|PM)?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(0), text
    return None, text

def extract_message(text):
    lower = text.lower()
    for phrase in [" to ", " about ", " that "]:
        if phrase in lower:
            after = lower.split(phrase, 1)[-1].strip()
            time_str, _ = extract_time_string(after)
            if time_str:
                after = after.replace(time_str, "").strip()
            return after if after else "your reminder"
    return "your reminder"

def parse_reminder(text):
    time_str, normalized = extract_time_string(text)
    message = extract_message(text)

    if not time_str:
        return None, message

    now = datetime.now(TZ)
    settings = {
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": "America/New_York",
        "RELATIVE_BASE": now.replace(tzinfo=None),
    }
    remind_time = dateparser.parse(time_str, settings=settings)

    if not remind_time or remind_time <= now:
        return None, message

    return remind_time, message

def add_reminder(text):
    remind_time, message = parse_reminder(text)
    if not remind_time:
        return "I couldn't figure out when to remind you. Try saying 'remind me at 9 PM to check emails'."
    reminders = load_reminders()
    reminders.append({"time": remind_time.isoformat(), "message": message})
    save_reminders(reminders)
    time_str = remind_time.strftime("%-I:%M %p")
    return f"Got it! I'll remind you to {message} at {time_str}."

def reminder_watcher():
    while True:
        now = datetime.now(TZ)
        reminders = load_reminders()
        pending = []
        fired = False
        for r in reminders:
            remind_time = datetime.fromisoformat(r["time"])
            if now >= remind_time:
                print(f"⏰ Reminder: {r['message']}")
                if _speak_fn:
                    _speak_fn(f"Hey Krishna, reminder: {r['message']}")
                fired = True
            else:
                pending.append(r)
        if fired:
            save_reminders(pending)
        time.sleep(30)

def start_watcher(speak_fn):
    set_speak(speak_fn)
    t = threading.Thread(target=reminder_watcher, daemon=True)
    t.start()
