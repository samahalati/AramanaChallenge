from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from core import i18n
from detection import llm
from detection.assistant import redteam
from monitoring.models import Alert
from monitoring.services.assistant import _alert_input

FAMILIES = ["model-output attack", "repair loop", "judge plumbing", "question", "evidence", "control",
            "judge: semantic attack", "judge: control", "model refusal", "model answers"]


class Command(BaseCommand):
    help = ("Red-team the LLM assistant. Default: deterministic layer with a scripted model/judge (no network, every alert, English + Persian). "
            "--live: ALSO run the semantic layer against the real provider from backend/.env (a few alerts; ~30 calls each).")

    def add_arguments(self, parser):
        parser.add_argument("--live", action="store_true", help="measure the judge and the model's refusals with the real provider")
        parser.add_argument("--alerts", type=int, default=2, help="alerts used by --live (default 2)")
        parser.add_argument("--write", help="write the report to this file")

    def handle(self, *args, **o):
        by_name: dict[str, list[bool]] = defaultdict(list)
        family: dict[str, str] = {}
        alerts = list(Alert.objects.all())
        if o["live"] and llm.provider_of(settings.LLM) == "none":
            raise SystemExit("--live needs LLM_PROVIDER / LLM_API_KEY (see backend/.env.example)")
        for lang in ("en", "fa"):
            token = i18n.set_lang(lang)
            try:
                terms = i18n.TERMS if lang == "fa" else None
                runs = [(a, redteam.run) for a in alerts] + ([(a, lambda x, l, t: redteam.live(x, settings.LLM, l, t)) for a in alerts[: o["alerts"]]] if o["live"] else [])
                for a, fn in runs:
                    for r in fn(_alert_input(a), lang, terms):
                        key = f"[{lang}] {r['name']}"
                        by_name[key].append(r["ok"])
                        family[key] = r["family"]
            finally:
                i18n._lang.reset(token)
        total, ok = sum(len(v) for v in by_name.values()), sum(sum(v) for v in by_name.values())
        lines = [f"LLM assistant guardrail evaluation  ({'deterministic + LIVE ' + settings.LLM['provider'] if o['live'] else 'deterministic, scripted model'}; "
                 f"{len(alerts)} real alerts, English + Persian, {total} checks)", "", f"OVERALL  {ok}/{total} safe  ({100 * ok / total:.1f}%)", ""]
        for fam in FAMILIES:
            names = [n for n in by_name if family[n] == fam]
            if names:
                lines += [f"{fam}  ({sum(sum(by_name[n]) for n in names)}/{sum(len(by_name[n]) for n in names)})"] + [f"  {'✔' if all(by_name[n]) else '✘'} {n:<58} {sum(by_name[n])}/{len(by_name[n])}" for n in names] + [""]
        report = "\n".join(lines)
        self.stdout.write(report)
        if o["write"]:
            open(o["write"], "w").write(report + "\n")
        if ok != total:
            raise SystemExit(1)
