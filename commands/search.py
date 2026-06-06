"""Search command — four cheapest morning trains per travel day, in time order.

Results are saved after every lookup. When the cheapest price changes from the
previous lookup the old price is appended to price_history on that day's record.
"""

import datetime as dt
from pathlib import Path

import click

from core.config import load_config
from core.client import TrainClient
from core.dates import travel_dates
from core.fares import parse_plan, cheapest_n, build_options, TrainOption
from core.storage import load_record, save_day

CONFIG_FILE = Path(__file__).parent.parent / "config.local.json"
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def format_day(heading: str, options: list[TrainOption]) -> str:
    """Render one day's trains as a text block (pure — easy to test)."""
    lines = [click.style(heading, fg="cyan", bold=True)]
    if not options:
        lines.append("  (no trains found in the window)")
        return "\n".join(lines)
    for o in options:
        kind = "Advance" if o.is_advance else "Anytime"
        price = f"£{o.price_pence / 100:.2f}"
        lines.append(f"  {o.depart} → {o.arrive}   {price:>8}   {kind}")
    return "\n".join(lines)


def day_payload(options: list[TrainOption], checked_at: str,
                previous: dict | None = None) -> dict:
    """Build the JSON-serialisable record for one day.

    If previous data exists and the cheapest price has changed, the old price
    is appended to price_history so the movement can be displayed later.
    """
    trains = [
        {"depart": o.depart, "arrive": o.arrive,
         "price_pence": o.price_pence, "is_advance": o.is_advance}
        for o in options
    ]

    history = list(previous.get("price_history", [])) if previous else []

    if previous and options:
        prev_trains = previous.get("trains", [])
        if prev_trains:
            prev_cheapest = min(prev_trains, key=lambda t: t["price_pence"])["price_pence"]
            new_cheapest = min(options, key=lambda o: o.price_pence).price_pence
            if prev_cheapest != new_cheapest:
                history.append({
                    "checked_at": previous["checked_at"],
                    "cheapest_pence": prev_cheapest,
                })

    payload: dict = {"checked_at": checked_at, "trains": trains}
    if history:
        payload["price_history"] = history
    return payload


def lookup_day(client: TrainClient, cfg, date: dt.date) -> list[TrainOption]:
    """Fetch and build the cheapest TrainOptions for one date (network)."""
    start = f"{date.isoformat()}T{cfg.window_start}:00"
    end = f"{date.isoformat()}T{cfg.window_end}:00"
    plan = client.plan_day(cfg.origin_nlc, cfg.destination_nlc, start, end)
    if not plan:
        return []
    chosen = cheapest_n(parse_plan(plan), cfg.show_cheapest)
    return build_options(chosen, fetch_detail=client.journey_detail)


@click.command("search")
@click.argument("week_date")
@click.option("--days", help="Comma-separated day names, e.g. Tue,Wed,Thu")
def search_command(week_date: str, days: str | None):
    """Show the cheapest morning trains for the week containing WEEK_DATE and save results."""
    cfg = load_config(CONFIG_FILE)
    day_names = [d.strip() for d in days.split(",")] if days else cfg.travel_days
    client = TrainClient(pause_seconds=cfg.request_pause_seconds)
    now = dt.datetime.now().replace(microsecond=0).isoformat()
    existing = load_record(cfg.storage_path)

    click.echo(f"{cfg.origin_name} → {cfg.destination_name}, "
               f"{cfg.window_start}–{cfg.window_end}\n")
    try:
        dates = travel_dates(week_date, day_names)
    except ValueError as e:
        raise click.BadParameter(str(e))
    for date in dates:
        heading = f"{_WEEKDAYS[date.weekday()]} {date.isoformat()}"
        options = lookup_day(client, cfg, date)
        click.echo(format_day(heading, options))
        previous = existing.get(date.isoformat())
        save_day(cfg.storage_path, date.isoformat(), day_payload(options, now, previous))
        click.echo()
