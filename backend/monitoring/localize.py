"""Presentation-time localisation of an alert (the database keeps canonical English; see `detection.i18n`)."""
import re

from core import i18n
from detection import i18n as det


def subject_label(a, people: dict) -> str:
    p = people.get(a.subject_user_id)
    return f"{p['name']} (#{det.fa_digits(p['id'])}، {i18n.TERMS.get(p['role'], p['role'])})" if p else "چند حساب"


def breakdown(a) -> list[dict]:
    rows = det.localize_breakdown(a.score_breakdown)
    for r in rows:
        r["value"] = i18n.TERMS.get(r["value"], r["value"])        # e.g. a severity token such as "high"
    return rows


def explanation(a, label: str, rows: list[dict]) -> str:
    text = det.build_explanation(a.scenario, label, a.risk_score, a.risk_level, rows, capped="capped at Low" in a.explanation)
    m = re.search(r"Escalated by clinical supervisor (.+?): (.*?)\n\n", a.explanation, re.S)
    if m:                                                          # keep the supervisor's own words in the explanation
        head, rest = text.split("\n\n", 1)
        text = f"{head}\n\nدلیل ارجاع (سوپروایزر {m.group(1)}): {m.group(2)}\n\n{rest}"
    return text


def apply(a, d: dict, people: dict, detail: bool) -> dict:
    """Mutates and returns the serialised alert dict `d` in Persian."""
    label = subject_label(a, people)
    d["title"] = det.localize_title(a.scenario, label, a.score_breakdown, a.dedup_key, a.title)
    d["category_label"] = i18n.CATEGORY.get(a.category, d["category_label"])
    if detail:
        rows = breakdown(a)
        d |= {"score_breakdown": rows, "explanation": explanation(a, label, rows), "recommended_action": det.tr_text(a.recommended_action),
              "advisory": i18n.t(d["advisory"])}
    return d
