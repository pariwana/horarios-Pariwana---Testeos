from rest_framework.routers import DefaultRouter

from apps.tenants.views import PropertyViewSet, TenantViewSet

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("properties", PropertyViewSet, basename="property")

urlpatterns = router.urls
