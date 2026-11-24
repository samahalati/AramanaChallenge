"""Clinical-operational boundary. Clients are pseudonyms only (no names, contact data or clinical narrative).
Practitioner references are plain integer IDs by design (no FK into the identity/HR tables)."""
from django.db import models
from django.utils import timezone


class SessionStatus(models.TextChoices):
    SCHEDULED, COMPLETED, CANCELLED, NO_SHOW = "scheduled", "completed", "cancelled", "no_show"


class Client(models.Model):
    client_ref = models.CharField(max_length=20, unique=True)
    primary_need = models.CharField(max_length=60)


class Session(models.Model):
    practitioner_id = models.IntegerField(db_index=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    group_id = models.CharField(max_length=40, null=True, blank=True)       # legitimate group sessions share it
    scheduled_start = models.DateTimeField(db_index=True)
    scheduled_end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=SessionStatus.choices, default=SessionStatus.SCHEDULED, db_index=True)
    mode = models.CharField(max_length=20, default="online")                # online | in_person
    location_code = models.CharField(max_length=40, null=True, blank=True)
    reported_duration_min = models.IntegerField(null=True, blank=True)
    checkin_at = models.DateTimeField(null=True, blank=True)
    checkout_at = models.DateTimeField(null=True, blank=True)
    modification_count = models.IntegerField(default=0)
    last_modified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["practitioner_id", "scheduled_start"])]


class Referral(models.Model):
    from_user_id = models.IntegerField(db_index=True)
    to_practitioner_id = models.IntegerField(db_index=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    need = models.CharField(max_length=60)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)
