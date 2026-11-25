from rest_framework.response import Response
from rest_framework.views import APIView

from clinical import services
from clinical.serializers import ReferralCreateSerializer, SessionCreateSerializer, SessionPatchSerializer, SessionSerializer
from core.permissions import deny
from hr.views import validated
from monitoring.visibility import can_read_clinical_of

CLINICAL_READ = ("clinical:read:own", "clinical:read:supervisees", "clinical:read:alerted")


class PractitionerSessionsView(APIView):
    """Role grants the *kind* of access; the relationship (own / current supervisee / alerted subject) grants the *record*."""
    perms = {"get": CLINICAL_READ}

    def get(self, request, pid):
        if not can_read_clinical_of(request.user, pid):
            deny(request, "clinical:read (relationship scope)")
            self.permission_denied(request, message="No relationship permits reading this practitioner's clinical records")
        return Response(services.list_sessions(request.user, pid, request.query_params))


class MyClientsView(APIView):
    perms = {"get": "clinical:read:own"}

    def get(self, request):
        return Response(services.my_clients(request.user))


class SessionCreateView(APIView):
    bodies = {"post": SessionCreateSerializer}
    perms = {"post": "clinical:write:own"}

    def post(self, request):
        d = validated(SessionCreateSerializer, request)
        return Response(SessionSerializer(services.create_session(request.user, d)).data, status=201)


class SessionDetailView(APIView):
    bodies = {"patch": SessionPatchSerializer}
    perms = {"patch": "clinical:write:own"}

    def patch(self, request, sid):
        return Response(SessionSerializer(services.update_session(request.user, sid, validated(SessionPatchSerializer, request))).data)


class SessionCheckView(APIView):
    perms = {"post": "clinical:write:own"}
    out = False

    def post(self, request, sid):
        return Response(SessionSerializer(services.check(request.user, sid, out=self.out)).data)


class EligibleView(APIView):
    perms = {"get": "referrals:write:own"}

    def get(self, request):
        return Response(services.eligible_practitioners(request.query_params.get("need", "")))


class ReferralView(APIView):
    bodies = {"post": ReferralCreateSerializer}
    perms = {"post": "referrals:write:own"}

    def post(self, request):
        return Response({"id": services.create_referral(request.user, validated(ReferralCreateSerializer, request)).id}, status=201)


class MyReferralsView(APIView):
    perms = {"get": "referrals:read:own"}

    def get(self, request):
        return Response(services.my_referrals(request.user))
