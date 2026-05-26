from rest_framework.permissions import BasePermission

from apps.modules.models import ModuleActivation
from apps.users.services import PermissionService


class ModuleEnabledPermission(BasePermission):
    module_key = None

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        if getattr(request.user, "is_super_admin", False):
            return True

        module_key = getattr(view, "module_key", self.module_key)
        tenant = getattr(request, "tenant", None)
        if not module_key or tenant is None:
            return True

        return ModuleActivation.objects.filter(
            tenant=tenant,
            module_key=module_key,
            is_enabled=True,
        ).exists()


class TenantScopedPermission(BasePermission):
    required_action = "can_access"

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        if getattr(request.user, "is_super_admin", False):
            return True

        tenant = getattr(request, "tenant", None)
        property_obj = getattr(request, "property", None)
        if tenant is None or property_obj is None:
            return False

        action = getattr(view, "required_action", self.required_action)
        return PermissionService.user_can_property_action(
            user=request.user,
            tenant=tenant,
            property_obj=property_obj,
            action=action,
        )
