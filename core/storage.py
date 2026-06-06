"""Local price record — a JSON file in the user's home dir, outside the repo.

Keyed by ISO date string. Designed to expand freely over the years: add fields to
a day's dict without migrations.
"""

import json
from pathlib import Path


def load_record(path: Path) -> dict:
    """Return the whole record, or {} if the file does not exist yet."""
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_day(path: Path, date_str: str, day_data: dict) -> None:
    """Merge one day's data into the record, creating the file/parent if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = load_record(path)
    record[date_str] = day_data
    path.write_text(json.dumps(record, indent=2, sort_keys=True))
