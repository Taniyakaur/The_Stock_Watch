from django.contrib import admin

from .models import Stock, Watchlist, WatchlistItem


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ["symbol", "name", "exchange"]
    search_fields = ["symbol", "name"]
    list_filter = ["exchange"]


class WatchlistItemInline(admin.TabularInline):
    model = WatchlistItem
    extra = 0
    autocomplete_fields = ["stock"]


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    list_filter = ["owner"]
    search_fields = ["name", "owner__username"]
    inlines = [WatchlistItemInline]


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ["watchlist", "stock", "target_price", "added_at"]
    list_filter = ["watchlist"]
    search_fields = ["stock__symbol", "watchlist__name"]
    autocomplete_fields = ["stock"]
