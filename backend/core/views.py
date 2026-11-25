from django.db import DatabaseError, connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core import constants as C
from core import i18n
from core.audit import verify_chain
from core.models import AccessEvent, AuditLog
from core.permissions import AUTHENTICATED
from core.rbac import ALERT_DOMAIN_VISIBILITY, INVESTIGATE_DOMAINS, ROLE_NAV, ROLE_PERMISSIONS


class Health(APIView):
    permission_classes, authentication_classes = [AllowAny], []

    def get(self, request):
        """Readiness probe for load balancers: 200 only when the database answers, so a replica without a database is taken out of rotation."""
        try:
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return Response({"status": "database unavailable"}, status=503)
        return Response({"status": "ok"})


class Labels(APIView):
    """Persian labels for every backend vocabulary (roles, statuses, actions, evidence keys…). Empty for English – the UI falls back to the raw tokens."""
    permission_classes, authentication_classes = [AllowAny], []

    def get(self, request):
        return Response(i18n.labels())


class RbacMatrix(APIView):
    """The matrix the API enforces – the UI renders exactly this (single source of truth)."""
    perms = {"get": AUTHENTICATED}

    def get(self, request):
        return Response({"roles": [{"role": r, "description": i18n.ROLE_DESCRIPTIONS[r] if i18n.lang() == "fa" else C.ROLE_DESCRIPTIONS[r], "permissions": sorted(ROLE_PERMISSIONS[r]), "nav": ROLE_NAV[r],
                                    "alert_domains_visible": sorted(ALERT_DOMAIN_VISIBILITY.get(r, [])), "alert_domains_investigate": sorted(INVESTIGATE_DOMAINS.get(r, []))}
                                   for r in C.Role.values]})


class AuditList(APIView):
    perms = {"get": "audit:read"}

    def get(self, request):
        q = request.query_params
        qs = AuditLog.objects.order_by("-id")
        qs = qs.filter(actor_id=q["actor_id"]) if q.get("actor_id") else qs
        qs = qs.filter(action=q["action"]) if q.get("action") else qs
        return Response([{"id": a.id, "ts": a.ts, "actor_id": a.actor_id, "action": a.action, "resource_type": a.resource_type, "resource_id": a.resource_id,
                          "outcome": a.outcome, "detail": a.detail, "hash": a.hash[:12]} for a in qs[:min(int(q.get("limit", 100)), 500)]])


class AuditVerify(APIView):
    perms = {"get": "audit:read"}

    def get(self, request):
        return Response(verify_chain())


class AccessEvents(APIView):
    perms = {"get": "audit:read"}

    def get(self, request):
        qs = AccessEvent.objects.order_by("-id")
        qs = qs.filter(event=request.query_params["event"]) if request.query_params.get("event") else qs
        return Response(list(qs.values("id", "ts", "user_id", "event", "permission", "path", "ip")[:min(int(request.query_params.get("limit", 100)), 500)]))
