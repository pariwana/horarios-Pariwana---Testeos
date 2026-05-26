from rest_framework.routers import DefaultRouter

from apps.modules.views import ModuleActivationViewSet

router = DefaultRouter()
router.register("modules", ModuleActivationViewSet, basename="module-activation")

urlpatterns = router.urls
