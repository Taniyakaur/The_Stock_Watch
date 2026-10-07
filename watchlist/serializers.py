import re

from rest_framework import serializers

from .models import Stock, Watchlist, WatchlistItem

SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ["id", "symbol", "name", "exchange"]

    def validate_symbol(self, value):
        # Field-level UniqueValidator runs on the raw value, so the
        # case-insensitive uniqueness check has to happen after normalizing.
        value = value.strip().upper()
        if not SYMBOL_RE.match(value):
            raise serializers.ValidationError(
                "Symbol must be 1-10 characters: letters, digits, '.' or '-'."
            )
        qs = Stock.objects.filter(symbol__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("stock with this symbol already exists.")
        return value


class WatchlistItemSerializer(serializers.ModelSerializer):
    stock_detail = StockSerializer(source="stock", read_only=True)
    target_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = WatchlistItem
        fields = [
            "id",
            "watchlist",
            "stock",
            "stock_detail",
            "target_price",
            "notes",
            "added_at",
        ]
        read_only_fields = ["added_at"]


class WatchlistSerializer(serializers.ModelSerializer):
    items = WatchlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Watchlist
        fields = ["id", "name", "created_at", "items"]
        read_only_fields = ["created_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be blank.")
        return value
