from rest_framework.routers import DefaultRouter

from apps.workers.views import AreaViewSet, ShiftViewSet, SpecialStateViewSet, WorkerViewSet

router = DefaultRouter()
router.register("areas", AreaViewSet, basename="area")
router.register("workers", WorkerViewSet, basename="worker")
router.register("shifts", ShiftViewSet, basename="shift")
router.register("special-states", SpecialStateViewSet, basename="special-state")

urlpatterns = router.urls
