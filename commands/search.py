"""
Search command — find advance train ticket prices.
"""

import click

from core.client import TrainClient


@click.command("search")
@click.argument("origin")
@click.argument("destination")
@click.argument("date", metavar="DATE (YYYY-MM-DD)")
def search_command(origin: str, destination: str, date: str):
    """Search for advance tickets between two stations on a date."""
    client = TrainClient()

    click.echo(f"Searching {origin} → {destination} on {date}…")
    results = client.search(origin, destination, date)

    if results is None:
        click.echo(click.style("No results.", fg="yellow"))
        return

    # TODO: display results
    click.echo(results)
