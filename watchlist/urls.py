from rest_framework.routers import DefaultRouter

from .views import StockViewSet, WatchlistItemViewSet, WatchlistViewSet

router = DefaultRouter()
router.register("stocks", StockViewSet, basename="stock")
router.register("watchlists", WatchlistViewSet, basename="watchlist")
router.register("items", WatchlistItemViewSet, basename="item")

urlpatterns = router.urls
