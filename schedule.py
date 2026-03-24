"""Schedule logic — quiet hours, work days, and snooze."""

from datetime import datetime, time, timedelta


def parse_time(s: str) -> time:
    """Parse 'HH:MM' into a time object."""
    parts = s.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def is_within_work_hours(
    now: datetime,
    work_start: str,
    work_end: str,
    work_days: list[int],
) -> bool:
    """Return True if `now` falls within configured work hours.

    work_days: list of weekday ints (0=Monday … 6=Sunday).
    """
    if now.weekday() not in work_days:
        return False
    start = parse_time(work_start)
    end = parse_time(work_end)
    current = now.time()
    if start <= end:
        return start <= current <= end
    # overnight range (e.g. 22:00 – 06:00)
    return current >= start or current <= end


def is_quiet_hours(
    now: datetime,
    quiet_start: str | None,
    quiet_end: str | None,
) -> bool:
    """Return True if `now` falls within quiet hours.

    Returns False if quiet hours are not configured (None values).
    """
    if quiet_start is None or quiet_end is None:
        return False
    start = parse_time(quiet_start)
    end = parse_time(quiet_end)
    current = now.time()
    if start <= end:
        return start <= current <= end
    # overnight range (e.g. 22:00 – 06:00)
    return current >= start or current <= end


def is_snoozed(snooze_until: datetime | None, now: datetime) -> bool:
    """Return True if snooze is active."""
    if snooze_until is None:
        return False
    return now < snooze_until


def compute_snooze_until(label: str, now: datetime) -> datetime:
    """Compute the snooze expiry time from a preset label.

    Recognised labels: '30 minutes', '1 hour', '2 hours', 'Until tomorrow'.
    """
    mapping = {
        "30 minutes": timedelta(minutes=30),
        "1 hour": timedelta(hours=1),
        "2 hours": timedelta(hours=2),
    }
    delta = mapping.get(label)
    if delta is not None:
        return now + delta

    # "Until tomorrow" → next day at work start (default 09:00)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    return tomorrow


def should_jingle(
    now: datetime,
    *,
    jingle_enabled: bool,
    snooze_until: datetime | None,
    quiet_start: str | None,
    quiet_end: str | None,
    work_hours_only: bool,
    work_start: str,
    work_end: str,
    work_days: list[int],
) -> bool:
    """Master gate: return True only if jingle should play right now."""
    if not jingle_enabled:
        return False
    if is_snoozed(snooze_until, now):
        return False
    if is_quiet_hours(now, quiet_start, quiet_end):
        return False
    if work_hours_only and not is_within_work_hours(now, work_start, work_end, work_days):
        return False
    return True
