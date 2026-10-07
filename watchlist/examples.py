"""A ready-made example watchlist for new users to start from."""
from django.db import transaction

from .models import Stock, Watchlist, WatchlistItem

EXAMPLE_LIST_NAME = "Popular stocks"

# Ten of the largest US companies by market value.
POPULAR_STOCKS = [
    ("AAPL", "Apple Inc", "NASDAQ"),
    ("MSFT", "Microsoft Corp", "NASDAQ"),
    ("NVDA", "NVIDIA Corp", "NASDAQ"),
    ("GOOGL", "Alphabet Inc (Google)", "NASDAQ"),
    ("AMZN", "Amazon.com Inc", "NASDAQ"),
    ("META", "Meta Platforms Inc", "NASDAQ"),
    ("AVGO", "Broadcom Inc", "NASDAQ"),
    ("TSLA", "Tesla Inc", "NASDAQ"),
    ("JPM", "JPMorgan Chase & Co", "NYSE"),
    ("V", "Visa Inc", "NYSE"),
]


@transaction.atomic
def create_example_watchlist(user):
    """Give `user` their own copy of the example list and return it."""
    watchlist = Watchlist.objects.create(owner=user, name=EXAMPLE_LIST_NAME)
    for symbol, name, exchange in POPULAR_STOCKS:
        stock = Stock.objects.filter(symbol__iexact=symbol).first()
        if stock is None:
            stock = Stock.objects.create(symbol=symbol, name=name, exchange=exchange)
        WatchlistItem.objects.create(watchlist=watchlist, stock=stock)
    return watchlist
