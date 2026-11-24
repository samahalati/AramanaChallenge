from django.urls import path
from rest_framework.routers import SimpleRouter

from accounts import views

router = SimpleRouter(trailing_slash=False)
router.register("admin/users", views.AdminUserViewSet, basename="admin-users")
urlpatterns = [path("auth/login", views.LoginView.as_view()), path("auth/me", views.MeView.as_view()),
               path("admin/activity", views.AdminActivityView.as_view()), *router.urls]
