import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from commands.refresh import refresh_price_data_command
from commands.search import WeekOutcome

# Real-calendar anchors (2026): 08 Jun is a Monday, so 09/10/11 Jun are Tue/Wed/Thu.


def _outcome(found: bool, fetched: bool = True) -> WeekOutcome:
    """A gather_week result; weeks are treated as freshly fetched by default."""
    return WeekOutcome(found=found, fetched=fetched)


def _cfg():
    cfg = MagicMock()
    cfg.travel_days = ["Tue", "Wed", "Thu"]
    cfg.request_pause_seconds = 0.0
    cfg.refresh_pause_min_seconds = 0.0
    cfg.refresh_pause_max_seconds = 0.0
    cfg.origin_name = "Origin"
    cfg.destination_name = "Dest"
    return cfg


def _run(fake_gather, today, args=None):
    """Invoke refresh with the REAL travel_dates (pure) and network/sleeps mocked."""
    sleep_mock = MagicMock()
    with patch("commands.refresh.load_config", return_value=_cfg()), \
         patch("commands.refresh.TrainClient"), \
         patch("commands.refresh.load_record", return_value={}), \
         patch("commands.refresh.gather_week", side_effect=fake_gather), \
         patch("commands.refresh.time.sleep", sleep_mock), \
         patch("commands.refresh.random.uniform", return_value=0.0), \
         patch("commands.refresh.dt") as mdt:
        mdt.date.today.return_value = today
        mdt.timedelta = dt.timedelta
        mdt.datetime.now.return_value.replace.return_value.isoformat.return_value = "now"
        result = CliRunner().invoke(refresh_price_data_command, args or [])
    return result, sleep_mock


def _capture_first_dates():
    seen = []

    def fake_gather(client, cfg, dates, now, existing, direction=None, on_day=None):
        seen.append(dates[0])
        return _outcome(len(seen) < 3)   # True, True, then False → stop after three

    return seen, fake_gather


def test_refresh_walks_real_travel_weeks_until_no_trains():
    # Tomorrow (08 Jun, Mon) → first travel day 09 Jun (Tue), then +7 each week.
    seen, fake_gather = _capture_first_dates()
    result, _ = _run(fake_gather, today=dt.date(2026, 6, 7))
    assert result.exit_code == 0
    assert seen == [dt.date(2026, 6, 9), dt.date(2026, 6, 16), dt.date(2026, 6, 23)]


def test_refresh_pauses_between_weeks_but_not_after_the_last():
    seen, fake_gather = _capture_first_dates()
    result, sleep_mock = _run(fake_gather, today=dt.date(2026, 6, 7))
    assert result.exit_code == 0
    assert sleep_mock.call_count == 2   # three weeks → two inter-week pauses


def test_refresh_stops_immediately_when_first_week_has_no_trains():
    calls = []

    def fake_gather(client, cfg, dates, now, existing, direction=None, on_day=None):
        calls.append(dates[0])
        return _outcome(False)

    result, sleep_mock = _run(fake_gather, today=dt.date(2026, 6, 7))
    assert result.exit_code == 0
    assert calls == [dt.date(2026, 6, 9)]
    assert sleep_mock.call_count == 0


def test_refresh_skips_first_week_when_its_travel_days_are_past():
    # Today 06 Jun (Sat) → tomorrow 07 Jun (Sun). The week containing the 7th
    # (Mon 01 Jun) has Tue/Wed/Thu on 02/03/04 Jun, all before the 7th, so that
    # week is skipped; gathering starts the following week (09 Jun).
    calls = []

    def fake_gather(client, cfg, dates, now, existing, direction=None, on_day=None):
        calls.append(dates[0])
        return _outcome(False)

    result, _ = _run(fake_gather, today=dt.date(2026, 6, 6))
    assert result.exit_code == 0
    assert calls == [dt.date(2026, 6, 9)]


def test_refresh_defaults_to_morning_direction():
    seen = []

    def fake_gather(client, cfg, dates, now, existing, direction=None, on_day=None):
        seen.append(direction)
        return _outcome(False)

    _run(fake_gather, today=dt.date(2026, 6, 7))
    assert seen[0] is None or seen[0].name == "morning"


def test_refresh_evening_flag_uses_evening_direction():
    seen = []

    def fake_gather(client, cfg, dates, now, existing, direction=None, on_day=None):
        seen.append(direction)
        return _outcome(False)

    result, _ = _run(fake_gather, today=dt.date(2026, 6, 7), args=["--evening"])
    assert result.exit_code == 0
    assert seen[0] is not None and seen[0].name == "evening"


def test_refresh_skips_pause_for_a_fully_cached_week():
    # Week one was entirely served from today's cache (found, but no fetch), so
    # there is nothing to space out; week two is fetched and empty, so we stop.
    # Result: zero pauses despite advancing past a found week.
    outcomes = iter([_outcome(True, fetched=False), _outcome(False, fetched=True)])

    def fake_gather(client, cfg, dates, now, existing, direction=None, on_day=None):
        return next(outcomes)

    result, sleep_mock = _run(fake_gather, today=dt.date(2026, 6, 7))
    assert result.exit_code == 0
    assert sleep_mock.call_count == 0


def test_refresh_reports_completion():
    def fake_gather(client, cfg, dates, now, existing, direction=None, on_day=None):
        return _outcome(False)

    result, _ = _run(fake_gather, today=dt.date(2026, 6, 7))
    assert "Done" in result.output
    assert "no trains were returned" in result.output
