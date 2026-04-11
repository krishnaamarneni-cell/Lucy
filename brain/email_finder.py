"""
Lucy's email finder.
Generates likely email patterns + verifies via SMTP.
Legal, free, ~70% hit rate for corporate emails.
"""

import smtplib
import socket
import dns.resolver
import re


EMAIL_PATTERNS = [
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{first}@{domain}",
    "{f}{last}@{domain}",
    "{first}.{l}@{domain}",
    "{last}.{first}@{domain}",
    "{f}.{last}@{domain}",
    "{last}{f}@{domain}",
    "{first}_{last}@{domain}",
]


def generate_emails(full_name: str, domain: str) -> list:
    """Generate likely email patterns for a person at a domain."""
    parts = full_name.lower().replace("-", " ").split()
    if len(parts) < 2:
        return [f"{parts[0]}@{domain}"]
    
    first = parts[0]
    last = parts[-1]
    f = first[0]
    l = last[0]
    
    domain = domain.lower().replace("www.", "").strip()
    
    emails = []
    for pattern in EMAIL_PATTERNS:
        email = pattern.format(first=first, last=last, f=f, l=l, domain=domain)
        if email not in emails:
            emails.append(email)
    return emails


def verify_email(email: str, timeout: int = 10) -> dict:
    """
    Verify if an email mailbox exists via SMTP.
    Returns dict with 'valid', 'reason'.
    """
    if "@" not in email:
        return {"valid": False, "reason": "invalid format"}
    
    domain = email.split("@")[1]
    
    try:
        # Step 1: Check MX records exist
        mx_records = dns.resolver.resolve(domain, "MX")
        mx = str(mx_records[0].exchange).rstrip(".")
    except Exception as e:
        return {"valid": False, "reason": f"no MX records"}
    
    try:
        # Step 2: Connect to SMTP and check if mailbox exists
        server = smtplib.SMTP(timeout=timeout)
        server.set_debuglevel(0)
        server.connect(mx, 25)
        server.helo("lucy.local")
        server.mail("verify@lucy.local")
        code, message = server.rcpt(email)
        server.quit()
        
        if code == 250:
            return {"valid": True, "reason": "mailbox exists"}
        elif code == 550:
            return {"valid": False, "reason": "mailbox does not exist"}
        else:
            return {"valid": None, "reason": f"ambiguous (code {code})"}
    except socket.timeout:
        return {"valid": None, "reason": "timeout"}
    except smtplib.SMTPServerDisconnected:
        return {"valid": None, "reason": "server disconnected (likely anti-spam)"}
    except Exception as e:
        return {"valid": None, "reason": f"error: {str(e)[:50]}"}


def find_email(full_name: str, domain: str, verify: bool = True) -> str:
    """
    Find the most likely email for a person at a domain.
    Returns a formatted markdown response.
    """
    candidates = generate_emails(full_name, domain)
    
    lines = [f"**Email candidates for {full_name} at {domain}:**\n"]
    
    verified_emails = []
    ambiguous_emails = []
    
    for email in candidates[:5]:  # Check top 5 patterns
        if verify:
            result = verify_email(email, timeout=5)
            if result["valid"] is True:
                verified_emails.append(email)
                lines.append(f"- ✅ **{email}** — verified")
            elif result["valid"] is False:
                lines.append(f"- ❌ {email} — {result['reason']}")
            else:
                ambiguous_emails.append(email)
                lines.append(f"- ⚠️ {email} — {result['reason']}")
        else:
            lines.append(f"- {email}")
    
    if verified_emails:
        lines.append(f"\n**Best match:** `{verified_emails[0]}`")
    elif ambiguous_emails:
        lines.append(f"\n**Likely candidates (couldn't verify):**")
        for e in ambiguous_emails[:3]:
            lines.append(f"  - `{e}`")
        lines.append("\n*Most corporate servers block SMTP verification. These are high-probability guesses based on common patterns.*")
    else:
        lines.append(f"\n**Pattern guesses (verification failed):**")
        for e in candidates[:3]:
            lines.append(f"  - `{e}`")
    
    return "\n".join(lines)


EMAIL_FINDER_TRIGGERS = [
    "find email", "find the email", "guess email",
    "email for", "what is the email", "email address for",
    "find recruiter email", "recruiter email",
]


def needs_email_finder(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in EMAIL_FINDER_TRIGGERS)


def handle_email_finder(text: str) -> str:
    """Parse request and find email."""
    import re
    
    # Extract name and domain
    # Patterns: "find email for John Smith at pfizer.com"
    match = re.search(r'(?:for|of)\s+(.+?)\s+(?:at|@|from)\s+([\w.-]+\.[a-z]{2,})', text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        domain = match.group(2).strip()
        return find_email(name, domain)
    
    # Pattern: "email for John Smith pfizer"
    match = re.search(r'(?:email|recruiter)\s+(?:for|of)?\s*(.+)', text, re.IGNORECASE)
    if match:
        parts = match.group(1).strip().split()
        if len(parts) >= 2:
            # Last word might be company
            last_word = parts[-1].lower()
            if "." not in last_word:
                domain = f"{last_word}.com"
                name = " ".join(parts[:-1])
                return find_email(name, domain)
    
    return "Tell me: 'find email for [Name] at [company.com]'\n\nExample: *find email for John Smith at pfizer.com*"
