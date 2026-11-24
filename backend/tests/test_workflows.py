"""Module A (HR) and Module B (supervision) workflows."""
from datetime import date, timedelta

import pytest

from accounts.models import User
from hr.models import Contract, LifecycleEvent, SupervisionAssignment
from supervision.models import Review

pytestmark = pytest.mark.django_db
HR, SUP1 = "hr@aramana.test", "supervisor1@aramana.test"


def test_practitioner_lifecycle_state_machine(api):
    r = api.post("/hr/practitioners", HR, email="new.therapist@aramana.test", full_name="New Therapist", role="therapist", specialization="anxiety", capacity_weekly_sessions=20, initial_password="LongPassw0rd!")
    assert r.status_code == 201 and r.json()["status"] == "pending_onboarding"
    uid = r.json()["id"]
    assert api.post("/auth/login", email="new.therapist@aramana.test", password="LongPassw0rd!").status_code == 401   # not active yet
    life = lambda action, reason="documented reason": api.post(f"/hr/practitioners/{uid}/lifecycle", HR, action=action, reason=reason)  # noqa: E731
    assert life("suspend").status_code == 409
    assert life("activate").json()["status"] == "active"
    assert api.post("/auth/login", email="new.therapist@aramana.test", password="LongPassw0rd!").status_code == 200
    assert life("reactivate").status_code == 409
    assert life("suspend").json()["status"] == "suspended" and life("reactivate").json()["status"] == "active"
    assert life("suspend", "x").status_code == 400                        # a documented reason is required
    assert life("terminate").json()["status"] == "terminated" and life("reactivate").status_code == 409
    events = [e["event"] for e in api.get(f"/hr/practitioners/{uid}", HR).json()["lifecycle"]][::-1]
    assert events == ["onboarding_started", "onboarded", "suspended", "reactivated", "terminated"]


def test_assignment_history_preserved_and_validated(api):
    sub = api.me("therapist4@aramana.test")
    old = next(a for a in api.get(f"/hr/practitioners/{sub}", HR).json()["assignments"] if a["current"] and a["supervisee_id"] == sub)
    new_sup, eff = api.me("supervisor8@aramana.test"), date.today() + timedelta(days=3)
    assert api.post("/hr/assignments", HR, supervisor_id=new_sup, supervisee_id=sub, effective_from=str(eff), reason="Caseload rebalancing").status_code == 201
    after = api.get(f"/hr/practitioners/{sub}", HR).json()["assignments"]
    assert next(a for a in after if a["id"] == old["id"])["effective_to"] == str(eff - timedelta(days=1))   # end-dated, not deleted
    assert any(a["supervisor_id"] == new_sup and a["effective_from"] == str(eff) for a in after)
    assert api.post("/hr/assignments", HR, supervisor_id=sub, supervisee_id=sub, reason="invalid self").status_code == 400
    assert api.post("/hr/assignments", HR, supervisor_id=new_sup, supervisee_id=sub, effective_from=str(eff), reason="duplicate").status_code == 409


def test_credentials_contracts_and_dashboard(api):
    uid = api.me("therapist6@aramana.test")
    cid = api.post(f"/hr/practitioners/{uid}/credentials", HR, kind="certification", title="EMDR", number="E-1", expires_on=str(date.today() + timedelta(days=10))).json()["id"]
    assert api.patch(f"/hr/credentials/{cid}", HR, status="revoked").status_code == 200
    assert api.post(f"/hr/practitioners/{uid}/contracts", HR, kind="fixed_term", start_date="2026-06-01", end_date="2026-01-01").status_code == 400
    assert api.post(f"/hr/practitioners/{uid}/contracts", HR, kind="fixed_term", start_date="2026-06-01", end_date=str(date.today() + timedelta(days=20))).status_code == 201
    dash = api.get("/hr/dashboard", HR).json()
    assert dash["practitioners_by_status"]["active"] >= 30 and any(c["title"] == "EMDR" for c in dash["credentials_expiring_or_expired"]) and dash["contracts_ending_soon"]
    assert "sessions" not in api.get(f"/hr/practitioners/{uid}", HR).json()                # no clinical data in the HR view


def test_terminate_closes_assignments_and_contracts(api):
    uid = api.me("therapist12@aramana.test")
    assert api.post(f"/hr/practitioners/{uid}/lifecycle", HR, action="terminate", reason="Contract ended by mutual agreement").status_code == 200
    assert not SupervisionAssignment.objects.filter(supervisee_id=uid, effective_to__isnull=True).exists()
    assert not Contract.objects.filter(user_id=uid, status="active").exists()


def test_supervisor_dashboard_and_supervisees(api):
    d = api.get("/supervision/dashboard", SUP1).json()
    assert {"supervisees_total", "active", "inactive", "pending_reviews", "overdue_reviews", "open_quality_issues", "cases_requiring_escalation", "recent_activity", "performance_trend"} <= set(d)
    assert d["supervisees_total"] == 3 and d["performance_trend"]
    assert len(api.get("/supervision/supervisees", SUP1).json()) == 3


def test_review_workflow_end_to_end(api):
    sub = api.get("/supervision/supervisees", SUP1).json()[0]["id"]
    rid = api.post("/supervision/reviews", SUP1, supervisee_id=sub, due_date=str(date.today() + timedelta(days=7))).json()["id"]
    assert api.post(f"/supervision/reviews/{rid}/start", SUP1).status_code == 200 and api.post(f"/supervision/reviews/{rid}/start", SUP1).status_code == 409
    body = dict(outcome="needs_changes", notes="Notes on case structure", feedback="Please update the plan", performance_score=3, has_documentation=True, minutes_spent=15)
    assert api.post(f"/supervision/reviews/{rid}/decision", SUP1, **body).status_code == 200 and api.post(f"/supervision/reviews/{rid}/decision", SUP1, **body).status_code == 409
    action = api.post(f"/supervision/reviews/{rid}/corrective-actions", SUP1, description="Update treatment plan", due_date=str(date.today() + timedelta(days=14)))
    assert action.status_code == 201
    assert api.post(f"/supervision/reviews/{rid}/close", SUP1).status_code == 400                         # open action => monitoring plan required
    assert api.post(f"/supervision/reviews/{rid}/close", SUP1, monitoring_plan="Re-review in two weeks").status_code == 200
    who = User.objects.get(pk=sub).email
    mine = api.get("/supervision/my-reviews", who).json()
    assert any(a["id"] == action.json()["id"] for a in mine["corrective_actions"]) and any(r["id"] == rid for r in mine["reviews"])
    assert api.patch(f"/supervision/corrective-actions/{action.json()['id']}", who, status="completed").status_code == 200
    assert any("needs_changes" in (e.reason or "") for e in LifecycleEvent.objects.filter(user_id=sub, event="supervision_review"))   # reflected in the operational record


def test_approval_without_documentation_is_allowed_but_flagged(api):
    sub = api.get("/supervision/supervisees", SUP1).json()[1]["id"]
    rid = api.post("/supervision/reviews", SUP1, supervisee_id=sub, due_date=str(date.today())).json()["id"]
    r = api.post(f"/supervision/reviews/{rid}/decision", SUP1, outcome="approved", notes="ok ok", feedback="ok ok", performance_score=4, has_documentation=False, minutes_spent=1)
    assert r.status_code == 200 and "without supporting documentation" in r.json()["warning"]


def test_supervisor_cannot_touch_other_supervisors_reviews(api):
    other = Review.objects.exclude(supervisor_id=api.me(SUP1)).first()
    assert api.get(f"/supervision/reviews/{other.id}", SUP1).status_code == 404
    assert api.post(f"/supervision/reviews/{other.id}/decision", SUP1, outcome="approved", notes="abc", feedback="abc", performance_score=5, has_documentation=True).status_code == 404


def test_therapist_session_and_referral_flow(api):
    t, c = "therapist2@aramana.test", "counselor1@aramana.test"
    clients = api.get("/clinical/my-clients", t).json()
    sid = api.post("/clinical/sessions", t, client_ref=clients[0]["client_ref"], scheduled_start="2027-01-11T10:00:00Z", duration_min=50)
    assert sid.status_code == 201
    assert api.patch(f"/clinical/sessions/{sid.json()['id']}", t, scheduled_start="2027-01-11T11:00:00Z").json()["modification_count"] == 1
    assert api.patch(f"/clinical/sessions/{sid.json()['id']}", "therapist3@aramana.test", status="cancelled").status_code == 404
    assert api.patch(f"/clinical/sessions/{sid.json()['id']}", t, status="cancelled").status_code == 200
    assert api.patch(f"/clinical/sessions/{sid.json()['id']}", t, status="completed").status_code == 409        # closed sessions cannot change status
    assert api.post("/clinical/sessions", t, client_ref="C-9999", scheduled_start="2027-01-11T10:00:00Z").status_code == 404
    eligible = api.get("/referrals/eligible?need=anxiety", c).json()
    assert len(eligible) == 5
    assert api.post("/referrals", c, client_ref=clients[0]["client_ref"], to_practitioner_id=eligible[0]["id"], need="anxiety").status_code == 201
    assert api.post("/referrals", c, client_ref=clients[0]["client_ref"], to_practitioner_id=eligible[0]["id"], need="bogus").status_code == 400
    assert api.get("/referrals/mine", c).json()
