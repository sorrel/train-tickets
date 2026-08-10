import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from core.client import TrainClient, TrainApiError

FIXTURES = Path(__file__).parent / "fixtures"


def _resp(status=200, text="", payload=None):
    r = MagicMock()
    r.status_code = status
    r.text = text
    if payload is not None:
        r.json.return_value = payload
    else:
        # text may be non-JSON (e.g. an HTML page scraped for the token), so
        # don't assume it parses.
        try:
            r.json.return_value = json.loads(text) if text else {}
        except json.JSONDecodeError:
            r.json.return_value = {}
    return r


def test_scrape_token_extracts_from_html():
    html = 'x{"apiAccessToken":"otrl|abc123","apiHost":"api.southeasternrailway.co.uk"}y'
    client = TrainClient(token_page="http://page")
    with patch.object(client.session, "get", return_value=_resp(text=html)):
        assert client.get_token() == "otrl|abc123"


def test_get_token_is_cached():
    html = '{"apiAccessToken":"otrl|once"}'
    client = TrainClient(token_page="http://page")
    with patch.object(client.session, "get", return_value=_resp(text=html)) as g:
        client.get_token()
        client.get_token()
        assert g.call_count == 1   # second call uses the cache


def test_token_scrape_raises_on_transport_error():
    # A proxy/connection fault while scraping the token must surface as a
    # TrainApiError like any other lookup failure — never a bare traceback.
    client = TrainClient(token_page="http://page", pause_seconds=0)
    with patch.object(client.session, "get",
                      side_effect=requests.ConnectionError("proxy timed out")):
        with pytest.raises(TrainApiError):
            client.plan_day("5230", "1072", "a", "b")


def test_token_scrape_raises_when_page_is_unavailable():
    # No token means no lookup is possible; that must not look like an empty day.
    client = TrainClient(token_page="http://page", pause_seconds=0)
    with patch.object(client.session, "get", return_value=_resp(status=503, text="down")):
        with pytest.raises(TrainApiError):
            client.plan_day("5230", "1072", "a", "b")


def test_token_scrape_raises_when_token_is_missing_from_page():
    client = TrainClient(token_page="http://page", pause_seconds=0)
    with patch.object(client.session, "get", return_value=_resp(text="<html>no token</html>")):
        with pytest.raises(TrainApiError):
            client.plan_day("5230", "1072", "a", "b")


def test_plan_day_posts_expected_body():
    plan = json.loads((FIXTURES / "journey-plan-sample.json").read_text())
    client = TrainClient(token_page="http://page", pause_seconds=0)
    client._token = "otrl|x"   # pre-seed to skip scraping
    with patch.object(client.session, "request", return_value=_resp(payload=plan)) as req:
        result = client.plan_day("5230", "1072", "2026-06-16T05:44:00", "2026-06-16T07:45:00")
    assert result == plan
    method, url = req.call_args.args[0], req.call_args.args[1]
    body = req.call_args.kwargs["json"]
    assert method == "POST" and url.endswith("/jp/journey-plan")
    assert body["origin"] == "5230" and body["destination"] == "1072"
    assert body["outward"]["rangeStart"] == "2026-06-16T05:44:00"
    assert body["outward"]["arriveDepart"] == "Depart"
    assert req.call_args.kwargs["headers"]["x-access-token"] == "otrl|x"


def _client():
    client = TrainClient(token_page="http://page", pause_seconds=0)
    client._token = "otrl|x"   # pre-seed to skip scraping
    return client


def test_request_retries_once_on_500_then_succeeds():
    client = _client()
    plan = {"result": {"outward": []}}
    responses = [_resp(status=500, text="boom"), _resp(payload=plan)]
    with patch.object(client.session, "request", side_effect=responses) as req:
        result = client.plan_day("5230", "1072", "a", "b")
    assert result == plan          # the retry succeeded
    assert req.call_count == 2      # one retry, no more


def test_request_raises_after_a_persistent_500():
    client = _client()
    with patch.object(client.session, "request",
                      return_value=_resp(status=500, text="still down")):
        with pytest.raises(TrainApiError):
            client.plan_day("5230", "1072", "a", "b")


def test_request_raises_on_transport_error():
    client = _client()
    with patch.object(client.session, "request",
                      side_effect=requests.ConnectionError("no route")):
        with pytest.raises(TrainApiError):
            client.plan_day("5230", "1072", "a", "b")


def test_horizon_422_returns_none_not_an_error():
    client = _client()
    payload = {"errors": [{"errorCode": "OutwardTimebandTooFarAhead"}]}
    with patch.object(client.session, "request",
                      return_value=_resp(status=422, payload=payload)):
        assert client.plan_day("5230", "1072", "a", "b") is None   # expected, not raised


def test_journey_detail_swallows_failure_and_returns_none():
    # A failed detail fetch drops that one train rather than failing the day.
    client = _client()
    with patch.object(client.session, "request",
                      return_value=_resp(status=500, text="boom")):
        assert client.journey_detail("/jp/journey/abc") is None
