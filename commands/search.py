"""Search command — the earliest morning trains per travel day, in time order.

Results are saved after every lookup. When the cheapest price changes from the
previous lookup the old price is appended to price_history on that day's record.
"""

import datetime as dt
from pathlib import Path
from typing import NamedTuple

import click

from core.config import load_config
from core.client import TrainClient
from core.dates import travel_dates, WEEKDAY_FULL
from core.directions import morning_direction, evening_direction, other_trains_key
from core.fares import (
    parse_plan, earliest_n, build_options, TrainOption,
    shows_railcard, RAILCARD_LABEL, options_from_record,
)


class WeekOutcome(NamedTuple):
    """What a week's gathering did. `found` — any date had trains (cached or
    fresh). `fetched` — at least one date actually hit the network (a fully
    cached week is False, so refresh can skip its between-week pause)."""
    found: bool
    fetched: bool
from core.storage import (
    load_record, save_day, clear_day_direction, write_meta, updated_horizon, META_KEY,
)

CONFIG_FILE = Path(__file__).parent.parent / "config.local.json"


def format_day(heading: str, options: list[TrainOption], evening: bool = False) -> str:
    """Render one day's trains as a text block (pure — easy to test).

    For the evening direction, a fare dearer than the £14.10 Network Railcard
    single is shown as the railcard instead (you'd buy that on the day). The
    arrival is omitted when blank — a same-day cached reprint has no stored time.
    """
    lines = [click.style(heading, fg="cyan", bold=True)]
    if not options:
        lines.append("  (no trains found in the window)")
        return "\n".join(lines)
    for o in options:
        when = f"{o.depart} → {o.arrive}" if o.arrive else o.depart
        if shows_railcard(o.price_pence, evening):
            lines.append(f"  {when}   {RAILCARD_LABEL}")
        else:
            kind = "Advance" if o.is_advance else "Anytime"
            price = f"£{o.price_pence / 100:.2f}"
            lines.append(f"  {when}   {price:>8}   {kind}")
    return "\n".join(lines)


def day_payload(options: list[TrainOption], checked_at: str,
                previous: dict | None = None, direction=None) -> dict:
    """Build the JSON-serialisable record for one day's direction.

    `direction` selects which record keys are written (morning uses the original
    keys; evening uses parallel "evening_*" keys). The other direction's data in
    `previous` is carried through untouched, so a single day record holds both.

    If previous data exists and this direction's cheapest price has changed, the
    old price is appended to that direction's history so the movement shows later.
    """
    if direction is None:
        trains_key, history_key, checked_key = "trains", "price_history", "checked_at"
    else:
        trains_key, history_key, checked_key = (
            direction.trains_key, direction.history_key, direction.checked_key)

    trains = [
        {"depart": o.depart, "price_pence": o.price_pence, "is_advance": o.is_advance}
        for o in options
    ]

    history = list(previous.get(history_key, [])) if previous else []

    if previous and options:
        prev_trains = previous.get(trains_key, [])
        if prev_trains:
            prev_cheapest = min(prev_trains, key=lambda t: t["price_pence"])["price_pence"]
            new_cheapest = min(options, key=lambda o: o.price_pence).price_pence
            if prev_cheapest != new_cheapest:
                history.append({
                    "checked_at": previous[checked_key],
                    "cheapest_pence": prev_cheapest,
                })

    # Start from the existing day so the opposite direction's keys are preserved.
    payload: dict = dict(previous) if previous else {}
    payload[checked_key] = checked_at
    payload[trains_key] = trains
    if history:
        payload[history_key] = history
    else:
        payload.pop(history_key, None)
    return payload


def lookup_day(client: TrainClient, cfg, date: dt.date, direction=None) -> list[TrainOption]:
    """Fetch the earliest TrainOptions for one date and direction (network).

    The journey-plan response carries no departure times — only journey refs and
    fares — so we fetch the detail (which has the times) for every journey it
    returns, sort by departure, then keep the earliest few. Selecting before we
    have times would slice the plan's own (non-temporal) order and miss early
    trains. A window returns only a handful of journeys. For the evening the
    plan's origin resolves to London Bridge, so the detail times are already the
    London Bridge departures.
    """
    direction = direction or morning_direction(cfg)
    start = f"{date.isoformat()}T{direction.window_start}:00"
    end = f"{date.isoformat()}T{direction.window_end}:00"
    plan = client.plan_day(direction.origin_nlc, direction.destination_nlc, start, end)
    if not plan:
        return []
    options = build_options(parse_plan(plan), fetch_detail=client.journey_detail)
    return earliest_n(options, cfg.show_count)


def _checked_today(prev: dict | None, direction, today: str) -> bool:
    """True if `prev` already holds this direction's trains, checked today.

    Only train-days are guarded: a no-train day clears its check marker, so it
    is never seen as "already done" and may still be re-checked.
    """
    if not prev or not prev.get(direction.trains_key):
        return False
    return (prev.get(direction.checked_key) or "")[:10] == today


def gather_week(client: TrainClient, cfg, dates, now: str, existing: dict,
                direction=None, on_day=None) -> WeekOutcome:
    """Look up, persist, and update the horizon for each date in a week.

    Operates on one `direction` (morning by default). Days with trains are
    saved under that direction's keys; days with none have only that direction
    cleared (the other direction's data is preserved) and feed the shared
    booking-horizon marker.

    A date whose trains were already fetched today (for this direction) is reused
    from the record without a network call — we never fetch the same thing twice
    in a day — and still reported to `on_day`. `on_day(date, options)` is called
    after each date, letting callers stream output or drive a progress bar.

    Returns a WeekOutcome(found, fetched). Shared by `search` and
    `refresh-price-data`.
    """
    direction = direction or morning_direction(cfg)
    today = now[:10]
    train_dates: list[str] = []
    no_train_dates: list[str] = []
    fetched = False
    for date in dates:
        ds = date.isoformat()
        prev = existing.get(ds)
        if _checked_today(prev, direction, today):
            # Already gathered today — reprint the saved trains, no network.
            options = options_from_record(prev[direction.trains_key])
            train_dates.append(ds)
        else:
            fetched = True
            options = lookup_day(client, cfg, date, direction)
            if options:
                save_day(cfg.storage_path, ds,
                         day_payload(options, now, prev, direction))
                train_dates.append(ds)
            else:
                clear_day_direction(cfg.storage_path, ds, direction,
                                    other_trains_key(direction))
                no_train_dates.append(ds)
        if on_day is not None:
            on_day(date, options)

    meta = updated_horizon(existing.get(META_KEY), train_dates, no_train_dates, now)
    write_meta(cfg.storage_path, meta)
    return WeekOutcome(found=bool(train_dates), fetched=fetched)


@click.command("search")
@click.argument("week_date")
@click.option("--days", help="Comma-separated day names, e.g. Tue,Wed,Thu")
@click.option("--evening", "evening", is_flag=True,
              help="Look up the evening return (London → home) instead of the morning.")
def search_command(week_date: str, days: str | None, evening: bool):
    """Show the cheapest trains for the week containing WEEK_DATE and save results.

    By default this is the morning trains to London; pass --evening for the
    evening return (London Terminals → home, timed at London Bridge).
    """
    cfg = load_config(CONFIG_FILE)
    direction = evening_direction(cfg) if evening else morning_direction(cfg)
    day_names = [d.strip() for d in days.split(",")] if days else cfg.travel_days
    client = TrainClient(pause_seconds=cfg.request_pause_seconds)
    now = dt.datetime.now().replace(microsecond=0).isoformat()
    existing = load_record(cfg.storage_path)

    click.echo(f"{direction.origin_name} → {direction.destination_name}, "
               f"{direction.window_start}–{direction.window_end}\n")
    try:
        dates = travel_dates(week_date, day_names)
    except ValueError as e:
        raise click.BadParameter(str(e))

    evening = direction.name == "evening"

    def show(date, options):
        heading = f"{WEEKDAY_FULL[date.weekday()]} {date.isoformat()}"
        click.echo(format_day(heading, options, evening))
        click.echo()

    gather_week(client, cfg, dates, now, existing, direction, on_day=show)
