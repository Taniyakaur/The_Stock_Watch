"""Target-price alerts: email each user once when a stock reaches their target."""
import logging
from collections import defaultdict

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from . import prices
from .models import WatchlistItem

logger = logging.getLogger(__name__)


def check_alerts():
    """Check every item with a target; return the number of emails sent."""
    items = list(
        WatchlistItem.objects.filter(target_price__isnull=False, watchlist__owner__isnull=False)
        .exclude(Q(watchlist__owner__email="") | Q(watchlist__owner__is_active=False))
        .select_related("stock", "watchlist__owner")
    )
    quotes = prices.get_quotes(item.stock.symbol for item in items)

    hits_by_user = defaultdict(list)
    for item in items:
        quote = quotes.get(item.stock.symbol)
        if quote is None:
            continue
        reached = quote["price"] >= item.target_price
        if reached and item.alert_sent_at is None:
            hits_by_user[item.watchlist.owner].append((item, quote["price"]))
        elif not reached and item.alert_sent_at is not None:
            # Price fell back below the target: re-arm for the next time.
            item.alert_sent_at = None
            item.save(update_fields=["alert_sent_at"])

    sent = 0
    for user, hits in hits_by_user.items():
        try:
            send_mail(_subject(hits), _body(user, hits), None, [user.email])
        except Exception:
            logger.exception("Could not send alert email to %s", user.username)
            continue  # try again next run
        now = timezone.now()
        WatchlistItem.objects.filter(id__in=[item.id for item, _ in hits]).update(alert_sent_at=now)
        sent += 1
    return sent


def _subject(hits):
    if len(hits) == 1:
        return f"Stock Watch: {hits[0][0].stock.symbol} reached your target price"
    return f"Stock Watch: {len(hits)} stocks reached your target prices"


def _body(user, hits):
    lines = [f"Hi {user.username},", ""]
    lines.append("These stocks reached the target price you set:" if len(hits) > 1
                 else "A stock reached the target price you set:")
    lines.append("")
    for item, price in sorted(hits, key=lambda h: h[0].stock.symbol):
        name = f" ({item.stock.name})" if item.stock.name else ""
        lines.append(
            f"  • {item.stock.symbol}{name} is now ${price:,.2f}"
            f" — your target was ${item.target_price:,.2f} (list: {item.watchlist.name})"
        )
    lines += ["", f"See your watchlists: {settings.SITE_URL}", "",
              "You'll get another email for a stock if it drops below your target "
              "and reaches it again, or if you set a new target."]
    return "\n".join(lines)
