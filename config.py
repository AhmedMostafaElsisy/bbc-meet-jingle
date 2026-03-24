import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))

CREDENTIALS_FILE = os.path.join(APP_DIR, "credentials.json")
TOKEN_FILE = os.path.join(APP_DIR, "token.json")
PREFS_FILE = os.path.join(APP_DIR, "prefs.json")
ASSETS_DIR = os.path.join(APP_DIR, "assets")
JINGLE_FILE = os.path.join(ASSETS_DIR, "bbc_news_theme.mp3")  # default fallback
CUSTOM_JINGLES_DIR = os.path.join(APP_DIR, "assets", "custom")

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

POLL_INTERVAL_SECONDS = 30
DEFAULT_JINGLE_DURATION = 16.8  # seconds — fallback if audio duration can't be read

# Built-in jingles: {display_name: filename relative to assets/}
BUILTIN_JINGLES = {
    "BBC News": "bbc_news_theme.mp3",
    "Netflix": "netflix.mp3",
}

DEFAULT_JINGLE = "BBC News"

VOLUME_PRESETS = {
    "Low": 0.3,
    "Medium": 0.6,
    "Full": 1.0,
}
