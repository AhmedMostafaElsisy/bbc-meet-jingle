import os
import sys
from datetime import datetime, time, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schedule import (
    compute_snooze_until,
    is_quiet_hours,
    is_snoozed,
    is_within_work_hours,
    parse_time,
    should_jingle,
)


# ------------------------------------------------------------------
# parse_time
# ------------------------------------------------------------------


class TestParseTime:
    def test_basic(self):
        assert parse_time("09:00") == time(9, 0)

    def test_afternoon(self):
        assert parse_time("18:30") == time(18, 30)

    def test_midnight(self):
        assert parse_time("00:00") == time(0, 0)

    def test_with_whitespace(self):
        assert parse_time("  14:15  ") == time(14, 15)


# ------------------------------------------------------------------
# is_within_work_hours
# ------------------------------------------------------------------


class TestIsWithinWorkHours:
    def test_weekday_within_hours(self):
        # Wednesday 10:30
        dt = datetime(2026, 3, 25, 10, 30)  # Wednesday = 2
        assert is_within_work_hours(dt, "09:00", "18:00", [0, 1, 2, 3, 4])

    def test_weekday_before_hours(self):
        dt = datetime(2026, 3, 25, 7, 0)
        assert not is_within_work_hours(dt, "09:00", "18:00", [0, 1, 2, 3, 4])

    def test_weekday_after_hours(self):
        dt = datetime(2026, 3, 25, 19, 0)
        assert not is_within_work_hours(dt, "09:00", "18:00", [0, 1, 2, 3, 4])

    def test_weekend_not_work_day(self):
        # Saturday = 5
        dt = datetime(2026, 3, 28, 10, 30)
        assert not is_within_work_hours(dt, "09:00", "18:00", [0, 1, 2, 3, 4])

    def test_weekend_included_in_work_days(self):
        dt = datetime(2026, 3, 28, 10, 30)
        assert is_within_work_hours(dt, "09:00", "18:00", [0, 1, 2, 3, 4, 5])

    def test_at_boundary_start(self):
        dt = datetime(2026, 3, 25, 9, 0)
        assert is_within_work_hours(dt, "09:00", "18:00", [0, 1, 2, 3, 4])

    def test_at_boundary_end(self):
        dt = datetime(2026, 3, 25, 18, 0)
        assert is_within_work_hours(dt, "09:00", "18:00", [0, 1, 2, 3, 4])

    def test_empty_work_days(self):
        dt = datetime(2026, 3, 25, 10, 30)
        assert not is_within_work_hours(dt, "09:00", "18:00", [])

    def test_overnight_range_evening(self):
        dt = datetime(2026, 3, 25, 23, 0)
        assert is_within_work_hours(dt, "22:00", "06:00", [0, 1, 2, 3, 4])

    def test_overnight_range_morning(self):
        dt = datetime(2026, 3, 25, 3, 0)
        assert is_within_work_hours(dt, "22:00", "06:00", [0, 1, 2, 3, 4])


# ------------------------------------------------------------------
# is_quiet_hours
# ------------------------------------------------------------------


class TestIsQuietHours:
    def test_not_configured(self):
        dt = datetime(2026, 3, 25, 22, 0)
        assert not is_quiet_hours(dt, None, None)

    def test_partially_configured(self):
        dt = datetime(2026, 3, 25, 22, 0)
        assert not is_quiet_hours(dt, "18:00", None)
        assert not is_quiet_hours(dt, None, "09:00")

    def test_within_quiet_hours_overnight(self):
        dt = datetime(2026, 3, 25, 22, 0)
        assert is_quiet_hours(dt, "18:00", "09:00")

    def test_within_quiet_hours_early_morning(self):
        dt = datetime(2026, 3, 25, 7, 0)
        assert is_quiet_hours(dt, "18:00", "09:00")

    def test_outside_quiet_hours(self):
        dt = datetime(2026, 3, 25, 12, 0)
        assert not is_quiet_hours(dt, "18:00", "09:00")

    def test_same_day_range(self):
        dt = datetime(2026, 3, 25, 14, 0)
        assert is_quiet_hours(dt, "12:00", "16:00")

    def test_outside_same_day_range(self):
        dt = datetime(2026, 3, 25, 17, 0)
        assert not is_quiet_hours(dt, "12:00", "16:00")


# ------------------------------------------------------------------
# is_snoozed
# ------------------------------------------------------------------


class TestIsSnoozed:
    def test_not_snoozed(self):
        assert not is_snoozed(None, datetime.now())

    def test_snoozed_active(self):
        future = datetime.now() + timedelta(hours=1)
        assert is_snoozed(future, datetime.now())

    def test_snooze_expired(self):
        past = datetime.now() - timedelta(hours=1)
        assert not is_snoozed(past, datetime.now())


# ------------------------------------------------------------------
# compute_snooze_until
# ------------------------------------------------------------------


class TestComputeSnoozeUntil:
    def test_30_minutes(self):
        now = datetime(2026, 3, 25, 14, 0)
        result = compute_snooze_until("30 minutes", now)
        assert result == datetime(2026, 3, 25, 14, 30)

    def test_1_hour(self):
        now = datetime(2026, 3, 25, 14, 0)
        result = compute_snooze_until("1 hour", now)
        assert result == datetime(2026, 3, 25, 15, 0)

    def test_2_hours(self):
        now = datetime(2026, 3, 25, 14, 0)
        result = compute_snooze_until("2 hours", now)
        assert result == datetime(2026, 3, 25, 16, 0)

    def test_until_tomorrow(self):
        now = datetime(2026, 3, 25, 20, 0)
        result = compute_snooze_until("Until tomorrow", now)
        assert result == datetime(2026, 3, 26, 9, 0)

    def test_unknown_label_defaults_to_tomorrow(self):
        now = datetime(2026, 3, 25, 14, 0)
        result = compute_snooze_until("unknown", now)
        assert result == datetime(2026, 3, 26, 9, 0)


# ------------------------------------------------------------------
# should_jingle (master gate)
# ------------------------------------------------------------------


class TestShouldJingle:
    def _defaults(self, **overrides):
        base = {
            "jingle_enabled": True,
            "snooze_until": None,
            "quiet_start": None,
            "quiet_end": None,
            "work_hours_only": False,
            "work_start": "09:00",
            "work_end": "18:00",
            "work_days": [0, 1, 2, 3, 4],
        }
        base.update(overrides)
        return base

    def test_all_clear(self):
        now = datetime(2026, 3, 25, 10, 0)
        assert should_jingle(now, **self._defaults())

    def test_disabled(self):
        now = datetime(2026, 3, 25, 10, 0)
        assert not should_jingle(now, **self._defaults(jingle_enabled=False))

    def test_snoozed(self):
        now = datetime(2026, 3, 25, 10, 0)
        snooze = datetime(2026, 3, 25, 11, 0)
        assert not should_jingle(now, **self._defaults(snooze_until=snooze))

    def test_quiet_hours_active(self):
        now = datetime(2026, 3, 25, 22, 0)
        assert not should_jingle(
            now, **self._defaults(quiet_start="18:00", quiet_end="09:00")
        )

    def test_outside_work_hours(self):
        now = datetime(2026, 3, 25, 20, 0)
        assert not should_jingle(now, **self._defaults(work_hours_only=True))

    def test_within_work_hours(self):
        now = datetime(2026, 3, 25, 10, 0)
        assert should_jingle(now, **self._defaults(work_hours_only=True))

    def test_work_hours_disabled_allows_anytime(self):
        now = datetime(2026, 3, 25, 23, 0)
        assert should_jingle(now, **self._defaults(work_hours_only=False))

    def test_weekend_with_work_hours_only(self):
        # Saturday at 10 AM
        now = datetime(2026, 3, 28, 10, 0)
        assert not should_jingle(now, **self._defaults(work_hours_only=True))
