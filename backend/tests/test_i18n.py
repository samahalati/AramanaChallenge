"""Persian / English presentation: the database stays canonical English, the API localises per request (Accept-Language),
numbers and scores never change with the language, and the LLM guardrails hold in Persian too."""
import json
import re

import pytest

from core import i18n
from detection import i18n as det_i18n
from detection.assistant import fallback, redteam
from detection.assistant import investigator
from detection.assistant.guardrails import CHECKS, validate, violations
from detection.assistant.pack import build_pack, fold
from monitoring.models import Alert
from monitoring.services import assistant as svc

pytestmark = pytest.mark.django_db
COMP = "compliance@aramana.test"
PERSIAN = re.compile(r"[؀-ۿ]")


def get(api, path, who=None, lang="fa"):
    extra = {"HTTP_AUTHORIZATION": f"Bearer {api.token(who)}"} if who else {}
    return api.client.get(f"/api{path}", HTTP_ACCEPT_LANGUAGE=lang, **extra)


def test_language_negotiation_and_labels(api):
    fa, en = get(api, "/meta/labels"), get(api, "/meta/labels", lang="en")
    assert fa["Content-Language"] == "fa" and en["Content-Language"] == "en"
    assert fa.json()["terms"]["critical"] == "بحرانی" and en.json()["terms"] == {}
    assert i18n.parse_accept_language("fa-IR,fa;q=0.9,en;q=0.5") == "fa" and i18n.parse_accept_language("de") == "en" and i18n.parse_accept_language(None) == "en"


def test_digits_roundtrip_and_decimal_separator():
    assert det_i18n.fa_digits("risk 12.5 of 100") == "risk ۱۲٫۵ of ۱۰۰" and det_i18n.fa_digits("ver 1.2.3") == "ver ۱.۲.۳"
    assert det_i18n.en_digits("۱۲٫۵") == "12.5" and fold("نمی‌کند ۴۲") == "نمیکند 42"


def test_alert_is_persian_but_numbers_and_state_are_identical(api):
    row = api.get("/alerts?limit=50", COMP).json()["items"][0]
    en = get(api, f"/alerts/{row['id']}", COMP, "en").json()
    fa = get(api, f"/alerts/{row['id']}", COMP, "fa").json()
    assert PERSIAN.search(fa["title"]) and PERSIAN.search(fa["explanation"]) and PERSIAN.search(fa["recommended_action"]) and PERSIAN.search(fa["advisory"])
    assert (fa["risk_score"], fa["risk_level"], fa["status"], fa["scenario"]) == (en["risk_score"], en["risk_level"], en["status"], en["scenario"])
    assert [b["points"] for b in fa["score_breakdown"]] == [b["points"] for b in en["score_breakdown"]]
    assert all(b.get("method_label") for b in fa["score_breakdown"])
    assert Alert.objects.get(id=row["id"]).title[:25].isascii()          # storage is canonical English (only the pseudonymous person names are Persian data)


def test_every_alert_explanation_is_fully_persian(api):
    """No English sentence fragments may leak into a Persian explanation (only product/algorithm names and identifiers)."""
    allowed = {"isolation", "forest", "alert", "case", "caseid"}
    for a in api.get("/alerts?limit=200", COMP).json()["items"]:
        d = get(api, f"/alerts/{a['id']}", COMP).json()
        words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", d["title"] + " " + d["explanation"] + " " + d["recommended_action"])} - allowed
        assert not words, (a["scenario"], words)


def test_errors_are_translated(api):
    r = get(api, "/hr/dashboard", "therapist1@aramana.test")
    assert r.status_code == 403 and PERSIAN.search(json.dumps(r.json(), ensure_ascii=False))
    assert not PERSIAN.search(json.dumps(get(api, "/hr/dashboard", "therapist1@aramana.test", "en").json()))


# ------------------------------------------------------------------ Persian LLM assistant
def fa_pack(alert: Alert):
    token = i18n.set_lang("fa")
    try:
        data = svc._alert_input(alert)
        return data, build_pack(data, "fa", i18n.TERMS)
    finally:
        i18n._lang.reset(token)


def test_persian_pack_is_pseudonymised_and_numbers_are_latin():
    alert = Alert.objects.first()
    data, pack = fa_pack(alert)
    text = pack.render()
    assert pack.lang == "fa" and PERSIAN.search(text) and not re.search(r"[۰-۹]", text) and "C-" not in text and "@" not in text
    assert pack.points and all(k.startswith("I") for k in pack.points)


def test_persian_fallback_passes_every_guardrail_for_every_alert():
    for alert in Alert.objects.all():
        data, pack = fa_pack(alert)
        b = fallback.briefing(pack, alert.scenario, data["recommended_action"])
        a = fallback.answer(pack, "چرا امتیاز بالاست و کدام شواهد آن را پشتیبانی می‌کنند؟")
        for kind, content in (("briefing", b), ("answer", a)):
            _, res = validate(kind, json.dumps(content, ensure_ascii=False), pack, {"هانیه رحیمی"})
            assert not violations(res), (alert.scenario, kind, violations(res))
        assert PERSIAN.search(b["summary"]) and a["cites"]


def test_persian_prompt_asks_for_persian_and_refusals():
    _, pack = fa_pack(Alert.objects.first())
    system = investigator._messages("answer", pack, "آیا باید این متخصص را تعلیق کنیم؟")[0]["content"]
    assert "Persian" in system and "REFUSE" in system


def test_persian_deterministic_guardrails_and_numbers():
    alert = Alert.objects.first()
    data, pack = fa_pack(alert)
    good = redteam.good(data, "fa", i18n.TERMS)
    assert not violations(validate("briefing", json.dumps(good, ensure_ascii=False), pack)[1])
    persian_digits = json.loads(json.dumps(good, ensure_ascii=False))
    persian_digits["summary"] = det_i18n.fa_digits(persian_digits["summary"].replace("[", "").replace("]", ""))
    assert not [v for v in violations(validate("briefing", json.dumps(persian_digits, ensure_ascii=False), pack)[1]) if v.startswith("numbers")]
    for name, check, reply in redteam.attacks_fa(data, i18n.TERMS):
        if check in redteam.DETERMINISTIC and name not in redteam.JUDGED_ONLY:
            assert any(v.startswith(check + ":") for v in violations(validate("briefing", reply, pack, redteam.NAMES)[1])), name


def test_service_serves_persian_briefing_and_stays_advisory(api):
    row = api.get("/alerts?limit=50", COMP).json()["items"][0]
    before = Alert.objects.get(id=row["id"])
    r = api.client.post(f"/api/alerts/{row['id']}/ai-summary", HTTP_AUTHORIZATION=f"Bearer {api.token(COMP)}", HTTP_ACCEPT_LANGUAGE="fa", format="json")
    assert r.status_code == 200
    body = r.json()
    assert PERSIAN.search(body["content"]["summary"]) and PERSIAN.search(body["advisory"]) and all(v == "pass" for v in body["guardrails"]["output"]["checks"].values())
    after = Alert.objects.get(id=row["id"])
    assert (after.risk_score, after.status) == (before.risk_score, before.status) and set(body["guardrails"]["output"]["checks"]) == set(CHECKS)


def test_seed_catalogs_exist_for_both_languages():
    """`seed_demo --lang en` once crashed because the English name lists were lost: both languages must be complete and parallel."""
    from seed import generate as g
    assert len(g.FIRST) > 20 and len(g.LAST) > 10 and len(g.FIRST_FA) > 20 and len(g.LAST_FA) > 10
    assert set(g.TEXT["en"]) == set(g.TEXT["fa"])
