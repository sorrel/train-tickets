"""
Train ticket API client.

Handles requests for journey and pricing data.
"""

import click
import requests


class TrainClient:
    """Client for fetching train pricing data."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "train-tickets-cli/0.1",
            "Accept": "application/json",
        })

    def search(self, origin: str, destination: str, date: str) -> dict | None:
        """
        Search for advance tickets between two stations on a given date.

        Returns parsed pricing data, or None on failure.
        """
        raise NotImplementedError("API backend not yet configured")

    def _request(self, method: str, url: str, **kwargs) -> dict | list | None:
        """Make a request and return parsed JSON, or None on failure."""
        try:
            resp = self.session.request(method, url, timeout=15, **kwargs)
        except requests.RequestException as e:
            click.echo(f"Request failed: {e}", err=True)
            return None

        if resp.status_code != 200:
            click.echo(f"API error {resp.status_code}: {resp.text[:200]}", err=True)
            return None

        return resp.json()
