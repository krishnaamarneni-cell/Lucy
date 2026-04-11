"""
Lucy's Morning Briefing.
Automatically generates a daily summary when the dashboard opens.
Covers: weather, calendar, emails, tasks, markets, and top news.
"""

import os
import time
from datetime import datetime
from pathlib import Path

LAST_BRIEFING_FILE = Path.home() / "Lucy" / "memory" / "last_briefing.json"


def _should_brief() -> bool:
    """Only brief once per session (not on every page refresh)."""
    import json
    try:
        if LAST_BRIEFING_FILE.exists():
            data = json.loads(LAST_BRIEFING_FILE.read_text())
            last = data.get("timestamp", 0)
            # Don't brief again within 2 hours
            if time.time() - last < 7200:
                return False
    except Exception:
        pass
    return True


def _mark_briefed():
    """Record that we just briefed."""
    import json
    LAST_BRIEFING_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_BRIEFING_FILE.write_text(json.dumps({
        "timestamp": time.time(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }))


def generate_briefing() -> str:
    """Generate the full morning briefing."""
    if not _should_brief():
        return ""

    now = datetime.now()
    hour = now.hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    sections = []
    sections.append(f"## {greeting}, Krishna\n")
    sections.append(f"*{now.strftime('%A, %B %d, %Y · %I:%M %p')}*\n")

    # 1. Weather
    try:
        import requests
        w = requests.get("https://wttr.in/Wilmington+Delaware?format=%C+%t", timeout=5).text.strip()
        sections.append(f"**Weather in Delaware:** {w}\n")
    except Exception:
        sections.append("**Weather:** Couldn\'t fetch weather\n")

    # 2. Calendar — today's events
    try:
        from brain.calendar import get_today_events
        cal = get_today_events()
        sections.append(f"**Schedule:**\n{cal}\n")
    except Exception:
        sections.append("**Schedule:** Couldn't check calendar\n")

    # 3. Unread emails count + top 3
    try:
        from brain.gmail import list_emails
        emails = list_emails(max_results=3, unread_only=True)
        sections.append(f"**Inbox:**\n{emails}\n")
    except Exception:
        sections.append("**Inbox:** Couldn't check email\n")

    # 4. Pending tasks
    try:
        from brain.tasks import list_tasks
        tasks = list_tasks()
        sections.append(f"**Tasks:**\n{tasks}\n")
    except Exception:
        pass

    # 5. Market summary — top stocks
    try:
        from brain.search import web_search
        market_data = web_search("stock market today S&P 500 Nasdaq Dow Jones summary", max_results=3)
        
        from groq import Groq
        from dotenv import load_dotenv
        load_dotenv()
        
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        market_summary = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": (
                    f"Summarize today's stock market in 3-4 bullet points. "
                    f"Include S&P 500, Nasdaq, and Dow Jones if available. "
                    f"Use markdown bullet points with bold index names. "
                    f"Data:\n{market_data}"
                )
            }],
        ).choices[0].message.content.strip()
        sections.append(f"**Markets:**\n{market_summary}\n")
    except Exception:
        pass

    # 6. Top 3 news
    try:
        from brain.search import web_search
        news_data = web_search("top news today", max_results=5)
        
        news_summary = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": (
                    f"List the top 3 news headlines today as numbered items. "
                    f"Format: 1. **Headline** — one sentence summary. "
                    f"No other text.\n\nData:\n{news_data}"
                )
            }],
        ).choices[0].message.content.strip()
        sections.append(f"**Top News:**\n{news_summary}\n")
    except Exception:
        pass

    # 7. GitHub activity
    try:
        import subprocess
        result = subprocess.run(
            ["git", "-C", str(Path.home() / "Lucy"), "log", "--oneline", "-3"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            commits = result.stdout.strip().split("\n")
            commit_lines = "\n".join(f"- `{c[:7]}` {c[8:]}" for c in commits)
            sections.append(f"**Recent commits:**\n{commit_lines}\n")
    except Exception:
        pass

    sections.append("---\n*Ask me anything or say 'refresh briefing' for an update.*")

    _mark_briefed()
    return "\n".join(sections)


def force_briefing() -> str:
    """Force a new briefing regardless of last briefing time."""
    import json
    # Reset the timer
    if LAST_BRIEFING_FILE.exists():
        LAST_BRIEFING_FILE.unlink()
    return generate_briefing()


BRIEFING_TRIGGERS = [
    "morning briefing", "daily briefing", "briefing",
    "refresh briefing", "what did i miss",
    "catch me up", "daily summary", "morning summary",
    "start my day", "good morning",
]


def needs_briefing(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in BRIEFING_TRIGGERS)
