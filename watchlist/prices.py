"""Live stock quotes, cached briefly.

Uses Finnhub (https://finnhub.io) when settings.FINNHUB_API_KEY is set,
otherwise Yahoo Finance via yfinance. Every function returns None for a
quote it can't get (unknown symbol, network error, provider outage) so the
API keeps working without prices.
"""
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

QUOTE_CACHE_SECONDS = 60
# Failed lookups are cached too, so a bad symbol doesn't cost a slow
# network call on every request.
MISS_CACHE_SECONDS = 300
MAX_WORKERS = 8
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"

_MISS = "missing"


def _cache_key(symbol):
    return f"quote:{symbol}"


def _to_decimal(value):
    if value is None or not math.isfinite(value):
        return None
    return Decimal(str(round(value, 2)))


def _make_quote(price, previous_close):
    price = _to_decimal(price)
    if price is None or price <= 0:
        return None
    previous_close = _to_decimal(previous_close)
    change_pct = None
    if previous_close:
        change_pct = ((price - previous_close) / previous_close * 100).quantize(
            Decimal("0.01")
        )
    return {"price": price, "change_pct": change_pct}


def _fetch_finnhub(symbol):
    resp = requests.get(
        FINNHUB_QUOTE_URL,
        params={"symbol": symbol, "token": settings.FINNHUB_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    # Finnhub answers unknown symbols with c=0 rather than an error.
    return _make_quote(data.get("c"), data.get("pc"))


def _fetch_yahoo(symbol):
    import yfinance as yf

    info = yf.Ticker(symbol).fast_info
    return _make_quote(info["last_price"], info["previous_close"])


def _fetch(symbol):
    fetch = _fetch_finnhub if settings.FINNHUB_API_KEY else _fetch_yahoo
    try:
        return fetch(symbol)
    except Exception as exc:
        # Log without the traceback: a Finnhub error message can echo the
        # request URL, which contains the API key.
        logger.warning("Could not fetch quote for %s: %s", symbol, type(exc).__name__)
        return None


def _store(symbol, quote):
    if quote is None:
        cache.set(_cache_key(symbol), _MISS, MISS_CACHE_SECONDS)
    else:
        cache.set(_cache_key(symbol), quote, QUOTE_CACHE_SECONDS)


def get_quotes(symbols):
    """Return {symbol: {"price", "change_pct"} | None}, fetching uncached
    symbols in parallel."""
    symbols = list(dict.fromkeys(symbols))
    cached = cache.get_many([_cache_key(s) for s in symbols])
    result = {}
    to_fetch = []
    for s in symbols:
        value = cached.get(_cache_key(s))
        if value is None:
            to_fetch.append(s)
        else:
            result[s] = None if value == _MISS else value

    if to_fetch:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(to_fetch))) as pool:
            for s, quote in zip(to_fetch, pool.map(_fetch, to_fetch)):
                _store(s, quote)
                result[s] = quote
    return result


def get_quote(symbol):
    return get_quotes([symbol])[symbol]


def get_price(symbol):
    quote = get_quote(symbol)
    return None if quote is None else quote["price"]
