"""Module B use-cases: dashboards, review workflow, corrective actions, quality issues, escalation."""
from collections import defaultdict
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import User
from accounts.selectors import names
from clinical.models import Session
from core import i18n
from core.audit import audit
from core.errors import Conflict
from core.statemachine import StateMachine
from hr.models import LifecycleEvent, SupervisionAssignment
from hr.selectors import current_supervisee_ids
from supervision.models import CorrectiveAction, QualityIssue, Review, ReviewStatus as RS, SupervisionMeeting
from supervision.signals import issue_escalated

REVIEW_FLOW = StateMachine({"start": ({RS.PENDING}, RS.IN_PROGRESS), "approved": ({RS.PENDING, RS.IN_PROGRESS}, RS.APPROVED),
                            "needs_changes": ({RS.PENDING, RS.IN_PROGRESS}, RS.NEEDS_CHANGES)})


def require_supervisee(sup: User, uid: int) -> None:
    if uid not in current_supervisee_ids(sup.id):
        raise PermissionDenied("Practitioner is not your current supervisee")


def own_review(sup: User, rid: int) -> Review:
    review = Review.objects.filter(pk=rid, supervisor_id=sup.id).first()
    if not review:
        raise NotFound("Review not found")
    require_supervisee(sup, review.supervisee_id)
    return review


def case_info(r: Review) -> dict | None:
    """Spec §4.3 "reviewing authorized case information": the reviewed session as the supervisor is allowed to see it (pseudonymous client, times, mode, durations)."""
    s = r.session
    if s is None:
        return None
    return {"client_ref": s.client.client_ref, "scheduled_start": s.scheduled_start, "scheduled_end": s.scheduled_end, "status": s.status, "mode": s.mode,
            "planned_duration_min": round((s.scheduled_end - s.scheduled_start).total_seconds() / 60), "reported_duration_min": s.reported_duration_min,
            "checkin_at": s.checkin_at, "checkout_at": s.checkout_at, "modification_count": s.modification_count}


def review_dict(r: Review, nm: dict, detail: bool = False) -> dict:
    d = {"id": r.id, "case_ref": r.case_ref, "supervisee_id": r.supervisee_id, "supervisee": nm.get(r.supervisee_id), "supervisor_id": r.supervisor_id,
         "status": r.status, "due_date": r.due_date, "decided_at": r.decided_at, "closed_at": r.closed_at, "has_documentation": r.has_documentation,
         "overdue": r.overdue, "performance_score": r.performance_score}
    if detail:
        d |= {"supervision_notes": r.supervision_notes, "feedback": r.feedback, "decision_minutes": r.decision_minutes, "session_id": r.session_id,
              "opened_at": r.opened_at, "started_at": r.started_at, "case": case_info(r),
              "corrective_actions": list(r.actions.values("id", "description", "due_date", "status", "completed_at"))}
    return d


# ------------------------------------------------------------------ dashboard & supervisees
def dashboard(sup: User) -> dict:
    ids = current_supervisee_ids(sup.id)
    reviews = list(Review.objects.filter(supervisor_id=sup.id, supervisee_id__in=ids))
    issues = list(QualityIssue.objects.filter(supervisor_id=sup.id, practitioner_id__in=ids))
    nm, subs = names(ids), User.objects.filter(id__in=ids)
    pending = [r for r in reviews if r.decided_at is None]
    weekly = defaultdict(list)
    for r in reviews:
        if r.decided_at and r.performance_score:
            weekly[(r.decided_at.date() - timedelta(days=r.decided_at.weekday()))].append(r.performance_score)
    recent = sorted((r for r in reviews if r.decided_at), key=lambda r: r.decided_at, reverse=True)[:8]
    meetings = SupervisionMeeting.objects.filter(supervisor_id=sup.id).order_by("-scheduled_at")[:4]
    return {
        "supervisees_total": len(ids), "active": subs.filter(status="active").count(), "inactive": subs.exclude(status="active").count(),
        "pending_reviews": len(pending), "overdue_reviews": sum(r.overdue for r in pending),
        "open_quality_issues": sum(i.status == "open" for i in issues), "cases_requiring_escalation": sum(i.status == "open" and i.severity == "high" for i in issues),
        "escalated_cases": sum(i.status == "escalated" for i in issues),
        "recent_activity": [{"ts": r.decided_at, "type": f"review_{r.status}", "supervisee": nm.get(r.supervisee_id), "case_ref": r.case_ref} for r in recent]
                           + [{"ts": m.scheduled_at, "type": f"meeting_{m.status}", "supervisee": nm.get(m.supervisee_id)} for m in meetings],
        "performance_trend": [{"week": str(w), "avg_score": round(sum(v) / len(v), 2), "reviews": len(v)} for w, v in sorted(weekly.items())][-10:],
        "overdue_list": [review_dict(r, nm) for r in pending if r.overdue][:10],
    }


def supervisees(sup: User) -> list[dict]:
    ids = current_supervisee_ids(sup.id)
    links = {a.supervisee_id: a for a in SupervisionAssignment.objects.filter(supervisor=sup, effective_to__isnull=True)}
    out = []
    for u in User.objects.filter(id__in=ids).order_by("full_name"):
        revs, meets = Review.objects.filter(supervisee_id=u.id, supervisor_id=sup.id), SupervisionMeeting.objects.filter(supervisee_id=u.id, supervisor_id=sup.id, status__in=["completed", "missed"])
        scores = [r.performance_score for r in revs if r.performance_score]
        done = meets.count()
        out.append({"id": u.id, "name": u.full_name, "status": u.status, "role": u.role,
                    "pending_reviews": sum(r.decided_at is None for r in revs), "overdue_reviews": sum(r.overdue for r in revs),
                    "avg_performance": round(sum(scores) / len(scores), 2) if scores else None,
                    "meeting_attendance": round(meets.filter(status="completed").count() / done, 2) if done else None,
                    "schedule_every_days": getattr(links.get(u.id), "schedule_every_days", None), "since": getattr(links.get(u.id), "effective_from", None)})
    return out


def supervisee_detail(sup: User, uid: int) -> dict:
    require_supervisee(sup, uid)
    u, nm = User.objects.get(pk=uid), names([uid])
    since = timezone.now() - timedelta(days=28)
    counts = dict(Session.objects.filter(practitioner_id=uid, scheduled_start__gte=since).values_list("status").annotate(n=Count("id")))
    audit(sup, "supervisee_view", "user", uid, fields=["review history", "session counts (28d)", "meetings", "quality issues"])
    return {"user": {"id": u.id, "name": u.full_name, "status": u.status, "role": u.role}, "sessions_last_28d": counts,
            "reviews": [review_dict(r, nm) for r in Review.objects.filter(supervisee_id=uid, supervisor_id=sup.id).order_by("-id")[:25]],
            "meetings": list(SupervisionMeeting.objects.filter(supervisee_id=uid).order_by("-scheduled_at").values("id", "scheduled_at", "status")[:10]),
            "quality_issues": list(QualityIssue.objects.filter(practitioner_id=uid).order_by("-id").values("id", "title", "category", "severity", "status"))}


# ------------------------------------------------------------------ meetings
def schedule_meeting(sup: User, d: dict) -> SupervisionMeeting:
    require_supervisee(sup, d["supervisee_id"])
    meeting = SupervisionMeeting.objects.create(supervisor_id=sup.id, supervisee_id=d["supervisee_id"], scheduled_at=d["scheduled_at"])
    audit(sup, "meeting_schedule", "meeting", meeting.id)
    return meeting


def update_meeting(sup: User, mid: int, status: str) -> SupervisionMeeting:
    meeting = SupervisionMeeting.objects.filter(pk=mid, supervisor_id=sup.id).first()
    if not meeting:
        raise NotFound("Meeting not found")
    meeting.status = status
    meeting.save()
    audit(sup, "meeting_update", "meeting", mid, status=status)
    return meeting


# ------------------------------------------------------------------ reviews
def list_reviews(sup: User, params) -> list[dict]:
    qs = Review.objects.filter(supervisor_id=sup.id, supervisee_id__in=current_supervisee_ids(sup.id)).order_by("due_date")
    qs = qs.filter(status=params["status"]) if params.get("status") else qs
    qs = qs.filter(supervisee_id=params["supervisee_id"]) if params.get("supervisee_id") else qs
    rows = list(qs[:300])
    nm = names({r.supervisee_id for r in rows})
    return [review_dict(r, nm) for r in rows if r.overdue or params.get("overdue") != "true"]


def create_review(sup: User, d: dict) -> Review:
    require_supervisee(sup, d["supervisee_id"])
    case_ref, session = "CASE-MANUAL", None
    if d.get("session_id"):
        session = Session.objects.filter(pk=d["session_id"], practitioner_id=d["supervisee_id"]).first()
        if not session:
            raise ValidationError("Session does not belong to this supervisee")
        case_ref = f"CASE-{session.id:06d}"
    review = Review.objects.create(supervisor_id=sup.id, supervisee_id=d["supervisee_id"], session=session, case_ref=case_ref, due_date=d["due_date"])
    audit(sup, "review_create", "review", review.id, supervisee=d["supervisee_id"])
    return review


def review_detail(sup: User, rid: int) -> dict:
    review = own_review(sup, rid)
    audit(sup, "review_view", "review", rid, fields=["case_ref", "case", "notes", "feedback", "corrective_actions"])
    return review_dict(review, names([review.supervisee_id]), detail=True)


def start_review(sup: User, rid: int) -> Review:
    review = own_review(sup, rid)
    review.status, review.started_at = REVIEW_FLOW.apply("start", review.status), timezone.now()
    review.save()
    audit(sup, "review_start", "review", rid)
    return review


@transaction.atomic
def decide_review(sup: User, rid: int, d: dict) -> dict:
    review, now = own_review(sup, rid), timezone.now()
    review.status = REVIEW_FLOW.apply(d["outcome"], review.status)
    minutes = d.get("minutes_spent")
    review.decided_at, review.decision_minutes = now, minutes if minutes is not None else (round((now - review.started_at).total_seconds() / 60, 1) if review.started_at else 0.0)
    review.supervision_notes, review.feedback, review.performance_score, review.has_documentation = d["notes"], d["feedback"], d["performance_score"], d["has_documentation"]
    review.save()
    # the outcome is reflected in the practitioner's OPERATIONAL record – summary only, no clinical content crosses the boundary
    LifecycleEvent.objects.create(user_id=review.supervisee_id, event="supervision_review", actor_id=sup.id, effective_date=date.today(),
                                  reason=f"{review.case_ref}: {d['outcome']} (score {d['performance_score']}/5)")
    audit(sup, "review_decision", "review", rid, outcome=d["outcome"], documentation=d["has_documentation"], minutes=review.decision_minutes)
    out = {"review": review_dict(review, names([review.supervisee_id]), detail=True)}
    if d["outcome"] == "approved" and not d["has_documentation"]:
        out["warning"] = i18n.t("Approved without supporting documentation. This is recorded and visible to compliance monitoring.")
    return out


def add_corrective_action(sup: User, rid: int, d: dict) -> CorrectiveAction:
    review = own_review(sup, rid)
    if review.closed_at:
        raise Conflict("Review is closed")
    action = CorrectiveAction.objects.create(review=review, assigned_to=review.supervisee_id, **d)
    audit(sup, "corrective_action_assign", "review", rid, action=action.id, assigned_to=review.supervisee_id)
    return action


def update_corrective_action(user: User, aid: int, status: str) -> CorrectiveAction:
    action = CorrectiveAction.objects.select_related("review").filter(pk=aid).first()
    if not action:
        raise NotFound("Action not found")
    if user.id not in (action.assigned_to, action.review.supervisor_id):
        raise PermissionDenied("Only the assignee or the supervisor can update this action")
    action.status, action.completed_at = status, timezone.now() if status == "completed" else None
    action.save()
    audit(user, f"corrective_action_{status}", "corrective_action", aid)
    return action


def close_review(sup: User, rid: int, plan: str | None) -> Review:
    review = own_review(sup, rid)
    if review.status not in (RS.APPROVED, RS.NEEDS_CHANGES):
        raise Conflict("Review must be decided before it can be closed")
    open_actions = review.actions.filter(status="open").count()
    if open_actions and not plan:
        raise ValidationError("Open corrective actions remain: provide a monitoring/improvement plan to close the review")
    review.closed_at = timezone.now()
    review.supervision_notes = f"{review.supervision_notes or ''}\n[Monitoring plan] {plan}".strip() if plan else review.supervision_notes
    review.save()
    audit(sup, "review_close", "review", rid, open_actions=open_actions)
    return review


def my_reviews(user: User) -> dict:
    """Therapist view: own outcomes and corrective actions."""
    revs = Review.objects.filter(supervisee_id=user.id, decided_at__isnull=False).order_by("-decided_at")[:30]
    return {"reviews": [{"id": r.id, "case_ref": r.case_ref, "status": r.status, "decided_at": r.decided_at, "feedback": r.feedback, "performance_score": r.performance_score} for r in revs],
            "corrective_actions": list(CorrectiveAction.objects.filter(assigned_to=user.id).order_by("-id").values("id", "description", "due_date", "status"))}


# ------------------------------------------------------------------ quality issues
def list_issues(sup: User) -> list[dict]:
    rows = list(QualityIssue.objects.filter(practitioner_id__in=current_supervisee_ids(sup.id)).order_by("-id"))
    nm = names({i.practitioner_id for i in rows})
    return [{"id": i.id, "practitioner_id": i.practitioner_id, "practitioner": nm.get(i.practitioner_id), "category": i.category, "title": i.title, "detail": i.detail,
             "severity": i.severity, "status": i.status, "source_alert_id": i.source_alert_id, "created_at": i.created_at} for i in rows]


def create_issue(sup: User, d: dict) -> QualityIssue:
    require_supervisee(sup, d["practitioner_id"])
    issue = QualityIssue.objects.create(supervisor_id=sup.id, **d)
    audit(sup, "quality_issue_create", "quality_issue", issue.id, category=d["category"])
    return issue


def own_issue(sup: User, iid: int) -> QualityIssue:
    issue = QualityIssue.objects.filter(pk=iid, supervisor_id=sup.id).first()
    if not issue:
        raise NotFound("Issue not found")
    return issue


def resolve_issue(sup: User, iid: int) -> QualityIssue:
    issue = own_issue(sup, iid)
    issue.status, issue.resolved_at = "resolved", timezone.now()
    issue.save()
    audit(sup, "quality_issue_resolve", "quality_issue", iid)
    return issue


@transaction.atomic
def escalate_issue(sup: User, iid: int, reason: str) -> dict:
    issue = own_issue(sup, iid)
    if issue.status == "escalated":
        raise Conflict("Already escalated")
    issue.status = "escalated"
    alert = next(a for _, a in issue_escalated.send(sender=QualityIssue, issue=issue, supervisor=sup, reason=reason) if a)
    issue.source_alert_id = alert.id
    issue.save()
    audit(sup, "quality_issue_escalate", "quality_issue", iid, alert=alert.alert_uid, category=issue.category)
    return {"issue_id": issue.id, "alert_uid": alert.alert_uid, "domain": alert.domain}
