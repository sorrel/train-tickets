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
    # Randomised pause between weeks during refresh-price-data, in seconds.
    # Kept deliberately slow and jittered so a long bulk run stays a polite
    # ordinary customer rather than a burst of traffic.
    refresh_pause_min_seconds: float = 5.0
    refresh_pause_max_seconds: float = 12.0
    # Evening direction (London → home). The route is the morning's stations
    # swapped; only the window differs. Defaulted so an existing config without
    # these fields keeps working — evening is opt-in via the --evening switch.
    evening_window_start: str = "17:45"
    evening_window_end: str = "19:15"


def load_config(path: Path) -> JourneyConfig:
    data = json.loads(Path(path).read_text())
    data["storage_path"] = Path(data["storage_path"]).expanduser()
    if "show_cheapest" in data:
        data["show_count"] = data.pop("show_cheapest")
    return JourneyConfig(**data)
