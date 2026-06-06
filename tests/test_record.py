import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from core.fares import TrainOption
from commands.record import day_payload, record_command


def test_day_payload_serialises_trains():
    options = [TrainOption("06:40", "07:30", 1640, True, "/b")]
    payload = day_payload(options, checked_at="2026-06-06T10:00:00")
    assert payload["checked_at"] == "2026-06-06T10:00:00"
    assert payload["trains"] == [
        {"depart": "06:40", "arrive": "07:30", "price_pence": 1640, "is_advance": True}
    ]


def _make_cfg(storage_path, travel_days=None):
    cfg = MagicMock()
    cfg.travel_days = travel_days or ["Tue"]
    cfg.storage_path = storage_path
    cfg.request_pause_seconds = 0.0
    cfg.origin_name = "Origin"
    cfg.destination_name = "Dest"
    cfg.window_start = "07:00"
    cfg.window_end = "09:00"
    cfg.show_cheapest = 4
    return cfg


def test_record_skips_frozen_past_date(tmp_path):
    """A date that is in the past and already in the record is not overwritten."""
    storage = tmp_path / "prices.json"
    # Seed record with a past date
    from core.storage import save_day
    past_date = "2026-06-02"  # Tuesday, clearly in the past relative to TODAY mock
    save_day(storage, past_date, {"checked_at": "2026-06-01T10:00:00", "trains": []})

    cfg = _make_cfg(storage, travel_days=["Tue"])

    with patch("commands.record.load_config", return_value=cfg), \
         patch("commands.record.TrainClient"), \
         patch("commands.record.travel_dates", return_value=[dt.date(2026, 6, 2)]), \
         patch("commands.record.dt") as mock_dt:
        mock_dt.datetime.now.return_value.replace.return_value.isoformat.return_value = "2026-06-06T10:00:00"
        mock_dt.date.today.return_value = dt.date(2026, 6, 6)
        mock_dt.date.fromisoformat = dt.date.fromisoformat

        runner = CliRunner()
        result = runner.invoke(record_command, ["2026-06-02"])

    assert result.exit_code == 0
    assert "Skipping" in result.output
    assert "frozen" in result.output
    # Original data untouched
    from core.storage import load_record
    record = load_record(storage)
    assert record[past_date]["checked_at"] == "2026-06-01T10:00:00"
