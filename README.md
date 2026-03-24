# BBC Meet Jingle

A macOS menu bar app that plays the BBC News theme music before your Google Meet calls — timed so the jingle ends exactly when the meeting starts.

![macOS](https://img.shields.io/badge/macOS-menu%20bar-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-green) ![Tests](https://img.shields.io/badge/tests-176%20passed-brightgreen) ![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)

## How It Works

The app sits in your macOS menu bar with a broadcast icon. It watches your Google Calendar and when a Google Meet call is approaching:

1. **Countdown** — shows a live second-by-second countdown: `Standup in 0:45`
2. **Jingle** — plays your chosen sound, timed so it finishes right as the meeting starts
3. **Urgent** — the last 10 seconds show a red indicator: `🔴 Standup in 0:07`
4. **Live** — at meeting time: `🟢 Standup is live!` — click to join the call in your browser (stays for 2 minutes)

### Timing

| Parameter | Value |
|-----------|-------|
| Calendar poll interval | Every **30 seconds** |
| Countdown update | Every **1 second** |
| Jingle start | **Sound duration** before meeting (e.g. 16.8s for BBC News) |
| Live indicator | **2 minutes** after meeting start |

## Features

- **Live countdown** in the menu bar, updated every second
- **Precision audio timing** — jingle ends exactly at meeting start, regardless of sound duration
- **Multiple jingles** — choose from BBC News, Netflix ta-dum, or add your own
- **Custom sound upload** — import any `.mp3`, `.wav`, `.ogg`, or `.m4a` via the native file picker
- **Click to join** — opens the Google Meet link in your browser
- **Snooze** — mute jingles for 30 min, 1 hour, 2 hours, or until tomorrow
- **Quiet hours** — auto-mute after 6 PM / 8 PM / 10 PM (configurable)
- **Work hours only** — restrict jingles to work days and hours (Mon–Fri, 9–6, customizable)
- **Status-aware icon** — menu bar shows current state (snoozed, quiet hours, off hours)
- **Preferences saved** — all settings persist across restarts
- **Template icon** — adapts to light/dark mode automatically
- **Auto-start** — runs as a Launch Agent, starts on login with no terminal needed

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
├── netflix.mp3          # Netflix ta-dum (~5s)
├── icon.png             # Menu bar icon (included)
└── custom/              # Your custom sounds go here
```

### 4. Run

```bash
python app.py
```

On first launch, click **"Authorize Google Calendar"** in the menu bar dropdown to complete the OAuth flow.

### 5. Auto-start (optional)

To run automatically on login without a terminal, install as a Launch Agent:

```bash
# Copy the plist (edit paths inside to match your setup)
cp com.user.bbcmeetjingle.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.user.bbcmeetjingle.plist
```

## Menu Bar States

| State | Menu Bar | Description |
|-------|----------|-------------|
| Idle | *(icon only)* | No upcoming meetings, jingles active |
| Jingles off | `🔇 Jingles off` | Jingle toggle is disabled |
| Snoozed | `😴 Snoozed 45m` | Snooze is active |
| Quiet hours | `🌙 Quiet hours` | Outside quiet hours window |
| Off hours | `🏢 Off hours` | Outside work hours/days |
| Countdown | `Standup in 2:05` | Live countdown to next Meet |
| Urgent | `🔴 Standup in 0:07` | Last 10 seconds |
| Live | `🟢 Standup is live!` | Meeting started — click to join |

### Dropdown Menu

- **Join Meeting** — click to open the Meet link
- **Jingle Enabled** — toggle on/off
- **Skip Next Jingle** — one-time skip
- **Test Jingle** — preview the sound
- **Jingle** — pick BBC News, Netflix, custom sounds, or import new ones
- **Snooze** — 30 min / 1 hour / 2 hours / Until tomorrow / Cancel
- **Schedule**
  - **Quiet Hours** — enable + presets (After 6 PM / 8 PM / 10 PM)
  - **Work Hours Only** — enable + presets (9–5, 9–6, 8–6, 10–7) + per-day toggles
- **Settings** — volume (Low / Medium / Full)
- **Authorize Google Calendar** — OAuth setup

## Project Structure

```
├── app.py                # Main menu bar app (entry point)
├── calendar_watcher.py   # Google Calendar polling logic
├── audio_player.py       # Jingle playback + multi-sound support
├── auth.py               # Google OAuth flow helpers
├── config.py             # Constants & configuration
├── schedule.py           # Quiet hours, work days, snooze logic
├── assets/
│   ├── icon.png          # Menu bar broadcast icon
│   └── custom/           # User-imported custom jingles
├── tests/                # Unit tests (176 tests, 95% coverage)
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
| ⚠️ Offline | Check internet — the app retries every 30 seconds |
| Missing audio | Place `.mp3` files in `assets/` and restart |

## Tech Stack

- **[rumps](https://github.com/jaredks/rumps)** — macOS menu bar framework
- **[pygame](https://www.pygame.org/)** — audio playback
- **[google-api-python-client](https://github.com/googleapis/google-api-python-client)** — Google Calendar API
- **[pyobjc](https://pyobjc.readthedocs.io/)** — native macOS file picker & Dock hiding
- **Python 3.10+**

## License

MIT
