"""
Lucy's Task Orchestrator.
Breaks complex multi-step requests into ordered tasks and executes them.

Example: "create a meeting at 2pm and send the link to sai"
→ Step 1: Find Sai's email in contacts
→ Step 2: Create Google Meet at 2pm
→ Step 3: Send meeting link to Sai's email
"""

import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


def needs_orchestration(text: str) -> bool:
    """Check if the request has multiple tasks joined by 'and', 'then', 'also'."""
    t = text.lower()
    
    # Must have a conjunction suggesting multiple actions
    has_conjunction = any(w in t for w in [" and ", " then ", " also ", " after that ",
                                            " plus ", " as well as "])
    if not has_conjunction:
        return False
    
    # Must have at least 2 action verbs
    action_words = ["create", "send", "draft", "read", "check", "add", "delete",
                    "save", "schedule", "share", "update", "cancel", "find",
                    "show", "list", "make", "set", "remove", "browse", "search"]
    count = sum(1 for w in action_words if w in t)
    return count >= 2


def _match_common_pattern(text: str) -> list | None:
    """Match common multi-step patterns without using LLM."""
    t = text.lower()
    
    # Pattern: create meet + send link to someone
    if any(w in t for w in ["meet", "meeting", "video call"]) and any(w in t for w in ["send", "share", "email"]):
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        to_addr = email_match.group(0) if email_match else ""
        return [
            {"tool": "meet", "instruction": text.split(" and ")[0].strip()},
            {"tool": "gmail_direct", "instruction": text, "to": to_addr},
        ]
    
    # Pattern: read email + draft response
    if "read email" in t and any(w in t for w in ["draft", "respond", "reply", "response"]):
        num_match = re.search(r'(\d+)', t)
        num = num_match.group(1) if num_match else "1"
        msg = ""
        for pattern in [r'saying\s+(.+?)$', r'response\s+(.+?)$', r'reply\s+(.+?)$']:
            m = re.search(pattern, t)
            if m:
                msg = m.group(1)
                break
        return [
            {"tool": "gmail_read", "instruction": f"read email {num}"},
            {"tool": "gmail_reply", "instruction": f"reply to email {num}", "message": msg},
        ]

    # Pattern: check emails + save to sheet
    if "email" in t and "sheet" in t and "save" in t:
        sheet_match = re.search(r'(?:called|named)\s+(.+?)(?:\s+and|\s*$)', t)
        sheet_name = sheet_match.group(1).strip() if sheet_match else "Email Data"
        return [
            {"tool": "gmail", "instruction": "list all recent emails"},
            {"tool": "sheets", "instruction": f"create a sheet called {sheet_name} and save all email addresses to it"},
        ]

    return None


def plan_steps(user_message: str) -> list:
    """Plan steps — try common patterns first, fall back to LLM."""
    # Try hardcoded patterns first (faster, more reliable)
    pattern_match = _match_common_pattern(user_message)
    if pattern_match:
        return pattern_match

    # Fall back to LLM planning
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{
            "role": "system",
            "content": (
                "You are a task planner. Break the user's request into simple, ordered steps. "
                "Each step must be a single action Lucy can do. "
                "Return ONLY a JSON array of objects with 'tool' and 'instruction' fields. "
                "No other text, no markdown, no explanation.\n\n"
                "Available tools:\n"
                "- gmail: read emails, send email, draft email\n"
                "- calendar: check schedule, create events\n"
                "- meet: create google meet with link\n"
                "- contacts: find, add, delete contacts\n"
                "- sheets: create/update spreadsheets\n"
                "- tasks: add, complete, delete tasks\n"
                "- youtube: check channels, get videos\n"
                "- search: web search for information\n"
                "- browse: read a website\n"
                "- goose: git operations, shell commands\n"
                "- career: job search, resume generation\n"
                "- brain: general conversation/questions\n\n"
                "Example input: 'create a meeting at 2pm and send the link to sai@gmail.com'\n"
                "Example output: [{\"tool\":\"meet\",\"instruction\":\"create a google meet at 2pm\"},{\"tool\":\"gmail\",\"instruction\":\"send email to sai@gmail.com with the meeting link from the previous step\"}]\n\n"
                "Example input: 'check my emails and save all sender addresses to a sheet'\n"
                "Example output: [{\"tool\":\"gmail\",\"instruction\":\"list all recent emails\"},{\"tool\":\"sheets\",\"instruction\":\"create a sheet called Email Senders and save all sender email addresses from the previous step\"}]"
            )
        }, {
            "role": "user",
            "content": user_message
        }],
    )

    text = response.choices[0].message.content.strip()
    # Clean markdown fences if present
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        steps = json.loads(text)
        if isinstance(steps, list):
            return steps
    except json.JSONDecodeError:
        pass

    return []


def execute_steps(steps: list) -> str:
    """Execute each step in order, passing context between them."""
    from brain.gmail import handle_gmail, send_email, draft_email
    from brain.calendar import handle_calendar
    from brain.meet import handle_meet
    from brain.contacts import handle_contacts, search_contact
    from brain.sheets import handle_sheets
    from brain.tasks import handle_task
    from brain.youtube import handle_youtube
    from brain.search import web_search
    from brain.browser import summarize_page
    import re as _re

    results = []
    context = {}  # Store results from previous steps

    for i, step in enumerate(steps):
        tool = step.get("tool", "brain")
        instruction = step.get("instruction", "")

        try:
            result = ""

            if tool == "meet":
                result = handle_meet(instruction)
                # Extract meet link for later steps
                link_match = _re.search(r'https://meet\.google\.com/[\w-]+', result)
                if link_match:
                    context["meet_link"] = link_match.group(0)
                time_match = _re.search(r'When: (.+)', result)
                if time_match:
                    context["meet_time"] = time_match.group(1)

            elif tool == "gmail_direct":
                # Direct send with meet context — no handler needed
                to_addr = step.get("to", "")
                if not to_addr:
                    email_match = _re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', instruction)
                    to_addr = email_match.group(0) if email_match else ""
                meet_link = context.get("meet_link", "")
                meet_time = context.get("meet_time", "")
                # Extract custom message
                msg = ""
                for pat in [r'saying\s+(.+?)$', r'message\s+(.+?)$']:
                    m = _re.search(pat, instruction, _re.IGNORECASE)
                    if m:
                        msg = m.group(1).strip()
                        break
                if not msg:
                    msg = "Here are the meeting details."
                body = f"Hi,\n\n{msg}\n\nGoogle Meet link: {meet_link}\nTime: {meet_time}\n\nBest,\nKrishna"
                result = send_email(to_addr, "Meeting Invitation", body)
                context["email_sent"] = True

            elif tool == "gmail_read":
                # Read a specific email
                num_match = _re.search(r'(\d+)', instruction)
                num = int(num_match.group(1)) if num_match else 1
                from brain.gmail import read_email
                result = read_email(index=num)
                context["last_email"] = result

            elif tool == "gmail_reply":
                # Reply to the email we just read
                email_content = context.get("last_email", "")
                msg = step.get("message", "")
                if email_content:
                    from brain.gmail import smart_reply
                    num_match = _re.search(r'(\d+)', instruction)
                    num = int(num_match.group(1)) if num_match else 1
                    result = smart_reply(num, msg)
                else:
                    result = "No email to reply to."

            elif tool == "gmail":
                # If we have context from previous steps, use it directly
                email_match = _re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', instruction)
                to_addr = email_match.group(0) if email_match else ""
                
                # Check if this is a send/draft step that should use context
                is_send = any(w in instruction.lower() for w in ["send", "draft", "email to", "link"])
                
                if is_send and to_addr and context.get("meet_link"):
                    # Build email with meeting context
                    meet_link = context.get("meet_link", "")
                    meet_time = context.get("meet_time", "")
                    
                    # Extract subject/message from instruction
                    subj_match = _re.search(r'subject\s+(.+?)(?:\s+body|\s+message|\s+with|\s+and|$)', instruction, _re.IGNORECASE)
                    subject = subj_match.group(1) if subj_match else "Meeting Invitation"
                    
                    # Find any custom message in the instruction
                    msg_parts = []
                    for pattern in [r"saying\s+(.+?)$", r"message\s+(.+?)$", r"body\s+(.+?)$", r"with\s+(.+?)$"]:
                        msg_match = _re.search(pattern, instruction, _re.IGNORECASE)
                        if msg_match:
                            msg_parts.append(msg_match.group(1))
                    
                    custom_msg = msg_parts[0] if msg_parts else ""
                    body = f"Hi,\n\n{custom_msg}\n\nGoogle Meet link: {meet_link}\nTime: {meet_time}\n\nBest,\nKrishna"
                    
                    result = send_email(to_addr, subject, body)
                    context["email_sent"] = True
                elif is_send and to_addr:
                    # Send without meet context
                    msg_match = _re.search(r'(?:saying|message|body|subject)\s+(.+)', instruction, _re.IGNORECASE)
                    body = msg_match.group(1) if msg_match else instruction
                    subject = "From Krishna"
                    subj_match = _re.search(r'subject\s+(.+?)(?:\s+body|\s+message|\s+saying|$)', instruction, _re.IGNORECASE)
                    if subj_match:
                        subject = subj_match.group(1)
                    result = send_email(to_addr, subject, body)
                else:
                    result = handle_gmail(instruction)

            elif tool == "contacts":
                result = handle_contacts(instruction)
                # Extract email if found
                email_match = _re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', result)
                if email_match:
                    context["contact_email"] = email_match.group(0)

            elif tool == "calendar":
                result = handle_calendar(instruction)
            elif tool == "sheets":
                result = handle_sheets(instruction)
            elif tool == "tasks":
                result = handle_task(instruction)
            elif tool == "youtube":
                result = handle_youtube(instruction)
            elif tool == "search":
                result = web_search(instruction)
            elif tool == "browse":
                result = summarize_page(instruction)
            else:
                result = f"{instruction}"

            results.append(result)

        except Exception as e:
            results.append(f"⚠️ Error in step {i+1}: {str(e)}")

    return "\n".join(results)


def handle_orchestration(text: str) -> str:
    """Plan and execute a multi-step request."""
    print(f"🎯 Orchestrator: planning steps for: {text[:80]}")

    steps = plan_steps(text)

    if not steps:
        return "I couldn't break that down into steps. Try being more specific about what you want me to do."

    # Show the plan
    plan_lines = ["**Execution plan:**\n"]
    for i, step in enumerate(steps, 1):
        plan_lines.append(f"{i}. **{step.get('tool', '?')}** — {step.get('instruction', '?')}")
    plan_lines.append("\n**Executing...**\n")

    plan_text = "\n".join(plan_lines)
    result = execute_steps(steps)

    return f"{plan_text}\n{result}"
