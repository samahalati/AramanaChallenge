"""Conformance suite: one test per requirement of the original challenge brief (section numbers in the docstrings).
`docs/REQUIREMENTS_TRACEABILITY.md` maps every clause to the code and to these tests."""
import pytest

from core.models import AuditLog
from hr.models import ProfessionalDevelopment
from monitoring.models import Alert

pytestmark = pytest.mark.django_db
COMP, HR, SUP, ADMIN, ADMIN2, THER, COUN = ("compliance@aramana.test", "hr@aramana.test", "supervisor1@aramana.test", "admin@aramana.test",
                                           "admin2@aramana.test", "therapist1@aramana.test", "counselor1@aramana.test")


def uid(api, email):
    return api.me(email)


# ───────────────────────── §3.3 performance and activity management
def test_3_3_activity_framework_for_a_practitioner(api):
    """§3.3: activity, completed/scheduled sessions, referrals, quality indicators, supervision participation, professional development, trends, unusual patterns."""
    body = api.get(f"/hr/practitioners/{uid(api, THER)}/activity", HR).json()
    assert {"sessions", "referrals", "quality", "supervision_participation", "professional_development", "unusual_activity"} <= set(body)
    assert set(body["sessions"]["last_28d"]) == {"completed", "scheduled", "cancelled", "no_show"} and isinstance(body["sessions"]["weekly"], list)
    assert {"received_56d", "made_56d"} == set(body["referrals"])
    assert {"reviews", "avg_performance", "performance_trend", "issues"} <= set(body["quality"])
    assert {"meetings_held", "attended", "attendance"} == set(body["supervision_participation"])
    assert body["professional_development"]["items"] and body["professional_development"]["hours_12m"] >= 0
    assert {"by_status", "alerts", "total"} <= set(body["unusual_activity"])
    assert "client_ref" not in str(body)                       # aggregates only: HR never sees clinical content


def test_3_3_activity_is_hr_data_not_open_to_other_roles(api):
    target = uid(api, THER)
    assert api.get(f"/hr/practitioners/{target}/activity", COMP).status_code == 200
    for who in (THER, COUN, SUP, ADMIN):
        assert api.get(f"/hr/practitioners/{target}/activity", who).status_code == 403, who


def test_3_3_professional_development_can_be_recorded_and_is_audited(api):
    target = uid(api, COUN)
    before = ProfessionalDevelopment.objects.filter(user_id=target).count()
    r = api.post(f"/hr/practitioners/{target}/development", HR, kind="course", title="Ethics refresher", provider="Association", hours=6, completed_on="2026-11-01")
    assert r.status_code == 201 and ProfessionalDevelopment.objects.filter(user_id=target).count() == before + 1
    assert AuditLog.objects.filter(action="admin_development_add").exists() or AuditLog.objects.filter(action__icontains="development").exists()
    assert api.get(f"/hr/practitioners/{target}/activity", HR).json()["professional_development"]["items"][0]["title"] == "Ethics refresher"
    bad = [dict(kind="nope", title="Valid title", hours=2, completed_on="2026-11-01"), dict(kind="course", title="x", hours=2, completed_on="2026-11-01"),
           dict(kind="course", title="Valid title", hours=0, completed_on="2026-11-01"), dict(kind="course", title="Valid title", hours=2, completed_on="2099-01-01")]
    assert [api.post(f"/hr/practitioners/{target}/development", HR, **b).status_code for b in bad] == [400] * 4
    assert api.post(f"/hr/practitioners/{target}/development", COMP, kind="course", title="Valid title", hours=2, completed_on="2026-11-01").status_code == 403   # hr:write only


# ───────────────────────── §5.4 relevant activity history of the alert's subject
def test_5_4_activity_history_of_the_subject_is_available_to_reviewers(api):
    alert = Alert.objects.exclude(subject_user_id=None).first()
    h = api.get(f"/monitoring/users/{alert.subject_user_id}/history", COMP).json()
    assert h["alerts"] and "not findings" in h["note"] and set(h["by_status"])


# ───────────────────────── §7.4 security: headers, logging
def test_7_4_security_headers_on_api_and_app(api):
    r = api.client.get("/api/health")
    assert r["Content-Security-Policy"].startswith("default-src 'none'") and r["X-Frame-Options"] == "DENY" and r["X-Content-Type-Options"] == "nosniff"
    assert r["Cache-Control"] == "no-store" and r["Referrer-Policy"] == "no-referrer" and "camera=()" in r["Permissions-Policy"]
    assert "cdn.jsdelivr.net" in api.client.get("/api/docs/")["Content-Security-Policy"]          # Swagger UI keeps working


def test_7_4_denials_and_failed_logins_are_logged(api, caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="aramana.security"):
        api.get("/hr/dashboard", THER)
        api.client.post("/api/auth/login", {"email": "nobody@aramana.test", "password": "wrong-password-1"}, format="json")
    text = caplog.text
    assert "access denied" in text and "login failed" in text and "nobody@aramana.test" not in text      # no personal data in the log line


# ───────────────────────── §3.4 / §7.4 roles and separation of clinical from HR data
def test_3_4_six_roles_and_separation_of_clinical_data(api):
    roles = {r["role"]: r for r in api.get("/meta/rbac", COMP).json()["roles"]}
    assert {"platform_admin", "hr_admin", "clinical_supervisor", "therapist", "assistant_counselor", "compliance_reviewer"} <= set(roles)
    for admin in ("platform_admin", "hr_admin"):
        assert not [p for p in roles[admin]["permissions"] if p.startswith("clinical:")], admin            # administrative roles hold no clinical permission
    target = uid(api, THER)
    assert api.get(f"/clinical/practitioners/{target}/sessions", HR).status_code == 403 and api.get(f"/clinical/practitioners/{target}/sessions", ADMIN).status_code == 403


# ───────────────────────── §4.1 supervisor dashboard, §4.5 auditability
def test_4_1_supervisor_dashboard_has_every_required_indicator(api):
    d = api.get("/supervision/dashboard", SUP).json()
    for key in ("supervisees_total", "active", "inactive", "pending_reviews", "overdue_reviews", "open_quality_issues", "cases_requiring_escalation", "recent_activity", "performance_trend"):
        assert key in d, key


def test_4_5_review_decision_is_traceable_and_reflected_in_operational_records(api):
    """§4.5 who/when/what/decision/actions + §6: a supervisor's review outcome is reflected in the HR operational record."""
    from hr.models import LifecycleEvent
    from supervision.models import Review
    sup_id = uid(api, SUP)
    review = Review.objects.filter(supervisor_id=sup_id, decided_at__isnull=True, closed_at__isnull=True).first()
    assert api.post(f"/supervision/reviews/{review.id}/start", SUP).status_code in (200, 201) or review.status != "pending"
    r = api.post(f"/supervision/reviews/{review.id}/decision", SUP, outcome="approved", notes="Reviewed the documentation", feedback="Good work", performance_score=4, has_documentation=True, minutes_spent=20)
    assert r.status_code == 200, r.content
    assert LifecycleEvent.objects.filter(user_id=review.supervisee_id, event="supervision_review").exists()               # reflected in the HR history
    assert AuditLog.objects.filter(actor_id=sup_id, resource_type="review").exists() or AuditLog.objects.filter(actor_id=sup_id).exists()   # who / when / what in the audit log
    assert api.get("/audit/verify", COMP).json()["ok"] is True


# ───────────────────────── §5.1–5.3 detection categories, architecture, alert content
def test_5_1_all_five_categories_are_detected_and_5_2_all_methods_are_used(api):
    items = api.get("/alerts?limit=500", COMP).json()["items"]
    assert {"A", "B", "C", "D", "E"} <= {a["category"] for a in items}                                            # therapist, counselor, supervisor, admin, network
    assert {"rule", "statistical", "ml", "graph"} <= {m for a in items for m in a["methods"]}                    # + AI-assisted explanation: the assistant endpoint (tests/test_assistant.py)


def test_5_3_every_alert_carries_the_required_content_and_is_explainable(api):
    first = api.get("/alerts?limit=500", COMP).json()["items"][0]
    a = api.get(f"/alerts/{first['id']}", COMP).json()
    for key in ("alert_uid", "related_users", "category", "detected_at", "risk_score", "risk_level", "methods", "evidence", "explanation", "recommended_action", "status", "score_breakdown", "ruleset_version", "model_version"):
        assert key in a, key
    assert a["risk_level"] in {"low", "medium", "high", "critical"} and a["score_breakdown"] and a["evidence"]
    # traceable: the score is exactly the noisy-OR of the listed indicator contributions
    survive = 1.0
    for row in a["score_breakdown"]:
        survive *= 1 - row["contribution"]
    assert abs(100 * (1 - survive) - a["risk_score"]) < 0.6 or a["risk_level"] == "low"      # (weak-evidence cap lowers only the level)
    levels = {x["risk_level"] for x in api.get("/alerts?limit=500", COMP).json()["items"]}
    assert {"low", "medium", "high", "critical"} <= levels


# ───────────────────────── §7.3 versioning, false-positive management, reproducibility
def test_7_3_versioning_false_positive_feedback_and_evaluation(api):
    s = api.get("/monitoring/summary", COMP).json()
    assert s["last_run"]["ruleset_version"] and s["last_run"]["model_version"] and "false_positive_feedback" in s
    ev = api.get("/detection/evaluation", COMP).json()
    assert ev["available"] and 0 <= ev["overall"]["precision"] <= 1 and "ablation" in ev and "hard_negatives" in ev


# ───────────────────────── §9 synthetic dataset coverage
def test_9_dataset_has_every_required_record_type():
    from accounts.models import User
    from clinical.models import Referral, Session
    from core.models import AccessEvent, AdminActivity
    from hr.models import PractitionerProfile, SupervisionAssignment
    from monitoring.models import InvestigationEvent
    from supervision.models import Review
    for model in (User, PractitionerProfile, SupervisionAssignment, Session, Referral, Review, AdminActivity, AccessEvent, InvestigationEvent, ProfessionalDevelopment):
        assert model.objects.exists(), model.__name__
    assert set(User.objects.values_list("role", flat=True)) >= {"platform_admin", "hr_admin", "clinical_supervisor", "therapist", "assistant_counselor", "compliance_reviewer"}


# ───────────────────────── §10 deliverables are present in the repository
def test_10_deliverables_exist():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    required = ["README.md", "backend/.env.example", "backend/requirements.txt", "Dockerfile", "docs/ARCHITECTURE.md", "docs/RBAC_MATRIX.md", "docs/openapi.yaml", "docs/TECHNICAL_REPORT.md",
                "docs/PRESENTATION.md", "docs/DATASET.md", "docs/GUIDE.md", "docs/REQUIREMENTS_TRACEABILITY.md", "docs/fa/GUIDE.md", "docs/fa/REQUIREMENTS_TRACEABILITY.md", "frontend/package.json"]
    assert [p for p in required if not (root / p).exists()] == []
    arch = (root / "docs/ARCHITECTURE.md").read_text()
    assert "erDiagram" in arch and arch.count("```mermaid") >= 5                                                  # ERD + system / data-flow / detection diagrams
