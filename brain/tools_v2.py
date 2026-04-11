"""
Lucy's unified tool system using Groq native function calling.
Replaces CEO pattern, needs_X functions, and orchestrator with proper tool schemas.
Groq decides which tools to call based on natural language + tool descriptions.
"""

import json
import os
from typing import Any


# ============================================================================
# TOOL DEFINITIONS — each tool has schema for Groq + Python function to execute
# ============================================================================

TOOLS = []


def register(name: str, description: str, parameters: dict, function):
    """Register a tool for Groq function calling."""
    TOOLS.append({
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
        "_execute": function,
    })


# --- GMAIL ---
def _gmail_list(unread_only: bool = False, max_results: int = 10) -> str:
    from brain.gmail import list_emails
    return list_emails(max_results=max_results, unread_only=unread_only)

register("gmail_list", 
    "List emails from Gmail inbox. Use for 'check my emails', 'show inbox', 'unread emails'.",
    {
        "type": "object",
        "properties": {
            "unread_only": {"type": "boolean", "description": "Only show unread emails"},
            "max_results": {"type": "integer", "description": "Max emails to return (default 10)"},
        },
    },
    _gmail_list)


def _gmail_read(index: int) -> str:
    from brain.gmail import read_email
    return read_email(index=index)

register("gmail_read",
    "Read the full content of a specific email by its position in the list (1 = most recent).",
    {
        "type": "object",
        "properties": {
            "index": {"type": "integer", "description": "Email position (1-based)"},
        },
        "required": ["index"],
    },
    _gmail_read)


def _gmail_draft(to: str, subject: str, body: str) -> str:
    from brain.gmail import draft_email
    return draft_email(to, subject, body)

register("gmail_draft",
    "Save an email as a draft in Gmail (does NOT send).",
    {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string"},
            "body": {"type": "string", "description": "Email body text"},
        },
        "required": ["to", "subject", "body"],
    },
    _gmail_draft)


def _gmail_send(to: str, subject: str, body: str) -> str:
    from brain.gmail import send_email
    return send_email(to, subject, body)

register("gmail_send",
    "Send an email immediately through Gmail. Use when user says 'send'.",
    {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
    _gmail_send)


def _gmail_smart_reply(email_index: int, instructions: str = "") -> str:
    from brain.gmail import smart_reply
    return smart_reply(email_index, instructions)

register("gmail_smart_reply",
    "Read an email and generate a smart reply, save to drafts. Use for 'reply to email 3' or 'draft response for email X'.",
    {
        "type": "object",
        "properties": {
            "email_index": {"type": "integer"},
            "instructions": {"type": "string", "description": "Extra instructions like 'saying I am interested'"},
        },
        "required": ["email_index"],
    },
    _gmail_smart_reply)


# --- CALENDAR ---
def _calendar_today() -> str:
    from brain.calendar import get_today_events
    return get_today_events()

register("calendar_today",
    "List today's calendar events.",
    {"type": "object", "properties": {}},
    _calendar_today)


def _calendar_week() -> str:
    from brain.calendar import get_week_events
    return get_week_events()

register("calendar_week",
    "List this week's calendar events.",
    {"type": "object", "properties": {}},
    _calendar_week)


def _calendar_create(summary: str, date: str, time: str = "") -> str:
    from brain.calendar import create_event
    return create_event(summary, date, time)

register("calendar_create",
    "Create a calendar event. Date format: YYYY-MM-DD. Time format: HH:MM (24hr).",
    {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Event title"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time": {"type": "string", "description": "HH:MM 24hr format, optional"},
        },
        "required": ["summary", "date"],
    },
    _calendar_create)


# --- MEET ---
def _meet_create(summary: str, date: str = "", time: str = "", attendees: list = None) -> str:
    from brain.meet import create_meet
    result = create_meet(summary, date, time, attendees=attendees or [])
    if result.get("success"):
        return f"Meeting created: **{result['summary']}** at {result['start']}\nLink: {result.get('meet_link', '')}"
    return f"Failed: {result.get('error', 'unknown')}"

register("meet_create",
    "Create a Google Meet video meeting with real link. Use for 'create a meeting', 'video call'. If date is omitted, defaults to today; if time is omitted, defaults to 2pm.",
    {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Meeting title"},
            "date": {"type": "string", "description": "YYYY-MM-DD or 'tomorrow'"},
            "time": {"type": "string", "description": "Natural time like '3pm' or '14:00'"},
            "attendees": {"type": "array", "items": {"type": "string"}, "description": "Email addresses"},
        },
        "required": ["summary"],
    },
    _meet_create)


# --- CONTACTS ---
def _contacts_add(name: str, email: str = "", phone: str = "") -> str:
    from brain.contacts import add_contact
    return add_contact(name, email, phone)

register("contacts_add",
    "Add a new contact to Google Contacts.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
        },
        "required": ["name"],
    },
    _contacts_add)


def _contacts_search(name: str) -> str:
    from brain.contacts import search_contact
    return search_contact(name)

register("contacts_search",
    "Find a contact by name. Returns their email and phone.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
    _contacts_search)


def _contacts_list() -> str:
    from brain.contacts import list_contacts
    return list_contacts()

register("contacts_list",
    "List all Google contacts.",
    {"type": "object", "properties": {}},
    _contacts_list)


# --- TASKS ---
def _tasks_add(description: str, priority: str = "medium", due: str = "") -> str:
    from brain.tasks import add_task
    return add_task(description, priority, due)

register("tasks_add",
    "Add a new task to the todo list.",
    {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "due": {"type": "string", "description": "Due date like 'tomorrow' or 'monday'"},
        },
        "required": ["description"],
    },
    _tasks_add)


def _tasks_list(show_completed: bool = False) -> str:
    from brain.tasks import list_tasks
    return list_tasks(show_completed=show_completed)

register("tasks_list",
    "List pending or all tasks.",
    {
        "type": "object",
        "properties": {
            "show_completed": {"type": "boolean"},
        },
    },
    _tasks_list)


def _tasks_complete(task_id: int) -> str:
    from brain.tasks import complete_task
    return complete_task(task_id=task_id)

register("tasks_complete",
    "Mark a task as completed.",
    {
        "type": "object",
        "properties": {"task_id": {"type": "integer"}},
        "required": ["task_id"],
    },
    _tasks_complete)


def _tasks_delete(task_id: int) -> str:
    from brain.tasks import delete_task
    return delete_task(task_id=task_id)

register("tasks_delete",
    "Delete a task.",
    {
        "type": "object",
        "properties": {"task_id": {"type": "integer"}},
        "required": ["task_id"],
    },
    _tasks_delete)


# --- SEARCH & WEB ---
def _search_web(query: str) -> str:
    from brain.search import web_search
    return web_search(query)

register("search_web",
    "Real-time web search for current info: news, stock prices, events, facts.",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    _search_web)


def _browser_read(url: str, task_hint: str = "") -> str:
    from brain.browser import summarize_page
    return summarize_page(url, task_hint=task_hint)

register("browser_read",
    "Fetch and summarize a website. Use for READING existing sites, NOT building them.",
    {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL or domain"},
            "task_hint": {"type": "string", "description": "What user wants from the page"},
        },
        "required": ["url"],
    },
    _browser_read)


# --- MENTOR (code building) ---
def _mentor_build(task: str) -> str:
    from brain.mentor import ask_mentor
    result = ask_mentor(task)
    if isinstance(result, dict):
        return result.get("output", "Mentor returned no output.")
    return str(result)

register("mentor_build",
    "Use Claude Code to BUILD real code files — HTML, Python, React, websites. Writes actual files to ~/Lucy/mentor_workspace/. Use for 'build a landing page', 'create a website', 'write a script'.",
    {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What to build, in detail"},
        },
        "required": ["task"],
    },
    _mentor_build)


# --- DEPLOYER ---
def _deploy(target: str = "both") -> str:
    from brain.deployer import handle_deployer
    return handle_deployer(f"deploy the latest project to {target}")

register("deploy_project",
    "Deploy the most recent mentor_workspace project to GitHub and/or Vercel.",
    {
        "type": "object",
        "properties": {
            "target": {"type": "string", "enum": ["github", "vercel", "both"]},
        },
    },
    _deploy)


# --- MUSIC ---
def _music_play(query: str) -> str:
    from brain.music import play_song
    return play_song(query)

register("music_play",
    "Search YouTube and open a song/video in the browser.",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    _music_play)


# --- EMAIL FINDER ---
def _email_find(name: str, domain: str) -> str:
    from brain.email_finder import find_email
    return find_email(name, domain)

register("email_find",
    "Generate and verify likely email addresses for a person at a company domain.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "domain": {"type": "string", "description": "e.g. pfizer.com"},
        },
        "required": ["name", "domain"],
    },
    _email_find)


# --- BRIEFING ---
def _briefing() -> str:
    from brain.briefing import force_briefing
    return force_briefing()

register("morning_briefing",
    "Generate daily briefing with weather, calendar, email, tasks, markets, news.",
    {"type": "object", "properties": {}},
    _briefing)


# --- TIME & DATE ---
def _get_time() -> str:
    from datetime import datetime
    now = datetime.now()
    return f"Current time: {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}"

register("get_time",
    "Get the current time and date. Use when user asks 'what time is it', 'what's today's date', 'what day is it'.",
    {"type": "object", "properties": {}},
    _get_time)


# --- KNOWLEDGE BASE ---
def _knowledge_search(query: str) -> str:
    from brain.learning import search_knowledge
    return search_knowledge(query)

register("knowledge_search",
    "Search Lucy's learned knowledge base. Covers SAP, Python, culture, self-improvement, web development.",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    _knowledge_search)


# ============================================================================
# EXECUTION
# ============================================================================

def get_tool_schemas():
    """Return the Groq-compatible tool schemas (without _execute)."""
    return [
        {"type": t["type"], "function": t["function"]}
        for t in TOOLS
    ]


def execute_tool(name: str, args) -> str:
    """Execute a tool by name with given args."""
    if args is None:
        args = {}
    if not isinstance(args, dict):
        args = {}
    for tool in TOOLS:
        if tool["function"]["name"] == name:
            try:
                return str(tool["_execute"](**args))
            except Exception as e:
                return f"Error executing {name}: {str(e)}"
    return f"Unknown tool: {name}"


def list_tools() -> list:
    return [t["function"]["name"] for t in TOOLS]
