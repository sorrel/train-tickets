import json
from pathlib import Path

from core.fares import parse_plan, cheapest_n, latest_n, parse_times, build_options, TrainOption

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


def test_latest_n_returns_last_n_in_order():
    options = parse_plan(_plan())
    last3 = latest_n(options, 3)
    assert len(last3) == 3
    assert last3 == options[-3:]


def test_latest_n_returns_all_when_fewer_than_n():
    assert latest_n([{"journey_ref": "/a", "price_pence": 100, "is_advance": False}], 5) == \
           [{"journey_ref": "/a", "price_pence": 100, "is_advance": False}]


def test_cheapest_n_returns_n_lowest_prices():
    options = parse_plan(_plan())
    top4 = cheapest_n(options, 4)
    assert len(top4) == 4
    prices = [o["price_pence"] for o in top4]
    assert prices == sorted(prices)
    assert max(prices) <= min(o["price_pence"] for o in options if o not in top4)


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
