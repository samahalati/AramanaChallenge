from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api = [
    path("", include("core.urls")), path("", include("accounts.urls")), path("hr/", include("hr.urls")),
    path("", include("clinical.urls")), path("supervision/", include("supervision.urls")), path("", include("monitoring.urls")),
    path("schema/", SpectacularAPIView.as_view(permission_classes=[], authentication_classes=[]), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[], authentication_classes=[])),
]
urlpatterns = [path("api/", include(api))]

dist = settings.FRONTEND_DIST          # production: Django also serves the built React app (single process)
if dist.exists():
    urlpatterns += [re_path(r"^assets/(?P<path>.*)$", serve, {"document_root": dist / "assets"}),
                    re_path(r"^(?!api/).*$", serve, {"document_root": dist, "path": "index.html"})]
