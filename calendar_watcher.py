import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

_MEET_DOMAIN = "meet.google.com"


def _parse_start(event: dict) -> datetime | None:
    """Return a timezone-aware datetime for the event start, or None for all-day events."""
    start_str = event.get("start", {}).get("dateTime")
    if not start_str:
        return None
    dt = datetime.fromisoformat(start_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_meet_link(event: dict) -> str | None:
    """Return the Google Meet link for an event, or None if not a Meet event."""
    hangout = event.get("hangoutLink")
    if hangout and _MEET_DOMAIN in hangout:
        return hangout

    entry_points = (
        event.get("conferenceData", {}).get("entryPoints", [])
    )
    for ep in entry_points:
        uri = ep.get("uri", "")
        if _MEET_DOMAIN in uri:
            return uri

    return None


class CalendarWatcher:
    def __init__(self, credentials: Any) -> None:
        self._service = build("calendar", "v3", credentials=credentials)

    def get_upcoming_meet_events(self, minutes_ahead: int = 10) -> list[dict]:
        """
        Return upcoming Google Meet events starting within `minutes_ahead` minutes.

        Each dict has: id, summary, start (datetime), meet_link (str).
        Returns an empty list on any error.
        """
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(minutes=minutes_ahead)

        try:
            result = (
                self._service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except HttpError as e:
            logger.warning("Calendar API error: %s", e)
            return []
        except Exception as e:
            logger.warning("Failed to fetch calendar events: %s", e)
            return []

        events = []
        for event in result.get("items", []):
            if event.get("status") == "cancelled":
                continue

            start = _parse_start(event)
            if start is None:
                continue  # all-day event

            if start <= now:
                continue  # already in progress

            meet_link = _extract_meet_link(event)
            if meet_link is None:
                continue

            events.append(
                {
                    "id": event["id"],
                    "summary": event.get("summary", "(No title)"),
                    "start": start,
                    "meet_link": meet_link,
                }
            )

        return events
