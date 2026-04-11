"""
Lucy's Google Sheets integration.
Create spreadsheets, read/write data, manage sheets.
"""

from brain.google_auth import get_credentials
from googleapiclient.discovery import build

SHEETS_TRIGGERS = [
    "spreadsheet", "sheet", "sheets", "google sheet",
    "create a sheet", "save to sheet", "add to sheet",
    "read sheet", "update sheet", "excel",
]


def needs_sheets(text: str) -> bool:
    t = text.lower()
    if any(trigger in t for trigger in SHEETS_TRIGGERS):
        return True
    # Also catch "save ... to a sheet" pattern
    if "save" in t and "sheet" in t:
        return True
    return False


def _get_sheets_service():
    return build("sheets", "v4", credentials=get_credentials())


def _get_drive_service():
    return build("drive", "v3", credentials=get_credentials())


def create_sheet(title: str, sheet_name: str = "Sheet1", headers: list = None, data: list = None) -> str:
    service = _get_sheets_service()

    body = {"properties": {"title": title}}
    if sheet_name != "Sheet1":
        body["sheets"] = [{"properties": {"title": sheet_name}}]

    try:
        spreadsheet = service.spreadsheets().create(body=body).execute()
        sheet_id = spreadsheet["spreadsheetId"]
        url = spreadsheet["spreadsheetUrl"]

        # Add headers if provided
        if headers:
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{sheet_name}!A1",
                valueInputOption="RAW", body={"values": [headers]}
            ).execute()

        # Add data if provided
        if data:
            start_row = 2 if headers else 1
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{sheet_name}!A{start_row}",
                valueInputOption="RAW", body={"values": data}
            ).execute()

        row_count = len(data) if data else 0
        return f"**Spreadsheet created: [{title}]({url})**\n- Sheet: {sheet_name}\n- Headers: {', '.join(headers) if headers else 'none'}\n- Rows: {row_count}"

    except Exception as e:
        return f"Couldn't create spreadsheet: {str(e)}"


def read_sheet(sheet_id: str, range_str: str = "Sheet1!A:Z") -> str:
    service = _get_sheets_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=range_str
        ).execute()
        rows = result.get("values", [])
        if not rows:
            return "Sheet is empty."

        lines = []
        headers = rows[0] if rows else []
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            lines.append("| " + " | ".join(padded) + " |")

        return "\n".join(lines)
    except Exception as e:
        return f"Couldn't read sheet: {str(e)}"


def append_to_sheet(sheet_id: str, data: list, sheet_name: str = "Sheet1") -> str:
    service = _get_sheets_service()
    try:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id, range=f"{sheet_name}!A:A",
            valueInputOption="RAW", body={"values": data}
        ).execute()
        return f"Added {len(data)} rows to the sheet."
    except Exception as e:
        return f"Couldn't append to sheet: {str(e)}"


def handle_sheets(text: str) -> str:
    t = text.lower()
    import re

    if any(w in t for w in ["create", "new", "make"]):
        # Extract sheet title
        title = "Lucy Data"
        title_match = re.search(r'(?:called|named|title)\s+(.+?)(?:\s+and\s+|\s+with\s+|$)', t)
        if title_match:
            title = title_match.group(1).strip()

        # Extract sheet name
        sheet_name = "Sheet1"
        sheet_match = re.search(r'sheet\s+(?:name\s+)?(\w+)', t)
        if sheet_match and sheet_match.group(1).lower() not in ["called", "named", "and", "with"]:
            sheet_name = sheet_match.group(1)

        # Check if they want to save emails to sheet
        if any(w in t for w in ["email", "emails", "inbox"]):
            from brain.gmail import list_emails
            from brain.google_auth import get_gmail_service
            service = get_gmail_service()
            results = service.users().messages().list(userId="me", maxResults=50).execute()
            messages = results.get("messages", [])

            headers = ["From", "Subject", "Date", "Email Address"]
            data = []
            for msg in messages:
                detail = service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                h = {hdr["name"]: hdr["value"] for hdr in detail.get("payload", {}).get("headers", [])}
                sender = h.get("From", "")
                email_addr = ""
                email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', sender)
                if email_match:
                    email_addr = email_match.group(0)
                if "<" in sender:
                    sender = sender.split("<")[0].strip().strip('"')
                data.append([sender, h.get("Subject", ""), h.get("Date", ""), email_addr])

            return create_sheet(title or "Email Contacts", sheet_name or "Users", headers, data)

        # Generic sheet creation
        headers_match = re.search(r'(?:headers?|columns?)\s+(.+?)(?:\s+and\s+save|$)', t)
        headers = []
        if headers_match:
            headers = [h.strip() for h in headers_match.group(1).split(",")]

        return create_sheet(title, sheet_name, headers if headers else None)

    return "I can create spreadsheets and save data. Try: 'create a sheet called Users and save all email addresses to it'"
