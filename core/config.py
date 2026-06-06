"""Load the committed journey configuration (.local file).

The .local file holds no private data — station codes, travel days, time window.
The only machine-local thing is the storage path, which points outside the repo.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class JourneyConfig:
    origin_nlc: str
    origin_name: str
    destination_nlc: str
    destination_name: str
    travel_days: list[str]
    window_start: str
    window_end: str
    show_count: int
    storage_path: Path
    request_pause_seconds: float


def load_config(path: Path) -> JourneyConfig:
    data = json.loads(Path(path).read_text())
    data["storage_path"] = Path(data["storage_path"]).expanduser()
    if "show_cheapest" in data:
        data["show_count"] = data.pop("show_cheapest")
    return JourneyConfig(**data)
