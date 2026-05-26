from rest_framework.routers import DefaultRouter

from apps.buk_exports.views import BukExportViewSet

router = DefaultRouter()
router.register("buk", BukExportViewSet, basename="buk")

urlpatterns = router.urls
