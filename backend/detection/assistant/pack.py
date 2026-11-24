"""Evidence pack: the ONLY thing a model ever sees.

* pseudonymised – no names, e-mails, client references; users appear as "#<id>"; IPs lose their last octet
* sanitised     – control characters stripped, fields truncated, e-mails removed (instruction-like text is handled by the prompt: evidence is DATA; the judge checks obedience)
* citable       – every fact has an ID (F1.., I1.., E1..) so answers can be checked against it
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from detection import i18n as fa
from detection.explain import SCENARIO_TEXT

MAX_EVIDENCE_ROWS, MAX_FIELD = 25, 140
CLIENT_KEYS = {"client_ref", "client_a", "client_b"}
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
IP = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def clean(text, limit: int = MAX_FIELD) -> tuple[str, int]:
    """Returns (safe text, number of neutralisations)."""
    s, flags = CONTROL.sub(" ", str(text)), 0
    s, n = EMAIL.subn("[e-mail removed]", s)
    flags += n
    s = IP.sub(r"\1.x", s)
    return (s[: limit - 1] + "…" if len(s) > limit else s), flags


@dataclass
class Pack:
    items: dict[str, str] = field(default_factory=dict)   # id -> text
    points: dict[str, float] = field(default_factory=dict)   # indicator id -> points (for ranking in the fallback)
    lang: str = "en"
    level: str = "low"
    flags: int = 0                                          # neutralisations applied to untrusted fields
    omitted: int = 0

    def render(self) -> str:
        return "\n".join(f"{k}: {v}" for k, v in self.items.items())

    def vocabulary(self) -> set[str]:
        return {w for t in self.items.values() for w in re.findall(r"[^\W\d_]{4,}", fold(t).lower())}


def _fields(row: dict, terms: dict) -> tuple[str, int]:
    parts, flags = [], 0
    for k, v in row.items():
        if k == "type" or k in CLIENT_KEYS or v is None:
            continue
        text, n = clean(v if not isinstance(v, (dict, list)) else str(v))
        parts.append(f"{terms.get(k, k)}={terms.get(text, text)}")
        flags += n
    return f"{terms.get(row.get('type'), row.get('type', 'record'))}: " + "؛ ".join(parts) if terms else f"{row.get('type', 'record')}: " + "; ".join(parts), flags


FOLD_DROP = re.compile("[\u200b-\u200f\u2060\ufeff\u064b-\u065f\u0640]")   # zero-width chars (incl. ZWNJ), Arabic diacritics, tatweel


def fold(text: str) -> str:
    """Canonical form for matching: NFKC, Latin digits, Persian letter variants unified, invisible characters removed."""
    return fa.en_digits(FOLD_DROP.sub("", unicodedata.normalize("NFKC", str(text)))).replace("ي", "ی").replace("ك", "ک")


def build_pack(alert: dict, lang: str = "en", terms: dict | None = None) -> Pack:
    """`alert` keys used: category, scenario, domain, risk_score, risk_level, methods, subject_user_id, score_breakdown, evidence, window_*, recommended_action.
    For lang="fa" the caller passes an already-localised breakdown/action; digits are normalised back to Latin so number checks stay exact."""
    terms, pack = terms or {}, Pack(level=alert["risk_level"], lang=lang)
    farsi = lang == "fa"
    subject = (f"کاربر #{alert['subject_user_id']}" if farsi else f"user #{alert['subject_user_id']}") if alert.get("subject_user_id") else ("چند حساب" if farsi else "several accounts")
    if farsi:
        methods = "، ".join(fa.METHOD.get(m, m) for m in alert.get("methods", []))
        pack.items["F1"] = (f"دسته {alert['category']}، سناریو {fa.SCENARIOS.get(alert['scenario'], {}).get('name', alert['scenario'])}، حوزه {terms.get(alert['domain'], alert['domain'])}، موضوع {subject}، "
                            f"ریسک {alert['risk_score']:.0f}/100 ({fa.LEVEL[alert['risk_level']]})، روش‌های تشخیص: {methods}")
    else:
        pack.items["F1"] = (f"category {alert['category']}, scenario {alert['scenario'].replace('_', ' ')}, domain {alert['domain']}, subject {subject}, "
                            f"risk {alert['risk_score']:.0f}/100 ({alert['risk_level']}), detection methods: {', '.join(alert.get('methods', []))}")
    if alert.get("window_start") and alert.get("window_end"):
        pack.items["F2"] = (f"بازه‌ی تحلیل {str(alert['window_start'])[:10]} تا {str(alert['window_end'])[:10]}" if farsi
                            else f"analysis window {str(alert['window_start'])[:10]} to {str(alert['window_end'])[:10]}")
    for i, b in enumerate(alert["score_breakdown"], 1):
        label, f1 = clean(b["label"])
        note, f2 = clean(b.get("note") or "")
        pack.flags += f1 + f2
        value, ref = clean(b["value"])[0], clean(b["threshold"])[0]
        pack.points[f"I{i}"] = float(b["points"])
        pack.items[f"I{i}"] = (f"شاخص {label}: مقدار={value}، مرجع={ref}، وزن={b['weight']}، قدرت={b['strength']}، امتیاز={b['points']}" + (f"، یادداشت={note}" if note else "") if farsi else
                               f"indicator {label}: value={value}, reference={ref}, weight={b['weight']}, strength={b['strength']}, points={b['points']}" + (f", note={note}" if note else ""))
    rows = alert.get("evidence", [])
    for i, row in enumerate(rows[:MAX_EVIDENCE_ROWS], 1):
        text, n = _fields(row, terms if farsi else {})
        pack.items[f"E{i}"], pack.flags = text, pack.flags + n
    benign = fa.SCENARIOS.get(alert["scenario"], {}).get("benign", []) if farsi else SCENARIO_TEXT.get(alert["scenario"], ("", []))[1]
    for i, text in enumerate(benign, 1):                      # generic knowledge, labelled as such (not evidence about this subject)
        pack.items[f"B{i}"] = (f"توضیح بی‌خطرِ ممکن برای بررسی (عمومی برای این سناریو، مشاهده‌نشده): {text}" if farsi
                               else f"possible benign explanation to rule out (generic for this scenario, not observed): {text}")
    if alert.get("recommended_action"):
        pack.items["A1"] = (f"اقدام پیشنهادیِ تحقیق: {clean(alert['recommended_action'], 260)[0]}" if farsi else f"recommended investigation action: {clean(alert['recommended_action'], 260)[0]}")
    pack.omitted = max(0, len(rows) - MAX_EVIDENCE_ROWS)
    if pack.omitted:
        pack.items["F3"] = f"{pack.omitted} ردیف شواهد دیگر نمایش داده نشده" if farsi else f"{pack.omitted} further evidence rows not shown"
    if farsi:   # models and the numeric guardrail work on Latin digits
        pack.items = {k: fa.en_digits(v) for k, v in pack.items.items()}
    return pack
