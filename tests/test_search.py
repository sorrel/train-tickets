import datetime as dt
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from types import SimpleNamespace

from core.fares import TrainOption
from core.storage import load_record, save_day, META_KEY
from core.directions import evening_direction, morning_direction
from commands.search import format_day, day_payload, search_command, gather_week


def _evening_dir():
    return evening_direction(SimpleNamespace(
        origin_nlc="5230", origin_name="TW", destination_nlc="1072",
        destination_name="LDN", window_start="05:55", window_end="08:05",
        evening_window_start="17:45", evening_window_end="19:15"))


def test_day_payload_evening_writes_evening_keys_and_preserves_morning():
    previous = {"checked_at": "2026-06-01T09:00:00",
                "trains": [{"depart": "06:05", "price_pence": 1250, "is_advance": True}]}
    options = [TrainOption("18:00", "19:00", 2110, True, "/e")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous, _evening_dir())
    # morning data untouched
    assert payload["trains"] == [{"depart": "06:05", "price_pence": 1250, "is_advance": True}]
    assert payload["checked_at"] == "2026-06-01T09:00:00"
    # evening data written under its own keys
    assert payload["evening_checked_at"] == "2026-06-06T10:00:00"
    assert payload["evening_trains"] == [
        {"depart": "18:00", "price_pence": 2110, "is_advance": True}]


def test_day_payload_evening_history_is_independent_of_morning():
    previous = {
        "checked_at": "2026-06-01T09:00:00",
        "trains": [{"depart": "06:05", "price_pence": 1250, "is_advance": True}],
        "evening_checked_at": "2026-06-01T09:00:00",
        "evening_trains": [{"depart": "18:00", "price_pence": 2110, "is_advance": True}],
    }
    options = [TrainOption("18:00", "19:00", 2200, True, "/e")]   # evening price rose
    payload = day_payload(options, "2026-06-06T10:00:00", previous, _evening_dir())
    assert payload["evening_price_history"] == [
        {"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 2110}]
    assert "price_history" not in payload   # morning history untouched


def test_format_day_shows_trains_in_time_order():
    options = [
        TrainOption("06:10", "07:01", 1950, True, "/a"),
        TrainOption("06:40", "07:30", 1640, True, "/b"),
        TrainOption("07:12", "08:03", 2490, False, "/c"),
    ]
    text = format_day("Tuesday 2026-08-11", options)
    assert "Tuesday 2026-08-11" in text
    assert text.index("06:10") < text.index("06:40") < text.index("07:12")
    assert "£16.40" in text and "£24.90" in text
    assert "Anytime" in text and "Advance" in text
    # search display shows arrival too (07:01, 07:30, 08:03), even though
    # storage keeps only the departure time
    assert "07:01" in text and "08:03" in text


def test_format_day_handles_no_trains():
    assert "no trains" in format_day("Tuesday 2026-08-11", []).lower()


def test_format_day_evening_shows_railcard_for_dearer_fares_only():
    options = [
        TrainOption("18:02", "18:50", 940, True, "/a"),    # under £14.10 — real fare
        TrainOption("18:34", "19:20", 1800, True, "/b"),   # over £14.10 — railcard
    ]
    text = format_day("Tuesday 2026-08-11", options, evening=True)
    assert "£9.40" in text and "Advance" in text          # cheap evening train kept
    assert "£14.10 Network Railcard" in text              # dearer one swapped
    assert "£18.00" not in text                           # raw dear price hidden


def test_format_day_morning_never_shows_railcard():
    options = [TrainOption("06:34", "07:20", 1800, True, "/b")]
    text = format_day("Tuesday 2026-08-11", options)      # morning (evening=False)
    assert "£18.00" in text
    assert "Network Railcard" not in text


def test_format_day_without_arrival_shows_departure_only():
    # A same-day cached reprint has no arrival time (not stored).
    options = [TrainOption("06:05", "", 1250, True, "")]
    text = format_day("Tuesday 2026-08-11", options)
    assert "06:05" in text and "£12.50" in text
    assert "→" not in text                                # no arrow without an arrival


def test_day_payload_serialises_trains():
    options = [TrainOption("06:40", "07:30", 1640, True, "/b")]
    payload = day_payload(options, checked_at="2026-06-06T10:00:00")
    assert payload["checked_at"] == "2026-06-06T10:00:00"
    assert payload["trains"] == [
        {"depart": "06:40", "price_pence": 1640, "is_advance": True}
    ]


def test_day_payload_no_history_when_price_unchanged():
    previous = {
        "checked_at": "2026-06-01T09:00:00",
        "trains": [{"depart": "07:00",
                    "price_pence": 1640, "is_advance": True}],
    }
    options = [TrainOption("07:00", "08:00", 1640, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous)
    assert "price_history" not in payload


def test_day_payload_records_history_when_price_rises():
    previous = {
        "checked_at": "2026-06-01T09:00:00",
        "trains": [{"depart": "07:00",
                    "price_pence": 1250, "is_advance": True}],
    }
    options = [TrainOption("07:00", "08:00", 1390, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous)
    assert payload["price_history"] == [
        {"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1250}
    ]


def test_day_payload_records_history_when_price_falls():
    previous = {
        "checked_at": "2026-06-01T09:00:00",
        "trains": [{"depart": "07:00",
                    "price_pence": 1390, "is_advance": True}],
    }
    options = [TrainOption("07:00", "08:00", 1250, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous)
    assert payload["price_history"][0]["cheapest_pence"] == 1390


def test_day_payload_accumulates_history_across_lookups():
    """History entries from previous record are preserved when price changes again."""
    previous = {
        "checked_at": "2026-06-03T09:00:00",
        "trains": [{"depart": "07:00",
                    "price_pence": 1390, "is_advance": True}],
        "price_history": [{"checked_at": "2026-06-01T09:00:00", "cheapest_pence": 1250}],
    }
    options = [TrainOption("07:00", "08:00", 1490, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous)
    assert len(payload["price_history"]) == 2
    assert payload["price_history"][0]["cheapest_pence"] == 1250
    assert payload["price_history"][1]["cheapest_pence"] == 1390


def test_day_payload_no_previous_means_no_history():
    options = [TrainOption("07:00", "08:00", 1250, True, "/b")]
    payload = day_payload(options, "2026-06-06T10:00:00", previous=None)
    assert "price_history" not in payload


# ---------------------------------------------------------------------------
# search_command — persistence: saves trains, skips empty days, records horizon
# ---------------------------------------------------------------------------

def _cfg(storage_path):
    cfg = MagicMock()
    cfg.travel_days = ["Tue"]
    cfg.storage_path = storage_path
    cfg.request_pause_seconds = 0.0
    cfg.origin_name = "Origin"
    cfg.destination_name = "Dest"
    cfg.window_start = "05:55"
    cfg.window_end = "08:05"
    cfg.show_count = 5
    cfg.origin_nlc = "5230"
    cfg.destination_nlc = "1072"
    cfg.evening_window_start = "17:45"
    cfg.evening_window_end = "19:15"
    return cfg


def _run_search(storage, lookup_result, week_date, search_dates, args=None):
    """Invoke search with lookup_day and network stubbed out."""
    cfg = _cfg(storage)
    with patch("commands.search.load_config", return_value=cfg), \
         patch("commands.search.TrainClient"), \
         patch("commands.search.travel_dates", return_value=search_dates), \
         patch("commands.search.lookup_day", side_effect=lookup_result), \
         patch("commands.search.dt") as mock_dt:
        mock_dt.datetime.now.return_value.replace.return_value.isoformat.return_value = \
            "2026-06-06T10:00:00"
        mock_dt.date.today.return_value = dt.date(2026, 6, 6)
        return CliRunner().invoke(search_command, [week_date] + (args or []))


def test_search_does_not_save_empty_days_but_records_horizon(tmp_path):
    storage = tmp_path / "prices.json"
    result = _run_search(storage, lambda *a: [], "2026-09-15", [dt.date(2026, 9, 15)])
    assert result.exit_code == 0
    record = load_record(storage)
    assert "2026-09-15" not in record          # empty day not saved
    assert record[META_KEY]["no_trains_from"] == "2026-09-15"
    assert record[META_KEY]["checked_at"] == "2026-06-06T10:00:00"


def test_search_removes_a_previously_saved_day_that_now_has_no_trains(tmp_path):
    storage = tmp_path / "prices.json"
    save_day(storage, "2026-09-15", {"checked_at": "2026-05-01T10:00:00",
                                      "trains": [{"depart": "06:05", "price_pence": 730,
                                                  "is_advance": True}]})
    result = _run_search(storage, lambda *a: [], "2026-09-15", [dt.date(2026, 9, 15)])
    assert result.exit_code == 0
    assert "2026-09-15" not in load_record(storage)


def test_search_saves_days_with_trains(tmp_path):
    storage = tmp_path / "prices.json"
    opts = [TrainOption("06:05", "06:53", 1250, True, "/a")]
    result = _run_search(storage, lambda *a: opts, "2026-08-11", [dt.date(2026, 8, 11)])
    assert result.exit_code == 0
    record = load_record(storage)
    assert record["2026-08-11"]["trains"] == [
        {"depart": "06:05", "price_pence": 1250, "is_advance": True}
    ]
    assert META_KEY not in record


def test_search_evening_saves_under_evening_keys(tmp_path):
    storage = tmp_path / "prices.json"
    opts = [TrainOption("18:00", "18:50", 2110, True, "/e")]
    result = _run_search(storage, lambda *a: opts, "2026-08-11",
                         [dt.date(2026, 8, 11)], args=["--evening"])
    assert result.exit_code == 0
    day = load_record(storage)["2026-08-11"]
    assert "trains" not in day
    assert day["evening_trains"] == [
        {"depart": "18:00", "price_pence": 2110, "is_advance": True}]


def test_search_evening_output_shows_railcard_for_dear_fare(tmp_path):
    storage = tmp_path / "prices.json"
    opts = [TrainOption("18:00", "18:50", 1800, True, "/e")]   # dearer than £14.10
    result = _run_search(storage, lambda *a: opts, "2026-08-11",
                         [dt.date(2026, 8, 11)], args=["--evening"])
    assert result.exit_code == 0
    assert "£14.10 Network Railcard" in result.output
    assert "£18.00" not in result.output
    # but the raw fare is still saved untouched
    assert load_record(storage)["2026-08-11"]["evening_trains"][0]["price_pence"] == 1800


def test_search_evening_preserves_existing_morning(tmp_path):
    storage = tmp_path / "prices.json"
    save_day(storage, "2026-08-11", {"checked_at": "2026-05-01T10:00:00",
                                     "trains": [{"depart": "06:05", "price_pence": 1250,
                                                 "is_advance": True}]})
    opts = [TrainOption("18:00", "18:50", 2110, True, "/e")]
    _run_search(storage, lambda *a: opts, "2026-08-11",
                [dt.date(2026, 8, 11)], args=["--evening"])
    day = load_record(storage)["2026-08-11"]
    assert day["trains"][0]["price_pence"] == 1250        # morning kept
    assert day["evening_trains"][0]["price_pence"] == 2110  # evening added


def test_search_evening_with_no_trains_keeps_morning(tmp_path):
    storage = tmp_path / "prices.json"
    save_day(storage, "2026-08-11", {"checked_at": "2026-05-01T10:00:00",
                                     "trains": [{"depart": "06:05", "price_pence": 1250,
                                                 "is_advance": True}]})
    _run_search(storage, lambda *a: [], "2026-08-11",
                [dt.date(2026, 8, 11)], args=["--evening"])
    day = load_record(storage)["2026-08-11"]
    assert day["trains"][0]["price_pence"] == 1250        # morning still there
    assert "evening_trains" not in day


def test_gather_week_evening_direction_saves_evening_trains(tmp_path):
    storage = tmp_path / "prices.json"
    cfg = _cfg(storage)
    opts = [TrainOption("18:00", "18:50", 2110, True, "/e")]
    with patch("commands.search.lookup_day", return_value=opts):
        outcome = gather_week(object(), cfg, [dt.date(2026, 8, 11)],
                              "2026-06-06T10:00:00", {}, direction=_evening_dir())
    assert outcome.found is True
    assert load_record(storage)["2026-08-11"]["evening_trains"][0]["price_pence"] == 2110


# ---------------------------------------------------------------------------
# gather_week — shared gathering used by search and refresh-price-data
# ---------------------------------------------------------------------------

def test_gather_week_calls_on_day_and_reports_found(tmp_path):
    storage = tmp_path / "prices.json"
    cfg = _cfg(storage)
    opts = [TrainOption("06:05", "06:53", 1250, True, "/a")]
    seen = []
    with patch("commands.search.lookup_day", return_value=opts):
        from commands.search import gather_week
        outcome = gather_week(cfg_client := object(), cfg, [dt.date(2026, 8, 11)],
                              "2026-06-06T10:00:00", {}, on_day=lambda d, o: seen.append((d, o)))
    assert outcome.found is True
    assert seen == [(dt.date(2026, 8, 11), opts)]
    assert load_record(storage)["2026-08-11"]["trains"][0]["price_pence"] == 1250


def test_gather_week_reports_not_found_when_no_trains(tmp_path):
    storage = tmp_path / "prices.json"
    cfg = _cfg(storage)
    with patch("commands.search.lookup_day", return_value=[]):
        from commands.search import gather_week
        outcome = gather_week(object(), cfg, [dt.date(2026, 9, 15)],
                              "2026-06-06T10:00:00", {})
    assert outcome.found is False
    assert load_record(storage)[META_KEY]["no_trains_from"] == "2026-09-15"


# ---------------------------------------------------------------------------
# Same-day guard — never fetch a direction twice in one day; reprint the cache
# ---------------------------------------------------------------------------

def test_gather_week_reuses_same_day_cache_without_fetching(tmp_path):
    storage = tmp_path / "prices.json"
    cfg = _cfg(storage)
    day = {"checked_at": "2026-06-06T08:00:00",          # earlier today
           "trains": [{"depart": "06:05", "price_pence": 1250, "is_advance": True}]}
    save_day(storage, "2026-08-11", day)
    existing = load_record(storage)
    seen = []

    def boom(*a, **k):
        raise AssertionError("must not fetch a direction already checked today")

    with patch("commands.search.lookup_day", side_effect=boom):
        outcome = gather_week(object(), cfg, [dt.date(2026, 8, 11)],
                              "2026-06-06T10:00:00", existing,
                              on_day=lambda d, o: seen.append(o))
    assert outcome.found is True
    assert outcome.fetched is False                       # no network used
    assert seen[0][0].price_pence == 1250                 # cached train reprinted
    # the original check time is preserved (not bumped to 10:00)
    assert load_record(storage)["2026-08-11"]["checked_at"] == "2026-06-06T08:00:00"


def test_gather_week_refetches_when_cache_is_from_a_previous_day(tmp_path):
    storage = tmp_path / "prices.json"
    cfg = _cfg(storage)
    save_day(storage, "2026-08-11",
             {"checked_at": "2026-06-05T10:00:00",        # yesterday
              "trains": [{"depart": "06:05", "price_pence": 1250, "is_advance": True}]})
    existing = load_record(storage)
    opts = [TrainOption("06:05", "06:53", 1190, True, "/a")]
    with patch("commands.search.lookup_day", return_value=opts):
        outcome = gather_week(object(), cfg, [dt.date(2026, 8, 11)],
                              "2026-06-06T10:00:00", existing)
    assert outcome.fetched is True
    assert load_record(storage)["2026-08-11"]["trains"][0]["price_pence"] == 1190


def test_gather_week_same_day_guard_is_per_direction(tmp_path):
    # Morning was checked today, but the evening has not been — so the evening
    # is still fetched (the guard is per direction, not per day).
    storage = tmp_path / "prices.json"
    cfg = _cfg(storage)
    save_day(storage, "2026-08-11",
             {"checked_at": "2026-06-06T08:00:00",
              "trains": [{"depart": "06:05", "price_pence": 1250, "is_advance": True}]})
    existing = load_record(storage)
    opts = [TrainOption("18:00", "18:50", 1100, True, "/e")]
    with patch("commands.search.lookup_day", return_value=opts) as lk:
        outcome = gather_week(object(), cfg, [dt.date(2026, 8, 11)],
                              "2026-06-06T10:00:00", existing, direction=_evening_dir())
    assert lk.called and outcome.fetched is True
    assert load_record(storage)["2026-08-11"]["evening_trains"][0]["price_pence"] == 1100
