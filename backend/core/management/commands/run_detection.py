import json

from django.core.management.base import BaseCommand

from monitoring.services.runs import run_detection


class Command(BaseCommand):
    help = "Run the fraud & anomaly detection engine (idempotent: de-duplicates against existing alerts)."

    def handle(self, *args, **o):
        r = run_detection()
        self.stdout.write(json.dumps({k: v for k, v in r.items() if k != "suppressed"}, indent=2, default=str))
