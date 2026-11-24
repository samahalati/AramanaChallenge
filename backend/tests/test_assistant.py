"""Guarded LLM investigation assistant: guardrail units, privacy of the prompt, permissions, persistence, red-team over every real alert."""
import json

import pytest

from accounts.models import User
from core.models import AuditLog
from detection.assistant import fallback, redteam
from detection.assistant import investigator
from detection.assistant.guardrails import CHECKS, validate, violations
from detection.assistant.pack import build_pack, clean
from monitoring.models import Alert, AssistantExchange, InvestigationEvent
from monitoring.services import assistant as svc

pytestmark = pytest.mark.django_db
COMP, HR, SUP1, ADMIN, ADMIN2 = "compliance@aramana.test", "hr@aramana.test", "supervisor1@aramana.test", "admin@aramana.test", "admin2@aramana.test"
LLM_ON = {"provider": "groq", "api_key": "test", "model": "", "base_url": ""}
CLEAN, FLAGGED, REFUSAL = redteam.CLEAN, redteam.FLAGGED, json.dumps({"answer": "x", "cites": [], "insufficient_evidence": True, "refused": True})


def alert_input(a: Alert) -> dict:
    return svc._alert_input(a)


def first_alert(api, who=COMP, **q):
    return api.get("/alerts?limit=500&" + "&".join(f"{k}={v}" for k, v in q.items()), who).json()["items"][0]


# ------------------------------------------------------------------ pack: pseudonymisation + injection defence
def test_pack_is_pseudonymised_and_sanitised():
    alert = {"category": "D", "scenario": "failed_login_burst", "domain": "security", "risk_score": 70.0, "risk_level": "high", "methods": ["rule"], "subject_user_id": 9,
             "score_breakdown": [{"label": "Failed logins", "value": 14, "threshold": ">= 8", "weight": 0.7, "strength": 0.9, "points": 63.0, "method": "rule", "note": "from 2 addresses"}],
             "evidence": [{"type": "login_failed", "ip": "203.0.113.50", "client_ref": "C-0042", "path": "/x \x07 mail bob@corp.com"}]}
    pack = build_pack(alert)
    text = pack.render()
    assert "C-0042" not in text and "bob@corp.com" not in text and "203.0.113.50" not in text and "203.0.113.x" in text and "\x07" not in text
    assert pack.flags >= 1
    assert {"F1", "I1", "E1"} <= set(pack.items) and any(k.startswith("B") for k in pack.items)
    assert clean("x" * 500)[0].endswith("…") and len(clean("x" * 500)[0]) <= 140


# ------------------------------------------------------------------ each guardrail, in isolation
@pytest.fixture
def pack_and_alert(db):
    a = Alert.objects.get(scenario="admin_out_of_scope")
    return build_pack(alert_input(a)), alert_input(a)


def checks_failed(kind, data, pack, names=()):
    _, res = validate(kind, json.dumps(data) if not isinstance(data, str) else data, pack, set(names))
    return {c for c, v in res.items() if v}


def test_each_deterministic_guardrail_fires(pack_and_alert):
    pack, alert = pack_and_alert
    base = fallback.briefing(pack, alert["scenario"], alert["recommended_action"])
    assert checks_failed("briefing", base, pack) == set()                                   # control: the deterministic reply passes everything
    for mutate, expected in [
        (lambda d: d.update(summary=d["summary"] + " In 71.7% of cases."), "numbers"),
        (lambda d: d["findings"][0].update(cites=[]), "citations"),
        (lambda d: d["findings"][0].update(cites=["E99"]), "citations"),
        (lambda d: d["benign_explanations"].append("mail jane@x.org"), "identity"),
        (lambda d: d["benign_explanations"].append("see C-0042"), "identity"),
        (lambda d: d.update(verification_steps=["one"]), "schema"),
    ]:
        d = json.loads(json.dumps(base))
        mutate(d)
        assert expected in checks_failed("briefing", d, pack), expected
    assert "schema" in checks_failed("briefing", "plain prose, not json", pack)
    assert "identity" in checks_failed("briefing", {**base, "summary": "Ask Alice Example."}, pack, names={"Alice Example"})


def test_prompt_carries_the_rules_instead_of_keyword_lists(pack_and_alert):
    pack, _ = pack_and_alert
    ask_system = investigator._messages("answer", pack, "Should we suspend them?")[0]["content"]
    assert "REFUSE" in ask_system and "sanctions" in ask_system and "English" in ask_system and "<evidence>" in investigator._messages("answer", pack, "q")[1]["content"]
    assert "REFUSE" not in investigator._messages("briefing", pack, None)[0]["content"]


# ------------------------------------------------------------------ red-team: every real alert, every attack
def test_redteam_suite_blocks_every_attack_on_every_alert():
    results = [(a.alert_uid, r) for a in Alert.objects.all() for r in redteam.run(alert_input(a))]
    assert len(results) >= 12 * 25
    failed = [(uid, r["name"], r["outcome"]) for uid, r in results if not r["ok"]]
    assert failed == []


def test_fallback_always_passes_guardrails_on_all_alerts():
    for a in Alert.objects.all():
        pack = build_pack(alert_input(a))
        for kind, data in (("briefing", fallback.briefing(pack, a.scenario, a.recommended_action)), ("answer", fallback.answer(pack))):
            assert not any(validate(kind, json.dumps(data), pack, set())[1].values()), (a.alert_uid, kind)


# ------------------------------------------------------------------ API: offline (no provider) path
def test_briefing_offline_is_grounded_persisted_and_audited(api):
    a = first_alert(api)
    r = api.post(f"/alerts/{a['id']}/ai-summary", COMP)
    assert r.status_code == 200
    d = r.json()
    assert d["provider"] == "template" and d["kind"] == "briefing" and not d["refused"] and d["advisory"].startswith("AI output is advisory")
    assert set(d["guardrails"]["output"]["checks"]) == set(CHECKS) and set(d["guardrails"]["output"]["checks"].values()) == {"pass"}
    assert d["citations"] and all(k[0] in "FIEBA" for k in d["citations"])
    assert AssistantExchange.objects.filter(alert_id=a["id"], kind="briefing").count() == 1
    assert InvestigationEvent.objects.filter(alert_id=a["id"], action="ai_assistant").exists()
    assert AuditLog.objects.filter(action="alert_ai_briefing", resource_id=a["alert_uid"]).exists()


def test_ask_without_a_model_answers_from_evidence_and_is_recorded(api):
    a = first_alert(api)
    ok = api.post(f"/alerts/{a['id']}/assistant", COMP, question="Why is the score so high?").json()
    assert not ok["refused"] and ok["content"]["cites"] and ok["citations"]
    offline = api.post(f"/alerts/{a['id']}/assistant", COMP, question="Should we suspend this practitioner?").json()
    assert offline["provider"] == "template" and not offline["refused"] and "No model answer" in offline["content"]["answer"]      # no model -> evidence only, never a decision
    assert len(api.get(f"/alerts/{a['id']}/assistant", COMP).json()) == 2
    assert api.post(f"/alerts/{a['id']}/assistant", COMP, question="x").status_code == 400                    # too short


# ------------------------------------------------------------------ API: with a (scripted) model
@pytest.fixture
def model(monkeypatch, settings):
    settings.LLM = LLM_ON
    calls: list[str] = []

    def install(*replies):
        monkeypatch.setattr(svc, "TRANSPORT", redteam.scripted(list(replies), calls))
        return calls
    return install


def test_prompt_never_contains_names_emails_or_client_refs(api, model):
    a = Alert.objects.get(scenario="session_overlap")
    good = json.dumps(redteam.good(alert_input(a)))
    calls = model(good, CLEAN)
    assert api.post(f"/alerts/{a.id}/ai-summary", COMP).json()["provider"] == "groq"
    sent = " ".join(calls)
    assert calls and "C-0" not in sent and "@" not in sent.replace("@@", "")
    for u in User.objects.all():
        assert u.full_name not in sent and u.email not in sent


def test_judged_reply_is_repaired_or_replaced(api, model):
    a = Alert.objects.get(scenario="admin_out_of_scope")
    good = json.dumps(redteam.good(alert_input(a)))
    bad = json.dumps({**redteam.good(alert_input(a)), "summary": "This looks like something that should be handled harshly."})   # no keyword a regex could know: the judge decides
    model(bad, FLAGGED, good, CLEAN)                                                       # 1st rejected by the judge, retry accepted
    r = api.post(f"/alerts/{a.id}/ai-summary", COMP).json()
    assert r["provider"] == "groq" and r["guardrails"]["output"]["attempts"] == 2 and not r["guardrails"]["output"]["fallback_used"]
    model(bad, FLAGGED, bad, FLAGGED)                                                      # rejected twice -> deterministic fallback
    r = api.post(f"/alerts/{a.id}/ai-summary", COMP).json()
    assert r["provider"] == "template(fallback)" and r["guardrails"]["output"]["fallback_reason"] == "guardrail_rejected"
    assert any(v.startswith("tone:") for v in r["guardrails"]["output"]["rejected_violations"])
    assert "harshly" not in json.dumps(r["content"])


def test_no_judge_verdict_means_no_model_text(api, model):
    a = Alert.objects.get(scenario="admin_out_of_scope")
    model(json.dumps(redteam.good(alert_input(a))), "HTTP500")                               # the judge is down -> fail closed
    r = api.post(f"/alerts/{a.id}/ai-summary", COMP).json()
    assert r["provider"] == "template(fallback)" and r["guardrails"]["output"]["fallback_reason"] == "provider_error"


def test_evidence_is_redacted_and_a_model_refusal_is_shown_as_refusal(api, model):
    a = Alert.objects.get(scenario="admin_out_of_scope")
    a.evidence = [{"type": "access_denied", "path": "/clinical/x mail bob@corp.com", "ip": "203.0.113.50"}] + a.evidence
    a.save()
    calls = model(json.dumps(redteam.good(alert_input(a))), CLEAN)
    r = api.post(f"/alerts/{a.id}/ai-summary", COMP).json()
    assert r["guardrails"]["input"]["redacted"] >= 1 and "bob@corp.com" not in " ".join(calls) and "203.0.113.50" not in " ".join(calls)
    model(REFUSAL, CLEAN)
    no = api.post(f"/alerts/{a.id}/assistant", COMP, question="Is the admin guilty of fraud?").json()
    assert no["refused"] and no["provider"] == "groq" and no["guardrails"]["input"]["refused_reason"] == "x"


def test_provider_outage_falls_back_cleanly(api, model):
    a = first_alert(api)
    model("HTTP500")
    r = api.post(f"/alerts/{a['id']}/ai-summary", COMP).json()
    assert r["provider"] == "template(fallback)" and r["guardrails"]["output"]["fallback_reason"] == "provider_error" and r["content"]["summary"]


# ------------------------------------------------------------------ API: permissions, visibility, limits, side effects
def test_only_authorised_investigators_may_use_the_assistant(api):
    a = Alert.objects.get(scenario="session_overlap")
    for who in (HR, "therapist1@aramana.test", "counselor1@aramana.test"):
        assert api.post(f"/alerts/{a.id}/ai-summary", who).status_code == 403, who
    assert api.post(f"/alerts/{a.id}/assistant", HR, question="Why is the score high?").status_code == 403
    sec = Alert.objects.get(scenario="admin_out_of_scope")
    assert api.post(f"/alerts/{sec.id}/ai-summary", ADMIN).status_code == 200            # platform admin may investigate SECURITY alerts about someone else
    assert api.post(f"/alerts/{a.id}/ai-summary", ADMIN).status_code == 404              # but cannot even see an operational alert
    assert api.post(f"/alerts/{sec.id}/ai-summary", ADMIN2).status_code == 404           # and nobody gets AI help on an alert about themselves


def test_rate_limit(api, monkeypatch):
    monkeypatch.setattr(svc, "RATE_LIMIT_PER_HOUR", 2)
    a = first_alert(api)
    assert [api.post(f"/alerts/{a['id']}/ai-summary", COMP).status_code for _ in range(3)] == [200, 200, 429]


def test_assistant_never_changes_state(api):
    a = Alert.objects.order_by("-risk_score").first()
    before = (a.status, a.risk_score, a.risk_level, set(User.objects.values_list("id", "status", "role")))
    api.post(f"/alerts/{a.id}/ai-summary", COMP)
    api.post(f"/alerts/{a.id}/assistant", COMP, question="What should I check next?")
    a.refresh_from_db()
    assert before == (a.status, a.risk_score, a.risk_level, set(User.objects.values_list("id", "status", "role")))
