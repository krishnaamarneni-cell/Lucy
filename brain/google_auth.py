"""
Unified Google OAuth for Lucy.
One login covers Gmail, Calendar, YouTube, Drive, Contacts, Sheets.
Token is cached locally — you only authenticate once.
"""

import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CREDENTIALS_FILE = Path.home() / "Lucy" / "credentials" / "google_oauth.json"
TOKEN_FILE = Path.home() / "Lucy" / "credentials" / "google_token.json"

# All scopes Lucy needs — one auth covers everything
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

_creds = None


def get_credentials() -> Credentials:
    """Get or refresh Google OAuth credentials."""
    global _creds

    if _creds and _creds.valid:
        return _creds

    if TOKEN_FILE.exists():
        _creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if _creds and _creds.expired and _creds.refresh_token:
        _creds.refresh(Request())
        TOKEN_FILE.write_text(_creds.to_json())
        return _creds

    if not _creds or not _creds.valid:
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                f"Google OAuth credentials not found at {CREDENTIALS_FILE}. "
                "Download from Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES
        )
        _creds = flow.run_local_server(port=8766, open_browser=False)
        TOKEN_FILE.write_text(_creds.to_json())

    return _creds


def get_gmail_service():
    """Get authenticated Gmail API service."""
    return build("gmail", "v1", credentials=get_credentials())


def get_calendar_service():
    """Get authenticated Calendar API service."""
    return build("calendar", "v3", credentials=get_credentials())


def get_youtube_service():
    """Get authenticated YouTube API service."""
    return build("youtube", "v3", credentials=get_credentials())


def get_drive_service():
    """Get authenticated Drive API service."""
    return build("drive", "v3", credentials=get_credentials())


def is_authenticated() -> bool:
    """Check if Google auth token exists and is valid."""
    try:
        creds = get_credentials()
        return creds is not None and creds.valid
    except Exception:
        return False
