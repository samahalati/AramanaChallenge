"""Observer: turn a supervisor's escalated quality issue into an alert for compliance. The score is the supervisor's own
severity judgement (manual indicator) – honest about provenance, still fully traceable."""
from django.utils import timezone

from core.constants import AlertStatus, Domain
from detection.explain import DISCLAIMER
from monitoring.models import Alert, AlertUser, InvestigationEvent

POINTS = {"low": 25, "medium": 50, "high": 75}


def on_issue_escalated(sender, issue, supervisor, reason, **kwargs) -> Alert:
    pts = POINTS[issue.severity]
    alert = Alert.objects.create(
        alert_uid=f"tmp-esc-{issue.id}-{timezone.now().timestamp()}", dedup_key=f"Q:escalation:{issue.id}", category="Q", scenario="supervisor_escalation", domain=Domain(issue.category),
        title=f"Supervisor escalation: {issue.title}", subject_user_id=issue.practitioner_id, risk_score=float(pts), risk_level="low" if pts < 35 else "medium" if pts < 60 else "high",
        methods=["manual"], explanation=f"Escalated by clinical supervisor {supervisor.full_name}: {reason}\n\n{DISCLAIMER}",
        recommended_action="Compliance review of the supervisor's concern; consider clinical or HR follow-up through the documented process.",
        evidence=[{"type": "quality_issue", "issue_id": issue.id, "category": issue.category, "severity": issue.severity, "detail": issue.detail}],
        score_breakdown=[{"name": "supervisor_judgement", "label": "Supervisor severity judgement", "value": issue.severity, "threshold": "n/a", "weight": 1.0, "strength": pts / 100,
                          "method": "manual", "contribution": pts / 100, "points": float(pts), "note": "Human input"}],
        record_refs=[f"quality_issue:{issue.id}"], ruleset_version="manual", model_version="n/a")
    alert.alert_uid = f"ALR-{alert.id:06d}"
    alert.save(update_fields=["alert_uid"])
    AlertUser.objects.create(alert=alert, user_id=issue.practitioner_id, role_in_alert="subject")
    InvestigationEvent.objects.create(alert=alert, actor_id=supervisor.id, action="created", note="Created from supervisor escalation", to_status=AlertStatus.NEW)
    return alert
