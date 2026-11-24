import json

from django.core.management.base import BaseCommand

from monitoring.evaluation import evaluate, format_report


class Command(BaseCommand):
    help = "Measure detection quality against the synthetic ground truth (precision/recall/F1, ablation)."

    def add_arguments(self, parser):
        parser.add_argument("--write", help="write JSON results to this path")

    def handle(self, *args, **o):
        result = evaluate()
        self.stdout.write(format_report(result))
        if o["write"]:
            open(o["write"], "w").write(json.dumps(result, indent=2, default=str))
