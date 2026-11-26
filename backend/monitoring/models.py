"""AI/monitoring boundary: detection runs, alerts, investigation timeline (IDs for people)."""
from django.db import models
from django.utils import timezone

from core.constants import AlertStatus, Domain


class DetectionRun(models.Model):
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True)
    triggered_by = models.IntegerField(null=True)
    ruleset_version = models.CharField(max_length=40)
    model_version = models.CharField(max_length=80)
    config_hash = models.CharField(max_length=64)
    as_of = models.DateTimeField(null=True)
    stats = models.JSONField(null=True)       # counts, suppressed candidates, timings


class Alert(models.Model):
    alert_uid = models.CharField(max_length=24, unique=True)
    category = models.CharField(max_length=2, db_index=True)
    scenario = models.CharField(max_length=60, db_index=True)
    domain = models.CharField(max_length=20, choices=Domain.choices, db_index=True)
    title = models.CharField(max_length=240)
    subject_user_id = models.IntegerField(null=True, db_index=True)
    risk_score = models.FloatField()
    risk_level = models.CharField(max_length=10, db_index=True)
    methods = models.JSONField()
    explanation = models.TextField()
    recommended_action = models.TextField()
    evidence = models.JSONField()
    score_breakdown = models.JSONField()
    record_refs = models.JSONField()
    status = models.CharField(max_length=24, choices=AlertStatus.choices, default=AlertStatus.NEW, db_index=True)
    assigned_to = models.IntegerField(null=True)
    dedup_key = models.CharField(max_length=160, db_index=True)
    run = models.ForeignKey(DetectionRun, null=True, on_delete=models.SET_NULL)
    ruleset_version = models.CharField(max_length=40)
    model_version = models.CharField(max_length=80)
    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now)
    window_start = models.DateTimeField(null=True)
    window_end = models.DateTimeField(null=True)


class AlertUser(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="users")
    user_id = models.IntegerField(db_index=True)
    role_in_alert = models.CharField(max_length=20, default="related")  # subject | related

    class Meta:
        unique_together = [("alert", "user_id")]


class InvestigationEvent(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="events")
    actor_id = models.IntegerField(null=True)
    action = models.CharField(max_length=30)
    note = models.TextField(null=True)
    from_status = models.CharField(max_length=24, null=True)
    to_status = models.CharField(max_length=24, null=True)
    ts = models.DateTimeField(default=timezone.now, db_index=True)


class AssistantExchange(models.Model):
    """Every AI-assistant interaction (briefing or question): what was asked, what was shown, and the guardrail report. Append-only."""
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="assistant_exchanges")
    actor_id = models.IntegerField(db_index=True)
    kind = models.CharField(max_length=10)            # briefing | answer
    question = models.TextField(null=True)
    provider = models.CharField(max_length=40)        # groq | gemini | ollama | custom | template | template(fallback) | guardrail (refused)
    refused = models.BooleanField(default=False)
    content = models.JSONField()
    citations = models.JSONField()
    guardrails = models.JSONField()
    ts = models.DateTimeField(default=timezone.now, db_index=True)
