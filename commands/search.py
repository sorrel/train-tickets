"""Search command — four cheapest morning trains per travel day, in time order."""

import datetime as dt
from pathlib import Path

import click

from core.config import load_config
from core.client import TrainClient
from core.dates import travel_dates
from core.fares import parse_plan, cheapest_n, build_options, TrainOption

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
    """Show the four cheapest morning trains for the week containing WEEK_DATE."""
    cfg = load_config(CONFIG_FILE)
    day_names = [d.strip() for d in days.split(",")] if days else cfg.travel_days
    client = TrainClient(pause_seconds=cfg.request_pause_seconds)

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
        click.echo()
