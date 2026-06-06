"""Local price record — a JSON file in the user's home dir, outside the repo.

Keyed by ISO date string. Designed to expand freely over the years: add fields to
a day's dict without migrations. One reserved non-date key, "meta", holds the
booking-horizon marker (see updated_horizon).
"""

import json
from pathlib import Path

META_KEY = "meta"


def load_record(path: Path) -> dict:
    """Return the whole record, or {} if the file does not exist yet."""
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _write(path: Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True))


def save_day(path: Path, date_str: str, day_data: dict) -> None:
    """Merge one day's data into the record, creating the file/parent if needed."""
    record = load_record(path)
    record[date_str] = day_data
    _write(path, record)


def remove_day(path: Path, date_str: str) -> None:
    """Drop a day from the record if present (e.g. a date with no trains)."""
    record = load_record(path)
    if record.pop(date_str, None) is not None:
        _write(path, record)


def write_meta(path: Path, meta: dict | None) -> None:
    """Set (or clear, when None) the reserved meta entry in the record."""
    record = load_record(path)
    if meta is None:
        record.pop(META_KEY, None)
    else:
        record[META_KEY] = meta
    _write(path, record)


def updated_horizon(current: dict | None, train_dates: list[str],
                    no_train_dates: list[str], checked_at: str) -> dict | None:
    """Recompute the booking-horizon marker after a search run (pure).

    The horizon is the earliest date for which a search returned no trains —
    i.e. the point beyond which advance fares are not yet on sale. We keep the
    earliest such date known, dropping it once trains appear at or after it.

    `current` is the existing {"no_trains_from", "checked_at"} marker or None.
    `train_dates` / `no_train_dates` are ISO date strings seen this run. Returns
    the new marker, or None when no horizon is known. The checked_at date is
    kept from `current` while the horizon is unchanged, so it records when the
    horizon was first discovered, not every re-check.
    """
    horizon = current["no_trains_from"] if current else None
    # Trains now exist at or after the old horizon → it has moved on.
    if horizon and any(d >= horizon for d in train_dates):
        horizon = None
    run_min = min(no_train_dates) if no_train_dates else None
    candidates = [d for d in (horizon, run_min) if d]
    if not candidates:
        return None
    new_horizon = min(candidates)
    if current and current.get("no_trains_from") == new_horizon:
        return {"no_trains_from": new_horizon, "checked_at": current["checked_at"]}
    return {"no_trains_from": new_horizon, "checked_at": checked_at}
