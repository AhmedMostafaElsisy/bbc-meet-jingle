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

# Allowed audio file extensions for import
ALLOWED_AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".m4a")

# Display timing
URGENT_SECONDS = 10  # red indicator in last N seconds
LIVE_TIMEOUT_SECONDS = 120  # keep "is live!" for 2 min after start

# Schedule defaults
DEFAULT_WORK_START = "09:00"
DEFAULT_WORK_END = "18:00"
DEFAULT_WORK_DAYS = [0, 1, 2, 3, 4]  # Mon-Fri (0=Monday)

# Snooze duration options in minutes
SNOOZE_OPTIONS = {
    "30 minutes": 30,
    "1 hour": 60,
    "2 hours": 120,
    "Until tomorrow": 0,  # sentinel — computed dynamically
}
