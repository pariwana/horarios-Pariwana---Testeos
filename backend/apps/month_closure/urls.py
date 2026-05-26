from rest_framework.routers import DefaultRouter

from apps.month_closure.views import MonthClosureViewSet

router = DefaultRouter()
router.register("month-closure", MonthClosureViewSet, basename="month-closure")

urlpatterns = router.urls
