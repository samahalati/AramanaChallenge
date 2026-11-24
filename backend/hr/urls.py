from django.urls import path
from rest_framework.routers import SimpleRouter

from hr import views

router = SimpleRouter(trailing_slash=False)
router.register("practitioners", views.PractitionerViewSet, basename="practitioner")
urlpatterns = [path("dashboard", views.DashboardView.as_view()), path("org-units", views.OrgUnitView.as_view()),
               path("assignments", views.AssignmentView.as_view()), path("credentials/<int:pk>", views.CredentialUpdateView.as_view()),
               path("contracts/<int:pk>", views.ContractUpdateView.as_view()), *router.urls]
