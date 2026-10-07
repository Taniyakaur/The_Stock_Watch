import pytest

from watchlist.models import Stock, Watchlist, WatchlistItem

pytestmark = pytest.mark.django_db

# Fake prices (see conftest.py): AAPL = 200.00 (+1.25%), MSFT = 450.00, others unknown.


@pytest.fixture
def tech(user):
    wl = Watchlist.objects.create(owner=user, name="Tech")
    for symbol, target in [("MSFT", None), ("AAPL", "150.00"), ("ZZZZ", "5.00")]:
        stock = Stock.objects.create(symbol=symbol, name=symbol.title())
        WatchlistItem.objects.create(watchlist=wl, stock=stock, target_price=target)
    return wl


@pytest.mark.parametrize("path", ["/api/watchlist", "/api/watchlist/"])
def test_lists_tickers_with_price_and_change(client, tech, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.data["count"] == 3
    rows = {r["symbol"]: r for r in resp.data["results"]}
    assert [r["symbol"] for r in resp.data["results"]] == ["AAPL", "MSFT", "ZZZZ"]
    assert rows["AAPL"] == {
        "symbol": "AAPL", "name": "Aapl", "price": "200.00", "change_pct": "1.25",
        "target_price": "150.00", "target_reached": True,
        "watchlist": "Tech", "watchlist_id": tech.id, "item_id": rows["AAPL"]["item_id"],
    }
    assert rows["MSFT"]["change_pct"] is None and rows["MSFT"]["target_reached"] is None


def test_unknown_ticker_has_null_price(client, tech):
    rows = {r["symbol"]: r for r in client.get("/api/watchlist").data["results"]}
    assert rows["ZZZZ"]["price"] is None
    assert rows["ZZZZ"]["target_reached"] is None


def test_only_your_own_tickers(client, tech, other_user):
    theirs = Watchlist.objects.create(owner=other_user, name="Bob's")
    WatchlistItem.objects.create(watchlist=theirs, stock=Stock.objects.create(symbol="TSLA"))
    symbols = [r["symbol"] for r in client.get("/api/watchlist").data["results"]]
    assert "TSLA" not in symbols


def test_empty(client):
    assert client.get("/api/watchlist").data == {"count": 0, "results": []}


def test_requires_login(anon_client):
    assert anon_client.get("/api/watchlist").status_code == 403


def test_read_only(client):
    assert client.post("/api/watchlist", {}).status_code == 405


def test_one_price_lookup_per_symbol(client, tech, user, fake_prices):
    other = Watchlist.objects.create(owner=user, name="Other")
    WatchlistItem.objects.create(watchlist=other, stock=Stock.objects.get(symbol="AAPL"))
    rows = client.get("/api/watchlist").data["results"]
    assert [r["symbol"] for r in rows].count("AAPL") == 2
    assert sorted(fake_prices) == ["AAPL", "MSFT", "ZZZZ"]
