import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from core.fares import TrainOption
from commands.search import format_day, day_payload


def test_format_day_shows_trains_in_time_order():
    options = [
        TrainOption("06:10", "07:01", 1950, True, "/a"),
        TrainOption("06:40", "07:30", 1640, True, "/b"),
        TrainOption("07:12", "08:03", 2490, False, "/c"),
    ]
    text = format_day("Tuesday 2026-08-11", options)
    assert "Tuesday 2026-08-11" in text
    assert text.index("06:10") < text.index("06:40") < text.index("07:12")
    assert "£16.40" in text and "£24.90" in text
    assert "Anytime" in text and "Advance" in text
    # search display shows arrival too (07:01, 07:30, 08:03), even though
    # storage keeps only the departure time
    assert "07:01" in text and "08:03" in text


def test_format_day_handles_no_trains():
    assert "no trains" in format_day("Tuesday 2026-08-11", []).lower()


def test_day_payload_serialises_trains():
    options = [TrainOption("06:40", "07:30", 1640, True, "/b")]
    payload = day_payload(options, checked_at="2026-06-06T10:00:00")
    assert payload["checked_at"] == "2026-06-06T10:00:00"
    assert payload["trains"] == [
        {"depart": "06:40", "price_pence": 1640, "is_advance": True}
    ]


def test_day_payload_no_history_when_price_unchanged():
    previous = {
        "checked_at": "2026-06-01T09:00:00",
        "trains": [{"depart": "07:00",
                    "price_pence": 1640, "is_advance": True}],
    }
    options = [TrainOption("07:00", "08:00", 1640, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous)
    assert "price_history" not in payload


def test_day_payload_records_history_when_price_rises():
    previous = {
        "checked_at": "2026-06-01T09:00:00",
        "trains": [{"depart": "07:00",
                    "price_pence": 1250, "is_advance": True}],
    }
    options = [TrainOption("07:00", "08:00", 1390, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous)
    assert payload["price_history"] == [
        {"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1250}
    ]


def test_day_payload_records_history_when_price_falls():
    previous = {
        "checked_at": "2026-06-01T09:00:00",
        "trains": [{"depart": "07:00",
                    "price_pence": 1390, "is_advance": True}],
    }
    options = [TrainOption("07:00", "08:00", 1250, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous)
    assert payload["price_history"][0]["cheapest_pence"] == 1390


def test_day_payload_accumulates_history_across_lookups():
    """History entries from previous record are preserved when price changes again."""
    previous = {
        "checked_at": "2026-06-03T09:00:00",
        "trains": [{"depart": "07:00",
                    "price_pence": 1390, "is_advance": True}],
        "price_history": [{"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1250}],
    }
    options = [TrainOption("07:00", "08:00", 1490, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous)
    assert len(payload["price_history"]) == 2
    assert payload["price_history"][0]["cheapest_pence"] == 1250
    assert payload["price_history"][1]["cheapest_pence"] == 1390


def test_day_payload_no_previous_means_no_history():
    options = [TrainOption("07:00", "08:00", 1250, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous=None)
    assert "price_history" not in payload
