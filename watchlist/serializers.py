import re

from rest_framework import serializers

from . import prices
from .models import Stock, Watchlist, WatchlistItem

SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")


class StockSerializer(serializers.ModelSerializer):
    current_price = serializers.SerializerMethodField()
    day_change_pct = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = ["id", "symbol", "name", "exchange", "current_price", "day_change_pct"]

    def get_current_price(self, obj):
        quote = prices.get_quote(obj.symbol)
        return None if quote is None else str(quote["price"])

    def get_day_change_pct(self, obj):
        quote = prices.get_quote(obj.symbol)
        if quote is None or quote["change_pct"] is None:
            return None
        return str(quote["change_pct"])

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

    def create(self, validated_data):
        # Fill in the company name/exchange when the user didn't type them.
        if not validated_data.get("name") or not validated_data.get("exchange"):
            profile = prices.get_profile(validated_data["symbol"])
            validated_data["name"] = validated_data.get("name") or profile["name"][:200]
            validated_data["exchange"] = (
                validated_data.get("exchange") or profile["exchange"][:50]
            )
        return super().create(validated_data)


class WatchlistItemSerializer(serializers.ModelSerializer):
    stock_detail = StockSerializer(source="stock", read_only=True)
    target_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
    )
    target_reached = serializers.SerializerMethodField()

    class Meta:
        model = WatchlistItem
        fields = [
            "id",
            "watchlist",
            "stock",
            "stock_detail",
            "target_price",
            "target_reached",
            "notes",
            "added_at",
        ]
        read_only_fields = ["added_at"]

    def get_target_reached(self, obj):
        """True once the live price is at or above the target price."""
        if obj.target_price is None:
            return None
        price = prices.get_price(obj.stock.symbol)
        if price is None:
            return None
        return price >= obj.target_price

    def validate_watchlist(self, value):
        # Don't reveal whether someone else's watchlist id exists.
        if value.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Watchlist not found.")
        return value


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
