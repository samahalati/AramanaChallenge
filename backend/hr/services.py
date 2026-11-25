"""Module A use-cases. Views stay thin; every state change is atomic, audited and recorded in the history."""
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q
from rest_framework.exceptions import NotFound, ValidationError

from accounts import services as accounts
from accounts.models import User
from core.audit import log_admin
from core.constants import Role, UserStatus
from core.errors import Conflict
from core.statemachine import StateMachine
from hr.models import Contract, Credential, LifecycleEvent, OrgUnit, PractitionerProfile, ProfessionalDevelopment, SupervisionAssignment
from hr.selectors import current_assignments
from hr.serializers import PRACTITIONER_ROLES

S = UserStatus
LIFECYCLE = StateMachine({   # action -> ({from}, to)
    "activate": ({S.PENDING}, S.ACTIVE), "suspend": ({S.ACTIVE}, S.SUSPENDED), "reactivate": ({S.SUSPENDED}, S.ACTIVE),
    "terminate": ({S.ACTIVE, S.SUSPENDED, S.PENDING}, S.TERMINATED)})
EVENT_NAMES = {"activate": "onboarded", "suspend": "suspended", "reactivate": "reactivated", "terminate": "terminated"}


def practitioners():
    return User.objects.filter(role__in=PRACTITIONER_ROLES).select_related("profile__org_unit")


def get_practitioner(uid: int) -> User:
    user = practitioners().filter(pk=uid).first()
    if not user:
        raise NotFound("Practitioner not found")
    return user


def add_history(user_id: int, event: str, reason: str | None, actor_id: int | None, effective: date | None = None) -> None:
    LifecycleEvent.objects.create(user_id=user_id, event=event, reason=reason, actor_id=actor_id, effective_date=effective or date.today())


@transaction.atomic
def create_practitioner(actor: User, d: dict) -> User:
    user = accounts.create_account(actor, email=d["email"], full_name=d["full_name"], role=d["role"], password=d["initial_password"])
    PractitionerProfile.objects.create(user=user, specialization=d.get("specialization"), org_unit_id=d.get("org_unit_id"),
                                       employment_type=d["employment_type"], hire_date=d.get("hire_date"),
                                       capacity_weekly_sessions=d["capacity_weekly_sessions"])
    add_history(user.id, "onboarding_started", "Profile created", actor.id)
    return user


@transaction.atomic
def update_profile(actor: User, uid: int, changes: dict) -> None:
    profile = get_practitioner(uid).profile
    before = {k: getattr(profile, k) for k in changes}
    for key, value in changes.items():
        setattr(profile, key, value)
    profile.save()
    log_admin(actor, "profile_edit", uid, before=before, after=changes)


@transaction.atomic
def change_lifecycle(actor: User, uid: int, action: str, reason: str, effective: date | None) -> User:
    """Onboard / suspend / reactivate / terminate: a HUMAN HR decision – never triggered by an alert or risk score."""
    user = get_practitioner(uid)
    user.status = LIFECYCLE.apply(action, user.status)
    user.save(update_fields=["status"])
    effective = effective or date.today()
    add_history(uid, EVENT_NAMES[action], reason, actor.id, effective)
    if user.status == S.TERMINATED:
        current_assignments().filter(Q(supervisee=user) | Q(supervisor=user)).update(effective_to=effective)
        Contract.objects.filter(user=user, status="active").update(status="terminated", end_date=effective)
    log_admin(actor, "status_change", uid, action=action, reason=reason, new_status=user.status)
    return user


@transaction.atomic
def assign_supervisor(actor: User, d: dict) -> SupervisionAssignment:
    supervisor, supervisee = User.objects.filter(pk=d["supervisor_id"]).first(), User.objects.filter(pk=d["supervisee_id"]).first()
    if not supervisor or supervisor.role != Role.CLINICAL_SUPERVISOR or supervisor.status != S.ACTIVE:
        raise ValidationError("supervisor must be an active clinical supervisor")
    if not supervisee or supervisee.role not in (Role.THERAPIST, Role.ASSISTANT_COUNSELOR) or supervisee.status != S.ACTIVE:
        raise ValidationError("supervisee must be an active therapist or assistant counselor")
    if supervisor.id == supervisee.id:
        raise ValidationError("self-supervision is not allowed")
    start = d.get("effective_from") or date.today()
    previous = list(SupervisionAssignment.objects.filter(supervisee=supervisee, effective_to__isnull=True))
    if any(a.supervisor_id == supervisor.id for a in previous):
        raise Conflict("This supervision relationship already exists")
    for a in previous:   # effective-dated: end the old relationship the day before, keep it as history
        a.effective_to = start - timedelta(days=1)
        a.save(update_fields=["effective_to"])
    new = SupervisionAssignment.objects.create(supervisor=supervisor, supervisee=supervisee, effective_from=start,
                                               schedule_every_days=d["schedule_every_days"], reason=d["reason"], created_by=actor.id)
    add_history(supervisee.id, "supervisor_reassigned" if previous else "supervisor_assigned", d["reason"], actor.id, start)
    log_admin(actor, "assignment_edit", supervisee.id, supervisor=supervisor.id, effective_from=str(start), replaced=[a.id for a in previous])
    return new


@transaction.atomic
def add_development(actor: User, uid: int, d: dict) -> ProfessionalDevelopment:
    get_practitioner(uid)
    item = ProfessionalDevelopment.objects.create(user_id=uid, recorded_by=actor.id, **d)
    log_admin(actor, "development_add", uid, title=item.title, hours=item.hours)
    return item


def record_change(actor: User, action: str, user_id: int, op: str, **detail) -> None:
    log_admin(actor, action, user_id, op=op, **detail)


def dashboard() -> dict:
    today = date.today()
    soon = today + timedelta(days=60)
    prac = practitioners()
    creds = Credential.objects.filter(expires_on__lte=soon).select_related("user").order_by("expires_on")
    ending = Contract.objects.filter(status="active", end_date__isnull=False, end_date__lte=soon).select_related("user").order_by("end_date")
    recent = LifecycleEvent.objects.select_related("user").order_by("-id")[:10]
    assigned = current_assignments().values("supervisee_id")
    return {
        "practitioners_by_status": dict(prac.values_list("status").annotate(n=Count("id"))),
        "practitioners_by_role": dict(prac.values_list("role").annotate(n=Count("id"))),
        "credentials_expiring_or_expired": [{"id": c.id, "user_id": c.user_id, "practitioner": c.user.full_name, "title": c.title, "expires_on": c.expires_on,
                                             "status": c.status, "days_to_expiry": (c.expires_on - today).days} for c in creds],
        "contracts_ending_soon": [{"id": c.id, "user_id": c.user_id, "practitioner": c.user.full_name, "kind": c.kind, "end_date": c.end_date} for c in ending],
        "recent_lifecycle": [{"user_id": e.user_id, "practitioner": e.user.full_name, "event": e.event, "reason": e.reason, "date": e.effective_date} for e in recent],
        "unassigned_supervisees": prac.filter(role=Role.THERAPIST, status=S.ACTIVE).exclude(id__in=assigned).count(),
    }


def org_tree() -> list[dict]:
    return [{"id": o.id, "name": o.name, "kind": o.kind, "parent_id": o.parent_id, "members": o.n}
            for o in OrgUnit.objects.annotate(n=Count("practitionerprofile"))]


def assignments_list(current_only: bool = True) -> list[dict]:
    qs = SupervisionAssignment.objects.select_related("supervisor", "supervisee").order_by("-effective_from")
    qs = qs.filter(effective_to__isnull=True) if current_only else qs
    return [{"id": a.id, "supervisor_id": a.supervisor_id, "supervisor": a.supervisor.full_name, "supervisee_id": a.supervisee_id,
             "supervisee": a.supervisee.full_name, "effective_from": a.effective_from, "effective_to": a.effective_to,
             "current": a.effective_to is None or a.effective_to >= date.today(), "schedule_every_days": a.schedule_every_days, "reason": a.reason} for a in qs]
