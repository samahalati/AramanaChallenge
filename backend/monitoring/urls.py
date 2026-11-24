from django.urls import path

from monitoring import views as v

urlpatterns = [
    path("alerts", v.AlertList.as_view()), path("alerts/<int:aid>", v.AlertDetail.as_view()), path("alerts/<int:aid>/actions", v.AlertAction.as_view()),
    path("alerts/<int:aid>/ai-summary", v.AlertAiSummary.as_view()), path("alerts/<int:aid>/assistant", v.AlertAssistant.as_view()), path("alerts/<int:aid>/route-to-supervisor", v.AlertRoute.as_view()),
    path("monitoring/summary", v.Summary.as_view()), path("monitoring/users/<int:uid>/history", v.UserHistory.as_view()),
    path("detection/run", v.RunDetection.as_view()), path("detection/runs", v.RunDetection.as_view()),
    path("detection/config", v.DetectionConfig.as_view()), path("detection/evaluation", v.Evaluation.as_view()),
]
