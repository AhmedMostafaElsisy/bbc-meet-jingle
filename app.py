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
    ALLOWED_AUDIO_EXTENSIONS,
    ASSETS_DIR,
    BUILTIN_JINGLES,
    CREDENTIALS_FILE,
    CUSTOM_JINGLES_DIR,
    DEFAULT_JINGLE,
    DEFAULT_JINGLE_DURATION,
    DEFAULT_WORK_DAYS,
    DEFAULT_WORK_END,
    DEFAULT_WORK_START,
    JINGLE_FILE,
    LIVE_TIMEOUT_SECONDS,
    POLL_INTERVAL_SECONDS,
    PREFS_FILE,
    SNOOZE_OPTIONS,
    URGENT_SECONDS,
    VOLUME_PRESETS,
)
from schedule import (
    compute_snooze_until,
    is_quiet_hours,
    is_snoozed,
    is_within_work_hours,
    should_jingle,
)

_ICON_PATH = os.path.join(ASSETS_DIR, "icon.png")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Day names for menu display
_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ------------------------------------------------------------------
# Pure helpers (no state)
# ------------------------------------------------------------------


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
        if filename.lower().endswith(ALLOWED_AUDIO_EXTENSIONS):
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

        # Thread lock for shared state
        self._lock = threading.Lock()

        # Core state (protected by _lock)
        self._credentials = None
        self._watcher: CalendarWatcher | None = None
        self._jingle_enabled = True
        self._skip_next = False
        self._played_events: dict[str, datetime] = {}
        self._next_event: dict | None = None
        self._active_meet_link: str | None = None
        self._is_live = False

        # Volume
        self._volume_label = "Full"
        self._volume = VOLUME_PRESETS["Full"]

        # Schedule state
        self._snooze_until: datetime | None = None
        self._quiet_start: str | None = None
        self._quiet_end: str | None = None
        self._work_hours_only = False
        self._work_start = DEFAULT_WORK_START
        self._work_end = DEFAULT_WORK_END
        self._work_days: list[int] = list(DEFAULT_WORK_DAYS)

        # Jingle catalog & selection
        self._jingle_catalog = _build_jingle_catalog()
        prefs = _load_prefs()
        self._selected_jingle = prefs.get("selected_jingle", DEFAULT_JINGLE)
        self._load_schedule_prefs(prefs)

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

        # Build menu
        self._build_menu_items()

        # Try loading existing credentials
        self._try_load_credentials()

        # Start background loop
        bg_thread = threading.Thread(target=self._background_loop, daemon=True)
        bg_thread.start()

    # ------------------------------------------------------------------
    # Preference persistence
    # ------------------------------------------------------------------

    def _load_schedule_prefs(self, prefs: dict) -> None:
        """Restore schedule settings from prefs dict."""
        self._quiet_start = prefs.get("quiet_start")
        self._quiet_end = prefs.get("quiet_end")
        self._work_hours_only = prefs.get("work_hours_only", False)
        self._work_start = prefs.get("work_start", DEFAULT_WORK_START)
        self._work_end = prefs.get("work_end", DEFAULT_WORK_END)
        self._work_days = prefs.get("work_days", list(DEFAULT_WORK_DAYS))

    def _save_current_prefs(self) -> None:
        prefs = _load_prefs()
        prefs["selected_jingle"] = self._selected_jingle
        prefs["volume_label"] = self._volume_label
        prefs["quiet_start"] = self._quiet_start
        prefs["quiet_end"] = self._quiet_end
        prefs["work_hours_only"] = self._work_hours_only
        prefs["work_start"] = self._work_start
        prefs["work_end"] = self._work_end
        prefs["work_days"] = self._work_days
        _save_prefs(prefs)

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _build_menu_items(self) -> None:
        """Create all menu items and assemble the menu."""
        self._join_item = rumps.MenuItem(
            "No upcoming Meet", callback=self._on_join
        )

        self._status_item = rumps.MenuItem("⚠️ No credentials")
        self._status_item.set_callback(None)

        # --- Jingle controls ---
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

        # --- Jingle picker submenu ---
        self._jingle_menu = rumps.MenuItem("🎵 Jingle")
        self._build_jingle_menu()

        # --- Snooze submenu ---
        self._snooze_menu = rumps.MenuItem("😴 Snooze")
        self._snooze_status = rumps.MenuItem("Not snoozed")
        self._snooze_status.set_callback(None)
        self._snooze_menu.add(self._snooze_status)
        self._snooze_menu.add(None)
        for label in SNOOZE_OPTIONS:
            self._snooze_menu.add(
                rumps.MenuItem(label, callback=self._make_snooze_callback(label))
            )
        self._snooze_menu.add(None)
        self._snooze_menu.add(
            rumps.MenuItem("Cancel Snooze", callback=self._on_cancel_snooze)
        )

        # --- Schedule submenu ---
        schedule_menu = rumps.MenuItem("📅 Schedule")

        # Quiet hours
        quiet_menu = rumps.MenuItem("🌙 Quiet Hours")
        self._quiet_toggle = rumps.MenuItem(
            "Enabled", callback=self._on_toggle_quiet
        )
        self._quiet_toggle.state = self._quiet_start is not None
        quiet_menu.add(self._quiet_toggle)
        quiet_menu.add(None)
        quiet_presets = [
            ("After 6 PM", "18:00", "09:00"),
            ("After 8 PM", "20:00", "09:00"),
            ("After 10 PM", "22:00", "07:00"),
        ]
        for name, start, end in quiet_presets:
            quiet_menu.add(rumps.MenuItem(
                name,
                callback=self._make_quiet_callback(start, end),
            ))
        schedule_menu.add(quiet_menu)

        # Work hours
        work_menu = rumps.MenuItem("🏢 Work Hours Only")
        self._work_toggle = rumps.MenuItem(
            "Enabled", callback=self._on_toggle_work_hours
        )
        self._work_toggle.state = self._work_hours_only
        work_menu.add(self._work_toggle)
        work_menu.add(None)

        work_presets = [
            ("9 AM – 5 PM", "09:00", "17:00"),
            ("9 AM – 6 PM", "09:00", "18:00"),
            ("8 AM – 6 PM", "08:00", "18:00"),
            ("10 AM – 7 PM", "10:00", "19:00"),
        ]
        for name, start, end in work_presets:
            work_menu.add(rumps.MenuItem(
                name,
                callback=self._make_work_hours_callback(start, end),
            ))

        work_menu.add(None)
        days_menu = rumps.MenuItem("Work Days")
        for i, day_name in enumerate(_DAY_NAMES):
            item = rumps.MenuItem(
                day_name, callback=self._make_work_day_callback(i)
            )
            item.state = i in self._work_days
            days_menu.add(item)
        work_menu.add(days_menu)
        schedule_menu.add(work_menu)

        # --- Settings submenu ---
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
            None,
            self._snooze_menu,
            schedule_menu,
            settings_menu,
            None,
            self._auth_item,
            quit_item,
        ]

    # ------------------------------------------------------------------
    # Jingle catalog helpers
    # ------------------------------------------------------------------

    def _build_jingle_menu(self) -> None:
        """Populate the jingle picker submenu."""
        for name in self._jingle_catalog:
            item = rumps.MenuItem(
                name, callback=self._make_jingle_callback(name)
            )
            item.state = name == self._selected_jingle
            self._jingle_menu.add(item)

        self._jingle_menu.add(None)
        self._jingle_menu.add(
            rumps.MenuItem("➕ Add Custom Sound…", callback=self._on_add_custom_jingle)
        )

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
            panel.setAllowedFileTypes_(
                [ext.lstrip(".") for ext in ALLOWED_AUDIO_EXTENSIONS]
            )

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
                    f"audio file into:\n\n{CUSTOM_JINGLES_DIR}"
                ),
            )
        except Exception as e:
            logger.error("Failed to import custom jingle: %s", e)
            rumps.alert(title="Import Failed", message=str(e))

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

        with self._lock:
            if events:
                events.sort(key=lambda e: e["start"])
                self._next_event = events[0]
            elif self._next_event is not None:
                now = datetime.now(timezone.utc)
                elapsed = (now - self._next_event["start"]).total_seconds()
                if elapsed > LIVE_TIMEOUT_SECONDS:
                    self._clear_event()

            self._prune_played_events()

    def _clear_event(self) -> None:
        self._next_event = None
        self._is_live = False
        self._active_meet_link = None

    # ------------------------------------------------------------------
    # Tick (every 1s) — live countdown + jingle trigger
    # ------------------------------------------------------------------

    def _get_idle_title(self) -> str:
        """Return a status-aware title for the menu bar when idle."""
        now = datetime.now()
        if not self._jingle_enabled:
            return "🔇 Jingles off"
        if is_snoozed(self._snooze_until, now):
            remaining = self._snooze_until - now
            mins = int(remaining.total_seconds() // 60)
            if mins >= 60:
                return f"😴 Snoozed {mins // 60}h {mins % 60}m"
            return f"😴 Snoozed {mins}m"
        if is_quiet_hours(now, self._quiet_start, self._quiet_end):
            return "🌙 Quiet hours"
        if self._work_hours_only and not is_within_work_hours(
            now, self._work_start, self._work_end, self._work_days
        ):
            return "🏢 Off hours"
        return ""

    def _tick(self) -> None:
        with self._lock:
            event = self._next_event
        if event is None:
            self.title = self._get_idle_title()
            self._join_item.title = "No upcoming Meet"
            with self._lock:
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
            with self._lock:
                self._is_live = True
                self._active_meet_link = event["meet_link"]
            self.title = f"🟢 {name} is live!"
            self._join_item.title = f"▶ Join: {name}"
        elif seconds_until <= URGENT_SECONDS:
            with self._lock:
                self._active_meet_link = event["meet_link"]
            self.title = f"🔴 {name} in {_format_countdown(seconds_until)}"
            self._join_item.title = f"▶ Join: {name}"
        else:
            with self._lock:
                self._is_live = False
                self._active_meet_link = event["meet_link"]
            countdown = _format_countdown(seconds_until)
            self.title = f"{name} in {countdown}"
            self._join_item.title = f"{name} in {countdown} — click to join"

    def _maybe_trigger_jingle(self, event: dict, seconds_until: float) -> None:
        event_id = event["id"]
        with self._lock:
            if event_id in self._played_events:
                return
            if not (0 < seconds_until <= self._jingle_duration):
                return

            # Mark as played regardless of schedule/enabled state
            self._played_events[event_id] = event["start"]

            skip = self._skip_next
            if skip:
                self._skip_next = False

        # Check the master schedule gate
        now_local = datetime.now()
        can_play = should_jingle(
            now_local,
            jingle_enabled=self._jingle_enabled,
            snooze_until=self._snooze_until,
            quiet_start=self._quiet_start,
            quiet_end=self._quiet_end,
            work_hours_only=self._work_hours_only,
            work_start=self._work_start,
            work_end=self._work_end,
            work_days=self._work_days,
        )
        if not can_play:
            return
        if skip:
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

    def _update_snooze_status(self) -> None:
        if self._snooze_until is None:
            self._snooze_status.title = "Not snoozed"
        else:
            remaining = self._snooze_until - datetime.now()
            if remaining.total_seconds() <= 0:
                self._snooze_until = None
                self._snooze_status.title = "Not snoozed"
            else:
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                if hours > 0:
                    self._snooze_status.title = f"🔇 Snoozed ({hours}h {mins}m left)"
                else:
                    self._snooze_status.title = f"🔇 Snoozed ({mins}m left)"

    # ------------------------------------------------------------------
    # Menu callbacks — Jingle controls
    # ------------------------------------------------------------------

    def _on_join(self, _) -> None:
        with self._lock:
            link = self._active_meet_link
        if link:
            webbrowser.open(link)

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
        with self._lock:
            self._jingle_enabled = not self._jingle_enabled
            sender.state = self._jingle_enabled

    def _on_skip_next(self, _) -> None:
        with self._lock:
            self._skip_next = True

    def _on_test_jingle(self, _) -> None:
        if not self._player.available:
            rumps.alert(
                title="Missing audio file",
                message="Place an audio file in the assets/ folder and restart the app.",
            )
            return
        self._player.test(self._volume)

    # ------------------------------------------------------------------
    # Menu callbacks — Volume
    # ------------------------------------------------------------------

    def _make_volume_callback(self, label: str):
        def callback(_) -> None:
            self._volume_label = label
            self._volume = VOLUME_PRESETS[label]
            for vol_label in VOLUME_PRESETS:
                if vol_label in self.menu["⚙️ Settings"]["Volume"]:
                    self.menu["⚙️ Settings"]["Volume"][vol_label].state = (
                        vol_label == label
                    )
            self._save_current_prefs()

        return callback

    # ------------------------------------------------------------------
    # Menu callbacks — Snooze
    # ------------------------------------------------------------------

    def _make_snooze_callback(self, label: str):
        def callback(_) -> None:
            now = datetime.now()
            self._snooze_until = compute_snooze_until(label, now)
            self._update_snooze_status()
            logger.info("Snoozed until %s", self._snooze_until)
        return callback

    def _on_cancel_snooze(self, _) -> None:
        self._snooze_until = None
        self._update_snooze_status()

    # ------------------------------------------------------------------
    # Menu callbacks — Quiet Hours
    # ------------------------------------------------------------------

    def _on_toggle_quiet(self, sender) -> None:
        if self._quiet_start is not None:
            # Disable quiet hours
            self._quiet_start = None
            self._quiet_end = None
            sender.state = False
        else:
            # Enable with default: after 6 PM
            self._quiet_start = "18:00"
            self._quiet_end = "09:00"
            sender.state = True
        self._save_current_prefs()

    def _make_quiet_callback(self, start: str, end: str):
        def callback(_) -> None:
            self._quiet_start = start
            self._quiet_end = end
            self._quiet_toggle.state = True
            self._save_current_prefs()
            logger.info("Quiet hours set: %s – %s", start, end)
        return callback

    # ------------------------------------------------------------------
    # Menu callbacks — Work Hours
    # ------------------------------------------------------------------

    def _on_toggle_work_hours(self, sender) -> None:
        self._work_hours_only = not self._work_hours_only
        sender.state = self._work_hours_only
        self._save_current_prefs()

    def _make_work_hours_callback(self, start: str, end: str):
        def callback(_) -> None:
            self._work_start = start
            self._work_end = end
            self._work_hours_only = True
            self._work_toggle.state = True
            self._save_current_prefs()
            logger.info("Work hours set: %s – %s", start, end)
        return callback

    def _make_work_day_callback(self, day_index: int):
        def callback(sender) -> None:
            if day_index in self._work_days:
                self._work_days = [d for d in self._work_days if d != day_index]
                sender.state = False
            else:
                self._work_days = sorted(self._work_days + [day_index])
                sender.state = True
            self._save_current_prefs()
        return callback

    # ------------------------------------------------------------------
    # Quit
    # ------------------------------------------------------------------

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
        pass


if __name__ == "__main__":
    _hide_dock_icon()
    BBCMeetJingleApp().run()
