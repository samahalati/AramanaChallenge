from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import User
from seed.generate import DEMO_PASSWORD, generate


class Command(BaseCommand):
    help = "Create synthetic demo data (no real data) with injected anomalies and a ground-truth file; optionally run detection."

    def add_arguments(self, parser):
        parser.add_argument("--seed-value", type=int, default=42)
        parser.add_argument("--lang", choices=["fa", "en"], default="fa", help="language of the demo data (names and free text)")
        parser.add_argument("--reset", action="store_true", help="flush the database first")
        parser.add_argument("--detect", action="store_true", help="run the detection engine afterwards")

    def handle(self, *args, **o):
        if o["reset"]:
            call_command("flush", interactive=False, verbosity=0)
        if User.objects.exists():
            return self.stdout.write("Database already has data – use --reset to regenerate.")
        generate(o["seed_value"], settings.GROUND_TRUTH_PATH, o["lang"])
        self.stdout.write(self.style.SUCCESS(f"Synthetic data generated (seed={o['seed_value']}). Demo password for all accounts: {DEMO_PASSWORD}"))
        if o["detect"]:
            call_command("run_detection")
