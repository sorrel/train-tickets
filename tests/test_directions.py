from types import SimpleNamespace

from core.directions import morning_direction, evening_direction, Direction


def _cfg():
    return SimpleNamespace(
        origin_nlc="5230", origin_name="Tunbridge Wells",
        destination_nlc="1072", destination_name="London Terminals",
        window_start="05:55", window_end="08:05",
        evening_window_start="17:45", evening_window_end="19:15",
    )


def test_morning_direction_uses_config_route_and_window():
    d = morning_direction(_cfg())
    assert isinstance(d, Direction)
    assert d.name == "morning"
    assert (d.origin_nlc, d.destination_nlc) == ("5230", "1072")
    assert (d.origin_name, d.destination_name) == ("Tunbridge Wells", "London Terminals")
    assert (d.window_start, d.window_end) == ("05:55", "08:05")


def test_morning_direction_uses_existing_record_keys():
    d = morning_direction(_cfg())
    assert (d.trains_key, d.history_key, d.checked_key) == (
        "trains", "price_history", "checked_at")


def test_evening_direction_swaps_route():
    d = evening_direction(_cfg())
    assert d.name == "evening"
    assert (d.origin_nlc, d.destination_nlc) == ("1072", "5230")
    assert (d.origin_name, d.destination_name) == ("London Terminals", "Tunbridge Wells")


def test_evening_direction_uses_evening_window():
    d = evening_direction(_cfg())
    assert (d.window_start, d.window_end) == ("17:45", "19:15")


def test_evening_direction_uses_evening_record_keys():
    d = evening_direction(_cfg())
    assert (d.trains_key, d.history_key, d.checked_key) == (
        "evening_trains", "evening_price_history", "evening_checked_at")
