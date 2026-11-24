"""Access policy that depends on alerts: who may see an alert, and who may read a practitioner's clinical records.
Role grants the KIND of access (core.rbac); relationship scoping grants the RECORD."""
from collections import defaultdict

from core.constants import Role
from core.rbac import ALERT_DOMAIN_VISIBILITY, has_perm
from hr.selectors import current_supervisee_ids
from monitoring.models import Alert, AlertUser


def alert_users(alert_ids) -> dict[int, dict[int, str]]:
    """{alert_id: {user_id: role_in_alert}}"""
    out = defaultdict(dict)
    for au in AlertUser.objects.filter(alert_id__in=list(alert_ids)):
        out[au.alert_id][au.user_id] = au.role_in_alert
    return out


def alert_visible(user, alert: Alert, uids: set[int]) -> bool:
    """Domain visibility + conflict-of-interest guard (never the subject / a related user) + supervisor relationship scoping."""
    if user.id in uids or alert.domain not in ALERT_DOMAIN_VISIBILITY.get(user.role, ()):
        return False
    if user.role == Role.CLINICAL_SUPERVISOR:
        mine = current_supervisee_ids(user.id)
        return bool(uids & mine) or alert.subject_user_id in mine
    return True


def visible_alerts(user, **flt) -> list[tuple[Alert, dict]]:
    domains = ALERT_DOMAIN_VISIBILITY.get(user.role, set())
    if not has_perm(user.role, "alerts:read") or not domains:
        return []
    qs = Alert.objects.filter(domain__in=domains).order_by("-risk_score", "-id")
    for lookup in ("status", "category", "domain", "scenario"):
        qs = qs.filter(**{lookup: flt[lookup]}) if flt.get(lookup) else qs
    qs = qs.filter(risk_level=flt["level"]) if flt.get("level") else qs
    alerts = list(qs)
    users = alert_users(a.id for a in alerts)
    rows = [(a, users[a.id]) for a in alerts if alert_visible(user, a, set(users[a.id]))]
    return [(a, u) for a, u in rows if a.status in ("new", "under_review", "info_requested", "escalated")] if flt.get("open_only") else rows


def can_read_clinical_of(user, practitioner_id: int) -> bool:
    if has_perm(user.role, "clinical:read:own") and user.id == practitioner_id:
        return True
    if has_perm(user.role, "clinical:read:supervisees") and practitioner_id in current_supervisee_ids(user.id):
        return True
    return has_perm(user.role, "clinical:read:alerted") and AlertUser.objects.filter(user_id=practitioner_id).exists()
