import pytest
from rest_framework.test import APIClient

from watchlist import prices
from watchlist.models import Stock, Watchlist, WatchlistItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


def test_stock_includes_current_price(client):
    stock = Stock.objects.create(symbol="AAPL")
    resp = client.get(f"/api/stocks/{stock.id}/")
    assert resp.data["current_price"] == "200.00"


def test_unknown_symbol_price_is_null(client):
    stock = Stock.objects.create(symbol="ZZZZ")
    resp = client.get(f"/api/stocks/{stock.id}/")
    assert resp.status_code == 200
    assert resp.data["current_price"] is None


@pytest.mark.parametrize(
    "target, expected",
    [("150.00", True), ("200.00", True), ("250.00", False), (None, None)],
)
def test_target_reached(client, target, expected):
    wl = Watchlist.objects.create(name="Tech")
    stock = Stock.objects.create(symbol="AAPL")
    item = WatchlistItem.objects.create(watchlist=wl, stock=stock, target_price=target)
    resp = client.get(f"/api/items/{item.id}/")
    assert resp.data["target_reached"] is expected


def test_target_reached_null_without_price(client):
    wl = Watchlist.objects.create(name="Tech")
    stock = Stock.objects.create(symbol="ZZZZ")
    item = WatchlistItem.objects.create(watchlist=wl, stock=stock, target_price="10")
    resp = client.get(f"/api/items/{item.id}/")
    assert resp.data["target_reached"] is None


def test_prices_are_cached(fake_prices):
    prices.get_price("AAPL")
    prices.get_price("AAPL")
    prices.get_price("ZZZZ")
    prices.get_price("ZZZZ")
    assert fake_prices == ["AAPL", "ZZZZ"]


def test_watchlist_fetches_each_symbol_once(client, fake_prices):
    wl = Watchlist.objects.create(name="Tech")
    for sym in ["AAPL", "MSFT"]:
        stock = Stock.objects.create(symbol=sym)
        WatchlistItem.objects.create(watchlist=wl, stock=stock, target_price="1")
    resp = client.get("/api/watchlists/")
    assert resp.status_code == 200
    assert sorted(fake_prices) == ["AAPL", "MSFT"]


def test_stock_includes_day_change(client):
    aapl = Stock.objects.create(symbol="AAPL")
    msft = Stock.objects.create(symbol="MSFT")
    assert client.get(f"/api/stocks/{aapl.id}/").data["day_change_pct"] == "1.25"
    assert client.get(f"/api/stocks/{msft.id}/").data["day_change_pct"] is None


def test_filter_stocks_by_symbol(client):
    Stock.objects.create(symbol="AAPL")
    Stock.objects.create(symbol="MSFT")
    resp = client.get("/api/stocks/?symbol=aapl")
    assert [s["symbol"] for s in resp.data["results"]] == ["AAPL"]


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_finnhub_quote_parsing(monkeypatch, settings):
    settings.FINNHUB_API_KEY = "test-key"
    monkeypatch.setattr(
        prices.requests, "get", lambda *a, **k: FakeResponse({"c": 110.0, "pc": 100.0})
    )
    assert prices._fetch_finnhub("AAPL") == {
        "price": prices.Decimal("110.00"),
        "change_pct": prices.Decimal("10.00"),
    }


def test_finnhub_unknown_symbol_is_none(monkeypatch, settings):
    settings.FINNHUB_API_KEY = "test-key"
    monkeypatch.setattr(
        prices.requests, "get", lambda *a, **k: FakeResponse({"c": 0, "pc": 0})
    )
    assert prices._fetch_finnhub("ZZZZ") is None
