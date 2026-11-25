"""HR boundary: workforce data. Owns profiles, credentials, contracts, professional development, lifecycle history and effective-dated assignments."""
from django.conf import settings
from django.db import models
from django.utils import timezone

U = settings.AUTH_USER_MODEL


class OrgUnit(models.Model):
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=30, default="team")  # region | team
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")


class PractitionerProfile(models.Model):
    user = models.OneToOneField(U, on_delete=models.CASCADE, related_name="profile")
    specialization = models.CharField(max_length=60, null=True, blank=True, db_index=True)
    org_unit = models.ForeignKey(OrgUnit, null=True, blank=True, on_delete=models.SET_NULL)
    employment_type = models.CharField(max_length=30, default="employee")  # employee | contractor | volunteer
    hire_date = models.DateField(null=True, blank=True)
    capacity_weekly_sessions = models.IntegerField(default=25)
    bio = models.TextField(null=True, blank=True)


class Credential(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="credentials")
    kind = models.CharField(max_length=30)  # license | certification | degree
    title = models.CharField(max_length=160)
    number = models.CharField(max_length=60)
    issuer = models.CharField(max_length=160, blank=True, default="")
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, default="valid")  # valid | expired | revoked | pending
    updated_at = models.DateTimeField(default=timezone.now)


class Contract(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="contracts")
    kind = models.CharField(max_length=40)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default="active")  # draft | active | ended | terminated
    document_ref = models.CharField(max_length=120, null=True, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)


class LifecycleEvent(models.Model):
    """Complete activity & status history (onboarding, suspension, reassignment, review-outcome summaries)."""
    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="lifecycle")
    event = models.CharField(max_length=40)
    reason = models.TextField(null=True, blank=True)
    effective_date = models.DateField()
    actor_id = models.IntegerField(null=True)
    created_at = models.DateTimeField(default=timezone.now)


class ProfessionalDevelopment(models.Model):
    """Professional development activities (trainings, courses, conferences, supervision hours) – feeds the HR activity view (spec §3.3)."""
    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="development")
    kind = models.CharField(max_length=30)  # training | course | conference | workshop | supervision_hours
    title = models.CharField(max_length=160)
    provider = models.CharField(max_length=160, blank=True, default="")
    hours = models.FloatField(default=0)
    completed_on = models.DateField(db_index=True)
    recorded_by = models.IntegerField(null=True)


class SupervisionAssignment(models.Model):
    """Supervisor–supervisee relationship, effective-dated: history is preserved, never overwritten."""
    supervisor = models.ForeignKey(U, on_delete=models.CASCADE, related_name="supervisee_links")
    supervisee = models.ForeignKey(U, on_delete=models.CASCADE, related_name="supervisor_links")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    schedule_every_days = models.IntegerField(default=7)
    reason = models.TextField(null=True, blank=True)
    created_by = models.IntegerField(null=True)

    class Meta:
        indexes = [models.Index(fields=["supervisee", "effective_to"])]
