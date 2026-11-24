"""Deterministic fallback: same output schema as the model, built ONLY from the evidence pack, so it passes every guardrail by construction
(a test proves that, in both languages). Used when no provider is configured, the provider fails, or the model's reply is rejected twice."""
from __future__ import annotations

from detection import i18n as fa
from detection.assistant.pack import Pack
from detection.explain import SCENARIO_TEXT

TEXT = {"en": {"steps": ["Verify the cited records against the source logs before drawing any conclusion.", "Ask the subject for context and document their answer before any decision."],
               "disclaimer": "This is an automated, advisory signal and not evidence of wrongdoing.", "no_detail": "No indicator detail is available for this alert.",
               "fallback_benign": "a legitimate explanation not captured in the data", "indicator": "indicator ",
               "lead": "No model answer is available, so the question was not interpreted. The key facts in the evidence: "},
        "fa": {"steps": ["پیش از هر نتیجه‌گیری، رکوردهای ارجاع‌شده را با گزارش‌های منبع تطبیق دهید.", "پیش از هر تصمیم، از فرد توضیح بخواهید و پاسخ او را ثبت کنید."],
               "disclaimer": "این یک سیگنال خودکار و مشورتی است و مدرکِ تخلف نیست.", "no_detail": "جزئیاتِ شاخص برای این هشدار در دسترس نیست.",
               "fallback_benign": "توضیحی مشروع که در داده ثبت نشده است", "indicator": "شاخص ",
               "lead": "پاسخ مدل در دسترس نیست، بنابراین پرسش تفسیر نشد. مهم‌ترین واقعیت‌های شواهد: "}}


def _indicator_ids(pack: Pack) -> list[str]:
    return sorted((k for k in pack.items if k.startswith("I")), key=lambda k: -pack.points.get(k, 0.0))


def briefing(pack: Pack, scenario: str, recommended_action: str = "") -> dict:
    tx, farsi = TEXT[pack.lang], pack.lang == "fa"
    top = _indicator_ids(pack)[:3]
    summary = f"{pack.items['F1']}. {tx['disclaimer']}"
    findings = [{"text": pack.items[i].replace(tx["indicator"], "", 1)[:290], "cites": [i]} for i in top] or [{"text": tx["no_detail"], "cites": ["F1"]}]
    benign = (fa.SCENARIOS.get(scenario, {}).get("benign") if farsi else SCENARIO_TEXT.get(scenario, ("", []))[1]) or [tx["fallback_benign"]]
    steps = ([recommended_action[:240]] if recommended_action else []) + tx["steps"]
    return {"summary": summary[:590], "findings": findings, "benign_explanations": [b[:240] for b in benign[:3]], "verification_steps": steps[:4]}


def answer(pack: Pack, question: str = "") -> dict:
    """No model available: show the strongest facts of the evidence, cited. (The question is not interpreted – that needs a model.)"""
    hits = ["F1"] + _indicator_ids(pack)[:3]
    body = " ".join(f"{pack.items[k][:200]} [{k}]." for k in hits)
    return {"answer": f"{TEXT[pack.lang]['lead']}{body}"[:690], "cites": hits, "insufficient_evidence": False}
