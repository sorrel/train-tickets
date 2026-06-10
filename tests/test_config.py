from pathlib import Path

from core.config import load_config, JourneyConfig


def test_load_config_reads_committed_example():
    cfg = load_config(Path(__file__).parent.parent / "config.example.json")
    assert isinstance(cfg, JourneyConfig)
    assert cfg.origin_name == "Origin station"
    assert cfg.destination_name == "Destination station"
    assert cfg.travel_days == ["Tue", "Wed", "Thu"]
    assert cfg.show_count == 5
    assert cfg.window_start == "05:45"
    assert cfg.window_end == "08:00"


def test_evening_window_defaults_when_absent(tmp_path):
    # An existing config.local.json without evening fields must keep working.
    f = tmp_path / "c.local"
    f.write_text('{"origin_nlc":"1","origin_name":"A","destination_nlc":"2",'
                 '"destination_name":"B","travel_days":["Mon"],"window_start":"05:45",'
                 '"window_end":"08:00","show_count":5,'
                 '"storage_path":"~/x/prices.json","request_pause_seconds":1.0}')
    cfg = load_config(f)
    assert cfg.evening_window_start == "17:45"
    assert cfg.evening_window_end == "19:15"


def test_evening_window_read_from_config_when_present(tmp_path):
    f = tmp_path / "c.local"
    f.write_text('{"origin_nlc":"1","origin_name":"A","destination_nlc":"2",'
                 '"destination_name":"B","travel_days":["Mon"],"window_start":"05:45",'
                 '"window_end":"08:00","show_count":5,'
                 '"storage_path":"~/x/prices.json","request_pause_seconds":1.0,'
                 '"evening_window_start":"18:00","evening_window_end":"19:00"}')
    cfg = load_config(f)
    assert cfg.evening_window_start == "18:00"
    assert cfg.evening_window_end == "19:00"


def test_storage_path_is_expanded(tmp_path):
    f = tmp_path / "c.local"
    f.write_text('{"origin_nlc":"1","origin_name":"A","destination_nlc":"2",'
                 '"destination_name":"B","travel_days":["Mon"],"window_start":"05:45",'
                 '"window_end":"08:00","show_count":5,'
                 '"storage_path":"~/x/prices.json","request_pause_seconds":1.0}')
    cfg = load_config(f)
    assert not str(cfg.storage_path).startswith("~")
    assert str(cfg.storage_path).endswith("x/prices.json")
