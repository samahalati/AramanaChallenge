from rest_framework.response import Response
from rest_framework.views import APIView

from hr.views import validated
from supervision import serializers as s, services


class SupervisionView(APIView):
    """Base for Module-B endpoints: reads need supervision:read, writes supervision:write."""
    perms = {"get": "supervision:read", "post": "supervision:write", "patch": "supervision:write"}


class Dashboard(SupervisionView):
    def get(self, request):
        return Response(services.dashboard(request.user))


class Supervisees(SupervisionView):
    def get(self, request):
        return Response(services.supervisees(request.user))


class SuperviseeDetail(SupervisionView):
    def get(self, request, uid):
        return Response(services.supervisee_detail(request.user, uid))


class Meetings(SupervisionView):
    def post(self, request):
        return Response({"id": services.schedule_meeting(request.user, validated(s.MeetingSerializer, request)).id}, status=201)


class MeetingDetail(SupervisionView):
    def patch(self, request, mid):
        return Response({"id": services.update_meeting(request.user, mid, validated(s.MeetingPatchSerializer, request)["status"]).id})


class Reviews(SupervisionView):
    def get(self, request):
        return Response(services.list_reviews(request.user, request.query_params))

    def post(self, request):
        return Response({"id": services.create_review(request.user, validated(s.ReviewCreateSerializer, request)).id}, status=201)


class ReviewDetail(SupervisionView):
    def get(self, request, rid):
        return Response(services.review_detail(request.user, rid))


class ReviewAction(SupervisionView):
    """POST /reviews/<id>/<start|decision|corrective-actions|close> – one class, one table (DRY)."""
    handlers = {
        "start": lambda u, rid, r: {"id": services.start_review(u, rid).id},
        "decision": lambda u, rid, r: services.decide_review(u, rid, validated(s.ReviewDecisionSerializer, r)),
        "corrective-actions": lambda u, rid, r: {"id": services.add_corrective_action(u, rid, validated(s.CorrectiveActionSerializer, r)).id},
        "close": lambda u, rid, r: {"id": services.close_review(u, rid, validated(s.CloseReviewSerializer, r).get("monitoring_plan")).id},
    }
    step = ""

    def post(self, request, rid):
        return Response(self.handlers[self.step](request.user, rid, request), status=201 if self.step == "corrective-actions" else 200)


class CorrectiveActionDetail(APIView):
    perms = {"patch": ("supervision:write", "supervision:read:own")}

    def patch(self, request, aid):
        return Response({"id": services.update_corrective_action(request.user, aid, validated(s.CorrectivePatchSerializer, request)["status"]).id})


class MyReviews(APIView):
    perms = {"get": "supervision:read:own"}

    def get(self, request):
        return Response(services.my_reviews(request.user))


class Issues(APIView):
    perms = {"get": "supervision:read", "post": "quality:write"}

    def get(self, request):
        return Response(services.list_issues(request.user))

    def post(self, request):
        return Response({"id": services.create_issue(request.user, validated(s.QualityIssueSerializer, request)).id}, status=201)


class IssueAction(APIView):
    perms = {"post": "quality:write"}
    escalate = False

    def post(self, request, iid):
        if self.escalate:
            return Response(services.escalate_issue(request.user, iid, validated(s.EscalateSerializer, request)["reason"]))
        return Response({"id": services.resolve_issue(request.user, iid).id})
