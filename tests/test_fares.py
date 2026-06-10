import json
from pathlib import Path

from core.fares import (
    parse_plan, earliest_n, parse_times, build_options, TrainOption,
    NETWORK_RAILCARD_PENCE, RAILCARD_LABEL, shows_railcard, effective_pence,
    options_from_record,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _plan():
    return json.loads((FIXTURES / "journey-plan-sample.json").read_text())


def test_parse_plan_extracts_every_journey():
    options = parse_plan(_plan())
    assert len(options) == 8


def test_parse_plan_reads_price_and_advance_flag():
    options = parse_plan(_plan())
    first = options[0]
    assert set(first) == {"journey_ref", "price_pence", "is_advance"}
    assert isinstance(first["price_pence"], int)


def test_is_advance_true_when_multiple_singles():
    # Journey index 4 in the fixture has an Advance fare (two singles, £16.40)
    options = parse_plan(_plan())
    cheapest = min(options, key=lambda o: o["price_pence"])
    assert cheapest["price_pence"] == 1640
    assert cheapest["is_advance"] is True


def test_is_advance_false_when_only_anytime():
    # Some journeys carry only the £24.90 Anytime single
    options = parse_plan(_plan())
    anytime_only = [o for o in options if o["price_pence"] == 2490]
    assert anytime_only
    assert all(o["is_advance"] is False for o in anytime_only)


def test_earliest_n_returns_first_n():
    assert earliest_n([1, 2, 3, 4, 5], 3) == [1, 2, 3]


def test_earliest_n_returns_all_when_fewer_than_n():
    assert earliest_n([1], 5) == [1]


def _detail(dep: str, arr: str) -> dict:
    return {"result": {
        "origin": {"time": {"scheduledTime": f"2026-06-16T{dep}:00"}},
        "destination": {"time": {"scheduledTime": f"2026-06-16T{arr}:00"}},
    }}


def test_earliest_selection_uses_departure_time_not_plan_order():
    """The plan's order is non-temporal; the earliest trains must still win.

    build_options fetches times for every journey and sorts by departure, so
    earliest_n then yields the genuinely earliest departures even when the plan
    lists a later train first.
    """
    parsed = [
        {"journey_ref": "/late", "price_pence": 1000, "is_advance": True},
        {"journey_ref": "/early", "price_pence": 2000, "is_advance": False},
        {"journey_ref": "/mid", "price_pence": 1500, "is_advance": True},
    ]
    details = {
        "/late": _detail("07:38", "08:24"),
        "/early": _detail("06:05", "06:53"),
        "/mid": _detail("06:40", "07:25"),
    }
    options = build_options(parsed, fetch_detail=lambda ref: details[ref])
    earliest2 = earliest_n(options, 2)
    assert [o.depart for o in earliest2] == ["06:05", "06:40"]


def test_parse_times_returns_hh_mm():
    detail = json.loads((FIXTURES / "journey-detail-sample.json").read_text())
    depart, arrive = parse_times(detail)
    assert depart == "05:46"
    assert arrive == "06:37"


def test_build_options_sorts_by_departure_time():
    # Two priced options; detail lookup is injected so no network is used.
    chosen = [
        {"journey_ref": "/b", "price_pence": 1640, "is_advance": True},
        {"journey_ref": "/a", "price_pence": 1950, "is_advance": True},
    ]
    details = {
        "/a": {"result": {"origin": {"time": {"scheduledTime": "2026-06-16T06:10:00"}},
                          "destination": {"time": {"scheduledTime": "2026-06-16T07:01:00"}}}},
        "/b": {"result": {"origin": {"time": {"scheduledTime": "2026-06-16T06:40:00"}},
                          "destination": {"time": {"scheduledTime": "2026-06-16T07:30:00"}}}},
    }
    options = build_options(chosen, fetch_detail=lambda ref: details[ref])
    assert [o.depart for o in options] == ["06:10", "06:40"]   # time order, not price order
    assert all(isinstance(o, TrainOption) for o in options)
    assert options[0].price_pence == 1950 and options[1].price_pence == 1640


# ---------------------------------------------------------------------------
# Network Railcard cap — evening fares above the £14.10 single back are never
# worth buying, so they are shown (and compared) as the railcard instead.
# ---------------------------------------------------------------------------

def test_network_railcard_single_is_fourteen_ten():
    assert NETWORK_RAILCARD_PENCE == 1410
    assert RAILCARD_LABEL == "£14.10 Network Railcard"


def test_shows_railcard_only_for_evening_fares_above_the_cap():
    assert shows_railcard(1500, evening=True) is True       # dearer evening → railcard
    assert shows_railcard(1410, evening=True) is False      # exactly the cap → not dearer
    assert shows_railcard(900, evening=True) is False       # cheaper evening → real fare
    assert shows_railcard(1500, evening=False) is False     # morning is never capped


def test_effective_pence_caps_only_dearer_evening_fares():
    assert effective_pence(1800, evening=True) == 1410      # capped to the railcard
    assert effective_pence(900, evening=True) == 900        # left alone when cheaper
    assert effective_pence(1800, evening=False) == 1800     # morning untouched


def test_options_from_record_rebuilds_trains_without_arrival():
    trains = [
        {"depart": "18:02", "price_pence": 940, "is_advance": True},
        {"depart": "18:34", "price_pence": 1800, "is_advance": True},
    ]
    options = options_from_record(trains)
    assert all(isinstance(o, TrainOption) for o in options)
    assert [o.depart for o in options] == ["18:02", "18:34"]
    assert [o.price_pence for o in options] == [940, 1800]
    assert options[0].is_advance is True
    assert options[0].arrive == ""        # arrival is not stored, so blank on reprint
