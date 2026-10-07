# Stock Watch

A small Django app for keeping watchlists of stocks. It shows live prices and 30-day trends, and emails you when a stock reaches the target price you set.

- **Watchlists:** group stocks into named lists (e.g. "Tech", "Long term"). Each account sees only its own lists.
- **Live prices:** current price and today's change from [Finnhub](https://finnhub.io), or Yahoo Finance when no Finnhub key is set. The company name is filled in automatically.
- **Charts:** a 30-day sparkline for every stock. Click a symbol for a 1-month / 6-month / 1-year chart with your target marked.
- **Alerts:** one email when a stock reaches your target. The alert re-arms if the price drops back below the target or you change the target.
- **REST API:** everything the page does is also available at `/api/` (Django REST Framework).

## Setup

You need Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then edit .env (see below)
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/ and create an account. The first account to sign up takes over any watchlists that were created before accounts existed.

## Configuration (`.env`)

| Setting | What it's for |
|---|---|
| `SECRET_KEY` | Django's own secret, used to sign login cookies. Generate one with `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`. |
| `DEBUG` | `1` while developing on your computer. `0` anywhere public. |
| `ALLOWED_HOSTS` | Hostnames the site may be served under, comma-separated. |
| `FINNHUB_API_KEY` | Free key from finnhub.io for prices and company names. Optional: without it, Yahoo Finance is used. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Email account that sends alerts. For Gmail, use an [App Password](https://myaccount.google.com/apppasswords), not your normal password. Leave them empty and emails are printed in the terminal instead. |
| `SITE_URL` | The link included in alert emails. |

`.env` holds secrets, and git ignores it. Never commit it.

## Target-price alerts

Alerts are sent by a separate command. Run it in a second terminal next to the web server:

```bash
python manage.py check_alerts --every 5     # check every 5 minutes; Ctrl+C to stop
python manage.py check_alerts               # check once (e.g. from cron)
```

## API

All endpoints need a logged-in user. Lists are paginated, 20 per page.

| Endpoint | Description |
|---|---|
| `GET/POST /api/watchlists/` | Your watchlists, each with its items |
| `GET/PATCH/DELETE /api/watchlists/<id>/` | One watchlist |
| `GET/POST /api/items/?watchlist=<id>` | Stocks on your lists: target price, `target_reached`, notes |
| `PATCH/DELETE /api/items/<id>/` | Change a target or note, or remove a stock from a list |
| `GET/POST /api/stocks/?symbol=AAPL` | The shared stock list, with `current_price` and `day_change_pct`. Editing and deleting stocks is admin-only. |
| `GET /api/stocks/<id>/history/?range=1mo\|6mo\|1y` | Daily closing prices |

The admin site is at `/admin/`. Create an admin account with `python manage.py createsuperuser`.

## Development

```bash
pytest            # run the tests (no internet needed: price lookups are faked)
ruff check .      # lint
```

GitHub Actions runs both on every push (`.github/workflows/tests.yml`).

Prices come from free data sources. They can be delayed by up to about 15 minutes, and they stay at the last close while the market is shut.
