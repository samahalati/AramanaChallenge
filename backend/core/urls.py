from django.urls import path

from core import views as v

urlpatterns = [path("health", v.Health.as_view()), path("meta/rbac", v.RbacMatrix.as_view()), path("meta/labels", v.Labels.as_view()), path("audit", v.AuditList.as_view()),
               path("audit/verify", v.AuditVerify.as_view()), path("audit/access-events", v.AccessEvents.as_view())]
