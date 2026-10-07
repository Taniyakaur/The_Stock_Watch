from decimal import Decimal

import pytest
from django.core.cache import cache

from watchlist import prices

FAKE_QUOTES = {
    "AAPL": {"price": Decimal("200.00"), "change_pct": Decimal("1.25")},
    "MSFT": {"price": Decimal("450.00"), "change_pct": None},
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
    yield calls
    cache.clear()
