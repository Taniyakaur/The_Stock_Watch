"""What happens when the market-data API misbehaves.

conftest.py replaces prices._fetch with a fake for every test; these tests put
the real one back and fake only the HTTP layer (requests.get), so the error
handling in prices.py is exercised for real.
"""
import logging

import pytest
import requests

from watchlist import prices
from watchlist.models import Stock

pytestmark = pytest.mark.django_db

# Captured at import time, before the autouse fixture swaps in the fakes.
REAL_FETCH = prices._fetch
REAL_GET_PROFILE = prices.get_profile
SECRET = "finnhub-test-key-123"


class FakeResponse:
    def __init__(self, data=None, status=200, bad_json=False):
        self._data = data
        self.status_code = status
        self._bad_json = bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error for url: ...token={SECRET}")

    def json(self):
        if self._bad_json:
            raise ValueError("Expecting value: line 1 column 1")
        return self._data


def raise_(exc):
    def fake_get(*args, **kwargs):
        raise exc
    return fake_get


def respond(response):
    return lambda *args, **kwargs: response


FAILURES = {
    "timeout": raise_(requests.Timeout("read timed out")),
    "connection error": raise_(requests.ConnectionError("no route to host")),
    "server error 500": respond(FakeResponse(status=500)),
    "rate limited 429": respond(FakeResponse(status=429)),
    "invalid json": respond(FakeResponse(bad_json=True)),
    "unexpected shape": respond(FakeResponse(data=["not", "a", "dict"])),
}


@pytest.fixture
def real_finnhub(monkeypatch, settings):
    settings.FINNHUB_API_KEY = SECRET
    monkeypatch.setattr(prices, "_fetch", REAL_FETCH)


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
def test_failure_gives_no_price(real_finnhub, monkeypatch, failure):
    monkeypatch.setattr(prices.requests, "get", failure)
    assert prices.get_quote("AAPL") is None


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
def test_api_still_works_when_prices_fail(real_finnhub, monkeypatch, client, failure):
    monkeypatch.setattr(prices.requests, "get", failure)
    stock = Stock.objects.create(symbol="AAPL", name="Apple Inc")
    resp = client.get(f"/api/stocks/{stock.id}/")
    assert resp.status_code == 200
    assert resp.data["current_price"] is None
    assert resp.data["day_change_pct"] is None


def test_unknown_ticker(real_finnhub, monkeypatch):
    # Finnhub answers unknown symbols with 200 and zeros, not an error.
    monkeypatch.setattr(prices.requests, "get", respond(FakeResponse({"c": 0, "pc": 0})))
    assert prices.get_quote("NOTREAL") is None


def test_requests_have_a_timeout(real_finnhub, monkeypatch):
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return FakeResponse({"c": 10, "pc": 9})

    monkeypatch.setattr(prices.requests, "get", fake_get)
    prices.get_quote("AAPL")
    assert seen.get("timeout"), "a hung API must not hang the page"


def test_failures_are_cached_so_the_rate_limit_is_spared(real_finnhub, monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        raise requests.Timeout()

    monkeypatch.setattr(prices.requests, "get", fake_get)
    for _ in range(5):
        prices.get_quote("AAPL")
    assert len(calls) == 1


def test_errors_are_logged_without_the_api_key(real_finnhub, monkeypatch, caplog):
    monkeypatch.setattr(prices.requests, "get", respond(FakeResponse(status=500)))
    with caplog.at_level(logging.WARNING, logger="watchlist.prices"):
        prices.get_quote("AAPL")
    assert "AAPL" in caplog.text
    assert SECRET not in caplog.text


def test_new_stock_is_saved_even_if_company_lookup_times_out(monkeypatch, settings, client):
    settings.FINNHUB_API_KEY = SECRET
    monkeypatch.setattr(prices, "get_profile", REAL_GET_PROFILE)
    monkeypatch.setattr(prices.requests, "get", raise_(requests.Timeout()))
    resp = client.post("/api/stocks/", {"symbol": "AAPL"})
    assert resp.status_code == 201
    assert resp.data["name"] == ""


def test_history_failure_returns_empty_chart(monkeypatch, client):
    def boom(symbol, period):
        raise requests.ConnectionError()

    monkeypatch.setattr(prices, "_history_yahoo", boom)
    stock = Stock.objects.create(symbol="AAPL")
    resp = client.get(f"/api/stocks/{stock.id}/history/")
    assert resp.status_code == 200
    assert resp.data["points"] == []
