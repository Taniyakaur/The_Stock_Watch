from django.urls import re_path
from rest_framework.routers import DefaultRouter

from .views import StockViewSet, WatchlistItemViewSet, WatchlistViewSet, watchlist_summary

router = DefaultRouter()
router.register("stocks", StockViewSet, basename="stock")
router.register("watchlists", WatchlistViewSet, basename="watchlist")
router.register("items", WatchlistItemViewSet, basename="item")

urlpatterns = [
    # /api/watchlist (with or without the trailing slash)
    re_path(r"^watchlist/?$", watchlist_summary, name="watchlist-summary"),
    *router.urls,
]
