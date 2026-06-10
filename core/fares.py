"""Parse SouthEastern journey-plan and journey-detail JSON into plain structures.

Pure functions — no network. The API wraps payloads in a {"result": ...} envelope.
Prices are in pence. A journey with more than one single fare has an Advance fare
below the Anytime ceiling; a journey with a single lone fare is Anytime-only.
"""

from dataclasses import dataclass
from typing import Callable

# The walk-up Network Railcard single fare back from London. An evening advance
# fare above this is never worth buying — you would just buy the railcard single
# on the day — so the evening direction shows (and compares) it as the railcard.
NETWORK_RAILCARD_PENCE = 1410
RAILCARD_LABEL = "£14.10 Network Railcard"


@dataclass
class TrainOption:
    depart: str        # "HH:MM"
    arrive: str        # "HH:MM" — blank when rebuilt from a stored record
    price_pence: int
    is_advance: bool
    journey_ref: str


def shows_railcard(price_pence: int, evening: bool) -> bool:
    """True when an evening fare is dearer than the £14.10 railcard single."""
    return evening and price_pence > NETWORK_RAILCARD_PENCE


def effective_pence(price_pence: int, evening: bool) -> int:
    """The price a sensible traveller actually pays.

    Evening advances above the railcard single are capped at £14.10 (you'd buy
    the railcard instead); everything else is left untouched. Used so the cheap
    markers compare what is really shown, not a hidden raw fare.
    """
    if shows_railcard(price_pence, evening):
        return NETWORK_RAILCARD_PENCE
    return price_pence


def options_from_record(trains: list[dict]) -> list["TrainOption"]:
    """Rebuild TrainOptions from a stored day (no network).

    The record keeps only departure, price and the advance flag, so a reprint of
    same-day cached results has a blank arrival and no journey ref.
    """
    return [
        TrainOption(depart=t["depart"], arrive="",
                    price_pence=t["price_pence"], is_advance=t["is_advance"],
                    journey_ref="")
        for t in trains
    ]


def parse_plan(plan: dict) -> list[dict]:
    """Return [{journey_ref, price_pence, is_advance}] for each journey in a plan response."""
    journeys = plan.get("result", {}).get("outward", [])
    options = []
    for jn in journeys:
        fares = jn.get("fares", {})
        price = fares.get("cheapest", {}).get("totalPrice")
        if price is None:
            continue
        options.append({
            "journey_ref": jn["journey"],
            "price_pence": price,
            "is_advance": len(fares.get("singles", [])) > 1,
        })
    return options


def earliest_n(options: list, n: int) -> list:
    """Return the first n options.

    Call this on a list already sorted by departure (build_options sorts that
    way), so the result is the n earliest departures. The journey-plan response
    has no times, so ordering must come from the detail fetch, not the plan.
    """
    return options[:n]


def parse_times(detail: dict) -> tuple[str, str]:
    """Return (departure, arrival) as 'HH:MM' from a journey-detail response."""
    result = detail.get("result", detail)
    dep = result["origin"]["time"]["scheduledTime"]
    arr = result["destination"]["time"]["scheduledTime"]
    return dep[11:16], arr[11:16]


def build_options(
    chosen: list[dict],
    fetch_detail: Callable[[str], dict],
) -> list[TrainOption]:
    """Turn chosen plan options into TrainOptions (with times), sorted by departure.

    `fetch_detail(journey_ref)` returns a journey-detail response. Injecting it keeps
    this function pure and testable; the client supplies the real network call.
    """
    options = []
    for o in chosen:
        depart, arrive = parse_times(fetch_detail(o["journey_ref"]))
        options.append(TrainOption(
            depart=depart, arrive=arrive,
            price_pence=o["price_pence"], is_advance=o["is_advance"],
            journey_ref=o["journey_ref"],
        ))
    options.sort(key=lambda t: t.depart)
    return options
