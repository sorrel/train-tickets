"""HTTP client for the SouthEastern public booking API.

Polite by design: a configurable pause between requests and an in-memory token cache.
We are an ordinary customer — never burst. See the api-politeness memory.
"""

import datetime as dt
import re
import time

import click
import requests

API_BASE = "https://api.southeasternrailway.co.uk"
_TOKEN_PAGE_DATE = (dt.date.today() + dt.timedelta(days=30)).isoformat()
DEFAULT_TOKEN_PAGE = (
    "https://ticket.southeasternrailway.co.uk/journeys-grid/5230/1072/"
    f"{_TOKEN_PAGE_DATE}T05:45//1//NEWx1"
)
_TOKEN_RE = re.compile(r'"apiAccessToken":"([^"]+)"')


class TrainClient:
    def __init__(self, token_page: str = DEFAULT_TOKEN_PAGE, pause_seconds: float = 1.0):
        self.session = requests.Session()
        self.session.headers.update({"user-agent": "Mozilla/5.0"})
        self.token_page = token_page
        self.pause_seconds = pause_seconds
        self._token: str | None = None

    def get_token(self) -> str | None:
        """Scrape (and cache) the public access token from the booking page."""
        if self._token:
            return self._token
        resp = self.session.get(self.token_page, timeout=15)
        if resp.status_code != 200:
            click.echo(f"Could not load booking page (HTTP {resp.status_code}).", err=True)
            return None
        match = _TOKEN_RE.search(resp.text)
        if not match:
            click.echo("Could not find access token on booking page.", err=True)
            return None
        self._token = match.group(1)
        return self._token

    def _headers(self) -> dict:
        return {"accept": "application/json", "content-type": "application/json",
                "x-access-token": self._token, "user-agent": "Mozilla/5.0"}

    def _request(self, method: str, path: str, json_body: dict | None = None) -> dict | None:
        if not self.get_token():
            return None
        time.sleep(self.pause_seconds)   # polite spacing before every API call
        try:
            resp = self.session.request(method, f"{API_BASE}{path}",
                                        json=json_body, headers=self._headers(), timeout=30)
        except requests.RequestException as e:
            click.echo(f"Request failed: {e}", err=True)
            return None
        if resp.status_code in (401, 403):
            self._token = None   # token rotated — drop cache so next run rescrapes
            click.echo("Access token rejected; clearing cache.", err=True)
            return None
        if resp.status_code != 200:
            click.echo(f"API error {resp.status_code}: {resp.text[:200]}", err=True)
            return None
        return resp.json()

    def plan_day(self, origin: str, destination: str, range_start: str, range_end: str) -> dict | None:
        """POST a journey-plan request for a single morning window."""
        body = {
            "origin": origin, "destination": destination,
            "outward": {"rangeStart": range_start, "rangeEnd": range_end, "arriveDepart": "Depart"},
            "openReturn": False, "adults": 1, "children": 0,
            "disableGroupSavings": True, "numJourneys": 10, "showCheapest": True,
            "doRealTime": False, "keepAllZoneFares": False, "filterFares": True,
            "channel": "web",
        }
        return self._request("POST", "/jp/journey-plan", body)

    def journey_detail(self, journey_ref: str) -> dict | None:
        """GET the detail (times) for a journey. journey_ref is the url-encoded path."""
        return self._request("GET", journey_ref)
