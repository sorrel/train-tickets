"""refresh-price-data — walk forward week by week, gathering fares until none remain.

Deliberately slow and careful: a randomised pause between weeks keeps us a
polite ordinary customer over a long run. Data is saved as each day is fetched,
so `view` in another terminal shows progress while this is still going. The long
command name is intentional — this is a once-in-a-while bulk job, not a habit.
"""

import datetime as dt
import random
import time

import click

from core.config import load_config
from core.client import TrainClient
from core.dates import travel_dates
from core.storage import load_record
from commands.search import gather_week, CONFIG_FILE

# Advance fares are typically on sale ~12 weeks ahead; a little headroom keeps
# the progress bar sensible. It is only an estimate — the run stops when a week
# returns no trains, however many weeks that takes.
_ESTIMATED_WEEKS = 14


@click.command("refresh-price-data")
def refresh_price_data_command():
    """Refresh fares for every week from tomorrow until no trains are returned.

    Slow by design — set it going and check back later (or watch `view` in
    another terminal). A randomised pause spaces out each week's requests.
    """
    cfg = load_config(CONFIG_FILE)
    client = TrainClient(pause_seconds=cfg.request_pause_seconds)

    start = dt.date.today() + dt.timedelta(days=1)
    click.echo(f"{cfg.origin_name} → {cfg.destination_name}")
    click.echo(f"Refreshing from {start.isoformat()} onwards, "
               f"week by week, until no trains are returned.\n")

    week_date = start
    weeks_done = 0
    with click.progressbar(length=_ESTIMATED_WEEKS, label="Refreshing prices",
                           item_show_func=lambda s: s or "") as bar:
        while True:
            now = dt.datetime.now().replace(microsecond=0).isoformat()
            existing = load_record(cfg.storage_path)
            # Only days from tomorrow onwards (the first week may be partly past).
            week_days = travel_dates(week_date.isoformat(), cfg.travel_days)
            dates = [d for d in week_days if d >= start]
            label = f"week of {week_date.isoformat()}"

            if not dates:
                week_date += dt.timedelta(days=7)
                continue

            found = gather_week(client, cfg, dates, now, existing)

            # Advance the bar by a week, but hold short of full until we stop,
            # so a finished run reads as 100% rather than overflowing the guess.
            step = 1 if weeks_done < _ESTIMATED_WEEKS - 1 else 0
            bar.update(step, current_item=label)
            weeks_done += 1

            if not found:
                bar.update(_ESTIMATED_WEEKS - bar.pos, current_item="done")
                break

            # Randomised, polite pause between weeks — never a burst.
            time.sleep(random.uniform(cfg.refresh_pause_min_seconds,
                                      cfg.refresh_pause_max_seconds))
            week_date += dt.timedelta(days=7)

    click.echo(f"\nDone. Walked {weeks_done} week(s) from {start.isoformat()}; "
               f"stopped when no trains were returned.")
