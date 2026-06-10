"""A travel direction — morning (to London) or evening (back from London).

Each Direction bundles the route, the time window, and which record keys hold
that direction's data. The morning direction uses the original record keys
("trains", "price_history", "checked_at") so existing data and display are
untouched; the evening direction uses parallel "evening_*" keys alongside them.

The evening route is simply the morning's stations swapped. For the evening the
booking page resolves "London Terminals" to London Bridge, so the journey
detail's origin time is already the London Bridge departure — no calling-point
lookup is needed and the politeness budget matches the morning's.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Direction:
    name: str            # "morning" | "evening"
    origin_nlc: str
    origin_name: str
    destination_nlc: str
    destination_name: str
    window_start: str
    window_end: str
    trains_key: str
    history_key: str
    checked_key: str


def morning_direction(cfg) -> Direction:
    return Direction(
        name="morning",
        origin_nlc=cfg.origin_nlc, origin_name=cfg.origin_name,
        destination_nlc=cfg.destination_nlc, destination_name=cfg.destination_name,
        window_start=cfg.window_start, window_end=cfg.window_end,
        trains_key="trains", history_key="price_history", checked_key="checked_at",
    )


def evening_direction(cfg) -> Direction:
    return Direction(
        name="evening",
        origin_nlc=cfg.destination_nlc, origin_name=cfg.destination_name,
        destination_nlc=cfg.origin_nlc, destination_name=cfg.origin_name,
        window_start=cfg.evening_window_start, window_end=cfg.evening_window_end,
        trains_key="evening_trains", history_key="evening_price_history",
        checked_key="evening_checked_at",
    )


def other_trains_key(direction: Direction) -> str:
    """The trains key of the *opposite* direction (used when clearing one side)."""
    return "evening_trains" if direction.name == "morning" else "trains"
