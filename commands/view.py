"""View command — display saved price records grouped by week."""

import datetime as dt

import click

from core.config import load_config
from core.storage import load_record
from commands.search import CONFIG_FILE

_SHORT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_short(d: dt.date) -> str:
    return f"{d.day:02d} {_SHORT_MONTHS[d.month - 1]}"


def _week_monday(date_str: str) -> dt.date:
    d = dt.date.fromisoformat(date_str)
    return d - dt.timedelta(days=d.weekday())


def _fmt_checked(checked_at: str) -> str:
    d = dt.date.fromisoformat(checked_at[:10])
    return f"{d.day:02d} {_SHORT_MONTHS[d.month - 1]} {d.year}"


def _price_change_suffix(day_data: dict, current_pence: int) -> str:
    """Return a coloured suffix showing price movement, or '' if no history."""
    history = day_data.get("price_history")
    if not history:
        return ""
    prev = history[-1]
    prev_pence = prev["cheapest_pence"]
    diff = current_pence - prev_pence
    since = _fmt_short(dt.date.fromisoformat(prev["checked_at"][:10]))
    if diff > 0:
        return click.style(f"  ↑£{diff / 100:.2f} since {since}", fg="red")
    return click.style(f"  ↓£{abs(diff) / 100:.2f} since {since}", fg="green")


def render_week(monday: dt.date, date_strs: list[str], record: dict, today: dt.date) -> list[str]:
    """Return display lines for one week (pure — no I/O, easy to test)."""
    lines = []

    present = [d for d in date_strs if d in record]
    checked_dates = [record[d]["checked_at"][:10] for d in present]
    uniform_check = len(set(checked_dates)) == 1 if checked_dates else False

    week_header = f"Week of Mon {_fmt_short(monday)} {monday.year}"
    if uniform_check:
        week_header += click.style(
            f"   (checked {_fmt_checked(record[present[0]]['checked_at'])})",
            fg="bright_black",
        )
    lines.append(click.style(week_header, fg="cyan", bold=True))

    for date_str in date_strs:
        date = dt.date.fromisoformat(date_str)
        day_name = _SHORT_DAYS[date.weekday()]

        if date_str not in record:
            lines.append(f"  {day_name} {_fmt_short(date)}   (no data)")
            continue

        day_data = record[date_str]
        trains = day_data["trains"]
        best = min(trains, key=lambda t: t["price_pence"]) if trains else None

        if best:
            price_col = f"£{best['price_pence'] / 100:>6.2f}"
            kind_col = "Advance" if best["is_advance"] else "Anytime"
            change = _price_change_suffix(day_data, best["price_pence"])
        else:
            price_col = " (no trains)"
            kind_col = ""
            change = ""

        per_day_check = (
            click.style(f"   checked {_fmt_checked(day_data['checked_at'])}", fg="bright_black")
            if not uniform_check else ""
        )

        body = f"  {day_name} {_fmt_short(date)}   {price_col}   {kind_col}"
        if date < today:
            body = click.style(body, fg="bright_black")
        elif date == today:
            body = click.style(body, fg="yellow")

        lines.append(body + per_day_check + change)

    return lines


@click.command("view")
def view_command():
    """Display saved price records grouped by week."""
    cfg = load_config(CONFIG_FILE)
    record = load_record(cfg.storage_path)

    if not record:
        click.echo("No price data saved yet. Use `search` to look up prices.")
        return

    today = dt.date.today()

    weeks: dict[dt.date, list[str]] = {}
    for date_str in sorted(record.keys()):
        monday = _week_monday(date_str)
        weeks.setdefault(monday, []).append(date_str)

    click.echo(f"{cfg.origin_name} → {cfg.destination_name}\n")

    for monday, date_strs in sorted(weeks.items()):
        for line in render_week(monday, date_strs, record, today):
            click.echo(line)
        click.echo()
