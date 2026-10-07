from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200, blank=True)
    exchange = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["symbol"]

    def __str__(self):
        return self.symbol


class Watchlist(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class WatchlistItem(models.Model):
    watchlist = models.ForeignKey(
        Watchlist, on_delete=models.CASCADE, related_name="items"
    )
    stock = models.ForeignKey(
        Stock, on_delete=models.PROTECT, related_name="watchlist_items"
    )
    target_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["watchlist", "stock"], name="unique_stock_per_watchlist"
            )
        ]

    def __str__(self):
        return f"{self.watchlist} - {self.stock}"
