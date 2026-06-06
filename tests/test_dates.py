import datetime as dt

from core.dates import week_of, travel_dates, parse_date


def test_week_of_returns_monday_to_sunday():
    # 2026-08-15 is a Saturday
    start, end = week_of("2026-08-15")
    assert start == dt.date(2026, 8, 10)   # Monday
    assert end == dt.date(2026, 8, 16)     # Sunday


def test_week_of_when_given_a_monday():
    start, end = week_of("2026-08-10")     # Monday
    assert start == dt.date(2026, 8, 10)
    assert end == dt.date(2026, 8, 16)


def test_travel_dates_default_tue_wed_thu():
    dates = travel_dates("2026-08-15")
    assert dates == [dt.date(2026, 8, 11), dt.date(2026, 8, 12), dt.date(2026, 8, 13)]


def test_travel_dates_custom_days():
    dates = travel_dates("2026-08-15", days=["Mon", "Fri"])
    assert dates == [dt.date(2026, 8, 10), dt.date(2026, 8, 14)]


def test_travel_dates_rejects_unknown_day():
    import pytest
    with pytest.raises(ValueError, match="Unknown day"):
        travel_dates("2026-08-15", days=["Mon", "Xyz"])


def test_parse_date_accepts_iso():
    assert parse_date("2026-06-08") == dt.date(2026, 6, 8)


def test_parse_date_accepts_british_slashes_day_first():
    # 08/06/2026 is 8 June (day-first), NOT 6 August (month-first)
    assert parse_date("08/06/2026") == dt.date(2026, 6, 8)


def test_parse_date_is_unambiguously_day_first():
    # Day 13 can't be a month, so this proves day-first parsing
    assert parse_date("13/06/2026") == dt.date(2026, 6, 13)


def test_parse_date_accepts_single_digits_and_two_digit_year():
    assert parse_date("8/6/2026") == dt.date(2026, 6, 8)
    assert parse_date("08/06/26") == dt.date(2026, 6, 8)


def test_parse_date_accepts_dashes_and_dots_day_first():
    assert parse_date("08-06-2026") == dt.date(2026, 6, 8)
    assert parse_date("08.06.2026") == dt.date(2026, 6, 8)


def test_parse_date_accepts_written_months():
    assert parse_date("8 June 2026") == dt.date(2026, 6, 8)
    assert parse_date("8 Jun 2026") == dt.date(2026, 6, 8)


def test_parse_date_rejects_gibberish_with_clear_message():
    import pytest
    with pytest.raises(ValueError, match="Unrecognised date"):
        parse_date("not-a-date")


def test_week_of_accepts_british_format():
    # 08/06/2026 is a Monday
    start, end = week_of("08/06/2026")
    assert start == dt.date(2026, 6, 8)
    assert end == dt.date(2026, 6, 14)
