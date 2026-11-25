"""Account use-cases: authentication with lockout, account creation, role/status administration."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied

from accounts.models import User
from core.audit import audit, log_admin, record_access
from core.constants import UserStatus
from core.errors import Conflict
from core.rbac import ROLE_NAV, ROLE_PERMISSIONS

log = logging.getLogger("aramana.security")


def profile(user: User) -> dict:
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role, "status": user.status,
            "permissions": sorted(ROLE_PERMISSIONS.get(user.role, ())), "nav": ROLE_NAV.get(user.role, [])}


def authenticate(email: str, password: str, ip: str | None) -> User:
    """Uniform failure for unknown user / bad password / inactive (no account enumeration); lockout after N failures."""
    email = email.strip().lower()
    user = User.objects.filter(email=email).first()
    if user is None:
        record_access(None, "login_failed", email_attempted=email, ip=ip)
        log.warning("login failed: unknown or inactive account ip=%s", ip)
        raise AuthenticationFailed("Invalid credentials")
    if user.locked_until and user.locked_until > timezone.now():
        record_access(user.id, "login_failed", email_attempted=email, ip=ip)
        log.warning("login refused: account locked user=%s ip=%s", user.id, ip)
        raise PermissionDenied("Account temporarily locked")
    if not user.check_password(password) or user.status != UserStatus.ACTIVE:
        user.failed_logins += 1
        if user.failed_logins >= settings.MAX_FAILED_LOGINS:
            user.failed_logins, user.locked_until = 0, timezone.now() + timedelta(minutes=settings.LOCKOUT_MINUTES)
            log.warning("account locked after repeated failures user=%s ip=%s", user.id, ip)
        user.save(update_fields=["failed_logins", "locked_until"])
        record_access(user.id, "login_failed", email_attempted=email, ip=ip)
        raise AuthenticationFailed("Invalid credentials")
    user.failed_logins, user.locked_until = 0, None
    user.save(update_fields=["failed_logins", "locked_until"])
    record_access(user.id, "login_ok", email_attempted=email, ip=ip)
    audit(user, "login", "session", user.id)
    return user


@transaction.atomic
def create_account(actor: User, *, email: str, full_name: str, role: str, password: str, status: str = UserStatus.PENDING) -> User:
    if User.objects.filter(email=email.lower()).exists():
        raise Conflict("E-mail already registered")
    user = User.objects.create_user(email, password, full_name=full_name, role=role, status=status, created_by=actor.id)
    log_admin(actor, "account_create", user.id, role=role)
    return user


def _target(actor: User, user_id: int) -> User:
    user = User.objects.filter(pk=user_id).first()
    if not user:
        raise NotFound("User not found")
    return user


def change_role(actor: User, user_id: int, role: str, reason: str) -> User:
    if user_id == actor.id:   # separation of duties: nobody elevates themselves; the attempt is itself audited (outside any transaction that would roll it back)
        audit(actor, "self_role_change_blocked", "user", user_id, outcome="denied", requested=role)
        raise PermissionDenied("Administrators cannot change their own role")
    with transaction.atomic():
        user = _target(actor, user_id)
        before, user.role = user.role, role
        user.save(update_fields=["role"])
        log_admin(actor, "role_change", user.id, **{"from": before, "to": role, "reason": reason})
    return user


@transaction.atomic
def change_status(actor: User, user_id: int, status: str, reason: str) -> User:
    user = _target(actor, user_id)
    if user.id == actor.id:
        raise PermissionDenied("Administrators cannot change their own status")
    if user.status == UserStatus.TERMINATED:
        raise Conflict("Terminated accounts cannot be re-enabled here (HR lifecycle)")
    user.status, user.failed_logins, user.locked_until = status, 0, None
    user.save(update_fields=["status", "failed_logins", "locked_until"])
    log_admin(actor, "status_change", user.id, to=status, reason=reason)
    return user
