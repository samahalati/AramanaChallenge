"""Detection engine: pure units + the four required scenarios + explainability, determinism, false-positive management."""
import pandas as pd
import pytest

from accounts.models import User
from detection import scoring
from detection.base import REGISTRY
from detection.engine import load_config
from detection.features import find_overlaps
from detection.types import Indicator
from monitoring import evaluation
from monitoring.models import Alert, AlertUser, DetectionRun
from monitoring.services.runs import run_detection

pytestmark = pytest.mark.django_db


def alerts_for(uid, cat=None):
    return list(Alert.objects.filter(subject_user_id=uid, **({"category": cat} if cat else {})))


# ------------------------------------------------------------------ pure units (no DB)
def test_noisy_or_points_sum_to_score():
    inds = [Indicator("a", "A", 1, 0, 0.7, 1.0, "rule"), Indicator("b", "B", 1, 0, 0.5, 0.6, "statistical"), Indicator("c", "C", 1, 0, 0.3, 1.0, "ml")]
    score, rows, capped = scoring.attribute(inds)
    assert score == pytest.approx(100 * (1 - 0.3 * 0.7 * 0.7), abs=0.1) and sum(r["points"] for r in rows) == pytest.approx(score, abs=0.1) and not capped


def test_weak_only_evidence_is_capped():
    inds = [Indicator("ml_isolation_forest", "ML", 1, 0, 0.9, 1.0, "ml"), Indicator("approval_burst", "vol", 1, 0, 0.9, 1.0, "statistical")]
    score, _, capped = scoring.attribute(inds, weak={"ml_isolation_forest", "approval_burst"}, weak_cap=34)
    assert capped and score == 34


def test_levels():
    levels = {"low": 0, "medium": 35, "high": 60, "critical": 80}
    assert [scoring.level_for(s, levels) for s in (10, 35, 59.9, 60, 80, 100)] == ["low", "medium", "medium", "high", "critical", "critical"]


def _s(i, start, end, **kw):
    return dict(id=i, practitioner_id=1, scheduled_start=pd.Timestamp(start), scheduled_end=pd.Timestamp(end), status="completed", group_id=None, mode="online",
                location_code=None, client_ref="C-1") | kw


def test_overlap_rule_edge_cases():
    df = pd.DataFrame([_s(1, "2026-01-05 09:00", "2026-01-05 09:50"), _s(2, "2026-01-05 09:50", "2026-01-05 10:40"),            # touching: not an overlap
                       _s(3, "2026-01-05 11:00", "2026-01-05 11:50"), _s(4, "2026-01-05 11:20", "2026-01-05 12:10", mode="in_person", location_code="B"),
                       _s(5, "2026-01-05 15:00", "2026-01-05 15:50", group_id="G1"), _s(6, "2026-01-05 15:00", "2026-01-05 15:50", group_id="G1"),   # same group: legit
                       _s(7, "2026-01-05 16:00", "2026-01-05 16:50", status="cancelled"), _s(8, "2026-01-05 16:10", "2026-01-05 17:00")])
    pairs = find_overlaps(df, 5)
    assert [(p["session_a"], p["session_b"]) for p in pairs] == [(3, 4)] and pairs[0]["overlap_min"] == 30
    df.loc[df.id == 3, ["mode", "location_code"]] = ["in_person", "A"]
    assert find_overlaps(df, 5)[0]["impossible"] is True


def test_detectors_are_registered_strategies():
    assert {c.__name__ for c in REGISTRY} >= {"SessionOverlap", "ReferralConcentration", "ApprovalAnomaly", "AdminScopeAbuse", "ReferralApprovalRing", "IsolationForestDetector"}


# ------------------------------------------------------------------ the required scenarios
def test_scenario1_overlapping_sessions(gt):
    a = next(x for x in alerts_for(gt["roles"]["T_overlap"], "A") if x.scenario == "session_overlap")
    assert a.risk_level in ("high", "critical") and "rule" in a.methods
    assert {"overlap_pairs", "impossible_location"} <= {b["name"] for b in a.score_breakdown}
    assert any(e["type"] == "session_overlap" for e in a.evidence) and a.record_refs and all(r.startswith("session:") for r in a.record_refs)


def test_scenario2_referral_network_and_policy_suppression(gt):
    conc = [a for a in alerts_for(gt["roles"]["C_conc"], "B") if a.scenario == "referral_concentration"]      # (the behaviour-shift alert is a separate scenario)
    assert conc and conc[0].risk_level in ("high", "critical")
    ev = [e for e in conc[0].evidence if e["type"] == "referral_distribution"]
    assert ev[0]["share"] > ev[0]["policy_expected_share"] + 0.2
    assert not alerts_for(gt["roles"]["C_spec"], "B")                     # specialisation unit must NOT alert …
    sup = [s for s in DetectionRun.objects.order_by("-id").first().stats["suppressed"] if s["counselor"] == gt["roles"]["C_spec"]]
    assert sup and sup[0]["naive_p"] <= 0.001 < sup[0]["policy_aware_p"]  # … and is listed as suppressed with both p-values


def test_scenario3_supervisor_approvals_and_hard_negative(gt):
    a = alerts_for(gt["roles"]["S_rubber"], "C")[0]
    assert a.risk_level in ("high", "critical") and {"approvals_missing_docs", "rapid_approvals"} <= {b["name"] for b in a.score_breakdown}
    assert any(e["type"] == "approval" and not e["has_documentation"] for e in a.evidence)
    assert all(b.risk_level == "low" for b in alerts_for(gt["roles"]["S_busy"], "C"))   # high volume, documented, normal pace


def test_scenario4_admin_out_of_scope(gt):
    a = alerts_for(gt["roles"]["admin2"], "D")[0]
    assert a.domain == "security" and a.risk_level == "critical" and {"denied_access_burst", "scope_probing"} <= {b["name"] for b in a.score_breakdown}
    assert sum(e["type"] == "access_denied" for e in a.evidence) >= 5


def test_network_ring_found_only_by_graph(gt):
    a = alerts_for(gt["roles"]["T_ring"], "E")[0]
    assert a.methods == ["graph"]
    assert {gt["roles"][k] for k in ("C_ring", "T_ring", "S_ring")} <= set(AlertUser.objects.filter(alert=a).values_list("user_id", flat=True))


# ------------------------------------------------------------------ evaluation, explainability, reproducibility
def test_evaluation_meets_targets_and_no_hard_negative_false_positives():
    res = evaluation.evaluate()
    assert res["overall"]["recall"] >= 0.9 and res["overall"]["precision"] >= 0.9 and res["hard_negatives"]["false_positives_at_min_level"] == 0
    assert res["ablation"]["full_ensemble"]["f1"] > res["ablation"]["rules_only"]["f1"]     # the layers add value


def test_every_alert_is_explainable_and_traceable():
    for a in Alert.objects.all():
        assert a.score_breakdown and a.explanation and a.recommended_action and a.ruleset_version and a.model_version and a.methods
        assert sum(b["points"] for b in a.score_breakdown) == pytest.approx(a.risk_score, abs=0.5) or "capped" in a.explanation.lower()
        assert "advisory" in a.explanation.lower()


def test_engine_is_deterministic_and_idempotent():
    before = {a.dedup_key: (a.risk_score, a.risk_level) for a in Alert.objects.all()}
    assert run_detection()["alerts_created"] == 0
    assert before == {a.dedup_key: (a.risk_score, a.risk_level) for a in Alert.objects.all()}


def test_false_positive_is_not_re_alerted_without_new_evidence(gt):
    a = alerts_for(gt["roles"]["T_inflate"], "A")[0]
    Alert.objects.filter(pk=a.pk).update(status="false_positive")
    assert run_detection()["alerts_created"] == 0 and Alert.objects.filter(dedup_key=a.dedup_key).count() == 1


def test_detection_never_modifies_users():
    snap = set(User.objects.values_list("id", "status", "role"))
    run_detection()
    assert snap == set(User.objects.values_list("id", "status", "role"))


def test_config_is_versioned():
    cfg, digest = load_config(__import__("django.conf", fromlist=["settings"]).settings.DETECTION_CONFIG)
    assert cfg.raw["ruleset_version"] and len(digest) == 64


def test_referral_behaviour_shift_detected_for_the_counselor_whose_targets_changed(gt):
    """Brief §5.1-B 'suspicious changes in referral behavior': the injected change is found, benign counselors are not flagged."""
    flagged = set(Alert.objects.filter(scenario="referral_behavior_shift").values_list("subject_user_id", flat=True))
    assert flagged == {gt["roles"]["C_conc"]}
    assert gt["roles"]["C_spec"] not in flagged
