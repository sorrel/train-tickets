#!/usr/bin/env python3
"""
Train Tickets CLI
Look up UK train advance ticket prices.
"""

import click

from commands.setup import ColouredGroup, status_command
from commands.search import search_command
from commands.view import view_command
from commands.refresh import refresh_price_data_command


@click.group(cls=ColouredGroup)
def cli():
    """Train Tickets — look up UK advance train prices."""
    pass


cli.add_command(status_command)
cli.add_command(search_command)
cli.add_command(view_command)
cli.add_command(refresh_price_data_command)


if __name__ == "__main__":
    cli()
