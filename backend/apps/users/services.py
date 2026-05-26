from apps.modules.models import ModuleActivation
from apps.tenants.models import Property
from apps.users.models import RoleChoices, UserAreaPermission, UserPropertyPermission, UserTenantRole


class PermissionService:
    @staticmethod
    def is_super_admin(user):
        return bool(getattr(user, "is_super_admin", False))

    @staticmethod
    def get_user_role(user, tenant):
        if PermissionService.is_super_admin(user):
            return RoleChoices.SUPER_ADMIN
        assignment = UserTenantRole.objects.filter(user=user, tenant=tenant).first()
        return assignment.role if assignment else None

    @staticmethod
    def user_can_property_action(user, tenant, property_obj, action):
        role = PermissionService.get_user_role(user, tenant)
        if role in {RoleChoices.SUPER_ADMIN, RoleChoices.ADMIN}:
            return True

        perm = UserPropertyPermission.objects.filter(
            user=user,
            tenant=tenant,
            property=property_obj,
            can_access=True,
        ).first()
        if not perm:
            return False
        return bool(getattr(perm, action, False))

    @staticmethod
    def user_can_tenant_role(user, tenant, allowed_roles):
        if PermissionService.is_super_admin(user):
            return True
        role = PermissionService.get_user_role(user, tenant)
        return role in set(allowed_roles)

    @staticmethod
    def user_can_module(user, tenant, module_key):
        if PermissionService.is_super_admin(user):
            return True
        return ModuleActivation.objects.filter(
            tenant=tenant,
            module_key=module_key,
            is_enabled=True,
        ).exists()

    @staticmethod
    def get_accessible_property_ids(user, tenant, action="can_access"):
        if PermissionService.is_super_admin(user):
            return list(Property.objects.filter(tenant=tenant).values_list("id", flat=True))
        role = PermissionService.get_user_role(user, tenant)
        if role == RoleChoices.ADMIN:
            return list(Property.objects.filter(tenant=tenant).values_list("id", flat=True))
        perms = UserPropertyPermission.objects.filter(
            user=user,
            tenant=tenant,
            can_access=True,
        )
        if action != "can_access":
            perms = perms.filter(**{action: True})
        return list(perms.values_list("property_id", flat=True))

    @staticmethod
    def user_can_area_schedule(user, tenant, property_obj, area):
        role = PermissionService.get_user_role(user, tenant)
        if role in {RoleChoices.SUPER_ADMIN, RoleChoices.ADMIN, RoleChoices.OPERATOR}:
            return True
        perm = UserAreaPermission.objects.filter(
            user=user,
            tenant=tenant,
            property=property_obj,
            area=area,
            can_view=True,
            can_schedule=True,
        ).exists()
        return perm
