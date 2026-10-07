from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Stock, Watchlist, WatchlistItem
from .serializers import (
    StockSerializer,
    WatchlistItemSerializer,
    WatchlistSerializer,
)


class StockViewSet(viewsets.ModelViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Stock is on one or more watchlists; remove it there first."},
                status=status.HTTP_409_CONFLICT,
            )


class WatchlistViewSet(viewsets.ModelViewSet):
    queryset = Watchlist.objects.prefetch_related("items__stock")
    serializer_class = WatchlistSerializer


class WatchlistItemViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistItemSerializer

    def get_queryset(self):
        qs = WatchlistItem.objects.select_related("stock")
        watchlist_id = self.request.query_params.get("watchlist")
        if watchlist_id:
            if not watchlist_id.isdigit():
                raise ValidationError({"watchlist": "Must be an integer id."})
            qs = qs.filter(watchlist_id=watchlist_id)
        return qs
