"""Week and travel-day calculations.

Weeks run Monday to Sunday. Any date belongs to exactly one week.
"""

import datetime as dt

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Accepted date formats, tried in order. Ambiguous numeric formats are day-first
# (British), so 08/06/2026 means 8 June, not 6 August. ISO is tried first because
# its 4-digit-year-first shape is unambiguous.
_DATE_FORMATS = [
    "%Y-%m-%d",   # 2026-06-08 (ISO)
    "%d/%m/%Y",   # 08/06/2026
    "%d/%m/%y",   # 08/06/26
    "%d-%m-%Y",   # 08-06-2026
    "%d.%m.%Y",   # 08.06.2026
    "%d %B %Y",   # 8 June 2026
    "%d %b %Y",   # 8 Jun 2026
]


def parse_date(date_str: str) -> dt.date:
    """Parse a date string in any of several common formats (day-first for
    ambiguous numeric forms). Raises ValueError with a clear message if none match.
    """
    text = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Unrecognised date '{date_str}'. Try YYYY-MM-DD or DD/MM/YYYY."
    )


def week_of(date_str: str) -> tuple[dt.date, dt.date]:
    """Return (Monday, Sunday) of the week containing the given date."""
    d = parse_date(date_str)
    monday = d - dt.timedelta(days=d.weekday())
    return monday, monday + dt.timedelta(days=6)


def travel_dates(date_str: str, days: list[str] | None = None) -> list[dt.date]:
    """Return the dates in the week matching the named days (default Tue/Wed/Thu)."""
    if days is None:
        days = ["Tue", "Wed", "Thu"]
    for name in days:
        if name not in _DAYS:
            raise ValueError(f"Unknown day '{name}'. Use one of: {', '.join(_DAYS)}.")
    monday, _ = week_of(date_str)
    wanted = sorted(_DAYS.index(name) for name in days)
    return [monday + dt.timedelta(days=offset) for offset in wanted]
