"""View command — display saved price records grouped by week."""

import datetime as dt

import click

from core.config import load_config
from core.dates import WEEKDAY_ABBR, MONTH_ABBR
from core.fares import effective_pence, shows_railcard, RAILCARD_LABEL
from core.storage import load_record, META_KEY
from commands.search import CONFIG_FILE

# How many trains are shown (and considered for the cheap markers) per day.
_TRAINS_PER_DAY = 2

# The two directions a day can hold, in display order. Each is (trains key,
# price-history key, label). The morning keys are the original record keys, so a
# day with only morning data renders exactly as it always has.
_DIRECTIONS = [
    ("trains", "price_history", "Morning"),
    ("evening_trains", "evening_price_history", "Evening"),
]


def cheapest_trains(trains: list[dict], n: int = _TRAINS_PER_DAY) -> list[dict]:
    """The n cheapest trains for a day, cheapest first."""
    return sorted(trains, key=lambda t: t["price_pence"])[:n]


def _fmt_short(d: dt.date) -> str:
    return f"{d.day:02d} {MONTH_ABBR[d.month - 1]}"


def _week_monday(date_str: str) -> dt.date:
    d = dt.date.fromisoformat(date_str)
    return d - dt.timedelta(days=d.weekday())


def _fmt_checked(checked_at: str) -> str:
    d = dt.date.fromisoformat(checked_at[:10])
    return f"{d.day:02d} {MONTH_ABBR[d.month - 1]} {d.year}"


def _fmt_full(d: dt.date) -> str:
    return f"{WEEKDAY_ABBR[d.weekday()]} {_fmt_short(d)} {d.year}"


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
        # A legacy empty day has no trains in *either* direction; an evening-only
        # day is not empty. Use whichever direction's check time is present.
        if not (day.get("trains") or day.get("evening_trains")):
            checked = day.get("checked_at") or day.get("evening_checked_at")
            if checked:
                candidates.append((date_str, checked))
    if not candidates:
        return None
    from_date, checked = min(candidates, key=lambda c: c[0])
    date = dt.date.fromisoformat(from_date)
    return click.style(
        f"No trains on sale from {_fmt_full(date)} onwards yet "
        f"(checked {_fmt_checked(checked)}).",
        fg="bright_black",
    )


def _price_change_suffix(day_data: dict, current_pence: int,
                         history_key: str = "price_history") -> str:
    """Return a coloured suffix showing price movement, or '' if no history."""
    history = day_data.get(history_key)
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


def _train_line(train: dict, change: str, date: dt.date, today: dt.date,
                indent: int = 4, evening: bool = False) -> str:
    """Render one train as an indented line (departure, price, fare type).

    An evening fare dearer than the £14.10 Network Railcard single is shown as
    the railcard instead — you'd buy that on the day rather than the advance.
    """
    if shows_railcard(train["price_pence"], evening):
        plain = f"{' ' * indent}{train['depart']}   {RAILCARD_LABEL}"
    else:
        price_col = f"£{train['price_pence'] / 100:>6.2f}"
        kind_col = "Advance" if train["is_advance"] else "Anytime"
        plain = f"{' ' * indent}{train['depart']}   {price_col}   {kind_col}"
    return _date_colour(plain, date, today) + change


def _render_direction(day_data: dict, date: dt.date, today: dt.date, spec: tuple,
                      global_cheapest: int | None, flag_cheapest: bool,
                      week_min: int | None, week_has_dearer: bool,
                      indent: int) -> list[str]:
    """Render one direction's trains for a day, with the cheap markers applied.

    Markers are scoped to this direction: morning and evening fares are never
    compared (they are different journeys), so each side carries its own global
    cheapest and per-week low.
    """
    trains_key, history_key, _label = spec
    evening = trains_key == "evening_trains"
    lines = []
    for i, train in enumerate(cheapest_trains(day_data[trains_key])):
        railcard = shows_railcard(train["price_pence"], evening)
        # Price history tracks the day's cheapest, so the movement marker
        # belongs on the cheapest train (the first line). A railcard line is
        # pinned at £14.10, so its raw movement isn't shown.
        change = (_price_change_suffix(day_data, train["price_pence"], history_key)
                  if i == 0 and not railcard else "")
        line = _train_line(train, change, date, today, indent, evening)
        # Markers compare the effective price, so capped evening fares (all
        # shown as £14.10) sort together rather than on a hidden raw fare.
        price = effective_pence(train["price_pence"], evening)
        if flag_cheapest and price == global_cheapest:
            line += click.style("  ← cheapest", fg="green", bold=True)
        elif week_has_dearer and price == week_min:
            line += click.style("  ← cheaper", fg="yellow", bold=True)
        lines.append(line)
    return lines


def render_week(monday: dt.date, date_strs: list[str], record: dict, today: dt.date,
                cheapest_price: int | None = None, flag_cheapest: bool = False,
                evening_cheapest: int | None = None, evening_flag: bool = False) -> list[str]:
    """Return display lines for one week (pure — no I/O, easy to test).

    Each day shows its two cheapest trains per direction (cheapest first),
    labelled by departure time. A day that also holds evening trains is split
    into labelled "Morning" / "Evening" sub-sections; a day with only morning
    trains renders flat, exactly as before evening existed.

    Two highlights, computed independently for each direction:
    - "← cheapest" (green) — the cheapest fare across the *whole* view for that
      direction (`cheapest_price` / `evening_cheapest`), flagged when the
      matching flag is set.
    - "← cheaper" (yellow) — the cheapest fare within *this week* for that
      direction, flagged when the week has a dearer train. A train that is the
      global cheapest takes the green label, so yellow only ever marks a week
      whose own low sits above the global low.
    """
    lines = []

    present = [d for d in date_strs if d in record]
    checked_dates = [record[d]["checked_at"][:10] for d in present if "checked_at" in record[d]]
    uniform_check = len(set(checked_dates)) == 1 if checked_dates else False

    week_header = f"Week of Mon {_fmt_short(monday)} {monday.year}"
    if uniform_check:
        week_header += click.style(
            f"   (checked {_fmt_checked(record[present[0]]['checked_at'])})",
            fg="bright_black",
        )
    lines.append(click.style(week_header, fg="cyan", bold=True))

    # Per-direction global markers and per-week low. The week low and whether a
    # dearer train sits beside it are the basis for the "← cheaper" (yellow) flag.
    params = {}
    for spec, gc, fc in (
        (_DIRECTIONS[0], cheapest_price, flag_cheapest),
        (_DIRECTIONS[1], evening_cheapest, evening_flag),
    ):
        wp = displayed_prices(record, date_strs, spec[0])
        wmin = min(wp) if wp else None
        params[spec[0]] = (gc, fc, wmin, bool(wp) and max(wp) > wmin)

    for date_str in date_strs:
        date = dt.date.fromisoformat(date_str)
        day_name = WEEKDAY_ABBR[date.weekday()]

        if date_str not in record:
            lines.append(f"  {day_name} {_fmt_short(date)}   (no data)")
            continue

        day_data = record[date_str]

        per_day_check = (
            click.style(f"   checked {_fmt_checked(day_data['checked_at'])}", fg="bright_black")
            if not uniform_check and "checked_at" in day_data else ""
        )
        header = _date_colour(f"  {day_name} {_fmt_short(date)}", date, today)
        lines.append(header + per_day_check)

        present_dirs = [s for s in _DIRECTIONS if day_data.get(s[0])]
        if not present_dirs:
            lines.append(_date_colour("    (no trains)", date, today))
            continue

        # Label the sections only once the evening direction is in play; a
        # morning-only day stays flat (4-space indent, no heading) as before.
        labelled = bool(day_data.get("evening_trains"))
        for spec in present_dirs:
            gc, fc, wmin, wdear = params[spec[0]]
            if labelled:
                lines.append(_date_colour(f"    {spec[2]}", date, today))
            lines.extend(_render_direction(
                day_data, date, today, spec, gc, fc, wmin, wdear,
                indent=6 if labelled else 4))

    return lines


def displayed_prices(record: dict, date_strs: list[str], trains_key: str = "trains") -> list[int]:
    """The prices actually shown (cheapest two per day) for the given dates.

    `trains_key` selects the direction ("trains" or "evening_trains"). Evening
    fares are returned at their effective price (capped at the £14.10 railcard),
    matching what is displayed, so the cheap markers compare like with like.
    """
    evening = trains_key == "evening_trains"
    return [
        effective_pence(t["price_pence"], evening)
        for d in date_strs
        if d in record and record[d].get(trains_key)
        for t in cheapest_trains(record[d][trains_key])
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
        day = record[date_str]
        if not (day.get("trains") or day.get("evening_trains")):
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

    # Cheapest fare across everything on show, computed per direction so the same
    # low is flagged wherever it appears — and so morning and evening (different
    # journeys) are never compared against each other.
    shown_dates = [d for date_strs in weeks.values() for d in date_strs]
    m_prices = displayed_prices(record, shown_dates, "trains")
    e_prices = displayed_prices(record, shown_dates, "evening_trains")
    m_cheapest = min(m_prices) if m_prices else None
    m_flag = bool(m_prices) and max(m_prices) > m_cheapest
    e_cheapest = min(e_prices) if e_prices else None
    e_flag = bool(e_prices) and max(e_prices) > e_cheapest

    # The evening route is the morning's stations reversed. Only label the
    # directions once evening data is actually on show, so a morning-only view
    # keeps its single, unadorned route line.
    if e_prices:
        click.echo(f"{cfg.origin_name} → {cfg.destination_name}  (morning)")
        click.echo(f"{cfg.destination_name} → {cfg.origin_name}  (evening)\n")
    else:
        click.echo(f"{cfg.origin_name} → {cfg.destination_name}\n")

    for monday, date_strs in sorted(weeks.items()):
        for line in render_week(monday, date_strs, record, today,
                                m_cheapest, m_flag, e_cheapest, e_flag):
            click.echo(line)
        click.echo()

    if note:
        click.echo(note)
