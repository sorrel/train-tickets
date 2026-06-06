"""View command — display saved price records grouped by week."""

import datetime as dt

import click

from core.config import load_config
from core.storage import load_record, META_KEY
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


def _fmt_full(d: dt.date) -> str:
    return f"{_SHORT_DAYS[d.weekday()]} {_fmt_short(d)} {d.year}"


def horizon_note(record: dict) -> str | None:
    """A note for the booking horizon — the earliest date with no trains found.

    Drawn from the stored meta marker and from any legacy empty-train days still
    in the record, whichever is earliest. Returns None when no horizon is known.
    """
    candidates: list[tuple[str, str]] = []
    meta = record.get(META_KEY)
    if meta and meta.get("no_trains_from"):
        candidates.append((meta["no_trains_from"], meta["checked_at"]))
    for date_str, day in record.items():
        if date_str == META_KEY:
            continue
        if not day.get("trains"):
            candidates.append((date_str, day["checked_at"]))
    if not candidates:
        return None
    from_date, checked = min(candidates, key=lambda c: c[0])
    date = dt.date.fromisoformat(from_date)
    return click.style(
        f"No trains on sale from {_fmt_full(date)} onwards yet "
        f"(checked {_fmt_checked(checked)}).",
        fg="bright_black",
    )


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


def _date_colour(text: str, date: dt.date, today: dt.date) -> str:
    """Dim past dates, highlight today, leave future dates plain."""
    if date < today:
        return click.style(text, fg="bright_black")
    if date == today:
        return click.style(text, fg="yellow")
    return text


def _train_line(train: dict, change: str, date: dt.date, today: dt.date) -> str:
    """Render one train as an indented line (departure, price, fare type)."""
    price_col = f"£{train['price_pence'] / 100:>6.2f}"
    kind_col = "Advance" if train["is_advance"] else "Anytime"
    plain = f"    {train['depart']}   {price_col}   {kind_col}"
    return _date_colour(plain, date, today) + change


def render_week(monday: dt.date, date_strs: list[str], record: dict, today: dt.date,
                cheapest_price: int | None = None, flag_cheapest: bool = False) -> list[str]:
    """Return display lines for one week (pure — no I/O, easy to test).

    Each day shows its two cheapest trains (cheapest first), labelled by
    departure time so it is clear which train each price belongs to.

    Two highlights:
    - "← cheapest" (green) — the cheapest fare across the *whole* view
      (`cheapest_price`), flagged when `flag_cheapest` is set.
    - "← cheaper" (yellow) — the cheapest fare within *this week*, flagged when
      the week has a dearer train. A train that is the global cheapest takes
      the green label, so yellow only ever marks a week whose own low sits
      above the global low.
    """
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

    # Cheapest fare shown this week, and whether a dearer train sits alongside
    # it — the basis for the per-week "← cheaper" (yellow) flag.
    week_prices = displayed_prices(record, date_strs)
    week_min = min(week_prices) if week_prices else None
    week_has_dearer = bool(week_prices) and max(week_prices) > week_min

    for date_str in date_strs:
        date = dt.date.fromisoformat(date_str)
        day_name = _SHORT_DAYS[date.weekday()]

        if date_str not in record:
            lines.append(f"  {day_name} {_fmt_short(date)}   (no data)")
            continue

        day_data = record[date_str]
        trains = day_data["trains"]

        per_day_check = (
            click.style(f"   checked {_fmt_checked(day_data['checked_at'])}", fg="bright_black")
            if not uniform_check else ""
        )
        header = _date_colour(f"  {day_name} {_fmt_short(date)}", date, today)
        lines.append(header + per_day_check)

        if not trains:
            lines.append(_date_colour("    (no trains)", date, today))
            continue

        cheapest = sorted(trains, key=lambda t: t["price_pence"])[:2]
        for i, train in enumerate(cheapest):
            # Price history tracks the day's cheapest, so the movement marker
            # belongs on the cheapest train (the first line).
            change = _price_change_suffix(day_data, train["price_pence"]) if i == 0 else ""
            line = _train_line(train, change, date, today)
            price = train["price_pence"]
            if flag_cheapest and price == cheapest_price:
                line += click.style("  ← cheapest", fg="green", bold=True)
            elif week_has_dearer and price == week_min:
                line += click.style("  ← cheaper", fg="yellow", bold=True)
            lines.append(line)

    return lines


def displayed_prices(record: dict, date_strs: list[str]) -> list[int]:
    """The prices actually shown (cheapest two per day) for the given dates."""
    return [
        t["price_pence"]
        for d in date_strs
        if d in record and record[d]["trains"]
        for t in sorted(record[d]["trains"], key=lambda t: t["price_pence"])[:2]
    ]


@click.command("view")
@click.option("--all", "-a", "show_all", is_flag=True,
              help="Show past and today's dates too (default: future only).")
def view_command(show_all: bool):
    """Display saved price records grouped by week (future dates by default)."""
    cfg = load_config(CONFIG_FILE)
    record = load_record(cfg.storage_path)

    if not record:
        click.echo("No price data saved yet. Use `search` to look up prices.")
        return

    today = dt.date.today()
    note = horizon_note(record)

    weeks: dict[dt.date, list[str]] = {}
    for date_str in sorted(record.keys()):
        if date_str == META_KEY:
            continue
        if not record[date_str].get("trains"):
            continue  # no-train days aren't shown — they're covered by the note
        if not show_all and dt.date.fromisoformat(date_str) <= today:
            continue
        monday = _week_monday(date_str)
        weeks.setdefault(monday, []).append(date_str)

    if not weeks:
        if note:
            click.echo(f"{cfg.origin_name} → {cfg.destination_name}\n")
            click.echo(note)
        else:
            click.echo("No future dates recorded. Use --all to see past dates.")
        return

    # Cheapest fare across everything on show, so the same low price is flagged
    # wherever it appears — even in a week that is uniformly priced at that low.
    shown_dates = [d for date_strs in weeks.values() for d in date_strs]
    prices = displayed_prices(record, shown_dates)
    cheapest_price = min(prices) if prices else None
    flag_cheapest = bool(prices) and max(prices) > cheapest_price

    click.echo(f"{cfg.origin_name} → {cfg.destination_name}\n")

    for monday, date_strs in sorted(weeks.items()):
        for line in render_week(monday, date_strs, record, today,
                                cheapest_price, flag_cheapest):
            click.echo(line)
        click.echo()

    if note:
        click.echo(note)
