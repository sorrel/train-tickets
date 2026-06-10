from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from commands.setup import status_command


def _run_status(cfg):
    with patch("core.config.load_config", return_value=cfg):
        return CliRunner().invoke(status_command, [])


def test_status_shows_both_directions_and_windows():
    cfg = MagicMock()
    cfg.origin_name = "Tunbridge Wells"
    cfg.destination_name = "London Terminals"
    cfg.window_start, cfg.window_end = "05:55", "08:05"
    cfg.evening_window_start, cfg.evening_window_end = "17:45", "19:15"
    cfg.travel_days = ["Tue", "Wed", "Thu"]
    cfg.storage_path = "/tmp/prices.json"

    result = _run_status(cfg)
    assert result.exit_code == 0
    assert "Tunbridge Wells → London Terminals" in result.output     # morning
    assert "05:55–08:05" in result.output
    assert "London Terminals → Tunbridge Wells" in result.output     # evening (reversed)
    assert "17:45–19:15" in result.output
