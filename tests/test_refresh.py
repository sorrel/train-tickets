import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from commands.refresh import refresh_price_data_command


def _cfg():
    cfg = MagicMock()
    cfg.travel_days = ["Tue", "Wed", "Thu"]
    cfg.request_pause_seconds = 0.0
    cfg.refresh_pause_min_seconds = 0.0
    cfg.refresh_pause_max_seconds = 0.0
    cfg.origin_name = "Origin"
    cfg.destination_name = "Dest"
    return cfg


def _run(fake_gather, travel=lambda wd, days: [wd], today=dt.date(2026, 6, 6)):
    sleep_mock = MagicMock()
    with patch("commands.refresh.load_config", return_value=_cfg()), \
         patch("commands.refresh.TrainClient"), \
         patch("commands.refresh.load_record", return_value={}), \
         patch("commands.refresh.gather_week", side_effect=fake_gather), \
         patch("commands.refresh.travel_dates", side_effect=travel), \
         patch("commands.refresh.time.sleep", sleep_mock), \
         patch("commands.refresh.random.uniform", return_value=0.0), \
         patch("commands.refresh.dt") as mdt:
        mdt.date.today.return_value = today
        mdt.timedelta = dt.timedelta
        mdt.datetime.now.return_value.replace.return_value.isoformat.return_value = "now"
        result = CliRunner().invoke(refresh_price_data_command, [])
    return result, sleep_mock


def test_refresh_starts_tomorrow_and_walks_weeks_until_no_trains():
    seen = []

    def fake_gather(client, cfg, dates, now, existing, on_day=None):
        seen.append(dates[0])
        return len(seen) < 3   # True, True, then False → stop

    result, sleep_mock = _run(fake_gather)
    assert result.exit_code == 0
    # First day is tomorrow (today + 1), then advancing by 7 days a week
    assert seen == [dt.date(2026, 6, 7), dt.date(2026, 6, 14), dt.date(2026, 6, 21)]


def test_refresh_pauses_between_weeks_but_not_after_the_last():
    seen = []

    def fake_gather(client, cfg, dates, now, existing, on_day=None):
        seen.append(dates[0])
        return len(seen) < 3

    result, sleep_mock = _run(fake_gather)
    assert result.exit_code == 0
    # Three weeks gathered → two inter-week pauses (none after the final week)
    assert sleep_mock.call_count == 2


def test_refresh_stops_immediately_when_first_week_has_no_trains():
    calls = []

    def fake_gather(client, cfg, dates, now, existing, on_day=None):
        calls.append(dates[0])
        return False

    result, sleep_mock = _run(fake_gather)
    assert result.exit_code == 0
    assert len(calls) == 1
    assert sleep_mock.call_count == 0


def test_refresh_skips_a_week_with_no_qualifying_dates():
    # First week's travel days are all before "tomorrow" → filtered to empty,
    # so that week is skipped without a gather; the next week proceeds.
    gathered = []

    def travel(wd, days):
        if wd == dt.date(2026, 6, 7):          # the first week_date (tomorrow)
            return [dt.date(2026, 6, 1)]        # a past date → filtered out
        return [wd]

    def fake_gather(client, cfg, dates, now, existing, on_day=None):
        gathered.append(dates[0])
        return False                            # stop after the first real gather

    result, _ = _run(fake_gather, travel=travel)
    assert result.exit_code == 0
    # The empty first week was skipped; gathering began the following week
    assert gathered == [dt.date(2026, 6, 14)]


def test_refresh_reports_completion():
    def fake_gather(client, cfg, dates, now, existing, on_day=None):
        return False

    result, _ = _run(fake_gather)
    assert "Done" in result.output
    assert "no trains were returned" in result.output
