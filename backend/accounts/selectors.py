"""Read helpers other apps use instead of reaching into the User table (keeps module boundaries explicit)."""
from accounts.models import User


def briefs(ids) -> dict[int, dict]:
    """{id: {id, name, role, status}} for a set of user ids."""
    return {u.id: {"id": u.id, "name": u.full_name, "role": u.role, "status": u.status} for u in User.objects.filter(id__in=list(ids))}


def names(ids) -> dict[int, str]:
    return {i: b["name"] for i, b in briefs(ids).items()}
