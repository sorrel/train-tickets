"""
Basic structural tests — verify modules import and CLI registers correctly.
No live API calls.
"""

import importlib


def test_cli_imports():
    module = importlib.import_module("tickets")
    assert hasattr(module, "cli")


def test_commands_importable():
    importlib.import_module("commands.setup")
    importlib.import_module("commands.search")


def test_client_importable():
    importlib.import_module("core.client")


def test_search_command_registered():
    from tickets import cli
    assert "search" in cli.commands


def test_status_command_registered():
    from tickets import cli
    assert "status" in cli.commands


def test_view_command_registered():
    from tickets import cli
    assert "view" in cli.commands


def test_refresh_command_registered():
    from tickets import cli
    assert "refresh-price-data" in cli.commands
