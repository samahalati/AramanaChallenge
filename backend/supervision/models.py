"""Module B data: supervisory reviews, corrective actions, quality issues, supervision meetings (IDs for people)."""
from datetime import date

from django.db import models
from django.utils import timezone


class ReviewStatus(models.TextChoices):
    PENDING, IN_PROGRESS, NEEDS_CHANGES, APPROVED = "pending", "in_progress", "needs_changes", "approved"


class Review(models.Model):
    supervisor_id = models.IntegerField(db_index=True)
    supervisee_id = models.IntegerField(db_index=True)
    session = models.ForeignKey("clinical.Session", null=True, blank=True, on_delete=models.SET_NULL)
    case_ref = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING, db_index=True)
    due_date = models.DateField()
    opened_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True, db_index=True)
    decision_minutes = models.FloatField(null=True, blank=True)      # reviewer time on task (behavioural feature)
    has_documentation = models.BooleanField(default=False)           # supporting documentation attached? (feature)
    supervision_notes = models.TextField(null=True, blank=True)
    feedback = models.TextField(null=True, blank=True)
    performance_score = models.IntegerField(null=True, blank=True)   # 1..5
    closed_at = models.DateTimeField(null=True, blank=True)

    @property
    def overdue(self) -> bool:
        return self.decided_at is None and self.due_date < date.today()


class CorrectiveAction(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="actions")
    description = models.TextField()
    assigned_to = models.IntegerField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, default="open")  # open | completed | cancelled
    completed_at = models.DateTimeField(null=True, blank=True)


class QualityIssue(models.Model):
    practitioner_id = models.IntegerField(db_index=True)
    supervisor_id = models.IntegerField(null=True, db_index=True)
    category = models.CharField(max_length=20)  # operational | clinical | misconduct
    title = models.CharField(max_length=200)
    detail = models.TextField(null=True, blank=True)
    severity = models.CharField(max_length=10, default="medium")
    status = models.CharField(max_length=20, default="open", db_index=True)  # open | resolved | escalated
    source_alert_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)


class SupervisionMeeting(models.Model):
    supervisor_id = models.IntegerField(db_index=True)
    supervisee_id = models.IntegerField(db_index=True)
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, default="scheduled")  # scheduled | completed | missed
