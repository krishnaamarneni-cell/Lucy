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
    "Build ONLY — write code files to disk without deploying. Use ONLY when user explicitly says 'just build' or does not mention deploy/live/github/vercel. If user says 'build and deploy' or 'build and ship' or 'go live', use build_and_deploy instead.",
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


# --- BUILD & DEPLOY (one-shot) ---
def _build_and_deploy(task: str, auto_open: bool = True) -> str:
    """Build a project via mentor, then deploy to GitHub + Vercel."""
    from brain.mentor import ask_mentor
    from brain.deployer import handle_deployer, find_latest_project
    import subprocess
    
    output = ["# 🏗️ Build + Deploy Pipeline\n"]
    
    # Step 1: Build with mentor
    output.append("## Step 1: Building with Claude Code mentor...")
    build_result = ask_mentor(task)
    if isinstance(build_result, dict):
        build_text = build_result.get("output", "")
        workspace = build_result.get("workspace", "")
        if not build_result.get("success"):
            return "\n".join(output) + f"\n❌ Build failed: {build_result.get('error', 'unknown')}"
    else:
        return "\n".join(output) + "\n❌ Build returned unexpected format"
    
    output.append(f"✅ Built at: `{workspace}`")
    output.append(f"{build_text[:400]}...\n" if len(build_text) > 400 else f"{build_text}\n")
    
    # Verify files exist
    project = find_latest_project()
    if not project:
        return "\n".join(output) + "\n❌ No files found in workspace"
    
    output.append(f"📁 Files: " + ", ".join(f.name for f in project.iterdir() if f.is_file())[:200])
    
    # Auto-open in browser
    if auto_open:
        html_files = list(project.glob("*.html"))
        if html_files:
            try:
                subprocess.run(["wslview", str(html_files[0])], timeout=3)
                output.append(f"👁️ Opened `{html_files[0].name}` in browser")
            except Exception:
                pass
    
    # Step 2: Deploy
    output.append("\n## Step 2: Deploying to GitHub + Vercel...")
    deploy_result = handle_deployer("deploy the latest project to both")
    output.append(deploy_result)
    
    return "\n".join(output)

register("build_and_deploy",
    "ONE-SHOT BUILD + DEPLOY. MUST use this when user says ANY of: 'build and deploy', 'build and ship', 'deploy to vercel', 'go live', 'make it live', 'push to github and vercel'. Chains mentor_build → deploy_project → returns live URL. ALWAYS prefer this over mentor_build when deploy is mentioned.",
    {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Full description of what to build (e.g. 'landing page for WealthClaude Pro with hero features pricing using Tailwind')"},
            "auto_open": {"type": "boolean", "description": "Open in browser after build (default true)"},
        },
        "required": ["task"],
    },
    _build_and_deploy)


# --- PROJECT MANAGEMENT (update, delete, list) ---
def _list_projects() -> str:
    """List all projects in mentor_workspace."""
    from pathlib import Path as P
    workspace = P.home() / "Lucy" / "mentor_workspace"
    if not workspace.exists():
        return "No projects found."
    
    projects = []
    for d in sorted(workspace.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if d.is_dir():
            files = [f.name for f in d.iterdir() if f.is_file()]
            if files:
                html = [f for f in files if f.endswith(".html")]
                projects.append({
                    "name": d.name,
                    "files": len(files),
                    "has_html": len(html) > 0,
                    "path": str(d),
                })
    
    if not projects:
        return "No projects with files found."
    
    lines = [f"**Projects in mentor_workspace ({len(projects)} total):**\n"]
    for i, p in enumerate(projects[:15], 1):
        icon = "🌐" if p["has_html"] else "📁"
        lines.append(f"{i}. {icon} **{p['name']}** — {p['files']} file(s)")
    return "\n".join(lines)

register("list_projects",
    "List all projects Lucy has built in mentor_workspace. Use for 'show my projects', 'list projects', 'what have I built'.",
    {"type": "object", "properties": {}},
    _list_projects)


def _update_project(project_name: str, changes: str, redeploy: bool = True) -> str:
    """Modify an existing project via mentor and optionally redeploy."""
    from brain.mentor import ask_mentor
    from brain.deployer import handle_deployer
    from pathlib import Path as P
    import subprocess
    
    workspace = P.home() / "Lucy" / "mentor_workspace"
    
    # Find project (exact or fuzzy match)
    project = workspace / project_name
    if not project.exists():
        for d in workspace.iterdir():
            if d.is_dir() and project_name.lower() in d.name.lower():
                project = d
                break
    
    if not project.exists():
        return f"Project '{project_name}' not found. Use list_projects to see available ones."
    
    # Read current index.html if exists
    html_file = project / "index.html"
    current_content = ""
    if html_file.exists():
        current_content = html_file.read_text()[:3000]
    
    output = [f"# 🔧 Updating: {project.name}\n"]
    
    # Ask mentor to update the file
    task = (
        f"The project is at {project}. "
        f"Current index.html content (first 3000 chars):\n\n```html\n{current_content}\n```\n\n"
        f"Apply these changes to index.html: {changes}\n\n"
        f"Use the Edit or Write tool to modify the file in place. "
        f"Keep the existing structure and only change what's requested."
    )
    
    build_result = ask_mentor(task)
    if isinstance(build_result, dict):
        if build_result.get("success"):
            output.append(f"✅ Mentor updated the file")
            output.append(f"{build_result.get('output', '')[:300]}")
        else:
            return "\n".join(output) + f"\n❌ Update failed"
    
    # Auto-open updated file
    if html_file.exists():
        try:
            subprocess.run(["wslview", str(html_file)], timeout=3)
            output.append("👁️ Opened updated file in browser")
        except Exception:
            pass
    
    # Redeploy if requested
    if redeploy:
        output.append("\n## Redeploying...")
        deploy_result = handle_deployer(f"deploy project {project.name} to both")
        output.append(deploy_result)
    
    return "\n".join(output)

register("update_project",
    "Modify an existing project with changes and optionally redeploy. Use for 'update the X project', 'change the hero text to Y', 'add a contact section to Z'.",
    {
        "type": "object",
        "properties": {
            "project_name": {"type": "string", "description": "Project folder name (e.g. task-e14acc86) or keyword"},
            "changes": {"type": "string", "description": "What changes to apply"},
            "redeploy": {"type": "boolean", "description": "Redeploy after update (default true)"},
        },
        "required": ["project_name", "changes"],
    },
    _update_project)


def _delete_project(project_name: str, delete_github: bool = True, delete_vercel: bool = True) -> str:
    """Delete a local project and optionally its GitHub repo and Vercel deployment."""
    from pathlib import Path as P
    import subprocess
    import shutil
    import os
    
    workspace = P.home() / "Lucy" / "mentor_workspace"
    
    # Find project
    project = workspace / project_name
    if not project.exists():
        for d in workspace.iterdir():
            if d.is_dir() and project_name.lower() in d.name.lower():
                project = d
                break
    
    if not project.exists():
        return f"Project '{project_name}' not found."
    
    output = [f"# 🗑️ Deleting: {project.name}\n"]
    
    env = {**os.environ}
    env["PATH"] = f"{P.home()}/.nvm/versions/node/v20.20.2/bin:{P.home()}/.local/bin:" + env.get("PATH", "")
    
    repo_name = project.name.replace("task-", "lucy-site-")
    
    # Delete GitHub repo
    if delete_github:
        try:
            result = subprocess.run(
                f"gh repo delete {repo_name} --yes",
                shell=True, capture_output=True, text=True, timeout=30, env=env,
            )
            if result.returncode == 0:
                output.append(f"✅ Deleted GitHub repo: {repo_name}")
            else:
                output.append(f"⚠️ GitHub: {result.stderr[:150]}")
        except Exception as e:
            output.append(f"⚠️ GitHub delete failed: {e}")
    
    # Delete Vercel deployment
    if delete_vercel:
        try:
            # Try to remove via vercel CLI
            result = subprocess.run(
                f"{P.home()}/.nvm/versions/node/v20.20.2/bin/vercel remove {project.name} --yes",
                shell=True, capture_output=True, text=True, timeout=30,
                cwd=str(project), env=env,
            )
            if result.returncode == 0:
                output.append(f"✅ Removed from Vercel")
            else:
                output.append(f"⚠️ Vercel: {result.stderr[:150] or 'may not exist'}")
        except Exception as e:
            output.append(f"⚠️ Vercel remove failed: {e}")
    
    # Delete local folder
    try:
        shutil.rmtree(project)
        output.append(f"✅ Deleted local folder: {project}")
    except Exception as e:
        output.append(f"❌ Local delete failed: {e}")
    
    return "\n".join(output)

register("delete_project",
    "Delete a project locally AND remove it from GitHub and Vercel. Destructive — only use when user explicitly says 'delete' or 'remove'.",
    {
        "type": "object",
        "properties": {
            "project_name": {"type": "string"},
            "delete_github": {"type": "boolean", "description": "Also delete GitHub repo (default true)"},
            "delete_vercel": {"type": "boolean", "description": "Also delete Vercel deployment (default true)"},
        },
        "required": ["project_name"],
    },
    _delete_project)


# --- JOB SEARCH ---
def _score_job(job_description: str, job_title: str = "", company: str = "") -> str:
    from brain.jobs import score_job, format_score
    result = score_job(job_description, job_title, company)
    return format_score(result)

def _find_sap_jobs(min_score: int = 75, max_jobs: int = 10) -> str:
    from brain.jobs import find_matching_jobs
    return find_matching_jobs(min_score=min_score, max_jobs=max_jobs)

register("find_sap_jobs",
    "Scan SAP job boards (Dice, Indeed, LinkedIn) for new contract roles, score each against Krishna's CV, return matches above threshold. Use for 'find new SAP jobs', 'check job boards', 'what SAP contracts are available'.",
    {
        "type": "object",
        "properties": {
            "min_score": {"type": "integer", "description": "Minimum match % to include (default 75)"},
            "max_jobs": {"type": "integer", "description": "Max jobs to scan (default 10)"},
        },
    },
    _find_sap_jobs)


def _find_recruiters(domain: str = "", company: str = "", job_url: str = "", job_title: str = "") -> str:
    from brain.jobs import find_recruiters_for_company, format_recruiters, _extract_domain_from_job
    if not domain and (job_url or job_title):
        domain = _extract_domain_from_job(job_url, job_title)
    if not domain and company:
        domain = company.lower().replace(" ", "") + ".com"
    if not domain:
        return "I need a company domain to find recruiters. Example: 'find recruiters at pfizer.com'"
    result = find_recruiters_for_company(domain, company)
    return format_recruiters(result)

def _draft_application(
    recruiter_email: str,
    recruiter_name: str = "",
    company: str = "",
    job_title: str = "",
    job_description: str = "",
    job_url: str = "",
) -> str:
    from brain.jobs import draft_application_email, save_to_gmail_drafts
    draft = draft_application_email(
        recruiter_email=recruiter_email,
        recruiter_name=recruiter_name,
        company=company,
        job_title=job_title,
        job_description=job_description,
        job_url=job_url,
    )
    return save_to_gmail_drafts(draft)

def _tailor_resume(job_title: str, company: str, job_description: str) -> str:
    from brain.jobs import tailor_resume
    result = tailor_resume(job_title, company, job_description)
    if "error" in result:
        return f"❌ {result['error']}"
    return f"✅ Tailored resume created\n\n**PDF:** `{result['pdf_path']}`\n**Markdown:** `{result['md_path']}`\n\n### Preview\n{result['preview']}..."

register("tailor_resume",
    "Generate a custom resume tailored to a specific job — reorders bullets and rewrites summary to emphasize matching keywords. Saves markdown + PDF to ~/career-ops/tailored/. Use before drafting an application email.",
    {
        "type": "object",
        "properties": {
            "job_title": {"type": "string"},
            "company": {"type": "string"},
            "job_description": {"type": "string"},
        },
        "required": ["job_title", "company", "job_description"],
    },
    _tailor_resume)


def _apply_to_job(
    job_title: str,
    company: str,
    job_description: str,
    recruiter_email: str,
    recruiter_name: str = "",
    job_url: str = "",
) -> str:
    """Full pipeline: tailor resume -> draft email -> attach tailored PDF -> save to Gmail drafts + log to tracker."""
    from brain.jobs import tailor_resume, draft_application_email, save_to_gmail_drafts, log_application
    
    # Step 1: Tailor the resume
    tailor = tailor_resume(job_title, company, job_description)
    if "error" in tailor:
        return f"❌ Tailoring failed: {tailor['error']}"
    
    # Step 2: Draft the email
    draft = draft_application_email(
        recruiter_email=recruiter_email,
        recruiter_name=recruiter_name,
        company=company,
        job_title=job_title,
        job_description=job_description,
        job_url=job_url,
    )
    
    # Step 3: Save with tailored attachment
    result = save_to_gmail_drafts(draft, custom_attachment=tailor["pdf_path"])
    
    # Step 4: Log to tracker sheet
    log_result = log_application(
        company=company,
        job_title=job_title,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email,
        status="draft",
        resume_file=tailor["pdf_path"],
        job_url=job_url,
    )
    
    return f"# ✅ Application prepared for {company}\n\n{result}\n\n{log_result}"

def _list_applications() -> str:
    from brain.jobs import list_applications
    return list_applications()

def _add_recruiter(name: str, company: str, email: str, role: str = "", source: str = "manual", priority: str = "medium", notes: str = "") -> str:
    from brain.jobs import add_recruiter
    return add_recruiter(name, company, email, role, source, priority, notes)

register("add_recruiter",
    "Add a recruiter to Lucy's persistent database. Use for 'add recruiter X at company Y with email Z'.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "company": {"type": "string"},
            "email": {"type": "string"},
            "role": {"type": "string"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "notes": {"type": "string"},
        },
        "required": ["name", "company", "email"],
    },
    _add_recruiter)


def _import_recruiters(domain: str, company: str = "") -> str:
    from brain.jobs import import_recruiters_from_hunter
    return import_recruiters_from_hunter(domain, company)

register("import_recruiters",
    "Find recruiters at a company via Hunter.io and add them all to Lucy's recruiters database. Use for 'import recruiters from pfizer.com'.",
    {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "company": {"type": "string"},
        },
        "required": ["domain"],
    },
    _import_recruiters)


def _list_recruiters(status: str = "all", limit: int = 20) -> str:
    from brain.jobs import list_recruiters
    return list_recruiters(status, limit)

register("list_recruiters",
    "Show recruiters from Lucy's database. Filter by status: all, new, drafted, contacted, replied.",
    {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["all", "new", "drafted", "contacted", "replied"]},
            "limit": {"type": "integer"},
        },
    },
    _list_recruiters)


def _batch_draft(job_title: str, job_description: str, daily_limit: int = 50) -> str:
    from brain.jobs import batch_draft_applications
    return batch_draft_applications(job_title, job_description, daily_limit)

def _sync_sent_emails() -> str:
    from brain.jobs import sync_sent_emails_to_recruiters
    return sync_sent_emails_to_recruiters()

register("sync_sent_emails",
    "Scan Gmail Sent folder for emails to recruiters in the database and auto-update their status to 'contacted'. Run this daily or after sending batch drafts manually.",
    {"type": "object", "properties": {}},
    _sync_sent_emails)


register("batch_draft_applications",
    "Create personalized drafts for all NEW recruiters in database for a specific job. Respects daily_limit (default 50/day to stay under Gmail thresholds). Each draft has a tailored resume attached. Marks recruiters as 'drafted' after processing.",
    {
        "type": "object",
        "properties": {
            "job_title": {"type": "string"},
            "job_description": {"type": "string"},
            "daily_limit": {"type": "integer", "description": "Max drafts per run (default 50)"},
        },
        "required": ["job_title", "job_description"],
    },
    _batch_draft)


register("list_applications",
    "Show all job applications Lucy has logged to the tracker sheet. Use for 'show my applications', 'what jobs have I applied to', 'open my tracker'.",
    {"type": "object", "properties": {}},
    _list_applications)


register("apply_to_job",
    "FULL PIPELINE: tailor resume + draft personalized email + attach tailored PDF + save to Gmail drafts. Use when user says 'apply to X', 'send my resume to X for this job'.",
    {
        "type": "object",
        "properties": {
            "job_title": {"type": "string"},
            "company": {"type": "string"},
            "job_description": {"type": "string"},
            "recruiter_email": {"type": "string"},
            "recruiter_name": {"type": "string"},
            "job_url": {"type": "string"},
        },
        "required": ["job_title", "company", "job_description", "recruiter_email"],
    },
    _apply_to_job)


register("draft_application",
    "Draft a personalized job application email using Krishna's CV and job details, save to Gmail drafts. Use after find_recruiters when user says 'draft an application to X' or 'write a cover email for this job'.",
    {
        "type": "object",
        "properties": {
            "recruiter_email": {"type": "string", "description": "Recruiter email address"},
            "recruiter_name": {"type": "string", "description": "Recruiter full name"},
            "company": {"type": "string", "description": "Company name"},
            "job_title": {"type": "string", "description": "Job title"},
            "job_description": {"type": "string", "description": "Job description text"},
            "job_url": {"type": "string", "description": "Job posting URL"},
        },
        "required": ["recruiter_email"],
    },
    _draft_application)


register("find_recruiters",
    "Find verified recruiter emails at a company using Hunter.io. Use after find_sap_jobs when user wants to contact someone about a specific job, or directly when user asks 'find recruiters at X'.",
    {
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Company domain like 'pfizer.com'"},
            "company": {"type": "string", "description": "Company name"},
            "job_url": {"type": "string", "description": "Job URL if coming from find_sap_jobs"},
            "job_title": {"type": "string", "description": "Job title for company extraction"},
        },
    },
    _find_recruiters)


register("score_job",
    "Score a SAP job description against Krishna's CV 0-100%. Returns match percent, fit reasons, concerns, and tailoring advice. Use when user pastes a job description and asks 'is this a fit', 'score this job', 'evaluate this role'.",
    {
        "type": "object",
        "properties": {
            "job_description": {"type": "string", "description": "Full job description text"},
            "job_title": {"type": "string", "description": "Job title if known"},
            "company": {"type": "string", "description": "Company name if known"},
        },
        "required": ["job_description"],
    },
    _score_job)


# --- TIME & DATE ---
def _get_time() -> str:
    from datetime import datetime
    now = datetime.now()
    return f"Current time: {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}"

# --- SKILL WORKSHOP ---
def _list_skills() -> str:
    from brain.skill_workshop import list_available_skills
    return list_available_skills()

register("list_available_skills",
    "Show skills Lucy can build herself from the catalog. Use for 'what skills can lucy learn', 'list skill workshop'.",
    {"type": "object", "properties": {}},
    _list_skills)


def _build_skill(skill_name: str) -> str:
    from brain.skill_workshop import build_skill
    return build_skill(skill_name)

register("build_skill",
    "Ask Lucy to build a new skill via Claude Code mentor. Saves to _pending for review. Use for 'build skill X', 'learn X', 'create tool for X'.",
    {
        "type": "object",
        "properties": {"skill_name": {"type": "string", "description": "Name from catalog like alpha_vantage, github_trending, etc."}},
        "required": ["skill_name"],
    },
    _build_skill)


def _approve_skill(skill_name: str) -> str:
    from brain.skill_workshop import approve_skill
    return approve_skill(skill_name)

register("approve_skill",
    "Approve a pending skill and activate it. Use after reviewing a built skill.",
    {
        "type": "object",
        "properties": {"skill_name": {"type": "string"}},
        "required": ["skill_name"],
    },
    _approve_skill)


def _reject_skill(skill_name: str, reason: str = "") -> str:
    from brain.skill_workshop import reject_skill
    return reject_skill(skill_name, reason)

register("reject_skill",
    "Reject a pending skill and move to rejected folder.",
    {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["skill_name"],
    },
    _reject_skill)


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
    # Coerce string booleans to real booleans (Groq sometimes sends "true"/"false")
    for k, v in list(args.items()):
        if isinstance(v, str) and v.lower() in ("true", "false"):
            args[k] = v.lower() == "true"
    for tool in TOOLS:
        if tool["function"]["name"] == name:
            try:
                return str(tool["_execute"](**args))
            except Exception as e:
                return f"Error executing {name}: {str(e)}"
    return f"Unknown tool: {name}"


def list_tools() -> list:
    return [t["function"]["name"] for t in TOOLS]



# ============================================================================
# AUTO-LOAD APPROVED SKILLS from brain/skills/_approved/
# ============================================================================

def _load_approved_skills():
    """Load all approved Lucy-built skills from brain/skills/_approved/."""
    import importlib.util
    from pathlib import Path as _P
    
    approved_dir = _P.home() / "Lucy" / "brain" / "skills" / "_approved"
    if not approved_dir.exists():
        return
    
    loaded = []
    for skill_file in approved_dir.glob("*.py"):
        if skill_file.name.startswith("test_") or skill_file.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(skill_file.stem, str(skill_file))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            
            if hasattr(mod, "TOOL_META"):
                meta = mod.TOOL_META
                register(
                    meta["name"],
                    meta["description"],
                    meta["parameters"],
                    meta["function"],
                )
                loaded.append(meta["name"])
        except Exception as e:
            print(f"Failed to load skill {skill_file.name}: {e}")
    
    if loaded:
        print(f"✨ Auto-loaded {len(loaded)} Lucy-built skills: {', '.join(loaded)}")


# Run the auto-loader when this module is imported
_load_approved_skills()
