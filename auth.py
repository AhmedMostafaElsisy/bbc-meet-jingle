import json
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import CREDENTIALS_FILE, SCOPES, TOKEN_FILE


def load_credentials() -> Credentials | None:
    """Load credentials from token.json, refreshing if expired. Returns None if unavailable."""
    if not os.path.exists(TOKEN_FILE):
        return None

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except RefreshError:
            return None

    return None


def run_auth_flow() -> Credentials | None:
    """Run the OAuth browser flow. Returns credentials or None if credentials.json is missing."""
    if not os.path.exists(CREDENTIALS_FILE):
        return None

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return creds


def _save_token(creds: Credentials) -> None:
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
