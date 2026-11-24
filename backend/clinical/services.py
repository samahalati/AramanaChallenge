"""Sessions and referrals. Scoped, audited, and every post-hoc edit is counted (a feature for anomaly detection)."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import User
from clinical.models import Client, Referral, Session, SessionStatus
from clinical.serializers import SessionSerializer
from core.audit import audit
from core.constants import Role, UserStatus
from core.statemachine import StateMachine

SESSION_FLOW = StateMachine({s: ({SessionStatus.SCHEDULED}, s) for s in ("completed", "cancelled", "no_show")})   # target -> ({from}, to)


def client_by_ref(ref: str) -> Client:
    client = Client.objects.filter(client_ref=ref).first()
    if not client:
        raise NotFound("Unknown client reference")
    return client


def caseload_client_ids(user_id: int) -> set[int]:
    return set(Referral.objects.filter(to_practitioner_id=user_id).values_list("client_id", flat=True)) | \
        set(Session.objects.filter(practitioner_id=user_id).values_list("client_id", flat=True))


def list_sessions(actor: User, practitioner_id: int, params) -> list[dict]:
    qs = Session.objects.filter(practitioner_id=practitioner_id).select_related("client").order_by("-scheduled_start")
    for key, lookup in (("since", "scheduled_start__date__gte"), ("until", "scheduled_start__date__lte"), ("status", "status")):
        qs = qs.filter(**{lookup: params[key]}) if params.get(key) else qs
    rows = SessionSerializer(qs[:200], many=True).data
    audit(actor, "clinical_read", "sessions", practitioner_id, rows=len(rows), fields=["timing", "status", "mode", "client_ref(pseudonym)", "check-in/out"])
    return rows


def my_clients(user: User) -> list[dict]:
    return list(Client.objects.filter(id__in=caseload_client_ids(user.id)).order_by("client_ref").values("client_ref", "primary_need"))


def create_session(user: User, d: dict) -> Session:
    client = client_by_ref(d["client_ref"])
    if client.id not in caseload_client_ids(user.id):
        raise PermissionDenied("Client is not in your caseload")
    start = d["scheduled_start"]
    session = Session.objects.create(practitioner_id=user.id, client=client, scheduled_start=start, scheduled_end=start + timedelta(minutes=d["duration_min"]),
                                     mode=d["mode"], location_code=d.get("location_code") or None)
    audit(user, "session_create", "sessions", session.id)
    return session


def _own(user: User, sid: int) -> Session:
    session = Session.objects.filter(pk=sid, practitioner_id=user.id).select_related("client").first()
    if not session:
        raise NotFound("Session not found")
    return session


@transaction.atomic
def update_session(user: User, sid: int, d: dict) -> Session:
    s, now = _own(user, sid), timezone.now()
    modified = False
    if d.get("status") and d["status"] != s.status:
        s.status, modified = SESSION_FLOW.apply(d["status"], s.status), d["status"] == "cancelled"
        if s.status == SessionStatus.COMPLETED:
            s.reported_duration_min = d.get("reported_duration_min") or int((s.scheduled_end - s.scheduled_start).total_seconds() / 60)
    elif "reported_duration_min" in d and s.status == SessionStatus.COMPLETED:
        s.reported_duration_min, modified = d["reported_duration_min"], True
    if d.get("scheduled_start") and d["scheduled_start"] != s.scheduled_start:
        s.scheduled_end, s.scheduled_start, modified = d["scheduled_start"] + (s.scheduled_end - s.scheduled_start), d["scheduled_start"], True
    if modified:
        s.modification_count, s.last_modified_at = s.modification_count + 1, now
    s.save()
    audit(user, "session_update", "sessions", s.id, changes={k: str(v) for k, v in d.items()})
    return s


def check(user: User, sid: int, out: bool = False) -> Session:
    s = _own(user, sid)
    if out and not s.checkin_at:
        raise ValidationError("No check-in recorded")
    setattr(s, "checkout_at" if out else "checkin_at", timezone.now())
    s.save()
    audit(user, "session_checkout" if out else "session_checkin", "sessions", s.id)
    return s


def eligible_practitioners(need: str) -> list[dict]:
    users = User.objects.filter(role=Role.THERAPIST, status=UserStatus.ACTIVE, profile__specialization=need).select_related("profile")
    return [{"id": u.id, "name": u.full_name, "specialization": need, "capacity_weekly_sessions": u.profile.capacity_weekly_sessions} for u in users]


def create_referral(user: User, d: dict) -> Referral:
    target = User.objects.filter(pk=d["to_practitioner_id"], role=Role.THERAPIST, status=UserStatus.ACTIVE).first()
    if not target:
        raise ValidationError("Target must be an active therapist")
    referral = Referral.objects.create(from_user_id=user.id, to_practitioner_id=target.id, client=client_by_ref(d["client_ref"]), need=d["need"])
    audit(user, "referral_create", "referrals", referral.id)
    return referral


def my_referrals(user: User) -> list[dict]:
    rows = Referral.objects.filter(from_user_id=user.id).select_related("client").order_by("-id")[:100]
    return [{"id": r.id, "client_ref": r.client.client_ref, "to_practitioner_id": r.to_practitioner_id, "need": r.need, "created_at": r.created_at} for r in rows]
