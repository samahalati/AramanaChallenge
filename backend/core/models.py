"""Security boundary: append-only audit chain, access events, admin activity (feeds the anomaly engine).
Person references are plain integer IDs (no FK) – this keeps the boundary between identity/HR/clinical/security data."""
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    ts = models.DateTimeField(default=timezone.now, db_index=True)
    actor_id = models.IntegerField(null=True, db_index=True)
    action = models.CharField(max_length=80)
    resource_type = models.CharField(max_length=60)
    resource_id = models.CharField(max_length=60, null=True)
    outcome = models.CharField(max_length=20, default="ok")
    detail = models.JSONField(null=True)
    prev_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64)


class AccessEvent(models.Model):
    ts = models.DateTimeField(default=timezone.now, db_index=True)
    user_id = models.IntegerField(null=True, db_index=True)
    email_attempted = models.CharField(max_length=255, null=True)
    event = models.CharField(max_length=30)  # login_ok | login_failed | access_denied
    resource_type = models.CharField(max_length=60, null=True)
    permission = models.CharField(max_length=80, null=True)
    path = models.CharField(max_length=255, null=True)
    ip = models.CharField(max_length=64, null=True)


class AdminActivity(models.Model):
    ts = models.DateTimeField(default=timezone.now, db_index=True)
    actor_id = models.IntegerField(db_index=True)
    action = models.CharField(max_length=40, db_index=True)
    target_user_id = models.IntegerField(null=True)
    detail = models.JSONField(null=True)
