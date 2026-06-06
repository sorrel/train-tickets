from pathlib import Path

from core.config import load_config, JourneyConfig


def test_load_config_reads_committed_example():
    cfg = load_config(Path(__file__).parent.parent / "config.example.json")
    assert isinstance(cfg, JourneyConfig)
    assert cfg.origin_name == "Origin station"
    assert cfg.destination_name == "Destination station"
    assert cfg.travel_days == ["Tue", "Wed", "Thu"]
    assert cfg.show_cheapest == 4
    assert cfg.window_start == "06:00"
    assert cfg.window_end == "08:00"


def test_storage_path_is_expanded(tmp_path):
    f = tmp_path / "c.local"
    f.write_text('{"origin_nlc":"1","origin_name":"A","destination_nlc":"2",'
                 '"destination_name":"B","travel_days":["Mon"],"window_start":"06:00",'
                 '"window_end":"08:00","show_cheapest":4,'
                 '"storage_path":"~/x/prices.json","request_pause_seconds":1.0}')
    cfg = load_config(f)
    assert not str(cfg.storage_path).startswith("~")
    assert str(cfg.storage_path).endswith("x/prices.json")
