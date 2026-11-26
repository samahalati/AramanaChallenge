"""RBAC / security: clinical vs HR separation, scoping, redaction, audit chain, lockout, token handling."""
import pytest

from accounts.models import User
from core.audit import verify_chain
from core.models import AccessEvent, AuditLog
from core.rbac import ROLE_PERMISSIONS

pytestmark = pytest.mark.django_db
HR, ADMIN, COMP = "hr@aramana.test", "admin@aramana.test", "compliance@aramana.test"


def test_permission_matrix_invariants():
    for role in ("hr_admin", "platform_admin"):
        assert not any(p.startswith("clinical:") for p in ROLE_PERMISSIONS[role])          # administrative roles hold no clinical access
    assert "hr:write" not in ROLE_PERMISSIONS["platform_admin"] and "users:manage" not in ROLE_PERMISSIONS["hr_admin"]
    assert "alerts:investigate" not in ROLE_PERMISSIONS["clinical_supervisor"]
    assert not any(p.startswith(("alerts", "hr", "clinical:read:alerted")) for p in ROLE_PERMISSIONS["therapist"])


def test_requires_authentication(api):
    for path in ("/hr/practitioners", "/alerts", "/supervision/dashboard", "/audit"):
        assert api.get(path).status_code == 401
    assert api.client.get("/api/alerts", HTTP_AUTHORIZATION="Bearer not.a.token").status_code == 401


def test_login_does_not_enumerate_accounts_and_locks_out(api):
    r1 = api.post("/auth/login", email="nobody@aramana.test", password="x")
    r2 = api.post("/auth/login", email="therapist20@aramana.test", password="wrong-password")
    assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()
    for _ in range(6):
        api.post("/auth/login", email="therapist21@aramana.test", password="bad")
    assert api.post("/auth/login", email="therapist21@aramana.test", password="Demo!2345").status_code == 403   # locked
    assert AccessEvent.objects.filter(event="login_failed", email_attempted="therapist21@aramana.test").exists()


def test_suspended_account_token_stops_working(api):
    assert api.get("/referrals/mine", "counselor6@aramana.test").status_code == 200
    assert api.patch(f"/admin/users/{api.me('counselor6@aramana.test')}/status", ADMIN, status="suspended", reason="security test").status_code == 200
    assert api.get("/referrals/mine", "counselor6@aramana.test").status_code == 401


def test_admin_roles_cannot_read_clinical_data_and_denials_are_recorded(api):
    t = api.me("therapist1@aramana.test")
    before = AccessEvent.objects.filter(event="access_denied").count()
    for who in (HR, ADMIN):
        assert api.get(f"/clinical/practitioners/{t}/sessions", who).status_code == 403
    assert AccessEvent.objects.filter(event="access_denied").count() == before + 2
    last = AccessEvent.objects.filter(event="access_denied").latest("id")
    assert last.permission and last.path.endswith("/sessions") and last.user_id
    assert AuditLog.objects.filter(action="access_denied", outcome="denied").exists()


def test_admin_cannot_modify_hr_records_or_see_alerts_outside_security(api):
    t = api.me("therapist1@aramana.test")
    assert api.post(f"/hr/practitioners/{t}/lifecycle", ADMIN, action="suspend", reason="no authority").status_code == 403
    domains = {a["domain"] for a in api.get("/alerts?limit=500", ADMIN).json()["items"]}
    assert domains and domains <= {"security"}


def test_hr_cannot_create_privileged_accounts(api):
    body = dict(email="x.y@aramana.test", full_name="X Y", role="compliance_reviewer", initial_password="LongPassw0rd!")
    assert api.post("/hr/practitioners", HR, **body).status_code == 400                       # role rejected by the schema
    assert api.post("/admin/users", HR, email="a@b.co", full_name="A B", role="hr_admin", password="LongPassw0rd!").status_code == 403


def test_platform_admin_cannot_escalate_own_privileges(api):
    assert api.patch(f"/admin/users/{api.me(ADMIN)}/role", ADMIN, role="compliance_reviewer", reason="give myself more").status_code == 403
    assert AuditLog.objects.filter(action="self_role_change_blocked").exists()


def test_supervisor_reads_only_current_supervisees(api):
    sup = "supervisor1@aramana.test"
    mine = [s["id"] for s in api.get("/supervision/supervisees", sup).json()]
    assert len(mine) == 3 and api.get(f"/clinical/practitioners/{mine[0]}/sessions", sup).status_code == 200
    other = User.objects.filter(role="therapist").exclude(id__in=mine).first().id
    assert api.get(f"/clinical/practitioners/{other}/sessions", sup).status_code == 403
    assert api.get(f"/supervision/supervisees/{other}", sup).status_code == 403


def test_therapist_reads_only_own_sessions(api):
    me, other = api.me("therapist2@aramana.test"), api.me("therapist3@aramana.test")
    assert api.get(f"/clinical/practitioners/{me}/sessions?status=completed", "therapist2@aramana.test").status_code == 200
    assert api.get(f"/clinical/practitioners/{other}/sessions", "therapist2@aramana.test").status_code == 403


def test_compliance_clinical_access_limited_to_alerted_subjects(api, gt):
    ok = api.get(f"/clinical/practitioners/{gt['roles']['T_overlap']}/sessions", COMP)
    assert ok.status_code == 200 and ok.json()[0]["client_ref"].startswith("C-")            # pseudonym only
    assert api.get(f"/clinical/practitioners/{api.me('therapist24@aramana.test')}/sessions", COMP).status_code == 403


def test_alert_visibility_by_role(api):
    assert all(a["domain"] in ("operational", "clinical") for a in api.get("/alerts?limit=500", "supervisor1@aramana.test").json()["items"])
    assert api.get("/alerts", "therapist1@aramana.test").status_code == 403 and api.get("/alerts", "counselor1@aramana.test").status_code == 403
    assert {"security", "misconduct", "operational"} <= {a["domain"] for a in api.get("/alerts?limit=500", COMP).json()["items"]}


def test_nobody_sees_alerts_about_themselves(api):
    for i in range(1, 9):
        who = f"supervisor{i}@aramana.test"
        me = api.me(who)
        assert all(me != a["subject_user_id"] and me not in {u["id"] for u in a["related_users"]} for a in api.get("/alerts?limit=500", who).json()["items"])
    admin2 = api.me("admin2@aramana.test")
    mine = next(a for a in api.get("/alerts?limit=500", COMP).json()["items"] if a["subject_user_id"] == admin2)
    assert api.get(f"/alerts/{mine['id']}", "admin2@aramana.test").status_code == 404


def test_client_refs_redacted_for_hr(api):
    first = api.get("/alerts?scenario=session_overlap", HR).json()["items"][0]
    blob = str(api.get(f"/alerts/{first['id']}", HR).json()["evidence"])
    assert "C-****" in blob and "'client_a': 'C-0" not in blob
    assert "C-****" not in str(api.get(f"/alerts/{first['id']}", COMP).json()["evidence"])


def test_audit_chain_verifies_and_detects_tampering(api):
    assert api.get("/audit/verify", COMP).json()["ok"] is True and api.get("/audit", HR).status_code == 403
    row = AuditLog.objects.latest("id")
    AuditLog.objects.filter(pk=row.pk).update(outcome="tampered")
    assert verify_chain() == {"ok": False, "checked": AuditLog.objects.filter(id__lt=row.id).count(), "first_bad_id": row.id}


def test_security_headers_and_no_cache(api):
    r = api.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY" and r.headers["Cache-Control"] == "no-store"


def test_api_docs_and_schema_are_served(api):
    assert api.get("/docs/").status_code == 200 and api.get("/schema/").status_code == 200


def test_audit_append_survives_a_lost_race(api, monkeypatch):
    """Two workers read the same tail: the loser must retry on the new tail instead of forking the chain (needed for several replicas)."""
    import core.audit as audit_mod
    audit_mod.audit(None, "first", "test")
    tail = audit_mod._tail()
    stale = iter([audit_mod.AuditLog.objects.order_by("-id").values_list("prev_hash", flat=True).first()])   # a tail someone else already extended
    monkeypatch.setattr(audit_mod, "_tail", lambda: next(stale, None) or tail)
    row = audit_mod.audit(None, "second", "test")
    assert row.prev_hash == tail and verify_chain()["ok"]
    assert AuditLog.objects.filter(prev_hash=tail).count() == 1


def test_dotenv_loader_handles_comments_and_quotes(tmp_path, monkeypatch):
    """What a client copies from the docs must work: `KEY=value   # comment`, quoted values, comment lines, `=` inside values."""
    from config.settings import _load_dotenv
    for k in ("T_A", "T_B", "T_C", "T_D", "T_E"):
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / ".env"
    f.write_text('# a comment\nT_A=gemini            # or groq\nT_B="quoted # not a comment"\nT_C=\nT_D=postgres://u:p@h:5432/db?x=1\nT_E = spaced\n', encoding="utf-8")
    _load_dotenv(f)
    import os
    assert (os.environ["T_A"], os.environ["T_B"], os.environ["T_C"], os.environ["T_D"], os.environ["T_E"]) == ("gemini", "quoted # not a comment", "", "postgres://u:p@h:5432/db?x=1", "spaced")
    for k in ("T_A", "T_B", "T_C", "T_D", "T_E"):
        os.environ.pop(k, None)
