from rest_framework.routers import DefaultRouter

from apps.users.views import (
    UserAreaPermissionViewSet,
    UserPropertyPermissionViewSet,
    UserTenantRoleViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("user-tenant-roles", UserTenantRoleViewSet, basename="user-tenant-role")
router.register("user-property-permissions", UserPropertyPermissionViewSet, basename="user-property-permission")
router.register("user-area-permissions", UserAreaPermissionViewSet, basename="user-area-permission")

urlpatterns = router.urls
