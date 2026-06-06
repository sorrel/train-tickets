import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from core.fares import TrainOption
from commands.search import format_day, day_payload, search_command


def test_format_day_shows_trains_in_time_order():
    options = [
        TrainOption("06:10", "07:01", 1950, True, "/a"),
        TrainOption("06:40", "07:30", 1640, True, "/b"),
        TrainOption("07:12", "08:03", 2490, False, "/c"),
    ]
    text = format_day("Tuesday 2026-08-11", options)
    assert "Tuesday 2026-08-11" in text
    # Departure times appear in order
    assert text.index("06:10") < text.index("06:40") < text.index("07:12")
    # Prices rendered in pounds
    assert "£16.40" in text and "£24.90" in text
    # Anytime-only train flagged differently from Advance
    assert "Anytime" in text and "Advance" in text


def test_format_day_handles_no_trains():
    assert "no trains" in format_day("Tuesday 2026-08-11", []).lower()


def test_day_payload_serialises_trains():
    options = [TrainOption("06:40", "07:30", 1640, True, "/b")]
    payload = day_payload(options, checked_at="2026-06-06T10:00:00")
    assert payload["checked_at"] == "2026-06-06T10:00:00"
    assert payload["trains"] == [
        {"depart": "06:40", "arrive": "07:30", "price_pence": 1640, "is_advance": True}
    ]


def _make_cfg(storage_path):
    cfg = MagicMock()
    cfg.travel_days = ["Tue"]
    cfg.storage_path = storage_path
    cfg.request_pause_seconds = 0.0
    cfg.origin_name = "Origin"
    cfg.destination_name = "Dest"
    cfg.window_start = "07:00"
    cfg.window_end = "09:00"
    cfg.show_cheapest = 4
    cfg.origin_nlc = "0000"
    cfg.destination_nlc = "0000"
    return cfg


def test_search_skips_frozen_past_date(tmp_path):
    """A past date already in the record is not overwritten on re-search."""
    storage = tmp_path / "prices.json"
    from core.storage import save_day
    past_date = "2026-06-02"
    save_day(storage, past_date, {"checked_at": "2026-06-01T10:00:00", "trains": []})

    cfg = _make_cfg(storage)

    with patch("commands.search.load_config", return_value=cfg), \
         patch("commands.search.TrainClient"), \
         patch("commands.search.travel_dates", return_value=[dt.date(2026, 6, 2)]), \
         patch("commands.search.dt") as mock_dt:
        mock_dt.datetime.now.return_value.replace.return_value.isoformat.return_value = "2026-06-06T10:00:00"
        mock_dt.date.today.return_value = dt.date(2026, 6, 6)
        mock_dt.date.fromisoformat = dt.date.fromisoformat

        runner = CliRunner()
        result = runner.invoke(search_command, ["2026-06-02"])

    assert result.exit_code == 0
    assert "frozen" in result.output
    from core.storage import load_record
    assert load_record(storage)[past_date]["checked_at"] == "2026-06-01T10:00:00"
