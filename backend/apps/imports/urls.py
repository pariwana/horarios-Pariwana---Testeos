from rest_framework.routers import DefaultRouter

from apps.imports.views import ImportBatchViewSet

router = DefaultRouter()
router.register("imports", ImportBatchViewSet, basename="import-batch")

urlpatterns = router.urls
