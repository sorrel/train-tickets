import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from core.fares import TrainOption
from core.storage import load_record, save_day, META_KEY
from commands.search import format_day, day_payload, search_command


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


# ---------------------------------------------------------------------------
# search_command — persistence: saves trains, skips empty days, records horizon
# ---------------------------------------------------------------------------

def _cfg(storage_path):
    cfg = MagicMock()
    cfg.travel_days = ["Tue"]
    cfg.storage_path = storage_path
    cfg.request_pause_seconds = 0.0
    cfg.origin_name = "Origin"
    cfg.destination_name = "Dest"
    cfg.window_start = "05:55"
    cfg.window_end = "08:05"
    cfg.show_count = 5
    cfg.origin_nlc = "0000"
    cfg.destination_nlc = "0000"
    return cfg


def _run_search(storage, lookup_result, week_date, search_dates):
    """Invoke search with lookup_day and network stubbed out."""
    cfg = _cfg(storage)
    with patch("commands.search.load_config", return_value=cfg), \
         patch("commands.search.TrainClient"), \
         patch("commands.search.travel_dates", return_value=search_dates), \
         patch("commands.search.lookup_day", side_effect=lookup_result), \
         patch("commands.search.dt") as mock_dt:
        mock_dt.datetime.now.return_value.replace.return_value.isoformat.return_value = \
            "2026-06-06T10:00:00"
        mock_dt.date.today.return_value = dt.date(2026, 6, 6)
        return CliRunner().invoke(search_command, [week_date])


def test_search_does_not_save_empty_days_but_records_horizon(tmp_path):
    storage = tmp_path / "prices.json"
    result = _run_search(storage, lambda *a: [], "2026-09-15", [dt.date(2026, 9, 15)])
    assert result.exit_code == 0
    record = load_record(storage)
    assert "2026-09-15" not in record          # empty day not saved
    assert record[META_KEY]["no_trains_from"] == "2026-09-15"
    assert record[META_KEY]["checked_at"] == "2026-06-06T10:00:00"


def test_search_removes_a_previously_saved_day_that_now_has_no_trains(tmp_path):
    storage = tmp_path / "prices.json"
    save_day(storage, "2026-09-15", {"checked_at": "2026-05-01T10:00:00",
                                      "trains": [{"depart": "06:05", "price_pence": 730,
                                                  "is_advance": True}]})
    result = _run_search(storage, lambda *a: [], "2026-09-15", [dt.date(2026, 9, 15)])
    assert result.exit_code == 0
    assert "2026-09-15" not in load_record(storage)


def test_search_saves_days_with_trains(tmp_path):
    storage = tmp_path / "prices.json"
    opts = [TrainOption("06:05", "06:53", 1250, True, "/a")]
    result = _run_search(storage, lambda *a: opts, "2026-08-11", [dt.date(2026, 8, 11)])
    assert result.exit_code == 0
    record = load_record(storage)
    assert record["2026-08-11"]["trains"] == [
        {"depart": "06:05", "price_pence": 1250, "is_advance": True}
    ]
    assert META_KEY not in record
