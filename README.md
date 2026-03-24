# BBC Meet Jingle

A macOS menu bar app that plays the BBC News theme music before your Google Meet calls — timed so the jingle ends exactly when the meeting starts.

Inspired by [Riley Walz](https://x.com/rileywalz)'s original Microsoft Teams version.

![macOS](https://img.shields.io/badge/macOS-menu%20bar-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-green) ![Tests](https://img.shields.io/badge/tests-107%20passed-brightgreen) ![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen)

## How It Works

The app sits in your macOS menu bar with a broadcast icon. It watches your Google Calendar and when a Google Meet call is approaching:

1. **Countdown** — shows a live second-by-second countdown: `Standup in 0:45`
2. **Jingle** — plays your chosen sound, timed so it finishes right as the meeting starts
3. **Urgent** — the last 10 seconds show a red indicator: `🔴 Standup in 0:07`
4. **Live** — at meeting time: `🟢 Standup is live!` — click to join the call in your browser

## Features

- **Live countdown** in the menu bar, updated every second
- **Precision audio timing** — jingle ends exactly at meeting start, regardless of sound duration
- **Multiple jingles** — choose from BBC News, Netflix ta-dum, or add your own
- **Custom sound upload** — import any `.mp3`, `.wav`, or `.ogg` via the native file picker
- **Click to join** — opens the Google Meet link in your browser
- **Preferences saved** — jingle selection and volume persist across restarts
- **Template icon** — adapts to light/dark mode automatically

## Setup

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Calendar API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Google Calendar API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Desktop app**
6. Download the JSON and save it as `credentials.json` in the project root
7. Configure the OAuth consent screen if prompted (add your email as a test user)

### 3. Add audio files

Place your jingle audio files in the `assets/` folder:

```
assets/
├── bbc_news_theme.mp3   # BBC News theme (~17s)
├── netflix.mp3          # Netflix ta-dum (~2.5s)
├── icon.png             # Menu bar icon (included)
└── custom/              # Your custom sounds go here
```

### 4. Run

```bash
python app.py
```

On first launch, click **"Authorize Google Calendar"** in the menu bar dropdown to complete the OAuth flow.

## Menu Bar

| State | Menu Bar | Description |
|-------|----------|-------------|
| Idle | `((•))` | No upcoming meetings |
| Countdown | `((•)) Standup in 2:05` | Live countdown to next Meet |
| Urgent | `🔴 Standup in 0:07` | Last 10 seconds |
| Live | `🟢 Standup is live!` | Meeting started — click to join |

### Dropdown Menu

- **Join Meeting** — click to open the Meet link
- **Jingle Enabled** — toggle on/off
- **Skip Next Jingle** — one-time skip
- **Test Jingle** — preview the sound
- **Jingle** — pick BBC News, Netflix, custom sounds, or import new ones
- **Settings** — volume (Low / Medium / Full)
- **Authorize Google Calendar** — OAuth setup

## Project Structure

```
├── app.py                # Main menu bar app (entry point)
├── calendar_watcher.py   # Google Calendar polling logic
├── audio_player.py       # Jingle playback + multi-sound support
├── auth.py               # Google OAuth flow helpers
├── config.py             # Constants & configuration
├── assets/
│   ├── icon.png          # Menu bar broadcast icon
│   └── custom/           # User-imported custom jingles
├── tests/                # Unit tests (107 tests, 93% coverage)
├── requirements.txt
└── setup.py              # py2app config for building .app bundle
```

## Build as .app (optional)

```bash
pip install py2app
python setup.py py2app
```

Creates a standalone `.app` in `dist/` that can be added to **Login Items** in System Settings for auto-start.

## Troubleshooting

| Status | Fix |
|--------|-----|
| ⚠️ No credentials.json | Follow the Google Calendar API setup above |
| 🔑 Re-authorize needed | Click "Authorize Google Calendar" in the menu |
| ⚠️ Offline | Check internet — the app retries automatically |
| Missing audio | Place `.mp3` files in `assets/` and restart |

## Tech Stack

- **[rumps](https://github.com/jaredks/rumps)** — macOS menu bar framework
- **[pygame](https://www.pygame.org/)** — audio playback
- **[google-api-python-client](https://github.com/googleapis/google-api-python-client)** — Google Calendar API
- **Python 3.10+**

## License

MIT
