from core.fares import TrainOption
from commands.search import format_day


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
