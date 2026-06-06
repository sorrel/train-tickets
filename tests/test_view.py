import datetime as dt

from commands.view import render_week, _week_monday, _fmt_short, _fmt_checked


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _day(date_str: str, price_pence: int = 1250, is_advance: bool = True,
         checked_at: str = "2026-06-06T10:00:00") -> dict:
    return {
        "checked_at": checked_at,
        "trains": [{"depart": "07:15", "arrive": "08:30",
                    "price_pence": price_pence, "is_advance": is_advance}],
    }


TODAY = dt.date(2026, 6, 6)
FUTURE = dt.date(2026, 8, 12)  # a Wednesday
MONDAY = FUTURE - dt.timedelta(days=FUTURE.weekday())


# ---------------------------------------------------------------------------
# Unit: helpers
# ---------------------------------------------------------------------------

def test_week_monday_returns_monday():
    assert _week_monday("2026-08-12").weekday() == 0  # Wednesday → its Monday


def test_fmt_short():
    assert _fmt_short(dt.date(2026, 8, 9)) == "09 Aug"


def test_fmt_checked_formats_iso_datetime():
    assert _fmt_checked("2026-06-06T10:00:00") == "06 Jun 2026"


# ---------------------------------------------------------------------------
# render_week
# ---------------------------------------------------------------------------

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


def test_render_week_shows_anytime_label():
    record = {"2026-08-12": _day("2026-08-12", is_advance=False)}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("Anytime" in l for l in lines)


def test_render_week_uniform_checked_date_in_header():
    """When all days in a week have the same checked_at date, it goes on the header."""
    record = {
        "2026-08-11": _day("2026-08-11", checked_at="2026-06-06T09:00:00"),
        "2026-08-12": _day("2026-08-12", checked_at="2026-06-06T09:05:00"),
    }
    monday = dt.date(2026, 8, 10)
    lines = render_week(monday, ["2026-08-11", "2026-08-12"], record, TODAY)
    header = lines[0]
    assert "checked" in header
    # Per-day lines should NOT repeat the checked date
    assert not any("checked" in l for l in lines[1:])


def test_render_week_per_day_checked_when_dates_differ():
    """When checked_at dates differ across days, each day line shows its own."""
    record = {
        "2026-08-11": _day("2026-08-11", checked_at="2026-06-01T09:00:00"),
        "2026-08-12": _day("2026-08-12", checked_at="2026-06-06T09:00:00"),
    }
    monday = dt.date(2026, 8, 10)
    lines = render_week(monday, ["2026-08-11", "2026-08-12"], record, TODAY)
    day_lines = lines[1:]
    assert all("checked" in l for l in day_lines)


def test_render_week_missing_date_shows_no_data():
    record = {}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("no data" in l for l in lines)


def test_render_week_no_trains_stored():
    record = {"2026-08-12": {"checked_at": "2026-06-06T10:00:00", "trains": []}}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("no trains" in l for l in lines)


def test_render_week_uses_cheapest_train():
    """When multiple trains stored, the cheapest price is shown."""
    record = {"2026-08-12": {
        "checked_at": "2026-06-06T10:00:00",
        "trains": [
            {"depart": "07:00", "arrive": "08:00", "price_pence": 2490, "is_advance": False},
            {"depart": "07:30", "arrive": "08:30", "price_pence": 1250, "is_advance": True},
        ],
    }}
    lines = render_week(MONDAY, ["2026-08-12"], record, TODAY)
    assert any("12.50" in l for l in lines)
    assert not any("24.90" in l for l in lines)
