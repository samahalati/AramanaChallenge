"""End-to-end flows across the three modules (brief §6)."""
import pytest

from accounts.models import User

pytestmark = pytest.mark.django_db
COMP, HR, SUP1, ADMIN = "compliance@aramana.test", "hr@aramana.test", "supervisor1@aramana.test", "admin@aramana.test"


def find(api, who, **q):
    return api.get("/alerts?limit=500&" + "&".join(f"{k}={v}" for k, v in q.items()), who).json()["items"]


def act(api, aid, action, note=None, who=COMP, **kw):
    return api.post(f"/alerts/{aid}/actions", who, action=action, note=note, **kw)


def test_flow1_overlapping_sessions_live_detection_to_investigation_closure(api):
    """Practitioner activity -> alert -> compliance examines -> request info -> substantiate (human) -> record unchanged."""
    t = "therapist1@aramana.test"
    ref = api.get("/clinical/my-clients", t).json()[0]["client_ref"]
    for start in ("2027-02-01T10:00:00Z", "2027-02-01T10:20:00Z"):                     # two overlapping 1:1 sessions are accepted, then flagged
        assert api.post("/clinical/sessions", t, client_ref=ref, scheduled_start=start).status_code == 201
    assert api.post("/detection/run", COMP).json()["alerts_created"] >= 1
    tid = api.me(t)
    a = next(x for x in find(api, COMP, scenario="session_overlap") if x["subject_user_id"] == tid)
    assert a["status"] == "new" and a["risk_level"] == "low"
    assert api.get(f"/alerts/{a['id']}", t).status_code == 403 and api.get(f"/alerts/{a['id']}", HR).status_code == 200
    assert act(api, a["id"], "close_substantiated", "x" * 40).status_code == 403          # new -> substantiated is not a legal jump
    assert act(api, a["id"], "start_review").status_code == 200
    assert act(api, a["id"], "request_info", "short").status_code == 400                   # documented note required
    assert act(api, a["id"], "request_info", "Please confirm which of the two sessions took place.").json()["status"] == "info_requested"
    assert act(api, a["id"], "provide_info", "Practitioner replied: calendar sync error.").json()["status"] == "under_review"
    res = act(api, a["id"], "close_substantiated", "Records inconsistency confirmed; schedule corrected with practitioner. No misconduct indicated.")
    assert res.status_code == 200 and res.json()["status"] == "closed_substantiated"
    tl = [e["action"] for e in res.json()["timeline"]]
    assert tl[0] == "created" and "viewed" in tl and tl[-1] == "close_substantiated"
    assert User.objects.get(pk=tid).status == "active"                                     # NO automatic penalty


def test_flow2_referral_concentration_false_positive_feedback(api, gt):
    a = next(x for x in find(api, COMP, scenario="referral_concentration") if x["subject_user_id"] == gt["roles"]["C_conc"])
    detail = api.get(f"/alerts/{a['id']}", COMP).json()
    assert detail["evidence"][0]["type"] == "referral_distribution" and "assignment policy" in detail["recommended_action"].lower()
    assert act(api, a["id"], "false_positive", "Counselor's clients requested these practitioners; documented in case file.").json()["status"] == "false_positive"
    assert any(f["scenario"] == "referral_concentration" and f["false_positive"] == 1 for f in api.get("/monitoring/summary", COMP).json()["false_positive_feedback"])
    assert api.post("/detection/run", COMP).json()["alerts_created"] == 0
    hist = api.get(f"/monitoring/users/{gt['roles']['C_conc']}/history", COMP).json()
    assert hist["by_status"].get("false_positive") == 1 and "not findings" in hist["note"]


def test_flow3_supervisor_approval_anomaly_routing_and_conflict_of_interest(api, gt):
    a = next(x for x in find(api, COMP, scenario="approval_burst") if x["subject_user_id"] == gt["roles"]["S_rubber"])
    assert "compliance_reviewer" in a["routed_to"]
    assert all(a["id"] not in {x["id"] for x in find(api, f"supervisor{i}@aramana.test")} for i in range(1, 9))
    d = api.get(f"/alerts/{a['id']}", COMP).json()
    assert any(e["type"] == "approval" and e["has_documentation"] is False for e in d["evidence"])
    assert act(api, a["id"], "comment", "HR: no pending contract matters for this supervisor.", HR).status_code == 200
    assert act(api, a["id"], "close_no_action", "x" * 20, HR).status_code == 403            # HR may comment, not adjudicate
    assert act(api, a["id"], "escalate", "Escalating to head of compliance for second review.").json()["status"] == "escalated"


def test_flow4_unauthorized_admin_activity_live(api):
    admin_id = api.me(ADMIN)
    assert all(api.get(f"/clinical/practitioners/{pid}/sessions", ADMIN).status_code == 403 for pid in range(15, 20))
    assert api.post("/detection/run", COMP).status_code == 200
    a = next(x for x in find(api, COMP, domain="security") if x["subject_user_id"] == admin_id)
    assert a["category"] == "D" and a["risk_level"] in ("medium", "high", "critical")     # 5 blocked probes: medium; seeded admin2 (9 + account abuse): critical
    assert api.get(f"/alerts/{a['id']}", ADMIN).status_code == 404                         # conflict-of-interest guard
    assert sum(e["type"] == "access_denied" for e in api.get(f"/alerts/{a['id']}", COMP).json()["evidence"]) >= 5
    assert act(api, a["id"], "escalate", "Possible compromised admin credentials – escalating.").json()["status"] == "escalated"
    assert sum(r["actor_id"] == admin_id for r in api.get("/audit?action=access_denied&limit=50", COMP).json()) >= 5


def test_flow5_quality_concern_routed_to_supervisor_and_escalation_back(api):
    cancel = find(api, COMP, scenario="cancellation_pattern")[0]
    r = api.post(f"/alerts/{cancel['id']}/route-to-supervisor", COMP, note="Please discuss the cancellation pattern in supervision.")
    assert r.status_code == 200, r.content
    sup = User.objects.get(pk=r.json()["supervisor_id"]).email
    issue = next(i for i in api.get("/supervision/quality-issues", sup).json() if i["source_alert_id"] == cancel["id"])
    assert issue["practitioner_id"] == cancel["subject_user_id"]
    mis = find(api, COMP, domain="misconduct")[0]
    assert api.post(f"/alerts/{mis['id']}/route-to-supervisor", COMP, note="attempt to route misconduct").status_code == 400
    sub = api.get("/supervision/supervisees", sup).json()[0]["id"]
    own = api.post("/supervision/quality-issues", sup, practitioner_id=sub, category="clinical", title="Treatment plans repeatedly outdated", severity="high").json()
    esc = api.post(f"/supervision/quality-issues/{own['id']}/escalate", sup, reason="Repeated unresolved concerns after two reviews.")
    assert esc.status_code == 200
    a = next(x for x in find(api, COMP) if x["alert_uid"] == esc.json()["alert_uid"])       # Observer: supervision signal -> monitoring alert
    assert a["category"] == "Q" and a["methods"] == ["manual"]
