from django.db.models import ProtectedError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import prices
from .models import Stock, Watchlist, WatchlistItem
from .serializers import (
    StockSerializer,
    WatchlistItemSerializer,
    WatchlistSerializer,
)


class WarmPricesMixin:
    """Fetch live prices for everything being serialized in one parallel batch,
    instead of one slow request per stock while rendering."""

    def symbols_for(self, obj):
        raise NotImplementedError

    def get_serializer(self, *args, **kwargs):
        if args and args[0] is not None:
            objs = args[0] if kwargs.get("many") else [args[0]]
            prices.get_quotes(sym for obj in objs for sym in self.symbols_for(obj))
        return super().get_serializer(*args, **kwargs)


class StockViewSet(WarmPricesMixin, viewsets.ModelViewSet):
    serializer_class = StockSerializer

    def get_queryset(self):
        qs = Stock.objects.all()
        symbol = self.request.query_params.get("symbol")
        if symbol:
            qs = qs.filter(symbol__iexact=symbol.strip())
        return qs

    def symbols_for(self, obj):
        return [obj.symbol]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Stock is on one or more watchlists; remove it there first."},
                status=status.HTTP_409_CONFLICT,
            )


class WatchlistViewSet(WarmPricesMixin, viewsets.ModelViewSet):
    queryset = Watchlist.objects.prefetch_related("items__stock")
    serializer_class = WatchlistSerializer

    def symbols_for(self, obj):
        return [item.stock.symbol for item in obj.items.all()]


class WatchlistItemViewSet(WarmPricesMixin, viewsets.ModelViewSet):
    serializer_class = WatchlistItemSerializer

    def symbols_for(self, obj):
        return [obj.stock.symbol]

    def get_queryset(self):
        qs = WatchlistItem.objects.select_related("stock")
        watchlist_id = self.request.query_params.get("watchlist")
        if watchlist_id:
            if not watchlist_id.isdigit():
                raise ValidationError({"watchlist": "Must be an integer id."})
            qs = qs.filter(watchlist_id=watchlist_id)
        return qs


@method_decorator(ensure_csrf_cookie, name="dispatch")
class HomeView(TemplateView):
    """The web page; all data is loaded from the API by the page's script."""

    template_name = "watchlist/index.html"
