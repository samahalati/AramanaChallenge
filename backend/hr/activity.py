"""Spec §3.3 – operational framework for monitoring a practitioner: activity, sessions, referrals, quality indicators,
supervision participation, professional development, performance trends and unusual-activity patterns.

Only AGGREGATES are returned (counts, rates, averages): no session content and no client references, so HR roles never
touch clinical data (separation of duties). The alert part goes through the monitoring visibility rules.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta

from django.utils import timezone

from clinical.models import Referral, Session
from hr.models import ProfessionalDevelopment
from supervision.models import QualityIssue, Review, SupervisionMeeting

WEEKS = 8


def _week(dt) -> str:
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def sessions(uid: int, now) -> dict:
    rows = list(Session.objects.filter(practitioner_id=uid, scheduled_start__gte=now - timedelta(weeks=WEEKS)).values_list("scheduled_start", "status"))
    recent = Counter(status for start, status in rows if start >= now - timedelta(days=28))
    weekly: dict[str, Counter] = defaultdict(Counter)
    for start, status in rows:
        weekly[_week(start)][status] += 1
    return {"last_28d": {k: recent.get(k, 0) for k in ("completed", "scheduled", "cancelled", "no_show")},
            "completion_rate": _rate(recent.get("completed", 0), recent.get("completed", 0) + recent.get("cancelled", 0) + recent.get("no_show", 0)),
            "weekly": [{"week": w, "completed": c.get("completed", 0), "cancelled": c.get("cancelled", 0) + c.get("no_show", 0), "scheduled": c.get("scheduled", 0)} for w, c in sorted(weekly.items())]}


def referrals(uid: int, now) -> dict:
    since = now - timedelta(days=56)
    return {"received_56d": Referral.objects.filter(to_practitioner_id=uid, created_at__gte=since).count(),
            "made_56d": Referral.objects.filter(from_user_id=uid, created_at__gte=since).count()}


def quality(uid: int) -> dict:
    reviews = list(Review.objects.filter(supervisee_id=uid))
    scored = [r for r in reviews if r.performance_score is not None and r.decided_at]
    weekly: dict[str, list[int]] = defaultdict(list)
    for r in scored:
        weekly[_week(r.decided_at)].append(r.performance_score)
    issues = QualityIssue.objects.filter(practitioner_id=uid)
    return {"reviews": {"decided": sum(1 for r in reviews if r.decided_at), "pending": sum(1 for r in reviews if not r.decided_at), "overdue": sum(1 for r in reviews if r.overdue)},
            "avg_performance": round(sum(r.performance_score for r in scored) / len(scored), 2) if scored else None,
            "performance_trend": [{"week": w, "avg_score": round(sum(v) / len(v), 2)} for w, v in sorted(weekly.items())][-WEEKS:],
            "issues": {"open": issues.filter(status="open").count(), "total": issues.count()}}


def participation(uid: int) -> dict:
    past = SupervisionMeeting.objects.filter(supervisee_id=uid, status__in=["completed", "missed"])
    done = past.filter(status="completed").count()
    return {"meetings_held": past.count(), "attended": done, "attendance": _rate(done, past.count())}


def development(uid: int, today: date) -> dict:
    rows = list(ProfessionalDevelopment.objects.filter(user_id=uid).order_by("-completed_on"))
    year = [r for r in rows if r.completed_on >= today - timedelta(days=365)]
    return {"hours_12m": round(sum(r.hours for r in year), 1), "count_12m": len(year),
            "items": [{"id": r.id, "kind": r.kind, "title": r.title, "provider": r.provider, "hours": r.hours, "completed_on": r.completed_on} for r in rows[:20]]}


def unusual(viewer, uid: int) -> dict:
    from monitoring.services.alerts import user_history     # late import: monitoring already depends on hr
    h = user_history(viewer, uid)
    return {"by_status": h["by_status"], "alerts": h["alerts"][:5], "total": len(h["alerts"]), "note": h["note"]}


def practitioner_activity(viewer, user) -> dict:
    now, today = timezone.now(), date.today()
    return {"user_id": user.id, "sessions": sessions(user.id, now), "referrals": referrals(user.id, now), "quality": quality(user.id),
            "supervision_participation": participation(user.id), "professional_development": development(user.id, today), "unusual_activity": unusual(viewer, user.id)}
