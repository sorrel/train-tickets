"""Record command — search a week and save the results to the local price record."""

import datetime as dt

import click

from core.config import load_config
from core.client import TrainClient
from core.dates import travel_dates
from core.fares import TrainOption
from core.storage import save_day
from commands.search import lookup_day, format_day, CONFIG_FILE, _WEEKDAYS


def day_payload(options: list[TrainOption], checked_at: str) -> dict:
    """Build the JSON-serialisable record for one day."""
    return {
        "checked_at": checked_at,
        "trains": [
            {"depart": o.depart, "arrive": o.arrive,
             "price_pence": o.price_pence, "is_advance": o.is_advance}
            for o in options
        ],
    }


@click.command("record")
@click.argument("week_date")
@click.option("--days", help="Comma-separated day names, e.g. Tue,Wed,Thu")
def record_command(week_date: str, days: str | None):
    """Search the week containing WEEK_DATE and save results to the local record."""
    cfg = load_config(CONFIG_FILE)
    day_names = [d.strip() for d in days.split(",")] if days else cfg.travel_days
    client = TrainClient(pause_seconds=cfg.request_pause_seconds)
    now = dt.datetime.now().replace(microsecond=0).isoformat()

    try:
        dates = travel_dates(week_date, day_names)
    except ValueError as e:
        raise click.BadParameter(str(e))
    for date in dates:
        heading = f"{_WEEKDAYS[date.weekday()]} {date.isoformat()}"
        options = lookup_day(client, cfg, date)
        click.echo(format_day(heading, options))
        save_day(cfg.storage_path, date.isoformat(), day_payload(options, now))
        click.echo()
    click.echo(click.style(f"Saved to {cfg.storage_path}", fg="green"))
