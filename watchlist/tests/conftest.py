from decimal import Decimal

import pytest
from django.core.cache import cache

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
