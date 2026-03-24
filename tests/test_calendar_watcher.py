import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calendar_watcher import CalendarWatcher, _extract_meet_link, _parse_start


class TestParseStart:
    def test_returns_none_for_all_day_event(self):
        event = {"start": {"date": "2026-03-24"}}
        assert _parse_start(event) is None

    def test_returns_none_for_missing_start(self):
        event = {}
        assert _parse_start(event) is None

    def test_parses_iso_datetime_with_tz(self):
        event = {"start": {"dateTime": "2026-03-24T14:00:00+02:00"}}
        result = _parse_start(event)
        assert result is not None
        assert result.tzinfo is not None
        assert result.hour == 14

    def test_parses_iso_datetime_without_tz(self):
        event = {"start": {"dateTime": "2026-03-24T14:00:00"}}
        result = _parse_start(event)
        assert result is not None
        assert result.tzinfo == timezone.utc


class TestExtractMeetLink:
    def test_returns_hangout_link(self):
        event = {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
        assert _extract_meet_link(event) == "https://meet.google.com/abc-defg-hij"

    def test_returns_none_for_non_meet_hangout(self):
        event = {"hangoutLink": "https://hangouts.google.com/something"}
        assert _extract_meet_link(event) is None

    def test_returns_meet_from_entry_points(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {"entryPointType": "video", "uri": "https://meet.google.com/xyz-abcd-efg"},
                    {"entryPointType": "phone", "uri": "tel:+1234567890"},
                ]
            }
        }
        assert _extract_meet_link(event) == "https://meet.google.com/xyz-abcd-efg"

    def test_returns_none_when_no_meet_link(self):
        event = {"summary": "Lunch"}
        assert _extract_meet_link(event) is None

    def test_returns_none_when_entry_points_have_no_meet(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {"entryPointType": "phone", "uri": "tel:+1234567890"},
                ]
            }
        }
        assert _extract_meet_link(event) is None


class TestCalendarWatcher:
    def _make_watcher(self):
        with patch("calendar_watcher.build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            watcher = CalendarWatcher(MagicMock())
            return watcher, mock_service

    def _mock_events_list(self, mock_service, items):
        mock_events = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {"items": items}
        mock_events.list.return_value = mock_list
        mock_service.events.return_value = mock_events

    def test_returns_empty_on_http_error(self):
        from googleapiclient.errors import HttpError

        watcher, mock_service = self._make_watcher()
        mock_events = MagicMock()
        mock_events.list.side_effect = HttpError(
            resp=MagicMock(status=500), content=b"error"
        )
        mock_service.events.return_value = mock_events

        result = watcher.get_upcoming_meet_events()
        assert result == []

    def test_returns_empty_on_generic_exception(self):
        watcher, mock_service = self._make_watcher()
        mock_events = MagicMock()
        mock_events.list.side_effect = ConnectionError("no network")
        mock_service.events.return_value = mock_events

        result = watcher.get_upcoming_meet_events()
        assert result == []

    def test_filters_cancelled_events(self):
        watcher, mock_service = self._make_watcher()
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        items = [
            {
                "id": "1",
                "status": "cancelled",
                "start": {"dateTime": future},
                "hangoutLink": "https://meet.google.com/abc",
            }
        ]
        self._mock_events_list(mock_service, items)

        result = watcher.get_upcoming_meet_events()
        assert result == []

    def test_filters_all_day_events(self):
        watcher, mock_service = self._make_watcher()
        items = [
            {
                "id": "1",
                "status": "confirmed",
                "start": {"date": "2026-03-24"},
                "hangoutLink": "https://meet.google.com/abc",
            }
        ]
        self._mock_events_list(mock_service, items)

        result = watcher.get_upcoming_meet_events()
        assert result == []

    def test_filters_past_events(self):
        watcher, mock_service = self._make_watcher()
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        items = [
            {
                "id": "1",
                "status": "confirmed",
                "start": {"dateTime": past},
                "hangoutLink": "https://meet.google.com/abc",
            }
        ]
        self._mock_events_list(mock_service, items)

        result = watcher.get_upcoming_meet_events()
        assert result == []

    def test_filters_non_meet_events(self):
        watcher, mock_service = self._make_watcher()
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        items = [
            {
                "id": "1",
                "status": "confirmed",
                "start": {"dateTime": future},
                "summary": "Lunch break",
            }
        ]
        self._mock_events_list(mock_service, items)

        result = watcher.get_upcoming_meet_events()
        assert result == []

    def test_returns_valid_meet_event(self):
        watcher, mock_service = self._make_watcher()
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        items = [
            {
                "id": "evt_42",
                "status": "confirmed",
                "start": {"dateTime": future},
                "summary": "Standup",
                "hangoutLink": "https://meet.google.com/abc-defg-hij",
            }
        ]
        self._mock_events_list(mock_service, items)

        result = watcher.get_upcoming_meet_events()
        assert len(result) == 1
        assert result[0]["id"] == "evt_42"
        assert result[0]["summary"] == "Standup"
        assert result[0]["meet_link"] == "https://meet.google.com/abc-defg-hij"
        assert isinstance(result[0]["start"], datetime)

    def test_returns_multiple_meet_events(self):
        watcher, mock_service = self._make_watcher()
        future1 = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()
        future2 = (datetime.now(timezone.utc) + timedelta(minutes=7)).isoformat()
        items = [
            {
                "id": "evt_1",
                "status": "confirmed",
                "start": {"dateTime": future1},
                "summary": "Meeting A",
                "hangoutLink": "https://meet.google.com/aaa",
            },
            {
                "id": "evt_2",
                "status": "confirmed",
                "start": {"dateTime": future2},
                "summary": "Meeting B",
                "hangoutLink": "https://meet.google.com/bbb",
            },
        ]
        self._mock_events_list(mock_service, items)

        result = watcher.get_upcoming_meet_events()
        assert len(result) == 2

    def test_default_summary_for_untitled_event(self):
        watcher, mock_service = self._make_watcher()
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        items = [
            {
                "id": "evt_no_title",
                "status": "confirmed",
                "start": {"dateTime": future},
                "hangoutLink": "https://meet.google.com/xyz",
            }
        ]
        self._mock_events_list(mock_service, items)

        result = watcher.get_upcoming_meet_events()
        assert result[0]["summary"] == "(No title)"
