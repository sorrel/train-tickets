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

# Transient server-side statuses worth one polite retry. SouthEastern's backend
# occasionally returns a 500 "InternalError"; the same request usually then works.
_RETRY_STATUSES = (500, 502, 503, 504)


class TrainApiError(Exception):
    """A genuine lookup failure (server error or transport fault).

    Distinct from a legitimate empty result or the expected beyond-horizon 422,
    both of which return None. Callers use this to tell "the lookup failed" apart
    from "there are simply no trains", so a server hiccup never masquerades as an
    empty day.
    """


class TrainClient:
    def __init__(self, token_page: str = DEFAULT_TOKEN_PAGE, pause_seconds: float = 1.0):
        self.session = requests.Session()
        self.session.headers.update({"user-agent": "Mozilla/5.0"})
        self.token_page = token_page
        self.pause_seconds = pause_seconds
        self._token: str | None = None

    def get_token(self) -> str:
        """Scrape (and cache) the public access token from the booking page.

        Raises TrainApiError if the token cannot be obtained — by transport fault,
        an unhappy booking page, or a page with no token in it. Without a token no
        lookup is possible at all, so this must never be mistaken for a day with
        no trains: it travels the same TrainApiError route as any other failure.
        """
        if self._token:
            return self._token
        try:
            resp = self.session.get(self.token_page, timeout=15)
        except requests.RequestException as e:
            raise TrainApiError(f"Could not reach the booking page: {e}") from e
        if resp.status_code != 200:
            raise TrainApiError(f"Could not load booking page (HTTP {resp.status_code}).")
        match = _TOKEN_RE.search(resp.text)
        if not match:
            raise TrainApiError("Could not find access token on booking page.")
        self._token = match.group(1)
        return self._token

    def _headers(self) -> dict:
        return {"accept": "application/json", "content-type": "application/json",
                "x-access-token": self._token, "user-agent": "Mozilla/5.0"}

    def _send(self, method: str, path: str, json_body: dict | None):
        """One politely-spaced HTTP call. Raises TrainApiError on a transport fault."""
        time.sleep(self.pause_seconds)   # polite spacing before every API call
        try:
            return self.session.request(method, f"{API_BASE}{path}",
                                        json=json_body, headers=self._headers(), timeout=30)
        except requests.RequestException as e:
            raise TrainApiError(f"Request failed: {e}") from e

    def _request(self, method: str, path: str, json_body: dict | None = None) -> dict | None:
        """Make a request, returning parsed JSON, or None for an empty/beyond-horizon
        result. Raises TrainApiError for a genuine failure (so callers can tell a
        server error apart from a day that simply has no trains)."""
        self.get_token()   # raises TrainApiError if we cannot get one
        resp = self._send(method, path, json_body)
        if resp.status_code in _RETRY_STATUSES:
            resp = self._send(method, path, json_body)   # one polite retry on a transient 5xx
        if resp.status_code in (401, 403):
            self._token = None   # token rotated — drop cache so next run rescrapes
            click.echo("Access token rejected; clearing cache.", err=True)
            return None
        if resp.status_code == 422:
            try:
                errors = resp.json().get("errors", [])
            except ValueError:   # body wasn't JSON
                errors = []
            if any(e.get("errorCode") == "OutwardTimebandTooFarAhead" for e in errors):
                return None  # beyond booking horizon — expected, not an error
            raise TrainApiError(f"API error {resp.status_code}: {resp.text[:200]}")
        if resp.status_code != 200:
            raise TrainApiError(f"API error {resp.status_code}: {resp.text[:200]}")
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
        """GET the detail (times) for a journey. journey_ref is the url-encoded path.

        A failed detail fetch returns None (the journey is dropped from the day)
        rather than failing the whole day — losing one train's time is better than
        losing the lot. The whole-day plan failure is the one that signals upward.
        """
        try:
            return self._request("GET", journey_ref)
        except TrainApiError as e:
            click.echo(f"  could not fetch journey detail ({e}); skipping it", err=True)
            return None
