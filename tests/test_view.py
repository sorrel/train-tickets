import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from commands.view import (
    render_week, view_command, displayed_prices,
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
# "cheaper" highlight — marks every train at the cheapest fare on show
# ---------------------------------------------------------------------------

_WK_MONDAY = dt.date(2026, 8, 10)
_TUE, _WED, _THU = "2026-08-11", "2026-08-12", "2026-08-13"


def test_render_week_marks_global_cheapest_green():
    record = {
        _TUE: _day(_TUE, price_pence=1800),
        _WED: _day(_WED, price_pence=1500),
        _THU: _day(_THU, price_pence=2100),
    }
    lines = render_week(_WK_MONDAY, [_TUE, _WED, _THU], record, TODAY,
                        cheapest_price=1500, flag_cheapest=True)
    cheapest = [l for l in lines if "cheapest" in l]
    assert len(cheapest) == 1
    assert "15.00" in cheapest[0]


def test_render_week_marks_every_train_at_global_cheapest():
    record = {
        _TUE: _day(_TUE, price_pence=1500),
        _WED: _day(_WED, price_pence=1500),
        _THU: _day(_THU, price_pence=2100),
    }
    lines = render_week(_WK_MONDAY, [_TUE, _WED, _THU], record, TODAY,
                        cheapest_price=1500, flag_cheapest=True)
    assert len([l for l in lines if "cheapest" in l]) == 2


def test_render_week_no_marks_when_flag_off_and_no_week_variation():
    record = {_TUE: _day(_TUE, price_pence=1500)}
    lines = render_week(_WK_MONDAY, [_TUE], record, TODAY,
                        cheapest_price=1500, flag_cheapest=False)
    assert not any("cheap" in l for l in lines)


def test_render_week_marks_week_cheapest_yellow_when_above_global():
    # Week low is 1490 (with a dearer 1800); the global low is 730 elsewhere,
    # so this week's cheapest is "cheaper" (yellow), not "cheapest" (green).
    record = {
        _TUE: {"checked_at": "2026-06-06T10:00:00", "trains": [
            {"depart": "05:46", "price_pence": 1490, "is_advance": True},
            {"depart": "06:05", "price_pence": 1800, "is_advance": True},
        ]},
    }
    lines = render_week(_WK_MONDAY, [_TUE], record, TODAY,
                        cheapest_price=730, flag_cheapest=True)
    text = "\n".join(lines)
    assert "← cheaper" in text and "← cheapest" not in text
    cheaper = [l for l in lines if "cheaper" in l]
    assert "14.90" in cheaper[0]


def test_render_week_global_cheapest_takes_precedence_over_week_cheaper():
    # The week's low IS the global low — it should be green "cheapest", not
    # yellow "cheaper".
    record = {
        _TUE: {"checked_at": "2026-06-06T10:00:00", "trains": [
            {"depart": "05:46", "price_pence": 730, "is_advance": True},
            {"depart": "06:05", "price_pence": 1800, "is_advance": True},
        ]},
    }
    lines = render_week(_WK_MONDAY, [_TUE], record, TODAY,
                        cheapest_price=730, flag_cheapest=True)
    text = "\n".join(lines)
    assert "← cheapest" in text
    assert "← cheaper\n" not in text and not text.rstrip().endswith("← cheaper")


def test_displayed_prices_takes_cheapest_two_per_day():
    record = {
        _TUE: {"checked_at": "2026-06-06T10:00:00", "trains": [
            {"depart": "07:00", "price_pence": 2100, "is_advance": False},
            {"depart": "07:15", "price_pence": 1400, "is_advance": True},
            {"depart": "07:45", "price_pence": 1900, "is_advance": True},
        ]},
    }
    assert sorted(displayed_prices(record, [_TUE])) == [1400, 1900]


# --- the regression the user hit: global, not per-week ---------------------

def test_cheapest_flags_uniform_low_week_against_a_dearer_week():
    # Week A is uniformly £7.30 (730); week B has a dearer £18.00 train. The
    # £7.30 trains are the global low, so every one is flagged green "cheapest".
    cheap = {"checked_at": "2026-06-06T10:00:00",
             "trains": [{"depart": "06:05", "price_pence": 730, "is_advance": True},
                        {"depart": "06:13", "price_pence": 730, "is_advance": True}]}
    dear = {"checked_at": "2026-06-06T10:00:00",
            "trains": [{"depart": "06:05", "price_pence": 1800, "is_advance": True}]}
    record = {
        "2026-08-11": dict(cheap), "2026-08-12": dict(cheap), "2026-08-13": dict(cheap),
        "2026-08-18": dict(dear),  # next week, dearer
    }
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0
    assert result.output.count("cheapest") == 6  # 3 days × 2 trains
    # The £18.00 train (its week's only price) is not flagged at all
    dear_lines = [l for l in result.output.splitlines() if "18.00" in l]
    assert dear_lines and not any("cheap" in l for l in dear_lines)


def test_two_tiers_green_global_and_yellow_weekly():
    # Week A: uniform £7.30 (global low → "cheapest"). Week B: £14.90 beside
    # £18.00 (week low above global → "cheaper").
    cheap = {"checked_at": "2026-06-06T10:00:00",
             "trains": [{"depart": "06:05", "price_pence": 730, "is_advance": True}]}
    mixed = {"checked_at": "2026-06-06T10:00:00",
             "trains": [{"depart": "05:46", "price_pence": 1490, "is_advance": True},
                        {"depart": "06:05", "price_pence": 1800, "is_advance": True}]}
    record = {"2026-08-11": dict(cheap), "2026-08-18": dict(mixed)}
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0
    assert result.output.count("← cheapest") == 1   # the £7.30
    assert result.output.count("← cheaper") == 1     # the £14.90
    cheaper_line = [l for l in result.output.splitlines() if "← cheaper" in l][0]
    assert "14.90" in cheaper_line


def test_cheap_markers_absent_when_everything_on_show_is_one_price():
    same = {"checked_at": "2026-06-06T10:00:00",
            "trains": [{"depart": "06:05", "price_pence": 1800, "is_advance": True}]}
    record = {"2026-08-11": dict(same), "2026-08-18": dict(same)}
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0
    assert "cheap" not in result.output


def test_cheapest_marker_coexists_with_price_change():
    # A train that is both the global cheapest AND has fallen in price should
    # show both the "↓ since" change and the "← cheapest" marker on one line.
    record = {
        "2026-08-11": {"checked_at": "2026-06-06T10:00:00",
                       "trains": [{"depart": "06:05", "price_pence": 730, "is_advance": True}],
                       "price_history": [{"checked_at": "2026-06-01T09:00:00",
                                          "cheapest_pence": 900}]},
        "2026-08-18": {"checked_at": "2026-06-06T10:00:00",
                       "trains": [{"depart": "06:05", "price_pence": 1800, "is_advance": True}]},
    }
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0
    line = [l for l in result.output.splitlines() if "07.30" in l or "7.30" in l][0]
    assert "↓" in line and "since" in line   # price-fall marker
    assert "← cheapest" in line              # cheapest marker, same line


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


# ---------------------------------------------------------------------------
# horizon note — "no trains on sale from X onwards"
# ---------------------------------------------------------------------------

def test_view_shows_horizon_note_from_meta():
    record = {
        "2026-08-11": _day("2026-08-11", checked_at="2026-05-20T10:00:00"),
        "meta": {"no_trains_from": "2026-09-15", "checked_at": "2026-06-02T10:00:00"},
    }
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0
    assert "No trains on sale from Tue 15 Sep 2026 onwards" in result.output
    assert "checked 02 Jun 2026" in result.output


def test_view_does_not_render_empty_days_as_rows():
    # Legacy empty-train days are folded into the note, not shown as "(no trains)"
    record = {
        "2026-08-11": _day("2026-08-11", checked_at="2026-05-20T10:00:00"),
        "2026-09-15": {"checked_at": "2026-06-02T10:00:00", "trains": []},
    }
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0
    assert "(no trains)" not in result.output
    assert "No trains on sale from Tue 15 Sep 2026 onwards" in result.output


def test_view_note_uses_earliest_of_meta_and_empty_days():
    record = {
        "2026-08-11": _day("2026-08-11", checked_at="2026-05-20T10:00:00"),
        "2026-09-22": {"checked_at": "2026-06-04T10:00:00", "trains": []},
        "meta": {"no_trains_from": "2026-09-15", "checked_at": "2026-06-02T10:00:00"},
    }
    result = _run_view(record, dt.date(2026, 6, 6))
    assert "from Tue 15 Sep 2026" in result.output   # the earlier of the two
    assert "22 Sep" not in result.output


def test_view_no_note_when_no_horizon():
    record = {"2026-08-11": _day("2026-08-11", checked_at="2026-05-20T10:00:00")}
    result = _run_view(record, dt.date(2026, 6, 6))
    assert "No trains on sale" not in result.output


def test_view_meta_key_not_treated_as_a_day():
    record = {
        "2026-08-11": _day("2026-08-11", checked_at="2026-05-20T10:00:00"),
        "meta": {"no_trains_from": "2026-09-15", "checked_at": "2026-06-02T10:00:00"},
    }
    result = _run_view(record, dt.date(2026, 6, 6))
    assert result.exit_code == 0   # would crash if "meta" were parsed as a date
