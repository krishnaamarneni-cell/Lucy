"""
Lucy as CEO — intelligently delegates tasks to specialist employees.
Replaces brittle keyword-based routing with LLM-powered classification.
"""

import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

EMPLOYEES = {
    "mentor": {
        "description": "Builds real code files, websites, scripts. Uses Claude Code with Write/Edit tools. USE FOR: creating HTML/CSS/JS files, building apps, writing Python scripts.",
        "examples": ["build a landing page", "create index.html", "write a python script", "build a SaaS site"],
    },
    "gmail": {
        "description": "Reads and sends real Gmail emails. Lists inbox, reads specific emails, drafts replies, sends messages.",
        "examples": ["check my emails", "read email 3", "draft reply to email 2", "send email to john@x.com"],
    },
    "calendar": {
        "description": "Manages Google Calendar events — lists schedule, creates events.",
        "examples": ["any meetings today", "my schedule this week", "schedule a call tomorrow at 3pm"],
    },
    "meet": {
        "description": "Creates Google Meet video meetings with real links and optionally sends them.",
        "examples": ["create a google meet at 2pm", "set up a video call with sai"],
    },
    "contacts": {
        "description": "Manages Google Contacts — add, find, delete, list contacts.",
        "examples": ["add contact john john@x.com", "who is sai in my contacts", "list my contacts"],
    },
    "sheets": {
        "description": "Creates and manages Google Sheets spreadsheets with data.",
        "examples": ["create a sheet of my email senders", "save all contacts to a spreadsheet"],
    },
    "tasks": {
        "description": "Manages local todo list — add, complete, delete, edit tasks.",
        "examples": ["add task update blog", "show my tasks", "complete task 3", "delete task 2"],
    },
    "youtube": {
        "description": "Tracks YouTube channels, gets latest videos, summarizes transcripts.",
        "examples": ["track fireship on youtube", "what's new from my channels", "summarize this video"],
    },
    "search": {
        "description": "Real-time web search via Tavily for current news, prices, facts, events.",
        "examples": ["amd stock price", "latest AI news", "who won the election", "current weather"],
    },
    "browser": {
        "description": "Fetches and reads website content. Summarizes pages. USE ONLY for reading/visiting existing sites, NOT for building them.",
        "examples": ["read hackernews.com", "browse techcrunch.com", "what's on wealthclaude.com"],
    },
    "career": {
        "description": "SAP career coach — job evaluation, resume tailoring, interview prep, rate advice.",
        "examples": ["what SAP roles fit me", "tailor my resume for this job", "what should I charge"],
    },
    "goose": {
        "description": "General shell/git/github operations. Runs commands in the terminal. Use for: git status, listing repos, file operations.",
        "examples": ["check my github repos", "git status of lucy", "list files in brain folder"],
    },
    "deployer": {
        "description": "Deploys projects to GitHub and Vercel.",
        "examples": ["deploy the latest project to vercel", "push this to github"],
    },
    "learning": {
        "description": "Manages Lucy's personal knowledge base — research topics, build study guides.",
        "examples": ["learn about SAP Fiori", "load python curriculum", "start learning"],
    },
    "music": {
        "description": "Opens YouTube videos/songs in browser.",
        "examples": ["play shape of you", "play arijit singh", "play lofi music"],
    },
    "email_finder": {
        "description": "Generates and verifies likely email addresses for a person at a domain.",
        "examples": ["find email for john smith at pfizer.com", "guess tim cook email"],
    },
    "briefing": {
        "description": "Generates morning briefing with weather, calendar, email, tasks, markets, news.",
        "examples": ["morning briefing", "catch me up", "daily summary"],
    },
    "orchestrator": {
        "description": "Handles multi-step tasks that require 2+ employees. USE WHEN: request has 'and' between actions like 'create meet AND send link'.",
        "examples": ["create meet and send link to sai", "read email 3 and draft response"],
    },
    "brain": {
        "description": "Default Groq conversation brain for everything else — general questions, chat, explanations, advice.",
        "examples": ["how are you", "what is quantum computing", "explain SAP MM", "good morning"],
    },
}


def delegate(user_message: str) -> dict:
    """Lucy the CEO decides which employee handles this task."""
    
    # Explicit override: "mentor ..." or "goose ..." prefix
    t = user_message.lower().strip()
    for employee_name in EMPLOYEES:
        if t.startswith(employee_name + " ") or t == employee_name:
            task = user_message[len(employee_name):].strip()
            return {
                "employee": employee_name,
                "task": task or user_message,
                "reason": "explicit prefix",
                "confidence": 1.0,
            }
    
    # Build classifier prompt
    employee_list = "\n".join(
        f"- **{name}**: {info['description']}" 
        for name, info in EMPLOYEES.items()
    )
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    prompt = f"""You are Lucy's task router. Classify the user's request into ONE employee.

EMPLOYEES:
{employee_list}

CRITICAL RULES:
1. "build/create a landing page/website/html" → mentor (NOT browser)
2. "read/browse/visit a website URL" → browser (NOT mentor)
3. Request with "and" connecting 2+ actions → orchestrator
4. General questions/chat → brain
5. When in doubt between two, pick the more specific one

Return ONLY this JSON format (no other text):
{{"employee": "name", "confidence": 0.0-1.0, "reason": "brief why"}}

User request: {user_message}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        result = json.loads(text)
        
        employee = result.get("employee", "brain")
        if employee not in EMPLOYEES:
            employee = "brain"
        
        return {
            "employee": employee,
            "task": user_message,
            "reason": result.get("reason", ""),
            "confidence": result.get("confidence", 0.5),
        }
    except Exception as e:
        return {
            "employee": "brain",
            "task": user_message,
            "reason": f"classifier error: {str(e)}",
            "confidence": 0.0,
        }


def execute(user_message: str) -> str:
    """Route to the right employee and execute."""
    decision = delegate(user_message)
    employee = decision["employee"]
    task = decision["task"]
    
    print(f"🏢 CEO → {employee} (conf: {decision['confidence']:.1f}, reason: {decision['reason']})")
    
    # Route to employee
    if employee == "mentor":
        from brain.mentor import ask_mentor, summarize_for_voice
        result = ask_mentor(task)
        if isinstance(result, dict):
            return result.get("output", "Mentor had no output.")
        return str(result)
    
    if employee == "gmail":
        from brain.gmail import handle_gmail
        return handle_gmail(task)
    
    if employee == "calendar":
        from brain.calendar import handle_calendar
        return handle_calendar(task)
    
    if employee == "meet":
        from brain.meet import handle_meet
        return handle_meet(task)
    
    if employee == "contacts":
        from brain.contacts import handle_contacts
        return handle_contacts(task)
    
    if employee == "sheets":
        from brain.sheets import handle_sheets
        return handle_sheets(task)
    
    if employee == "tasks":
        from brain.tasks import handle_task
        return handle_task(task)
    
    if employee == "youtube":
        from brain.youtube import handle_youtube
        return handle_youtube(task)
    
    if employee == "search":
        from brain.search import web_search
        return web_search(task)
    
    if employee == "browser":
        from brain.browser import summarize_page
        urls = re.findall(r'https?://\S+', task)
        url = urls[0] if urls else None
        if not url:
            from brain.browser import resolve_site
            url = resolve_site(task)
        if url:
            return summarize_page(url, task_hint=task)
        return "I need a URL or known site name to browse."
    
    if employee == "career":
        from brain.agents.career import ask_career_fast, is_heavy_career_task, ask_career, summarize_for_voice
        if is_heavy_career_task(task):
            result = ask_career(task)
            return summarize_for_voice(result)
        return ask_career_fast(task)
    
    if employee == "goose":
        from brain.agents.goose import ask_goose, summarize_for_voice
        result = ask_goose(task)
        return summarize_for_voice(result)
    
    if employee == "deployer":
        from brain.deployer import handle_deployer
        return handle_deployer(task)
    
    if employee == "learning":
        from brain.learning import handle_learning
        return handle_learning(task)
    
    if employee == "music":
        from brain.music import handle_music
        return handle_music(task)
    
    if employee == "email_finder":
        from brain.email_finder import handle_email_finder
        return handle_email_finder(task)
    
    if employee == "briefing":
        from brain.briefing import force_briefing
        return force_briefing()
    
    if employee == "orchestrator":
        from brain.orchestrator import handle_orchestration
        return handle_orchestration(task)
    
    # Default: brain (general conversation)
    return None  # Signal caller to use normal Groq chat
