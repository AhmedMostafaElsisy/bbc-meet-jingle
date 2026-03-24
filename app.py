#!/usr/bin/env python3
"""BBC Meet Jingle — macOS menu bar app."""

import json
import logging
import os
import threading
import time
import webbrowser
from datetime import datetime, timedelta, timezone

import rumps

from audio_player import AudioPlayer, get_audio_duration, import_custom_jingle
from auth import load_credentials, run_auth_flow
from calendar_watcher import CalendarWatcher
from config import (
    ASSETS_DIR,
    BUILTIN_JINGLES,
    CREDENTIALS_FILE,
    CUSTOM_JINGLES_DIR,
    DEFAULT_JINGLE,
    DEFAULT_JINGLE_DURATION,
    JINGLE_FILE,
    POLL_INTERVAL_SECONDS,
    PREFS_FILE,
    VOLUME_PRESETS,
)

_ICON_PATH = os.path.join(ASSETS_DIR, "icon.png")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_URGENT_SECONDS = 10  # show red indicator in last 10s
_LIVE_TIMEOUT_SECONDS = 120  # keep "is live!" for 2 min after start


def _format_countdown(seconds: float) -> str:
    """Format seconds as M:SS countdown string."""
    total = max(0, int(seconds))
    mins = total // 60
    secs = total % 60
    return f"{mins}:{secs:02d}"


def _load_prefs() -> dict:
    """Load user preferences from disk."""
    if not os.path.exists(PREFS_FILE):
        return {}
    try:
        with open(PREFS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_prefs(prefs: dict) -> None:
    """Save user preferences to disk."""
    try:
        with open(PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except OSError as e:
        logger.error("Failed to save preferences: %s", e)


def _discover_custom_jingles() -> dict[str, str]:
    """Return {display_name: full_path} for user-added jingles."""
    if not os.path.isdir(CUSTOM_JINGLES_DIR):
        return {}
    jingles = {}
    for filename in sorted(os.listdir(CUSTOM_JINGLES_DIR)):
        if filename.lower().endswith((".mp3", ".wav", ".ogg")):
            name = os.path.splitext(filename)[0]
            jingles[name] = os.path.join(CUSTOM_JINGLES_DIR, filename)
    return jingles


def _build_jingle_catalog() -> dict[str, str]:
    """Return {display_name: full_path} for all available jingles."""
    catalog = {}
    for name, filename in BUILTIN_JINGLES.items():
        path = os.path.join(ASSETS_DIR, filename)
        if os.path.exists(path):
            catalog[name] = path
    catalog.update(_discover_custom_jingles())
    return catalog


class BBCMeetJingleApp(rumps.App):
    def __init__(self) -> None:
        super().__init__("", quit_button=None)
        if os.path.exists(_ICON_PATH):
            self.icon = _ICON_PATH
            self.template = True

        # State
        self._credentials = None
        self._watcher: CalendarWatcher | None = None
        self._jingle_enabled = True
        self._skip_next = False
        self._played_events: dict[str, datetime] = {}  # event_id -> start time
        self._volume_label = "Full"
        self._volume = VOLUME_PRESETS["Full"]
        self._next_event: dict | None = None
        self._active_meet_link: str | None = None
        self._is_live = False

        # Jingle catalog & selection
        self._jingle_catalog = _build_jingle_catalog()
        prefs = _load_prefs()
        self._selected_jingle = prefs.get("selected_jingle", DEFAULT_JINGLE)
        saved_volume = prefs.get("volume_label")
        if saved_volume and saved_volume in VOLUME_PRESETS:
            self._volume_label = saved_volume
            self._volume = VOLUME_PRESETS[saved_volume]

        # Resolve initial jingle path
        initial_path = self._jingle_catalog.get(self._selected_jingle, JINGLE_FILE)
        self._player = AudioPlayer(initial_path)
        self._jingle_duration = (
            self._player.duration
            if self._player.duration > 0
            else DEFAULT_JINGLE_DURATION
        )

        # Menu items
        self._join_item = rumps.MenuItem(
            "No upcoming Meet", callback=self._on_join
        )

        self._status_item = rumps.MenuItem("⚠️ No credentials")
        self._status_item.set_callback(None)

        self._jingle_toggle = rumps.MenuItem(
            "Jingle Enabled", callback=self._on_toggle_jingle
        )
        self._jingle_toggle.state = True

        self._skip_item = rumps.MenuItem(
            "⏭ Skip Next Jingle", callback=self._on_skip_next
        )

        self._test_item = rumps.MenuItem(
            "🔊 Test Jingle", callback=self._on_test_jingle
        )

        # Jingle picker submenu
        self._jingle_menu = rumps.MenuItem("🎵 Jingle")
        self._build_jingle_menu()

        # Settings submenu
        settings_menu = rumps.MenuItem("⚙️ Settings")
        volume_menu = rumps.MenuItem("Volume")
        for label in VOLUME_PRESETS:
            item = rumps.MenuItem(
                label, callback=self._make_volume_callback(label)
            )
            item.state = label == self._volume_label
            volume_menu.add(item)
        settings_menu.add(volume_menu)

        self._auth_item = rumps.MenuItem(
            "🔑 Authorize Google Calendar", callback=self._on_authorize
        )

        quit_item = rumps.MenuItem("Quit", callback=self._on_quit)

        self.menu = [
            self._join_item,
            None,
            self._status_item,
            None,
            self._jingle_toggle,
            self._skip_item,
            self._test_item,
            self._jingle_menu,
            settings_menu,
            None,
            self._auth_item,
            quit_item,
        ]

        # Try loading existing credentials
        self._try_load_credentials()

        # Start background loop (calendar poll every 30s + display tick every 1s)
        bg_thread = threading.Thread(target=self._background_loop, daemon=True)
        bg_thread.start()

    # ------------------------------------------------------------------
    # Jingle catalog helpers
    # ------------------------------------------------------------------

    def _build_jingle_menu(self) -> None:
        """Populate the jingle picker submenu (used during init)."""
        for name in self._jingle_catalog:
            item = rumps.MenuItem(
                name, callback=self._make_jingle_callback(name)
            )
            item.state = name == self._selected_jingle
            self._jingle_menu.add(item)

        self._jingle_menu.add(None)  # separator
        add_item = rumps.MenuItem(
            "➕ Add Custom Sound…", callback=self._on_add_custom_jingle
        )
        self._jingle_menu.add(add_item)

    def _rebuild_jingle_menu(self) -> None:
        """Rebuild the jingle picker submenu after importing a new sound."""
        self._jingle_catalog = _build_jingle_catalog()
        self._jingle_menu.clear()
        self._build_jingle_menu()

    def _select_jingle(self, name: str) -> None:
        """Switch to a different jingle by name."""
        path = self._jingle_catalog.get(name)
        if path is None:
            logger.warning("Jingle not found in catalog: %s", name)
            return

        self._selected_jingle = name
        self._player.switch_jingle(path)
        self._jingle_duration = (
            self._player.duration
            if self._player.duration > 0
            else DEFAULT_JINGLE_DURATION
        )

        # Update checkmarks
        for item_name in self._jingle_menu:
            item = self._jingle_menu[item_name]
            if hasattr(item, "state"):
                item.state = item.title == name

        # Persist selection
        self._save_current_prefs()
        logger.info("Switched jingle to: %s (%.1fs)", name, self._jingle_duration)

    def _make_jingle_callback(self, name: str):
        def callback(_) -> None:
            self._select_jingle(name)
        return callback

    def _on_add_custom_jingle(self, _) -> None:
        """Open a file dialog to import a custom jingle."""
        try:
            from AppKit import NSOpenPanel
            panel = NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(True)
            panel.setCanChooseDirectories_(False)
            panel.setAllowsMultipleSelection_(False)
            panel.setTitle_("Choose a jingle audio file")
            panel.setAllowedFileTypes_(["mp3", "wav", "ogg", "m4a"])

            if panel.runModal() == 1:  # NSOKButton
                source_path = str(panel.URLs()[0].path())
                filename = import_custom_jingle(source_path, CUSTOM_JINGLES_DIR)
                if filename:
                    display_name = os.path.splitext(filename)[0]
                    self._rebuild_jingle_menu()
                    self._select_jingle(display_name)
                    logger.info("Imported custom jingle: %s", display_name)
        except ImportError:
            rumps.alert(
                title="File Picker Unavailable",
                message=(
                    "Could not open file picker. Please manually copy your "
                    "audio file (.mp3/.wav/.ogg) into:\n\n"
                    f"{CUSTOM_JINGLES_DIR}"
                ),
            )
        except Exception as e:
            logger.error("Failed to import custom jingle: %s", e)
            rumps.alert(title="Import Failed", message=str(e))

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def _save_current_prefs(self) -> None:
        prefs = _load_prefs()
        prefs["selected_jingle"] = self._selected_jingle
        prefs["volume_label"] = self._volume_label
        _save_prefs(prefs)

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    def _try_load_credentials(self) -> None:
        if not os.path.exists(CREDENTIALS_FILE):
            self._set_status("⚠️ No credentials.json — click 🔑 to set up")
            return

        creds = load_credentials()
        if creds:
            self._credentials = creds
            self._watcher = CalendarWatcher(creds)
            self._set_status("✅ Connected")
        else:
            self._set_status("🔑 Re-authorize needed")

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _background_loop(self) -> None:
        tick_count = 0
        while True:
            try:
                if tick_count % POLL_INTERVAL_SECONDS == 0:
                    self._poll_calendar()
                self._tick()
            except Exception as e:
                logger.exception("Background loop error: %s", e)
            tick_count += 1
            time.sleep(1)

    # ------------------------------------------------------------------
    # Calendar polling (every 30s)
    # ------------------------------------------------------------------

    def _poll_calendar(self) -> None:
        if self._watcher is None:
            return

        try:
            events = self._watcher.get_upcoming_meet_events(minutes_ahead=10)
        except Exception as e:
            logger.warning("Calendar fetch error: %s", e)
            self._set_status("⚠️ Offline")
            return

        if events:
            events.sort(key=lambda e: e["start"])
            self._next_event = events[0]
        elif self._next_event is not None:
            # Keep showing "is live!" for recently started meetings
            now = datetime.now(timezone.utc)
            elapsed = (now - self._next_event["start"]).total_seconds()
            if elapsed > _LIVE_TIMEOUT_SECONDS:
                self._clear_event()

        self._prune_played_events()

    def _clear_event(self) -> None:
        self._next_event = None
        self._is_live = False
        self._active_meet_link = None

    # ------------------------------------------------------------------
    # Tick (every 1s) — live countdown + jingle trigger
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        event = self._next_event
        if event is None:
            self.title = ""
            self._join_item.title = "No upcoming Meet"
            self._is_live = False
            self._active_meet_link = None
            return

        now = datetime.now(timezone.utc)
        seconds_until = (event["start"] - now).total_seconds()

        self._update_display(event, seconds_until)
        self._maybe_trigger_jingle(event, seconds_until)

    def _update_display(self, event: dict, seconds_until: float) -> None:
        name = event["summary"]

        if seconds_until <= 0:
            # Meeting is live!
            self._is_live = True
            self._active_meet_link = event["meet_link"]
            self.title = f"🟢 {name} is live!"
            self._join_item.title = f"▶ Join: {name}"
        elif seconds_until <= _URGENT_SECONDS:
            # Urgent — last 10 seconds, red indicator
            self._active_meet_link = event["meet_link"]
            self.title = f"🔴 {name} in {_format_countdown(seconds_until)}"
            self._join_item.title = f"▶ Join: {name}"
        else:
            # Normal countdown
            self._is_live = False
            self._active_meet_link = event["meet_link"]
            countdown = _format_countdown(seconds_until)
            self.title = f"{name} in {countdown}"
            self._join_item.title = f"{name} in {countdown} — click to join"

    def _maybe_trigger_jingle(self, event: dict, seconds_until: float) -> None:
        event_id = event["id"]
        if event_id in self._played_events:
            return
        if not (0 < seconds_until <= self._jingle_duration):
            return

        # Mark as played regardless of enabled/skip state
        self._played_events[event_id] = event["start"]

        if not self._jingle_enabled:
            return
        if self._skip_next:
            self._skip_next = False
            logger.info("Skipped jingle for: %s", event["summary"])
            return

        logger.info(
            "Playing jingle for: %s (%.1fs until meeting)",
            event["summary"],
            seconds_until,
        )
        self._player.play(self._volume)

    def _prune_played_events(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        self._played_events = {
            eid: start
            for eid, start in self._played_events.items()
            if start > cutoff
        }

    # ------------------------------------------------------------------
    # Menu label helpers
    # ------------------------------------------------------------------

    def _set_status(self, text: str) -> None:
        self._status_item.title = text

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _on_join(self, _) -> None:
        if self._active_meet_link:
            webbrowser.open(self._active_meet_link)

    @rumps.clicked("🔑 Authorize Google Calendar")
    def _on_authorize(self, _) -> None:
        if not os.path.exists(CREDENTIALS_FILE):
            rumps.alert(
                title="Missing credentials.json",
                message=(
                    "To set up Google Calendar access:\n\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create a project and enable the Google Calendar API\n"
                    "3. Create OAuth 2.0 credentials (Desktop app)\n"
                    "4. Download the JSON and save it as credentials.json\n"
                    "   in the app folder, then re-open the app."
                ),
            )
            return

        self._set_status("🔄 Authorizing...")
        try:
            creds = run_auth_flow()
            if creds:
                self._credentials = creds
                self._watcher = CalendarWatcher(creds)
                self._set_status("✅ Connected")
            else:
                self._set_status("⚠️ Authorization failed")
        except Exception as e:
            logger.error("Auth error: %s", e)
            self._set_status("⚠️ Authorization failed")

    def _on_toggle_jingle(self, sender) -> None:
        self._jingle_enabled = not self._jingle_enabled
        sender.state = self._jingle_enabled

    def _on_skip_next(self, _) -> None:
        self._skip_next = True
        rumps.notification(
            title="BBC Meet Jingle",
            subtitle="Skip set",
            message="Jingle will be skipped for the next meeting.",
        )

    def _on_test_jingle(self, _) -> None:
        if not self._player.available:
            rumps.alert(
                title="Missing audio file",
                message=(
                    "Place an audio file in the assets/ folder and restart the app."
                ),
            )
            return
        self._player.test(self._volume)

    def _make_volume_callback(self, label: str):
        def callback(_) -> None:
            self._volume_label = label
            self._volume = VOLUME_PRESETS[label]
            for vol_label in VOLUME_PRESETS:
                if vol_label in self.menu["⚙️ Settings"]["Volume"]:
                    self.menu["⚙️ Settings"]["Volume"][vol_label].state = vol_label == label
            self._save_current_prefs()

        return callback

    def _on_quit(self, _) -> None:
        self._player.stop()
        rumps.quit_application()


def _hide_dock_icon() -> None:
    """Hide the Python icon from the Dock (LSUIElement = True)."""
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )
    except ImportError:
        pass  # pyobjc not available — Dock icon will show


if __name__ == "__main__":
    _hide_dock_icon()
    BBCMeetJingleApp().run()
