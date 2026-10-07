import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from watchlist.alerts import check_alerts
from watchlist.models import Stock, Watchlist, WatchlistItem

pytestmark = pytest.mark.django_db

# Fake prices (see conftest.py): AAPL = 200.00, MSFT = 450.00, others unknown.


@pytest.fixture
def tech(user):
    return Watchlist.objects.create(owner=user, name="Tech")


def add(watchlist, symbol, target):
    stock, _ = Stock.objects.get_or_create(symbol=symbol, defaults={"name": symbol.title()})
    return WatchlistItem.objects.create(watchlist=watchlist, stock=stock, target_price=target)


def test_emails_when_target_reached(tech, mailoutbox):
    item = add(tech, "AAPL", "150.00")
    assert check_alerts() == 1
    assert len(mailoutbox) == 1
    mail = mailoutbox[0]
    assert mail.to == ["alice@example.com"]
    assert "AAPL reached your target" in mail.subject
    assert "$200.00" in mail.body and "$150.00" in mail.body and "Tech" in mail.body
    item.refresh_from_db()
    assert item.alert_sent_at is not None


def test_no_email_below_target(tech, mailoutbox):
    add(tech, "AAPL", "250.00")
    assert check_alerts() == 0
    assert mailoutbox == []


def test_only_emails_once(tech, mailoutbox):
    add(tech, "AAPL", "150.00")
    check_alerts()
    check_alerts()
    assert len(mailoutbox) == 1


def test_several_hits_are_one_email(tech, mailoutbox):
    add(tech, "AAPL", "150.00")
    add(tech, "MSFT", "400.00")
    assert check_alerts() == 1
    assert "2 stocks" in mailoutbox[0].subject
    assert "AAPL" in mailoutbox[0].body and "MSFT" in mailoutbox[0].body


def test_each_user_gets_their_own_email(tech, other_user, mailoutbox):
    add(tech, "AAPL", "150.00")
    add(Watchlist.objects.create(owner=other_user, name="Bob's"), "MSFT", "400.00")
    assert check_alerts() == 2
    assert sorted(m.to[0] for m in mailoutbox) == ["alice@example.com", "bob@example.com"]
    bob_mail = next(m for m in mailoutbox if m.to == ["bob@example.com"])
    assert "AAPL" not in bob_mail.body


def test_rearms_after_price_falls_below_target(tech, mailoutbox):
    item = add(tech, "AAPL", "150.00")
    check_alerts()
    WatchlistItem.objects.filter(id=item.id).update(target_price="250.00")  # now below target
    check_alerts()
    item.refresh_from_db()
    assert item.alert_sent_at is None
    WatchlistItem.objects.filter(id=item.id).update(target_price="150.00")
    check_alerts()
    assert len(mailoutbox) == 2


def test_changing_target_via_api_rearms(client, tech, mailoutbox):
    item = add(tech, "AAPL", "150.00")
    check_alerts()
    client.patch(f"/api/items/{item.id}/", {"target_price": "180.00"})
    item.refresh_from_db()
    assert item.alert_sent_at is None
    check_alerts()
    assert len(mailoutbox) == 2


def test_saving_same_target_does_not_rearm(client, tech):
    item = add(tech, "AAPL", "150.00")
    check_alerts()
    client.patch(f"/api/items/{item.id}/", {"target_price": "150.00", "notes": "hi"})
    item.refresh_from_db()
    assert item.alert_sent_at is not None


def test_skips_unknown_prices_and_users_without_email(user, mailoutbox):
    add(Watchlist.objects.create(owner=user, name="A"), "ZZZZ", "1.00")
    noemail = get_user_model().objects.create_user("nomail", "", "pw-nomail-123")
    add(Watchlist.objects.create(owner=noemail, name="B"), "AAPL", "1.00")
    add(Watchlist.objects.create(name="Unowned"), "MSFT", "1.00")
    assert check_alerts() == 0
    assert mailoutbox == []


def test_failed_email_is_retried_next_time(tech, mailoutbox, monkeypatch):
    from watchlist import alerts

    item = add(tech, "AAPL", "150.00")
    real_send_mail = alerts.send_mail

    def boom(*a, **k):
        raise OSError("mail server down")

    monkeypatch.setattr(alerts, "send_mail", boom)
    assert check_alerts() == 0
    item.refresh_from_db()
    assert item.alert_sent_at is None
    monkeypatch.setattr(alerts, "send_mail", real_send_mail)
    assert check_alerts() == 1


def test_command_runs_once(tech, mailoutbox, capsys):
    add(tech, "AAPL", "150.00")
    call_command("check_alerts")
    assert "sent 1 alert email" in capsys.readouterr().out
    assert len(mailoutbox) == 1
