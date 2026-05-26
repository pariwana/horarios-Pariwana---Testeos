from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthcheck(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", healthcheck, name="healthcheck"),
    path("api/auth/", include("apps.users.urls")),
    path("api/", include("apps.users.api_urls")),
    path("api/", include("apps.tenants.urls")),
    path("api/", include("apps.modules.urls")),
    path("api/", include("apps.workers.urls")),
    path("api/", include("apps.scheduling.urls")),
    path("api/", include("apps.imports.urls")),
    path("api/", include("apps.buk_exports.urls")),
    path("api/", include("apps.month_closure.urls")),
    path("api/", include("apps.audit.urls")),
]
