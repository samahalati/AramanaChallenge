from pathlib import Path

import yaml
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from hr.views import validated
from monitoring import evaluation
from monitoring.models import DetectionRun
from monitoring.serializers import AlertActionSerializer, AskSerializer, RouteSerializer
from monitoring.services import alerts, assistant, runs


class AlertList(APIView):
    perms = {"get": "alerts:read"}

    def get(self, request):
        q = request.query_params
        flt = {k: q.get(k) for k in ("status", "level", "category", "domain", "scenario")} | {"open_only": q.get("open_only") == "true"}
        return Response(alerts.list_alerts(request.user, min(int(q.get("limit", 100)), 500), int(q.get("offset", 0)), **flt))


class AlertDetail(APIView):
    perms = {"get": "alerts:read"}

    def get(self, request, aid):
        return Response(alerts.alert_detail(request.user, aid))


class AlertAction(APIView):
    perms = {"post": ("alerts:comment", "alerts:investigate")}

    def post(self, request, aid):
        d = validated(AlertActionSerializer, request)
        return Response(alerts.act(request.user, aid, d["action"], d.get("note"), d.get("assign_to")))


class AlertAiSummary(APIView):
    perms = {"post": "alerts:investigate"}

    def post(self, request, aid):
        return Response(assistant.brief(request.user, aid))


class AlertAssistant(APIView):
    """Grounded Q&A over one alert's evidence. GET = history; POST {question} = ask (guardrails + citations)."""
    perms = {"get": "alerts:investigate", "post": "alerts:investigate"}

    def get(self, request, aid):
        return Response(assistant.history(request.user, aid))

    def post(self, request, aid):
        return Response(assistant.ask(request.user, aid, validated(AskSerializer, request)["question"]))


class AlertRoute(APIView):
    perms = {"post": "alerts:investigate"}

    def post(self, request, aid):
        return Response(alerts.route_to_supervisor(request.user, aid, validated(RouteSerializer, request)["note"]))


class Summary(APIView):
    perms = {"get": "alerts:read"}

    def get(self, request):
        return Response(alerts.monitoring_summary(request.user))


class UserHistory(APIView):
    perms = {"get": "alerts:read"}

    def get(self, request, uid):
        return Response(alerts.user_history(request.user, uid))


class RunDetection(APIView):
    perms = {"post": "detection:run", "get": "detection:read"}

    def post(self, request):
        return Response(runs.run_detection(triggered_by=request.user.id))

    def get(self, request):
        rows = DetectionRun.objects.order_by("-id")[:20]
        return Response([{"id": r.id, "finished_at": r.finished_at, "ruleset_version": r.ruleset_version, "model_version": r.model_version, "as_of": r.as_of,
                          "alerts_created": (r.stats or {}).get("alerts_created"), "alerts_updated": (r.stats or {}).get("alerts_updated")} for r in rows])


class DetectionConfig(APIView):
    perms = {"get": "detection:read"}

    def get(self, request):
        return Response(yaml.safe_load(Path(settings.DETECTION_CONFIG).read_text()))


class Evaluation(APIView):
    perms = {"get": "detection:run"}

    def get(self, request):
        if not Path(settings.GROUND_TRUTH_PATH).exists():
            return Response({"available": False, "reason": "No synthetic ground truth file – evaluation needs the synthetic dataset."})
        return Response({"available": True, **evaluation.evaluate()})
