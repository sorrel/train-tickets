import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from commands.view import (
    render_week, view_command,
    _week_monday, _fmt_short, _fmt_checked, _price_change_suffix,
)


def _day(date_str: str, price_pence: int = 1250, is_advance: bool = True,
         checked_at: str = "2026-06-06T10:00:00", price_history=None) -> dict:
    d = {
        "checked_at": checked_at,
        "trains": [{"depart": "07:15", "arrive": "08:30",
                    "price_pence": price_pence, "is_advance": is_advance}],
    }
    if price_history:
        d["price_history"] = price_history
    return d


TODAY = dt.date(2026, 6, 6)
FUTURE = dt.date(2026, 8, 12)
MONDAY = FUTURE - dt.timedelta(days=FUTURE.weekday())


def test_week_monday_returns_monday():
    assert _week_monday("2026-08-12").weekday() == 0


def test_fmt_short():
    assert _fmt_short(dt.date(2026, 8, 9)) == "09 Aug"


def test_fmt_checked_formats_iso_datetime():
    assert _fmt_checked("2026-06-06T10:00:00") == "06 Jun 2026"


def test_price_change_suffix_no_history():
    assert _price_change_suffix({"trains": []}, 1250) == ""


def test_price_change_suffix_rise():
    day = {"price_history": [{"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1250}]}
    suffix = _price_change_suffix(day, 1390)
    assert "↑" in suffix and "1.40" in suffix and "01 Jun" in suffix


def test_price_change_suffix_fall():
    day = {"price_history": [{"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1390}]}
    suffix = _price_change_suffix(day, 1250)
    assert "↓" in suffix and "1.40" in suffix


def test_price_change_suffix_uses_most_recent_history_entry():
    """Only the last history entry is shown (most recent previous price)."""
    day = {"price_history": [
        {"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1100},
        {"checked_at": "2026-06-03T09:00:00", "cheapest_pence": 1250},
    ]}
    suffix = _price_change_suffix(day, 1390)
    assert "1.40" in suffix   # diff from 1250, not 1100
    assert "03 Jun" in suffix


def test_render_week_shows_week_header():
    record = {"2026-08-12": _day("2026-08-12")}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("Week of Mon" in l for l in lines)


def test_render_week_shows_price_in_pounds():
    record = {"2026-08-12": _day("2026-08-12", price_pence=1250)}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("£" in l and "12.50" in l for l in lines)


def test_render_week_shows_advance_label():
    record = {"2026-08-12": _day("2026-08-12", is_advance=True)}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("Advance" in l for l in lines)


def test_render_week_shows_price_rise():
    history = [{"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1100}]
    record = {"2026-08-12": _day("2026-08-12", price_pence=1250, price_history=history)}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("↑" in l for l in lines)


def test_render_week_shows_price_fall():
    history = [{"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1390}]
    record = {"2026-08-12": _day("2026-08-12", price_pence=1250, price_history=history)}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("↓" in l for l in lines)


def test_render_week_uniform_checked_date_in_header():
    record = {
        "2026-08-11": _day("2026-08-11", checked_at="2026-06-06T09:00:00"),
        "2026-08-12": _day("2026-08-12", checked_at="2026-06-06T09:05:00"),
    }
    monday = dt.date(2026, 8, 10)
    lines = render_week(monday, ["2026-08-11", "2026-08-12"], record, TODAY)
    assert "checked" in lines[0]
    assert not any("checked" in l for l in lines[1:])


def test_render_week_per_day_checked_when_dates_differ():
    record = {
        "2026-08-11": _day("2026-08-11", checked_at="2026-06-01T09:00:00"),
        "2026-08-12": _day("2026-08-12", checked_at="2026-06-06T09:00:00"),
    }
    monday = dt.date(2026, 8, 10)
    lines = render_week(monday, ["2026-08-11", "2026-08-12"], record, TODAY)
    # Each day's header carries its own checked date (two days, two markers)
    assert len([l for l in lines if "checked" in l]) == 2


def test_render_week_missing_date_shows_no_data():
    lines = render_week(MONDAY, ["2026-08-12"], {}, TODAY)
    assert any("no data" in l for l in lines)


def test_render_week_no_trains_stored():
    record = {"2026-08-12": {"checked_at": "2026-06-06T10:00:00", "trains": []}}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("no trains" in l for l in lines)


def test_render_week_shows_cheapest_two_trains():
    record = {"2026-08-12": {
        "checked_at": "2026-06-06T10:00:00",
        "trains": [
            {"depart": "07:00", "price_pence": 2490, "is_advance": False},
            {"depart": "07:30", "price_pence": 1250, "is_advance": True},
            {"depart": "07:45", "price_pence": 1890, "is_advance": True},
        ],
    }}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    text = "\n".join(lines)
    # The two cheapest are shown; the most expensive (24.90) is dropped
    assert "12.50" in text and "18.90" in text
    assert "24.90" not in text
    # Departure times make clear which train is which
    assert "07:30" in text and "07:45" in text
    assert "07:00" not in text
    # Cheapest is listed first
    assert text.index("12.50") < text.index("18.90")


def test_render_week_shows_only_one_train_when_only_one_stored():
    record = {"2026-08-12": _day("2026-08-12", price_pence=1250)}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    # One header line + one train line (plus the week header)
    train_lines = [l for l in lines if "£" in l]
    assert len(train_lines) == 1


# ---------------------------------------------------------------------------
# "cheaper" highlight — computed fresh, marks the cheapest day(s) of the week
# ---------------------------------------------------------------------------

_WK_MONDAY = dt.date(2026, 8, 10)
_TUE, _WED, _THU = "2026-08-11", "2026-08-12", "2026-08-13"


def test_cheaper_marks_the_single_cheapest_day():
    record = {
        _TUE: _day(_TUE, price_pence=1800),
        _WED: _day(_WED, price_pence=1500),   # cheapest
        _THU: _day(_THU, price_pence=2100),
    }
    lines = render_week(_WK_MONDAY, [_TUE, _WED, _THU], record, TODAY)
    cheaper = [l for l in lines if "cheaper" in l]
    assert len(cheaper) == 1
    assert "15.00" in cheaper[0]


def test_cheaper_marks_all_days_tied_at_minimum():
    record = {
        _TUE: _day(_TUE, price_pence=1500),   # tie cheapest
        _WED: _day(_WED, price_pence=1500),   # tie cheapest
        _THU: _day(_THU, price_pence=2100),
    }
    lines = render_week(_WK_MONDAY, [_TUE, _WED, _THU], record, TODAY)
    assert len([l for l in lines if "cheaper" in l]) == 2


def test_cheaper_absent_when_all_days_same_price():
    record = {
        _TUE: _day(_TUE, price_pence=1800),
        _WED: _day(_WED, price_pence=1800),
        _THU: _day(_THU, price_pence=1800),
    }
    lines = render_week(_WK_MONDAY, [_TUE, _WED, _THU], record, TODAY)
    assert not any("cheaper" in l for l in lines)


def test_cheaper_absent_for_lone_day():
    record = {_WED: _day(_WED, price_pence=1500)}
    lines = render_week(_WK_MONDAY, [_WED], record, TODAY)
    assert not any("cheaper" in l for l in lines)


def test_cheaper_uses_day_cheapest_when_multiple_trains():
    # Wednesday's cheapest train (1400) is the week minimum even though it also
    # has a dearer train; the marker lands on Wednesday.
    record = {
        _TUE: _day(_TUE, price_pence=1800),
        _WED: {"checked_at": "2026-06-06T10:00:00", "trains": [
            {"depart": "07:15", "price_pence": 1400, "is_advance": True},
            {"depart": "07:45", "price_pence": 1900, "is_advance": True},
        ]},
    }
    lines = render_week(_WK_MONDAY, [_TUE, _WED], record, TODAY)
    cheaper = [l for l in lines if "cheaper" in l]
    assert len(cheaper) == 1
    assert "14.00" in cheaper[0]


# ---------------------------------------------------------------------------
# view_command — future-only by default, --all to include past/today
# ---------------------------------------------------------------------------

def _run_view(record: dict, today: dt.date, args=None):
    cfg = MagicMock()
    cfg.storage_path = "/tmp/unused.json"
    cfg.origin_name = "Origin"
    cfg.destination_name = "Dest"
    with patch("commands.view.load_config", return_value=cfg), \
         patch("commands.view.load_record", return_value=record), \
         patch("commands.view.dt") as mock_dt:
        mock_dt.date.today.return_value = today
        mock_dt.date.fromisoformat = dt.date.fromisoformat
        mock_dt.timedelta = dt.timedelta
        return CliRunner().invoke(view_command, args or [])


def test_view_hides_past_and_today_by_default():
    # checked_at deliberately not in June, so it can't be confused with a day row
    record = {
        "2026-06-01": _day("2026-06-01", checked_at="2026-05-20T10:00:00"),  # past
        "2026-06-06": _day("2026-06-06", checked_at="2026-05-20T10:00:00"),  # today
        "2026-06-10": _day("2026-06-10", checked_at="2026-05-20T10:00:00"),  # future
    }
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0
    assert "10 Jun" in result.output      # future shown
    assert "01 Jun" not in result.output  # past hidden
    assert "06 Jun" not in result.output  # today hidden


def test_view_all_shows_everything():
    record = {
        "2026-06-01": _day("2026-06-01"),
        "2026-06-06": _day("2026-06-06"),
        "2026-06-10": _day("2026-06-10"),
    }
    result = _run_view(record, dt.date(2026, 6, 6), ["--all"])
    assert result.exit_code == 0
    assert "01 Jun" in result.output
    assert "06 Jun" in result.output
    assert "10 Jun" in result.output


def test_view_message_when_only_past_dates():
    record = {"2026-06-01": _day("2026-06-01")}
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0
    assert "No future dates" in result.output
