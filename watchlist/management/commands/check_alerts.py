import time

from django.core.management.base import BaseCommand

from watchlist.alerts import check_alerts


class Command(BaseCommand):
    help = "Email users whose stocks reached their target price."

    def add_arguments(self, parser):
        parser.add_argument(
            "--every",
            type=int,
            metavar="MINUTES",
            help="Keep running and check again every MINUTES (e.g. --every 5).",
        )

    def handle(self, *args, every=None, **options):
        if every is not None and every < 1:
            self.stderr.write("--every must be at least 1 minute.")
            return
        while True:
            sent = check_alerts()
            self.stdout.write(
                f"{time.strftime('%H:%M:%S')} checked targets, sent {sent} alert email(s)."
            )
            if every is None:
                return
            time.sleep(every * 60)
