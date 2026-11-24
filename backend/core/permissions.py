"""One declarative permission class for the whole API (Open/Closed: new views just declare `perms`).

    class MyView(APIView):
        perms = {"get": "hr:read", "post": "hr:write"}         # APIView: keyed by HTTP method
        perms = {"list": "hr:read", "lifecycle": "hr:write"}   # ViewSet: keyed by action;  "*" = default

Missing entry => denied (secure by default). Every denial is persisted as an access event + audit row; this is the
raw signal for the "unauthorized administrative activity" scenario.
"""
from rest_framework.permissions import BasePermission

from core.audit import audit, record_access
from core.rbac import has_perm

AUTHENTICATED = "authenticated"   # any signed-in user


def deny(request, permission: str) -> None:
    resource = request.path.strip("/").split("/")[1:2] or ["root"]
    record_access(request.user.id, "access_denied", permission=permission, resource_type=resource[0], path=request.path,
                  ip=request.META.get("REMOTE_ADDR"))
    audit(request.user, "access_denied", resource[0], request.path, outcome="denied", permission=permission, method=request.method)


class RolePermission(BasePermission):
    message = "Insufficient permissions for this resource"

    def has_permission(self, request, view):
        if request.user is None:
            return False
        key = getattr(view, "action", None) or request.method.lower()
        need = getattr(view, "perms", {}).get(key) or getattr(view, "perms", {}).get("*")
        needed = (need,) if isinstance(need, str) else tuple(need or ())
        if needed == (AUTHENTICATED,):
            return True
        if needed and any(has_perm(request.user.role, p) for p in needed):
            return True
        deny(request, "|".join(needed) or f"undeclared:{key}")
        return False
