"""
Lucy's Gmail integration.
Read, search, draft, and send emails through Google API.
"""

import base64
from email.mime.text import MIMEText
from brain.google_auth import get_gmail_service

GMAIL_TRIGGERS = [
    "email", "emails", "inbox", "gmail", "mail",
    "unread", "read my email", "check my email",
    "send email", "draft email", "compose email",
    "reply to", "any new emails", "messages",
    "save draft", "save it to draft", "save to draft",
    "update draft", "send it", "send the email",
    "draft a response", "draft response", "create response",
    "respond to", "reply", "response for",
]


def needs_gmail(text: str) -> bool:
    t = text.lower()
    # Don't catch requests meant for contacts, meet, or sheets
    if any(w in t for w in ["contact", "contacts", "add contact", "save contact", "delete contact",
                             "google meet", "meet link", "video call", "create a meeting",
                             "spreadsheet", "sheet", "sheets", "create a sheet", "save to sheet"]):
        return False
    return any(trigger in t for trigger in GMAIL_TRIGGERS)


def list_emails(max_results: int = 10, unread_only: bool = False) -> str:
    service = get_gmail_service()
    query = "is:unread" if unread_only else ""
    results = service.users().messages().list(
        userId="me", maxResults=max_results, q=query
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return "No unread emails." if unread_only else "Inbox is empty."

    lines = [f"**{'Unread' if unread_only else 'Recent'} emails:**\n"]
    for i, msg in enumerate(messages, 1):
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()

        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        sender = headers.get("From", "Unknown")
        subject = headers.get("Subject", "(no subject)")
        date = headers.get("Date", "")

        # Clean sender name
        if "<" in sender:
            sender = sender.split("<")[0].strip().strip('"')

        snippet = detail.get("snippet", "")[:80]
        lines.append(f"{i}. **{subject}**")
        lines.append(f"   From: {sender} — {snippet}...")
        lines.append("")

    lines.append(f"*{len(messages)} emails shown*")
    return "\n".join(lines)


def read_email(index: int = 1, search_query: str = "") -> str:
    service = get_gmail_service()
    query = search_query if search_query else ""
    results = service.users().messages().list(
        userId="me", maxResults=index, q=query
    ).execute()

    messages = results.get("messages", [])
    if not messages or index > len(messages):
        return "Couldn't find that email."

    msg = messages[index - 1]
    detail = service.users().messages().get(userId="me", id=msg["id"]).execute()

    headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
    sender = headers.get("From", "Unknown")
    subject = headers.get("Subject", "(no subject)")
    date = headers.get("Date", "")

    # Extract body — handle plain text, HTML, and nested multipart
    body = ""
    payload = detail.get("payload", {})
    
    def _extract_body(payload):
        """Recursively search for body content in email parts."""
        texts = {"plain": "", "html": ""}
        if "body" in payload and payload["body"].get("data"):
            mime = payload.get("mimeType", "")
            decoded = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
            if "plain" in mime:
                texts["plain"] = decoded
            elif "html" in mime:
                texts["html"] = decoded
        if "parts" in payload:
            for part in payload["parts"]:
                sub = _extract_body(part)
                if sub["plain"]:
                    texts["plain"] = sub["plain"]
                if sub["html"] and not texts["html"]:
                    texts["html"] = sub["html"]
        return texts
    
    texts = _extract_body(payload)
    if texts["plain"]:
        body = texts["plain"]
    elif texts["html"]:
        # Strip HTML tags to get readable text
        import re as _re
        body = texts["html"]
        body = _re.sub(r'<style[^>]*>.*?</style>', '', body, flags=_re.DOTALL)
        body = _re.sub(r'<script[^>]*>.*?</script>', '', body, flags=_re.DOTALL)
        body = _re.sub(r'<[^>]+>', ' ', body)
        body = _re.sub(r'&nbsp;', ' ', body)
        body = _re.sub(r'&amp;', '&', body)
        body = _re.sub(r'&lt;', '<', body)
        body = _re.sub(r'&gt;', '>', body)
        body = _re.sub(r'\s+', ' ', body).strip()
    
    body = body[:2000].strip() if body else "(no readable content)"
    # Use snippet as fallback
    if body == "(no readable content)":
        body = detail.get("snippet", "(no content)")

    return f"## {subject}\n**From:** {sender}\n**Date:** {date}\n\n{body}"


def draft_email(to: str, subject: str, body: str) -> str:
    service = get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()

    return f"Draft created: **{subject}** to {to}. Check your Gmail drafts to review and send."


def send_email(to: str, subject: str, body: str) -> str:
    service = get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    return f"Email sent: **{subject}** to {to}"


def smart_reply(email_index: int, extra_instructions: str = "") -> str:
    """Read an email and generate a smart reply, then save as Gmail draft."""
    import os
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()

    # Read the original email
    original = read_email(index=email_index)
    if "no readable content" in original.lower():
        return "Couldn't read that email to generate a reply."

    # Extract sender email from the original
    import re
    sender_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', original)
    sender = sender_match.group(0) if sender_match else ""

    # Extract subject
    subj_match = re.search(r'^## (.+)$', original, re.MULTILINE)
    subject = subj_match.group(1) if subj_match else "Re: your email"
    if not subject.startswith("Re:"):
        subject = f"Re: {subject}"

    # Generate reply via Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = (
        f"You are writing an email reply on behalf of Krishna Amarneni.\n"
        f"Krishna runs WealthClaude (wealthclaude.com), an AI portfolio tracker.\n"
        f"His email is krishna.amarneni@gmail.com.\n\n"
        f"Original email:\n{original}\n\n"
        f"Write a professional, friendly reply. Keep it concise — 3-5 sentences.\n"
        f"Only include From, To, Subject, and the message body.\n"
        f"From should be Krishna's real email only.\n"
        f"Do NOT add CC or BCC.\n"
    )
    if extra_instructions:
        prompt += f"Additional instructions: {extra_instructions}\n"

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )
    reply_text = response.choices[0].message.content.strip()

    # Extract just the body from the generated reply
    body_lines = []
    started = False
    for line in reply_text.split("\n"):
        if line.strip().startswith(("From:", "To:", "Subject:", "CC:", "BCC:")):
            continue
        if line.strip():
            started = True
        if started:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    if not body:
        body = reply_text

    # Actually save to Gmail drafts
    try:
        result = draft_email(sender, subject, body)
        return f"**Draft reply to {sender}:**\n\n{body}\n\n---\n✅ {result}\n\n*Say 'update draft' with changes, or 'send it' to send.*"
    except Exception as e:
        return f"**Generated reply:**\n\n{body}\n\n---\n⚠️ Couldn't save to drafts: {str(e)}"


def handle_gmail(text: str) -> str:
    t = text.lower()
    import re

    # 1. Read specific email: "read email 3", "show full email 3", "email number 3"
    num_match = re.search(r'(\d+)', t)
    has_email_word = any(w in t for w in ["email", "mail", "message"])
    has_read_word = any(w in t for w in ["read", "open", "show", "view", "full", "see", "display"])
    
    if num_match and has_email_word and has_read_word:
        return read_email(index=int(num_match.group(1)))

    # 2. Reply to email: "reply to email 3", "respond to email 3", "draft response for 3"
    if num_match and any(w in t for w in ["reply", "respond", "response"]):
        extra = ""
        # Check for extra instructions after the number
        after_num = text[num_match.end():].strip()
        if after_num:
            extra = after_num
        return smart_reply(int(num_match.group(1)), extra)

    # 3. Draft/send email to address
    email_addr = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
    if email_addr and any(w in t for w in ["draft", "compose", "write", "create", "send", "email to", "mail to"]):
        to_addr = email_addr.group(0)
        subj_match = re.search(r'subject\s+(.+?)(?:\s+body\s+|\s+message\s+|$)', text, re.IGNORECASE)
        body_match = re.search(r'(?:body|message)\s+(.+)', text, re.IGNORECASE)
        subject = subj_match.group(1).strip() if subj_match else ""
        body = body_match.group(1).strip() if body_match else ""
        
        if subject and body:
            if "send" in t:
                return send_email(to_addr, subject, body)
            return draft_email(to_addr, subject, body)
        if subject:
            return f"Got it — email to **{to_addr}** about **{subject}**. What should the message say?"
        return f"I'll draft an email to **{to_addr}**. What should the **subject** and **message** be?"

    # 4. Unread emails
    if any(w in t for w in ["unread", "new email", "any new", "check my"]):
        return list_emails(unread_only=True)

    # 5. List inbox
    if any(w in t for w in ["inbox", "recent", "my email", "list", "show"]):
        return list_emails(max_results=10)

    # Catch "draft a response" / "reply to this" without a number — assume last email context
    if any(w in t for w in ["reply", "respond", "response", "draft a"]):
        # Default to email 1 if no number specified
        extra = t.replace("draft", "").replace("reply", "").replace("respond", "").replace("response", "").replace("a", "").strip()
        return smart_reply(1, extra)

    # Default
    return list_emails(max_results=5)


def draft_email_with_attachment(to: str, subject: str, body: str, attachment_path: str = "") -> str:
    """Create a Gmail draft with an optional file attachment."""
    import base64
    import mimetypes
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    from pathlib import Path as _P
    
    try:
        service = get_gmail_service()
        
        message = MIMEMultipart()
        message["to"] = to
        message["subject"] = subject
        message.attach(MIMEText(body, "plain"))
        
        attached_name = ""
        if attachment_path:
            fpath = _P(attachment_path).expanduser()
            if fpath.exists():
                ctype, encoding = mimetypes.guess_type(str(fpath))
                if ctype is None or encoding is not None:
                    ctype = "application/octet-stream"
                main_type, sub_type = ctype.split("/", 1)
                with fpath.open("rb") as f:
                    file_data = f.read()
                part = MIMEBase(main_type, sub_type)
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={fpath.name}",
                )
                message.attach(part)
                attached_name = fpath.name
            else:
                return f"❌ Attachment not found: {attachment_path}"
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw}},
        ).execute()
        
        status = f"Draft created: **{subject}** to {to}"
        if attached_name:
            status += f"\n📎 Attached: {attached_name}"
        status += "\nCheck your Gmail drafts to review and send."
        return status
    except Exception as e:
        return f"❌ Failed to create draft: {str(e)}"
