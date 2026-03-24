import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_app():
    """Create a BBCMeetJingleApp with all external dependencies mocked."""
    with (
        patch("app.AudioPlayer") as mock_player_cls,
        patch("app.load_credentials", return_value=None),
        patch("app.os.path.exists", return_value=False),
        patch("app.threading.Thread"),
        patch("app._load_prefs", return_value={}),
        patch("app._build_jingle_catalog", return_value={
            "BBC News": "/fake/bbc.mp3",
            "Netflix": "/fake/netflix.mp3",
        }),
    ):
        mock_player = MagicMock()
        mock_player.available = True
        mock_player.duration = 16.8
        mock_player_cls.return_value = mock_player

        from app import BBCMeetJingleApp

        app = BBCMeetJingleApp()
        return app, mock_player


def _make_event(summary="Standup", seconds_from_now=30, event_id="evt_1"):
    start = datetime.now(timezone.utc) + timedelta(seconds=seconds_from_now)
    return {
        "id": event_id,
        "summary": summary,
        "start": start,
        "meet_link": "https://meet.google.com/abc",
    }


# ------------------------------------------------------------------
# _format_countdown
# ------------------------------------------------------------------


class TestFormatCountdown:
    def test_seconds_only(self):
        from app import _format_countdown

        assert _format_countdown(7) == "0:07"

    def test_minutes_and_seconds(self):
        from app import _format_countdown

        assert _format_countdown(125) == "2:05"

    def test_zero(self):
        from app import _format_countdown

        assert _format_countdown(0) == "0:00"

    def test_negative_clamps_to_zero(self):
        from app import _format_countdown

        assert _format_countdown(-5) == "0:00"

    def test_exact_minute(self):
        from app import _format_countdown

        assert _format_countdown(60) == "1:00"

    def test_large_value(self):
        from app import _format_countdown

        assert _format_countdown(600) == "10:00"


# ------------------------------------------------------------------
# Preferences helpers
# ------------------------------------------------------------------


class TestPrefsHelpers:
    def test_load_prefs_returns_empty_for_missing_file(self):
        from app import _load_prefs

        with patch("app.os.path.exists", return_value=False):
            assert _load_prefs() == {}

    def test_load_prefs_reads_json(self, tmp_path):
        from app import _load_prefs

        prefs_file = tmp_path / "prefs.json"
        prefs_file.write_text('{"selected_jingle": "Netflix"}')
        with patch("app.PREFS_FILE", str(prefs_file)):
            result = _load_prefs()
            assert result["selected_jingle"] == "Netflix"

    def test_load_prefs_handles_corrupt_json(self, tmp_path):
        from app import _load_prefs

        prefs_file = tmp_path / "prefs.json"
        prefs_file.write_text("{bad json")
        with patch("app.PREFS_FILE", str(prefs_file)):
            assert _load_prefs() == {}

    def test_save_prefs_writes_json(self, tmp_path):
        from app import _save_prefs

        prefs_file = tmp_path / "prefs.json"
        with patch("app.PREFS_FILE", str(prefs_file)):
            _save_prefs({"selected_jingle": "BBC News", "volume_label": "Full"})
            data = json.loads(prefs_file.read_text())
            assert data["selected_jingle"] == "BBC News"


# ------------------------------------------------------------------
# Jingle catalog helpers
# ------------------------------------------------------------------


class TestJingleCatalog:
    def test_discover_custom_jingles(self, tmp_path):
        from app import _discover_custom_jingles

        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        (custom_dir / "epic.mp3").write_bytes(b"data")
        (custom_dir / "chill.wav").write_bytes(b"data")
        (custom_dir / "readme.txt").write_bytes(b"not audio")

        with patch("app.CUSTOM_JINGLES_DIR", str(custom_dir)):
            result = _discover_custom_jingles()
            assert "chill" in result
            assert "epic" in result
            assert "readme" not in result

    def test_discover_custom_jingles_empty_when_no_dir(self):
        from app import _discover_custom_jingles

        with patch("app.CUSTOM_JINGLES_DIR", "/nonexistent/path"):
            assert _discover_custom_jingles() == {}

    def test_discover_custom_jingles_includes_m4a(self, tmp_path):
        from app import _discover_custom_jingles

        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        (custom_dir / "tune.m4a").write_bytes(b"data")

        with patch("app.CUSTOM_JINGLES_DIR", str(custom_dir)):
            result = _discover_custom_jingles()
            assert "tune" in result


# ------------------------------------------------------------------
# App init
# ------------------------------------------------------------------


class TestAppInit:
    def test_creates_with_default_state(self):
        app, _ = _make_app()
        assert app._jingle_enabled is True
        assert app._skip_next is False
        assert app._played_events == {}
        assert app._volume == 1.0
        assert app._next_event is None
        assert app._is_live is False
        assert app._active_meet_link is None

    def test_has_thread_lock(self):
        app, _ = _make_app()
        import threading
        assert type(app._lock) is type(threading.Lock())

    def test_jingle_duration_from_player(self):
        app, _ = _make_app()
        assert app._jingle_duration == 16.8

    def test_jingle_duration_falls_back_to_default(self):
        with (
            patch("app.AudioPlayer") as mock_player_cls,
            patch("app.load_credentials", return_value=None),
            patch("app.os.path.exists", return_value=False),
            patch("app.threading.Thread"),
            patch("app._load_prefs", return_value={}),
            patch("app._build_jingle_catalog", return_value={}),
        ):
            mock_player = MagicMock()
            mock_player.available = False
            mock_player.duration = 0.0
            mock_player_cls.return_value = mock_player

            from app import BBCMeetJingleApp

            app = BBCMeetJingleApp()
            assert app._jingle_duration == 16.8

    def test_loads_saved_jingle_preference(self):
        with (
            patch("app.AudioPlayer") as mock_player_cls,
            patch("app.load_credentials", return_value=None),
            patch("app.os.path.exists", return_value=False),
            patch("app.threading.Thread"),
            patch("app._load_prefs", return_value={
                "selected_jingle": "Netflix",
                "volume_label": "Low",
            }),
            patch("app._build_jingle_catalog", return_value={
                "BBC News": "/fake/bbc.mp3",
                "Netflix": "/fake/netflix.mp3",
            }),
        ):
            mock_player = MagicMock()
            mock_player.available = True
            mock_player.duration = 2.5
            mock_player_cls.return_value = mock_player

            from app import BBCMeetJingleApp

            app = BBCMeetJingleApp()
            assert app._selected_jingle == "Netflix"
            assert app._volume_label == "Low"
            assert app._volume == 0.3

    def test_status_shows_no_credentials(self):
        app, _ = _make_app()
        assert (
            "No credentials" in app._status_item.title
            or "Re-authorize" in app._status_item.title
        )

    def test_default_schedule_state(self):
        app, _ = _make_app()
        assert app._snooze_until is None
        assert app._quiet_start is None
        assert app._quiet_end is None
        assert app._work_hours_only is False
        assert app._work_start == "09:00"
        assert app._work_end == "18:00"
        assert app._work_days == [0, 1, 2, 3, 4]

    def test_loads_schedule_prefs(self):
        with (
            patch("app.AudioPlayer") as mock_player_cls,
            patch("app.load_credentials", return_value=None),
            patch("app.os.path.exists", return_value=False),
            patch("app.threading.Thread"),
            patch("app._load_prefs", return_value={
                "quiet_start": "22:00",
                "quiet_end": "07:00",
                "work_hours_only": True,
                "work_start": "10:00",
                "work_end": "19:00",
                "work_days": [0, 1, 2, 3, 4, 5],
            }),
            patch("app._build_jingle_catalog", return_value={
                "BBC News": "/fake/bbc.mp3",
            }),
        ):
            mock_player = MagicMock()
            mock_player.available = True
            mock_player.duration = 16.8
            mock_player_cls.return_value = mock_player

            from app import BBCMeetJingleApp

            app = BBCMeetJingleApp()
            assert app._quiet_start == "22:00"
            assert app._quiet_end == "07:00"
            assert app._work_hours_only is True
            assert app._work_start == "10:00"
            assert app._work_end == "19:00"
            assert 5 in app._work_days


# ------------------------------------------------------------------
# Jingle selection
# ------------------------------------------------------------------


class TestJingleSelection:
    def test_select_jingle_switches_player(self):
        app, mock_player = _make_app()
        mock_player.duration = 2.5
        with patch("app._save_prefs"):
            app._select_jingle("Netflix")
        mock_player.switch_jingle.assert_called_once_with("/fake/netflix.mp3")
        assert app._selected_jingle == "Netflix"
        assert app._jingle_duration == 2.5

    def test_select_jingle_ignores_unknown_name(self):
        app, mock_player = _make_app()
        app._select_jingle("NonExistent")
        mock_player.switch_jingle.assert_not_called()

    def test_select_jingle_persists_prefs(self):
        app, mock_player = _make_app()
        mock_player.duration = 2.5
        with patch("app._save_prefs") as mock_save:
            app._select_jingle("Netflix")
            mock_save.assert_called_once()


# ------------------------------------------------------------------
# _tick — display updates
# ------------------------------------------------------------------


class TestGetIdleTitle:
    def test_empty_when_all_clear(self):
        app, _ = _make_app()
        assert app._get_idle_title() == ""

    def test_shows_jingles_off(self):
        app, _ = _make_app()
        app._jingle_enabled = False
        assert app._get_idle_title() == "🔇 Jingles off"

    def test_shows_snoozed_minutes(self):
        app, _ = _make_app()
        app._snooze_until = datetime.now() + timedelta(minutes=25)
        title = app._get_idle_title()
        assert "😴 Snoozed" in title
        assert "25m" in title or "24m" in title

    def test_shows_snoozed_hours(self):
        app, _ = _make_app()
        app._snooze_until = datetime.now() + timedelta(hours=1, minutes=30)
        title = app._get_idle_title()
        assert "😴 Snoozed 1h 30m" in title or "😴 Snoozed 1h 29m" in title

    def test_shows_quiet_hours(self):
        app, _ = _make_app()
        app._quiet_start = "00:00"
        app._quiet_end = "23:59"
        assert app._get_idle_title() == "🌙 Quiet hours"

    def test_shows_off_hours(self):
        app, _ = _make_app()
        app._work_hours_only = True
        app._work_start = "00:00"
        app._work_end = "00:01"
        app._work_days = []  # no work days = always off hours
        assert app._get_idle_title() == "🏢 Off hours"

    def test_priority_disabled_over_snoozed(self):
        app, _ = _make_app()
        app._jingle_enabled = False
        app._snooze_until = datetime.now() + timedelta(hours=1)
        assert app._get_idle_title() == "🔇 Jingles off"

    def test_priority_snoozed_over_quiet(self):
        app, _ = _make_app()
        app._snooze_until = datetime.now() + timedelta(hours=1)
        app._quiet_start = "00:00"
        app._quiet_end = "23:59"
        assert "😴 Snoozed" in app._get_idle_title()


class TestTick:
    def test_default_when_no_event(self):
        app, _ = _make_app()
        app._next_event = None
        app._tick()
        assert app._join_item.title == "No upcoming Meet"

    def test_shows_countdown(self):
        app, _ = _make_app()
        app._next_event = _make_event(seconds_from_now=120)
        app._tick()
        assert "Standup in " in app.title
        assert "click to join" in app._join_item.title

    def test_shows_urgent_under_10s(self):
        app, _ = _make_app()
        app._next_event = _make_event(seconds_from_now=5)
        app._played_events["evt_1"] = app._next_event["start"]
        app._tick()
        assert "🔴" in app.title
        assert "Standup in 0:0" in app.title
        assert "▶ Join" in app._join_item.title

    def test_shows_live_when_past_start(self):
        app, _ = _make_app()
        app._next_event = _make_event(seconds_from_now=-5)
        app._tick()
        assert "🟢" in app.title
        assert "is live!" in app.title
        assert app._is_live is True
        assert app._active_meet_link == "https://meet.google.com/abc"
        assert "▶ Join" in app._join_item.title

    def test_sets_meet_link_for_future_event(self):
        app, _ = _make_app()
        app._next_event = _make_event(seconds_from_now=60)
        app._tick()
        assert app._active_meet_link == "https://meet.google.com/abc"
        assert app._is_live is False


# ------------------------------------------------------------------
# _maybe_trigger_jingle
# ------------------------------------------------------------------


class TestMaybeTriggerJingle:
    def test_triggers_within_jingle_duration(self):
        app, mock_player = _make_app()
        event = _make_event(seconds_from_now=10)
        with patch("app.should_jingle", return_value=True):
            app._maybe_trigger_jingle(event, 10.0)
        mock_player.play.assert_called_once_with(1.0)
        assert "evt_1" in app._played_events

    def test_does_not_trigger_outside_duration(self):
        app, mock_player = _make_app()
        event = _make_event(seconds_from_now=30)
        app._maybe_trigger_jingle(event, 30.0)
        mock_player.play.assert_not_called()

    def test_does_not_replay(self):
        app, mock_player = _make_app()
        event = _make_event(seconds_from_now=10)
        app._played_events["evt_1"] = event["start"]
        app._maybe_trigger_jingle(event, 10.0)
        mock_player.play.assert_not_called()

    def test_marks_played_even_when_schedule_blocks(self):
        app, mock_player = _make_app()
        event = _make_event(seconds_from_now=10)
        with patch("app.should_jingle", return_value=False):
            app._maybe_trigger_jingle(event, 10.0)
        mock_player.play.assert_not_called()
        assert "evt_1" in app._played_events

    def test_skips_and_resets_skip_flag(self):
        app, mock_player = _make_app()
        app._skip_next = True
        event = _make_event(seconds_from_now=10)
        with patch("app.should_jingle", return_value=True):
            app._maybe_trigger_jingle(event, 10.0)
        mock_player.play.assert_not_called()
        assert app._skip_next is False
        assert "evt_1" in app._played_events

    def test_does_not_trigger_at_zero_or_negative(self):
        app, mock_player = _make_app()
        event = _make_event(seconds_from_now=-1)
        app._maybe_trigger_jingle(event, -1.0)
        mock_player.play.assert_not_called()

    def test_respects_quiet_hours(self):
        app, mock_player = _make_app()
        app._quiet_start = "18:00"
        app._quiet_end = "09:00"
        event = _make_event(seconds_from_now=10)
        # should_jingle will check quiet hours; mock it to return False
        with patch("app.should_jingle", return_value=False):
            app._maybe_trigger_jingle(event, 10.0)
        mock_player.play.assert_not_called()

    def test_respects_snooze(self):
        app, mock_player = _make_app()
        app._snooze_until = datetime.now() + timedelta(hours=1)
        event = _make_event(seconds_from_now=10)
        with patch("app.should_jingle", return_value=False):
            app._maybe_trigger_jingle(event, 10.0)
        mock_player.play.assert_not_called()


# ------------------------------------------------------------------
# _poll_calendar
# ------------------------------------------------------------------


class TestPollCalendar:
    def test_returns_early_when_no_watcher(self):
        app, _ = _make_app()
        app._watcher = None
        app._poll_calendar()

    def test_sets_next_event(self):
        app, _ = _make_app()
        mock_watcher = MagicMock()
        mock_watcher.get_upcoming_meet_events.return_value = [
            _make_event(seconds_from_now=300)
        ]
        app._watcher = mock_watcher
        app._poll_calendar()
        assert app._next_event is not None
        assert app._next_event["id"] == "evt_1"

    def test_clears_expired_live_event(self):
        app, _ = _make_app()
        mock_watcher = MagicMock()
        mock_watcher.get_upcoming_meet_events.return_value = []
        app._watcher = mock_watcher
        app._next_event = _make_event(seconds_from_now=-600)
        app._poll_calendar()
        assert app._next_event is None

    def test_keeps_recent_live_event(self):
        app, _ = _make_app()
        mock_watcher = MagicMock()
        mock_watcher.get_upcoming_meet_events.return_value = []
        app._watcher = mock_watcher
        app._next_event = _make_event(seconds_from_now=-60)
        app._poll_calendar()
        assert app._next_event is not None
        assert app._next_event["id"] == "evt_1"

    def test_handles_fetch_error(self):
        app, _ = _make_app()
        mock_watcher = MagicMock()
        mock_watcher.get_upcoming_meet_events.side_effect = ConnectionError("offline")
        app._watcher = mock_watcher
        app._poll_calendar()
        assert "Offline" in app._status_item.title


# ------------------------------------------------------------------
# _prune_played_events
# ------------------------------------------------------------------


class TestPrunePlayedEvents:
    def test_prunes_old_events(self):
        app, _ = _make_app()
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        app._played_events = {"old_evt": old_time, "recent_evt": recent_time}
        app._prune_played_events()
        assert "old_evt" not in app._played_events
        assert "recent_evt" in app._played_events


# ------------------------------------------------------------------
# Menu callbacks
# ------------------------------------------------------------------


class TestMenuCallbacks:
    def test_toggle_jingle(self):
        app, _ = _make_app()
        sender = MagicMock()
        app._jingle_enabled = True
        app._on_toggle_jingle(sender)
        assert app._jingle_enabled is False
        assert sender.state is False
        app._on_toggle_jingle(sender)
        assert app._jingle_enabled is True
        assert sender.state is True

    def test_skip_next(self):
        app, _ = _make_app()
        app._on_skip_next(None)
        assert app._skip_next is True

    def test_test_jingle_plays(self):
        app, mock_player = _make_app()
        app._on_test_jingle(None)
        mock_player.test.assert_called_once_with(1.0)

    def test_test_jingle_alerts_when_unavailable(self):
        app, mock_player = _make_app()
        mock_player.available = False
        with patch("app.rumps.alert") as mock_alert:
            app._on_test_jingle(None)
            mock_alert.assert_called_once()

    def test_volume_callback_saves_prefs(self):
        app, _ = _make_app()
        callback = app._make_volume_callback("Low")
        with patch("app._save_prefs"):
            callback(None)
        assert app._volume_label == "Low"
        assert app._volume == 0.3

    def test_quit_stops_player(self):
        app, mock_player = _make_app()
        with patch("app.rumps.quit_application"):
            app._on_quit(None)
        mock_player.stop.assert_called_once()


# ------------------------------------------------------------------
# Snooze callbacks
# ------------------------------------------------------------------


class TestSnoozeCallbacks:
    def test_snooze_sets_time(self):
        app, _ = _make_app()
        callback = app._make_snooze_callback("30 minutes")
        callback(None)
        assert app._snooze_until is not None
        # Should be roughly 30 min from now
        remaining = (app._snooze_until - datetime.now()).total_seconds()
        assert 1700 < remaining < 1900

    def test_cancel_snooze(self):
        app, _ = _make_app()
        app._snooze_until = datetime.now() + timedelta(hours=1)
        app._on_cancel_snooze(None)
        assert app._snooze_until is None

    def test_snooze_status_not_snoozed(self):
        app, _ = _make_app()
        app._snooze_until = None
        app._update_snooze_status()
        assert app._snooze_status.title == "Not snoozed"

    def test_snooze_status_active(self):
        app, _ = _make_app()
        app._snooze_until = datetime.now() + timedelta(minutes=45)
        app._update_snooze_status()
        assert "🔇 Snoozed" in app._snooze_status.title
        assert "45m" in app._snooze_status.title or "44m" in app._snooze_status.title

    def test_snooze_status_expired_auto_clears(self):
        app, _ = _make_app()
        app._snooze_until = datetime.now() - timedelta(minutes=1)
        app._update_snooze_status()
        assert app._snooze_until is None
        assert app._snooze_status.title == "Not snoozed"


# ------------------------------------------------------------------
# Quiet hours callbacks
# ------------------------------------------------------------------


class TestQuietHoursCallbacks:
    def test_toggle_quiet_on(self):
        app, _ = _make_app()
        sender = MagicMock()
        app._quiet_start = None
        app._quiet_end = None
        with patch("app._save_prefs"):
            app._on_toggle_quiet(sender)
        assert app._quiet_start == "18:00"
        assert app._quiet_end == "09:00"
        assert sender.state is True

    def test_toggle_quiet_off(self):
        app, _ = _make_app()
        sender = MagicMock()
        app._quiet_start = "18:00"
        app._quiet_end = "09:00"
        with patch("app._save_prefs"):
            app._on_toggle_quiet(sender)
        assert app._quiet_start is None
        assert app._quiet_end is None
        assert sender.state is False

    def test_quiet_preset(self):
        app, _ = _make_app()
        callback = app._make_quiet_callback("22:00", "07:00")
        with patch("app._save_prefs"):
            callback(None)
        assert app._quiet_start == "22:00"
        assert app._quiet_end == "07:00"


# ------------------------------------------------------------------
# Work hours callbacks
# ------------------------------------------------------------------


class TestWorkHoursCallbacks:
    def test_toggle_work_hours(self):
        app, _ = _make_app()
        sender = MagicMock()
        with patch("app._save_prefs"):
            app._on_toggle_work_hours(sender)
        assert app._work_hours_only is True
        assert sender.state is True

    def test_work_hours_preset(self):
        app, _ = _make_app()
        callback = app._make_work_hours_callback("10:00", "19:00")
        with patch("app._save_prefs"):
            callback(None)
        assert app._work_start == "10:00"
        assert app._work_end == "19:00"
        assert app._work_hours_only is True

    def test_toggle_work_day_off(self):
        app, _ = _make_app()
        sender = MagicMock()
        assert 4 in app._work_days  # Friday
        callback = app._make_work_day_callback(4)
        with patch("app._save_prefs"):
            callback(sender)
        assert 4 not in app._work_days
        assert sender.state is False

    def test_toggle_work_day_on(self):
        app, _ = _make_app()
        sender = MagicMock()
        assert 5 not in app._work_days  # Saturday
        callback = app._make_work_day_callback(5)
        with patch("app._save_prefs"):
            callback(sender)
        assert 5 in app._work_days
        assert sender.state is True


# ------------------------------------------------------------------
# Join meeting
# ------------------------------------------------------------------


class TestJoinMeeting:
    def test_opens_browser_with_link(self):
        app, _ = _make_app()
        app._active_meet_link = "https://meet.google.com/abc"
        with patch("app.webbrowser.open") as mock_open:
            app._on_join(None)
            mock_open.assert_called_once_with("https://meet.google.com/abc")

    def test_does_nothing_without_link(self):
        app, _ = _make_app()
        app._active_meet_link = None
        with patch("app.webbrowser.open") as mock_open:
            app._on_join(None)
            mock_open.assert_not_called()


# ------------------------------------------------------------------
# Preferences persistence
# ------------------------------------------------------------------


class TestPrefsPersistence:
    def test_save_current_prefs_includes_schedule(self):
        app, _ = _make_app()
        app._quiet_start = "22:00"
        app._quiet_end = "07:00"
        app._work_hours_only = True
        app._work_start = "10:00"
        app._work_end = "19:00"
        app._work_days = [0, 1, 2, 3, 4, 5]

        saved = {}

        def capture_prefs(prefs):
            saved.update(prefs)

        with (
            patch("app._load_prefs", return_value={}),
            patch("app._save_prefs", side_effect=capture_prefs),
        ):
            app._save_current_prefs()

        assert saved["quiet_start"] == "22:00"
        assert saved["quiet_end"] == "07:00"
        assert saved["work_hours_only"] is True
        assert saved["work_start"] == "10:00"
        assert saved["work_end"] == "19:00"
        assert 5 in saved["work_days"]
