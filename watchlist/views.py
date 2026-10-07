from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import CreateView, TemplateView
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from . import prices
from .examples import EXAMPLE_LIST_NAME, create_example_watchlist
from .forms import SignUpForm
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
    """Stocks are shared by everyone: any user can look them up or add one,
    but only admins can edit or delete them."""

    serializer_class = StockSerializer

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Stock.objects.all()
        symbol = self.request.query_params.get("symbol")
        if symbol:
            qs = qs.filter(symbol__iexact=symbol.strip())
        return qs

    def symbols_for(self, obj):
        return [obj.symbol]

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Daily closing prices: /api/stocks/<id>/history/?range=1mo|6mo|1y"""
        period = request.query_params.get("range", "1mo")
        if period not in prices.HISTORY_RANGES:
            raise ValidationError({"range": f"Use one of: {', '.join(prices.HISTORY_RANGES)}."})
        stock = self.get_object()
        return Response({
            "symbol": stock.symbol,
            "range": period,
            "points": prices.get_history(stock.symbol, prices.HISTORY_RANGES[period]),
        })

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Stock is on one or more watchlists; remove it there first."},
                status=status.HTTP_409_CONFLICT,
            )


class WatchlistViewSet(WarmPricesMixin, viewsets.ModelViewSet):
    serializer_class = WatchlistSerializer

    def get_queryset(self):
        return Watchlist.objects.filter(owner=self.request.user).prefetch_related(
            "items__stock"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=["post"])
    def example(self, request):
        """POST /api/watchlists/example/ adds a "Popular stocks" list for you
        (or returns the one you already have)."""
        existing = self.get_queryset().filter(name=EXAMPLE_LIST_NAME).first()
        if existing is not None:
            return Response(self.get_serializer(existing).data)
        watchlist = create_example_watchlist(request.user)
        watchlist = self.get_queryset().get(pk=watchlist.pk)
        return Response(self.get_serializer(watchlist).data, status=status.HTTP_201_CREATED)

    def symbols_for(self, obj):
        return [item.stock.symbol for item in obj.items.all()]


class WatchlistItemViewSet(WarmPricesMixin, viewsets.ModelViewSet):
    serializer_class = WatchlistItemSerializer

    def symbols_for(self, obj):
        return [obj.stock.symbol]

    def get_queryset(self):
        qs = WatchlistItem.objects.filter(
            watchlist__owner=self.request.user
        ).select_related("stock")
        watchlist_id = self.request.query_params.get("watchlist")
        if watchlist_id:
            if not watchlist_id.isdigit():
                raise ValidationError({"watchlist": "Must be an integer id."})
            qs = qs.filter(watchlist_id=watchlist_id)
        return qs



@api_view(["GET"])
def watchlist_summary(request):
    """GET /api/watchlist: every ticker on your watchlists with its latest
    price and daily change, as one flat list."""
    items = (
        WatchlistItem.objects.filter(watchlist__owner=request.user)
        .select_related("stock", "watchlist")
        .order_by("stock__symbol", "watchlist__name")
    )
    quotes = prices.get_quotes(item.stock.symbol for item in items)
    results = []
    for item in items:
        quote = quotes.get(item.stock.symbol)
        price = quote["price"] if quote else None
        change = quote["change_pct"] if quote else None
        target = item.target_price
        results.append({
            "symbol": item.stock.symbol,
            "name": item.stock.name,
            "price": None if price is None else str(price),
            "change_pct": None if change is None else str(change),
            "target_price": None if target is None else str(target),
            "target_reached": None if price is None or target is None else price >= target,
            "watchlist": item.watchlist.name,
            "watchlist_id": item.watchlist_id,
            "item_id": item.id,
        })
    return Response({"count": len(results), "results": results})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class HomeView(LoginRequiredMixin, TemplateView):
    """The web page; all data is loaded from the API by the page's script."""

    template_name = "watchlist/index.html"


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            first_account = not get_user_model().objects.exists()
            user = form.save()
            if first_account:
                # Watchlists made before accounts existed belong to the first user.
                Watchlist.objects.filter(owner=None).update(owner=user)
        login(self.request, user)
        return redirect("home")
