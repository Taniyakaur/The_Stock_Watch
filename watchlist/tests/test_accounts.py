import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from watchlist.models import Stock, Watchlist, WatchlistItem

pytestmark = pytest.mark.django_db

User = get_user_model()


def signup(browser, username, email="new@example.com", password="a-Strong-pass-42"):
    return browser.post("/signup/", {
        "username": username, "email": email,
        "password1": password, "password2": password,
    })


# --- Pages -------------------------------------------------------------------

def test_home_redirects_to_login_when_logged_out():
    resp = Client().get("/")
    assert resp.status_code == 302
    assert resp["Location"].startswith("/login/")


def test_home_page_loads_when_logged_in(user):
    browser = Client()
    browser.force_login(user)
    resp = browser.get("/")
    assert resp.status_code == 200
    assert b"Signed in as" in resp.content


def test_login_and_signup_pages_load():
    assert Client().get("/login/").status_code == 200
    assert Client().get("/signup/").status_code == 200


def test_signup_creates_account_and_logs_in():
    browser = Client()
    resp = signup(browser, "carol")
    assert resp.status_code == 302 and resp["Location"] == "/"
    assert User.objects.get(username="carol").email == "new@example.com"
    assert browser.get("/").status_code == 200


def test_signup_requires_email():
    resp = signup(Client(), "dave", email="")
    assert resp.status_code == 200  # form shown again with an error
    assert not User.objects.filter(username="dave").exists()


def test_first_account_claims_existing_watchlists():
    old = Watchlist.objects.create(name="From before accounts")
    signup(Client(), "first")
    old.refresh_from_db()
    assert old.owner.username == "first"


def test_later_accounts_do_not_claim_watchlists(user):
    old = Watchlist.objects.create(name="Orphan")
    signup(Client(), "second")
    old.refresh_from_db()
    assert old.owner is None


def test_login_and_logout():
    User.objects.create_user("erin", "erin@example.com", "a-Strong-pass-42")
    browser = Client()
    resp = browser.post("/login/", {"username": "erin", "password": "a-Strong-pass-42"})
    assert resp.status_code == 302
    assert browser.get("/").status_code == 200
    browser.post("/logout/")
    assert browser.get("/").status_code == 302


# --- API privacy -------------------------------------------------------------

def test_api_requires_login(anon_client):
    assert anon_client.get("/api/watchlists/").status_code == 403
    assert anon_client.get("/api/stocks/").status_code == 403


def test_watchlist_created_for_current_user(client, user):
    resp = client.post("/api/watchlists/", {"name": "Mine"})
    assert Watchlist.objects.get(id=resp.data["id"]).owner == user


def test_users_only_see_their_own_watchlists(client, other_user):
    theirs = Watchlist.objects.create(owner=other_user, name="Bob's")
    assert client.get("/api/watchlists/").data["count"] == 0
    assert client.get(f"/api/watchlists/{theirs.id}/").status_code == 404
    assert client.delete(f"/api/watchlists/{theirs.id}/").status_code == 404
    assert Watchlist.objects.filter(id=theirs.id).exists()


def test_cannot_add_to_someone_elses_watchlist(client, other_user):
    theirs = Watchlist.objects.create(owner=other_user, name="Bob's")
    stock = Stock.objects.create(symbol="AAPL")
    resp = client.post("/api/items/", {"watchlist": theirs.id, "stock": stock.id})
    assert resp.status_code == 400
    assert not WatchlistItem.objects.exists()


def test_cannot_see_or_edit_someone_elses_items(client, other_user):
    theirs = Watchlist.objects.create(owner=other_user, name="Bob's")
    stock = Stock.objects.create(symbol="AAPL")
    item = WatchlistItem.objects.create(watchlist=theirs, stock=stock)
    assert client.get("/api/items/").data["count"] == 0
    assert client.patch(f"/api/items/{item.id}/", {"notes": "hi"}).status_code == 404


def test_cannot_move_item_into_someone_elses_watchlist(client, user, other_user):
    mine = Watchlist.objects.create(owner=user, name="Mine")
    theirs = Watchlist.objects.create(owner=other_user, name="Bob's")
    stock = Stock.objects.create(symbol="AAPL")
    item = WatchlistItem.objects.create(watchlist=mine, stock=stock)
    resp = client.patch(f"/api/items/{item.id}/", {"watchlist": theirs.id})
    assert resp.status_code == 400


def test_only_admins_edit_or_delete_stocks(client, admin_client):
    stock = Stock.objects.create(symbol="AAPL")
    assert client.patch(f"/api/stocks/{stock.id}/", {"name": "x"}).status_code == 403
    assert client.delete(f"/api/stocks/{stock.id}/").status_code == 403
    assert admin_client.patch(f"/api/stocks/{stock.id}/", {"name": "Apple"}).status_code == 200
    assert admin_client.delete(f"/api/stocks/{stock.id}/").status_code == 204
