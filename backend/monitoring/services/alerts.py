"""Alert access + investigation workflow + monitoring views (Module C ⟷ A/B integration).

Safeguards: role+domain+relationship visibility; never the subject; client refs redacted for non-clinical roles; substantiated
closure requires evidence review + a documented finding; NOTHING here changes a practitioner's status/role/contract.
"""
from collections import Counter, defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.selectors import briefs
from core import i18n
from core.audit import audit
from core.constants import CATEGORY_LABELS, RISK_LEVELS, AlertStatus as S, Domain
from core.rbac import INVESTIGATE_DOMAINS, can_see_client_refs, has_perm
from core.statemachine import StateMachine
from hr.selectors import current_supervisor_id
from monitoring import localize
from monitoring.models import Alert, DetectionRun, InvestigationEvent
from monitoring.visibility import alert_users, alert_visible, visible_alerts
from supervision.models import QualityIssue

ROUTING = {Domain.OPERATIONAL: ["hr_admin", "clinical_supervisor", "compliance_reviewer"], Domain.CLINICAL: ["clinical_supervisor", "compliance_reviewer"],
           Domain.MISCONDUCT: ["compliance_reviewer", "hr_admin"], Domain.SECURITY: ["platform_admin", "compliance_reviewer"]}
OPEN, CLOSED = S.open(), S.closed()
WORKFLOW = StateMachine({
    "start_review": ({S.NEW}, S.UNDER_REVIEW), "request_info": ({S.NEW, S.UNDER_REVIEW, S.ESCALATED}, S.INFO_REQUESTED), "provide_info": ({S.INFO_REQUESTED}, S.UNDER_REVIEW),
    "escalate": ({S.NEW, S.UNDER_REVIEW, S.INFO_REQUESTED}, S.ESCALATED), "false_positive": (set(OPEN), S.FALSE_POSITIVE), "close_no_action": (set(OPEN), S.CLOSED_NO_ACTION),
    "close_substantiated": ({S.UNDER_REVIEW, S.ESCALATED}, S.CLOSED_SUBSTANTIATED), "reopen": (set(CLOSED), S.UNDER_REVIEW)})
NOTE_MIN = {"request_info": 10, "escalate": 10, "false_positive": 10, "close_no_action": 10, "close_substantiated": 30, "reopen": 10, "comment": 3}
CLIENT_KEYS = {"client_ref", "client_a", "client_b"}


def redact(evidence, role: str):
    """Data minimisation: pseudonymous client references are masked for roles without clinical access."""
    if can_see_client_refs(role):
        return evidence
    walk = lambda x: ({k: ("C-****" if k in CLIENT_KEYS and v else walk(v)) for k, v in x.items()} if isinstance(x, dict) else [walk(i) for i in x] if isinstance(x, list) else x)  # noqa: E731
    return walk(evidence)


def alert_dict(user, a: Alert, users: dict, people: dict, detail: bool = False) -> dict:
    d = {"id": a.id, "alert_uid": a.alert_uid, "category": a.category, "category_label": CATEGORY_LABELS.get(a.category), "scenario": a.scenario, "domain": a.domain, "title": a.title,
         "subject_user_id": a.subject_user_id, "subject": people.get(a.subject_user_id), "related_users": [people[u] | {"role_in_alert": r} for u, r in users.items() if u in people],
         "risk_score": a.risk_score, "risk_level": a.risk_level, "methods": a.methods, "status": a.status, "assigned_to": a.assigned_to, "detected_at": a.detected_at,
         "updated_at": a.updated_at, "routed_to": ROUTING.get(a.domain, []), "ruleset_version": a.ruleset_version, "model_version": a.model_version}
    if detail:
        d |= {"explanation": a.explanation, "recommended_action": a.recommended_action, "evidence": redact(a.evidence, user.role), "score_breakdown": a.score_breakdown,
              "record_refs": a.record_refs, "window_start": a.window_start, "window_end": a.window_end,
              "advisory": "Advisory only. This alert does not establish fraud or misconduct; decisions require authorised human review."}
    return localize.apply(a, d, people, detail) if i18n.lang() == "fa" else d


def list_alerts(user, limit: int, offset: int, **flt) -> dict:
    rows = visible_alerts(user, **flt)
    people = briefs({u for _, us in rows for u in us} | {a.subject_user_id for a, _ in rows if a.subject_user_id})
    return {"total": len(rows), "items": [alert_dict(user, a, us, people) for a, us in rows[offset:offset + limit]]}


def get_visible(user, alert_id: int) -> tuple[Alert, dict]:
    alert = Alert.objects.filter(pk=alert_id).first()
    users = alert_users([alert_id]).get(alert_id, {}) if alert else {}
    if not alert or not has_perm(user.role, "alerts:read") or not alert_visible(user, alert, set(users)):
        if alert:   # indistinguishable from "not found" (no existence leak); the attempt is audited
            audit(user, "alert_access_denied", "alert", alert_id, outcome="denied")
        raise NotFound("Alert not found")
    return alert, users


def allowed_actions(user, a: Alert) -> list[str]:
    actions = ["comment"] if has_perm(user.role, "alerts:comment") else []
    if has_perm(user.role, "alerts:investigate") and a.domain in INVESTIGATE_DOMAINS.get(user.role, ()):
        actions += WORKFLOW.actions_from(a.status) + ["assign"]
    return actions


def alert_detail(user, alert_id: int) -> dict:
    alert, users = get_visible(user, alert_id)
    events = list(alert.events.order_by("id"))
    if has_perm(user.role, "alerts:investigate") and not any(e.action == "viewed" and e.actor_id == user.id and e.ts > timezone.now() - timedelta(minutes=10) for e in events):
        events.append(InvestigationEvent.objects.create(alert=alert, actor_id=user.id, action="viewed", note="Evidence viewed"))
    audit(user, "alert_view", "alert", alert.alert_uid, evidence_items=len(alert.evidence), client_refs_visible=can_see_client_refs(user.role))
    people = briefs(set(users) | {e.actor_id for e in events if e.actor_id} | ({alert.subject_user_id} - {None}))
    others = Alert.objects.filter(subject_user_id=alert.subject_user_id).exclude(pk=alert.pk) if alert.subject_user_id else Alert.objects.none()
    return alert_dict(user, alert, users, people, detail=True) | {
        "timeline": [{"id": e.id, "ts": e.ts, "actor": people[e.actor_id]["name"] if e.actor_id in people else i18n.TERMS["system"] if i18n.lang() == "fa" else "system", "action": e.action, "note": i18n.t(e.note) if e.note else e.note,
                      "from_status": e.from_status, "to_status": e.to_status} for e in events],
        "longitudinal_context": {"other_alerts_for_subject": others.count(), "by_status": dict(Counter(o.status for o in others)),
                                 "note": i18n.t("Prior alerts are context for reviewers only. They are not findings, do not alter this risk score, and create no presumption of misconduct.")},
        "allowed_actions": allowed_actions(user, alert)}


def act(user, alert_id: int, action: str, note: str | None, assign_to: int | None) -> dict:
    alert, users = get_visible(user, alert_id)
    if action not in allowed_actions(user, alert):
        raise PermissionDenied(f"Action '{action}' is not allowed for your role or the alert's current status")
    note = (note or "").strip()
    if len(note) < NOTE_MIN.get(action, 0):
        raise ValidationError(f"A documented note of at least {NOTE_MIN[action]} characters is required for '{action}'")
    before = alert.status
    with transaction.atomic():
        if action == "assign":
            target = briefs([assign_to or user.id]).get(assign_to or user.id)
            if not target or not has_perm(target["role"], "alerts:investigate") or alert.domain not in INVESTIGATE_DOMAINS.get(target["role"], ()):
                raise ValidationError("Assignee must be an active reviewer authorised for this alert's domain")
            if target["id"] in users:
                raise ValidationError("Assignee is involved in this alert (conflict of interest)")
            alert.assigned_to = target["id"]
            alert.status = S.UNDER_REVIEW if alert.status == S.NEW else alert.status
            InvestigationEvent.objects.create(alert=alert, actor_id=user.id, action="assigned", note=f"Assigned to {target['name']}. {note}".strip())
        elif action == "comment":
            InvestigationEvent.objects.create(alert=alert, actor_id=user.id, action="comment", note=note)
        else:
            if action == "close_substantiated" and not alert.events.filter(actor_id=user.id, action="viewed").exists():
                raise ValidationError("The evidence must be reviewed by the closing reviewer before an alert can be closed as substantiated")
            alert.status = WORKFLOW.apply(action, alert.status)
            alert.assigned_to = alert.assigned_to or (user.id if action == "start_review" else None)
            InvestigationEvent.objects.create(alert=alert, actor_id=user.id, action=action, note=note, from_status=before, to_status=alert.status)
        alert.updated_at = timezone.now()
        alert.save()
        audit(user, f"alert_{action}", "alert", alert.alert_uid, note_len=len(note), status=alert.status)
        return alert_detail(user, alert.id)


def route_to_supervisor(user, alert_id: int, note: str) -> dict:
    """An operational/clinical concern becomes a quality issue for the practitioner's CURRENT supervisor (Module B)."""
    alert, users = get_visible(user, alert_id)
    if not has_perm(user.role, "alerts:investigate") or alert.domain not in INVESTIGATE_DOMAINS.get(user.role, ()):
        raise PermissionDenied("Not allowed to route this alert")
    if alert.domain not in (Domain.OPERATIONAL, Domain.CLINICAL):
        raise ValidationError("Only operational/clinical concerns are routed to supervisors; potential misconduct stays with compliance/HR")
    supervisor = alert.subject_user_id and current_supervisor_id(alert.subject_user_id)
    if not supervisor:
        raise ValidationError("Practitioner has no current supervisor")
    if supervisor in users:
        raise ValidationError("The practitioner's supervisor is involved in this alert (conflict of interest)")
    with transaction.atomic():
        issue = QualityIssue.objects.create(practitioner_id=alert.subject_user_id, supervisor_id=supervisor, category=alert.domain, source_alert_id=alert.id, detail=note,
                                            title=f"{alert.scenario.replace('_', ' ').capitalize()} – referred from monitoring ({alert.alert_uid})",
                                            severity={"low": "low", "medium": "medium"}.get(alert.risk_level, "high"))
        InvestigationEvent.objects.create(alert=alert, actor_id=user.id, action="routed_to_supervisor", note=f"Routed to supervisor #{supervisor}: {note}")
        audit(user, "alert_route_to_supervisor", "alert", alert.alert_uid, supervisor=supervisor)
        return {"quality_issue_id": issue.id, "supervisor_id": supervisor}


def monitoring_summary(user) -> dict:
    alerts = [a for a, _ in visible_alerts(user)]
    weekly = Counter(a.detected_at.date() - timedelta(days=a.detected_at.weekday()) for a in alerts)
    feedback = defaultdict(lambda: {"closed": 0, "false_positive": 0})
    for a in (a for a in alerts if a.status in CLOSED):
        feedback[a.scenario]["closed"] += 1
        feedback[a.scenario]["false_positive"] += a.status == S.FALSE_POSITIVE
    run = DetectionRun.objects.order_by("-id").first()
    internal = has_perm(user.role, "detection:run")
    return {"total": len(alerts), "open": sum(a.status in OPEN for a in alerts), "by_level": {lv: sum(a.risk_level == lv for a in alerts) for lv in RISK_LEVELS},
            "by_status": dict(Counter(a.status for a in alerts)), "by_category": dict(Counter(a.category for a in alerts)), "by_domain": dict(Counter(a.domain for a in alerts)),
            "weekly_trend": [{"week": str(k), "alerts": v} for k, v in sorted(weekly.items())],
            "false_positive_feedback": [{"scenario": s, **v, "fp_rate": round(v["false_positive"] / v["closed"], 2)} for s, v in feedback.items()],
            "last_run": run and {"id": run.id, "finished_at": run.finished_at, "ruleset_version": run.ruleset_version, "model_version": run.model_version, "as_of": run.as_of,
                                 "alerts_created": (run.stats or {}).get("alerts_created"), "suppressed": (run.stats or {}).get("suppressed", []) if internal else []}}


def user_history(user, uid: int) -> dict:
    rows = [(a, us) for a, us in visible_alerts(user) if uid in us]
    return {"user": briefs([uid]).get(uid), "by_status": dict(Counter(a.status for a, _ in rows)),
            "alerts": [{"id": a.id, "alert_uid": a.alert_uid, "title": a.title, "risk_level": a.risk_level, "status": a.status, "detected_at": a.detected_at, "scenario": a.scenario} for a, _ in rows],
            "note": i18n.t("Longitudinal monitoring context only: alerts are not findings; false positives and closed-no-action outcomes are part of this record.")}
