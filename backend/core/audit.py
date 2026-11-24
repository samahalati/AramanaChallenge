"""Tamper-evident audit trail (SHA-256 hash chain) + access events + admin activity."""
import hashlib
import json

from django.utils import timezone

from core.models import AccessEvent, AdminActivity, AuditLog

GENESIS = "0" * 64


def _digest(prev, ts, actor_id, action, rtype, rid, outcome, detail) -> str:
    payload = json.dumps([prev, ts.isoformat(), actor_id, action, rtype, rid, outcome, detail], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def audit(actor, action: str, resource: str, rid=None, /, *, outcome: str = "ok", ts=None, **detail) -> AuditLog:
    """Append one chained row. `actor` may be a user, an id or None."""
    prev = AuditLog.objects.order_by("-id").values_list("hash", flat=True).first() or GENESIS
    ts, rid = ts or timezone.now(), None if rid is None else str(rid)
    actor_id = getattr(actor, "id", actor)
    detail = detail or None
    return AuditLog.objects.create(ts=ts, actor_id=actor_id, action=action, resource_type=resource, resource_id=rid, outcome=outcome,
                                   detail=detail, prev_hash=prev, hash=_digest(prev, ts, actor_id, action, resource, rid, outcome, detail))


def record_access(user_id, event: str, **fields) -> AccessEvent:
    return AccessEvent.objects.create(user_id=user_id, event=event, **fields)


def log_admin(actor, action: str, target_id=None, /, **detail) -> None:
    """Administrative change = activity record (for anomaly detection) + audit row (for traceability)."""
    AdminActivity.objects.create(actor_id=actor.id, action=action, target_user_id=target_id, detail=detail or None)
    audit(actor, action, "user", target_id, **detail)


def verify_chain() -> dict:
    prev, n = GENESIS, 0
    for r in AuditLog.objects.order_by("id").iterator():
        if r.prev_hash != prev or r.hash != _digest(prev, r.ts, r.actor_id, r.action, r.resource_type, r.resource_id, r.outcome, r.detail):
            return {"ok": False, "checked": n, "first_bad_id": r.id}
        prev, n = r.hash, n + 1
    return {"ok": True, "checked": n, "first_bad_id": None}
