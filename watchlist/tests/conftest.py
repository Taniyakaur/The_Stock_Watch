from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from watchlist import prices

FAKE_QUOTES = {
    "AAPL": {"price": Decimal("200.00"), "change_pct": Decimal("1.25")},
    "MSFT": {"price": Decimal("450.00"), "change_pct": None},
}

FAKE_PROFILES = {"AAPL": {"name": "Apple Inc", "exchange": "NASDAQ"}}
FAKE_HISTORY = {
    "AAPL": [{"date": "2026-10-06", "close": 198.5}, {"date": "2026-10-07", "close": 200.0}],
}


@pytest.fixture(autouse=True)
def fake_prices(monkeypatch):
    """Never hit Yahoo in tests; unknown symbols behave like a failed lookup."""
    cache.clear()
    calls = []

    def fetch(symbol):
        calls.append(symbol)
        return FAKE_QUOTES.get(symbol)

    monkeypatch.setattr(prices, "_fetch", fetch)
    monkeypatch.setattr(prices, "get_profile", lambda symbol: FAKE_PROFILES.get(
        symbol, {"name": "", "exchange": ""}))
    monkeypatch.setattr(prices, "_history_yahoo", lambda symbol, period: FAKE_HISTORY.get(symbol, []))
    yield calls
    cache.clear()


@pytest.fixture(autouse=True)
def fast_passwords(settings):
    # The real password hasher is deliberately slow; tests don't need that.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("alice", "alice@example.com", "pw-alice-123")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user("bob", "bob@example.com", "pw-bob-123")


@pytest.fixture
def client(user):
    """An API client logged in as `user`."""
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def admin_client(db):
    admin = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw-admin-123")
    c = APIClient()
    c.force_authenticate(admin)
    return c
