"""
Lucy's Google Contacts integration.
Save, search, update, and delete contacts.
"""

from brain.google_auth import get_credentials
from googleapiclient.discovery import build

CONTACTS_TRIGGERS = [
    "contact", "contacts", "save contact", "add contact",
    "delete contact", "remove contact", "update contact",
    "find contact", "search contact", "who is",
    "phone number", "email for", "save this as contact",
    "my contacts", "list contacts",
]


def needs_contacts(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in CONTACTS_TRIGGERS)


def _get_people_service():
    return build("people", "v1", credentials=get_credentials())


def search_contact(name: str) -> str:
    service = _get_people_service()
    results = service.people().searchContacts(
        query=name, readMask="names,emailAddresses,phoneNumbers", pageSize=5
    ).execute()

    contacts = results.get("results", [])
    if not contacts:
        return f"No contact found for '{name}'."

    lines = [f"**Contacts matching '{name}':**\n"]
    for c in contacts:
        person = c.get("person", {})
        names = person.get("names", [{}])
        emails = person.get("emailAddresses", [])
        phones = person.get("phoneNumbers", [])

        display_name = names[0].get("displayName", "Unknown") if names else "Unknown"
        email_str = ", ".join(e.get("value", "") for e in emails) if emails else "no email"
        phone_str = ", ".join(p.get("value", "") for p in phones) if phones else "no phone"

        lines.append(f"- **{display_name}** — {email_str} | {phone_str}")

    return "\n".join(lines)


def add_contact(name: str, email: str = "", phone: str = "") -> str:
    service = _get_people_service()

    body = {"names": [{"givenName": name}]}
    if email:
        body["emailAddresses"] = [{"value": email}]
    if phone:
        body["phoneNumbers"] = [{"value": phone}]

    try:
        person = service.people().createContact(body=body).execute()
        resource = person.get("resourceName", "")
        return f"Contact saved: **{name}**" + (f" ({email})" if email else "") + (f" | {phone}" if phone else "")
    except Exception as e:
        return f"Couldn't save contact: {str(e)}"


def delete_contact(name: str) -> str:
    service = _get_people_service()
    results = service.people().searchContacts(
        query=name, readMask="names", pageSize=1
    ).execute()

    contacts = results.get("results", [])
    if not contacts:
        return f"No contact found for '{name}' to delete."

    resource = contacts[0].get("person", {}).get("resourceName", "")
    if not resource:
        return "Couldn't find the contact resource to delete."

    try:
        service.people().deleteContact(resourceName=resource).execute()
        return f"Deleted contact: **{name}**"
    except Exception as e:
        return f"Couldn't delete contact: {str(e)}"


def list_contacts(max_results: int = 20) -> str:
    service = _get_people_service()
    results = service.people().connections().list(
        resourceName="people/me", pageSize=max_results,
        personFields="names,emailAddresses,phoneNumbers"
    ).execute()

    connections = results.get("connections", [])
    if not connections:
        return "No contacts found."

    lines = ["**Your contacts:**\n"]
    for c in connections:
        names = c.get("names", [{}])
        emails = c.get("emailAddresses", [])
        display_name = names[0].get("displayName", "Unknown") if names else "Unknown"
        email_str = emails[0].get("value", "") if emails else ""
        entry = f"- **{display_name}**"
        if email_str:
            entry += f" — {email_str}"
        lines.append(entry)

    lines.append(f"\n*{len(connections)} contacts*")
    return "\n".join(lines)


def handle_contacts(text: str) -> str:
    t = text.lower()
    import re

    if any(w in t for w in ["list", "my contacts", "all contacts", "show contacts"]):
        return list_contacts()

    if any(w in t for w in ["delete", "remove"]):
        name = re.sub(r'(?:delete|remove)\s+(?:contact\s+)?', '', t, flags=re.IGNORECASE).strip()
        if name:
            return delete_contact(name)
        return "Which contact should I delete?"

    if any(w in t for w in ["save", "add", "create"]):
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        phone_match = re.search(r'[\d\s\-\+\(\)]{7,}', text)
        name = re.sub(r'(?:save|add|create)\s+(?:contact\s+)?(?:for\s+)?', '', t, flags=re.IGNORECASE)
        name = re.sub(r'[\w.+-]+@[\w-]+\.[\w.]+', '', name)
        if phone_match:
            name = name.replace(phone_match.group(0), '')
        name = name.strip().strip(',').strip()
        if not name:
            return "What's the contact name? Say: 'add contact Sai sai@gmail.com'"
        email = email_match.group(0) if email_match else ""
        phone = phone_match.group(0).strip() if phone_match else ""
        return add_contact(name, email, phone)

    if any(w in t for w in ["find", "search", "who is", "look up"]):
        name = re.sub(r'(?:find|search|who is|look up)\s+(?:contact\s+)?', '', t, flags=re.IGNORECASE).strip()
        if name:
            return search_contact(name)
        return "Who are you looking for?"

    return list_contacts()
