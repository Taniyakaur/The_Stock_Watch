import pytest

from watchlist.models import Stock, Watchlist

pytestmark = pytest.mark.django_db


def test_create_stock_uppercases_symbol(client):
    resp = client.post("/api/stocks/", {"symbol": " aapl ", "name": "Apple"})
    assert resp.status_code == 201
    assert resp.data["symbol"] == "AAPL"


def test_duplicate_symbol_rejected(client):
    Stock.objects.create(symbol="AAPL")
    resp = client.post("/api/stocks/", {"symbol": "aapl"})
    assert resp.status_code == 400


def test_watchlist_with_items(client, user):
    wl = Watchlist.objects.create(owner=user, name="Tech")
    stock = Stock.objects.create(symbol="MSFT", name="Microsoft")
    resp = client.post(
        "/api/items/",
        {"watchlist": wl.id, "stock": stock.id, "target_price": "450.00"},
    )
    assert resp.status_code == 201

    detail = client.get(f"/api/watchlists/{wl.id}/")
    assert detail.status_code == 200
    assert detail.data["items"][0]["stock_detail"]["symbol"] == "MSFT"


def test_same_stock_twice_in_watchlist_rejected(client, user):
    wl = Watchlist.objects.create(owner=user, name="Tech")
    stock = Stock.objects.create(symbol="MSFT")
    client.post("/api/items/", {"watchlist": wl.id, "stock": stock.id})
    resp = client.post("/api/items/", {"watchlist": wl.id, "stock": stock.id})
    assert resp.status_code == 400


def test_filter_items_by_watchlist(client, user):
    a = Watchlist.objects.create(owner=user, name="A")
    b = Watchlist.objects.create(owner=user, name="B")
    s = Stock.objects.create(symbol="TSLA")
    client.post("/api/items/", {"watchlist": a.id, "stock": s.id})
    client.post("/api/items/", {"watchlist": b.id, "stock": s.id})
    resp = client.get(f"/api/items/?watchlist={a.id}")
    assert resp.data["count"] == 1


def test_duplicate_symbol_different_case_rejected(client):
    Stock.objects.create(symbol="AAPL")
    resp = client.post("/api/stocks/", {"symbol": " Aapl "})
    assert resp.status_code == 400


def test_invalid_symbol_rejected(client):
    resp = client.post("/api/stocks/", {"symbol": "BAD SYM!"})
    assert resp.status_code == 400


def test_negative_target_price_rejected(client, user):
    wl = Watchlist.objects.create(owner=user, name="Tech")
    stock = Stock.objects.create(symbol="NVDA")
    resp = client.post(
        "/api/items/",
        {"watchlist": wl.id, "stock": stock.id, "target_price": "-1.00"},
    )
    assert resp.status_code == 400


def test_blank_watchlist_name_rejected(client):
    resp = client.post("/api/watchlists/", {"name": "   "})
    assert resp.status_code == 400


def test_non_integer_watchlist_filter_rejected(client):
    resp = client.get("/api/items/?watchlist=abc")
    assert resp.status_code == 400


def test_deleting_stock_on_watchlist_conflicts(client, admin_client, user):
    wl = Watchlist.objects.create(owner=user, name="Tech")
    stock = Stock.objects.create(symbol="AMD")
    client.post("/api/items/", {"watchlist": wl.id, "stock": stock.id})
    resp = admin_client.delete(f"/api/stocks/{stock.id}/")
    assert resp.status_code == 409
    assert Stock.objects.filter(pk=stock.pk).exists()


def test_update_and_delete_watchlist(client, user):
    wl = Watchlist.objects.create(owner=user, name="Old")
    resp = client.patch(f"/api/watchlists/{wl.id}/", {"name": "New"})
    assert resp.status_code == 200
    assert resp.data["name"] == "New"
    resp = client.delete(f"/api/watchlists/{wl.id}/")
    assert resp.status_code == 204


def test_add_example_watchlist(client, user, other_user):
    from watchlist.examples import EXAMPLE_LIST_NAME, POPULAR_STOCKS

    Stock.objects.create(symbol="AAPL", name="Already here")
    resp = client.post("/api/watchlists/example/")
    assert resp.status_code == 201
    assert resp.data["name"] == EXAMPLE_LIST_NAME
    symbols = {i["stock_detail"]["symbol"] for i in resp.data["items"]}
    assert symbols == {s for s, _, _ in POPULAR_STOCKS}
    assert Watchlist.objects.get(id=resp.data["id"]).owner == user
    # Existing stocks are reused, not duplicated.
    assert Stock.objects.filter(symbol="AAPL").count() == 1
    assert Stock.objects.get(symbol="AAPL").name == "Already here"


def test_example_watchlist_is_a_private_copy(client, user, other_user):
    from rest_framework.test import APIClient

    client.post("/api/watchlists/example/")
    bob = APIClient()
    bob.force_authenticate(other_user)
    bob.post("/api/watchlists/example/")
    assert Watchlist.objects.filter(owner=user).count() == 1
    assert Watchlist.objects.filter(owner=other_user).count() == 1
    assert Stock.objects.count() == 10


def test_example_watchlist_not_duplicated(client, user):
    first = client.post("/api/watchlists/example/")
    again = client.post("/api/watchlists/example/")
    assert again.status_code == 200
    assert again.data["id"] == first.data["id"]
    assert Watchlist.objects.filter(owner=user).count() == 1
