from rest_framework.routers import DefaultRouter

from apps.scheduling.views import ScheduleAssignmentViewSet

router = DefaultRouter()
router.register("assignments", ScheduleAssignmentViewSet, basename="assignment")

urlpatterns = router.urls
