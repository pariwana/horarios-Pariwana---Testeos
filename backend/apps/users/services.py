from apps.modules.models import ModuleActivation
from apps.tenants.models import Property
from apps.users.models import RoleChoices, RoleProfile, UserAreaPermission, UserPropertyPermission, UserTenantRole


PROPERTY_PERMISSION_KEYS = [
    "can_access",
    "can_schedule",
    "can_export_buk",
    "can_manage_workers",
    "can_manage_shifts",
    "can_manage_areas",
    "can_manage_users",
    "can_view_reports",
    "can_use_control",
]


DEFAULT_ROLE_PROFILES = [
    {
        "code": "admin",
        "name": "Administrador",
        "base_role": RoleChoices.ADMIN,
        "description": "Acceso completo en la sede asignada.",
        "permissions": {key: True for key in PROPERTY_PERMISSION_KEYS},
    },
    {
        "code": "operator",
        "name": "Operador",
        "base_role": RoleChoices.OPERATOR,
        "description": "Gestiona trabajadores, turnos, asignacion, control y BUK en sedes permitidas.",
        "permissions": {
            "can_access": True,
            "can_schedule": True,
            "can_export_buk": True,
            "can_manage_workers": True,
            "can_manage_shifts": True,
            "can_manage_areas": False,
            "can_manage_users": False,
            "can_view_reports": True,
            "can_use_control": True,
        },
    },
    {
        "code": "supervisor",
        "name": "Supervisor",
        "base_role": RoleChoices.SUPERVISOR,
        "description": "Ve y asigna horarios solo en areas autorizadas.",
        "permissions": {
            "can_access": True,
            "can_schedule": True,
            "can_export_buk": False,
            "can_manage_workers": False,
            "can_manage_shifts": False,
            "can_manage_areas": False,
            "can_manage_users": False,
            "can_view_reports": False,
            "can_use_control": False,
        },
    },
]


class RoleProfileService:
    @staticmethod
    def normalize_permissions(permissions):
        return {key: bool((permissions or {}).get(key)) for key in PROPERTY_PERMISSION_KEYS}

    @staticmethod
    def ensure_defaults(tenant):
        profiles = []
        for item in DEFAULT_ROLE_PROFILES:
            profile, _ = RoleProfile.objects.update_or_create(
                tenant=tenant,
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "base_role": item["base_role"],
                    "description": item["description"],
                    "permissions": RoleProfileService.normalize_permissions(item["permissions"]),
                    "is_system": True,
                    "active": True,
                },
            )
            profiles.append(profile)
        return profiles

    @staticmethod
    def get_active_profiles(tenant):
        RoleProfileService.ensure_defaults(tenant)
        return RoleProfile.objects.filter(tenant=tenant, active=True).order_by("base_role", "name")

    @staticmethod
    def permission_defaults_for_profile(profile):
        if profile is None:
            return {}
        return RoleProfileService.normalize_permissions(profile.permissions)


class PermissionService:
    @staticmethod
    def _area_permissions_for_user(user, tenant, property_obj):
        return UserAreaPermission.objects.filter(
            user=user,
            tenant=tenant,
            property=property_obj,
        )

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
        if role in {RoleChoices.SUPER_ADMIN, RoleChoices.ADMIN}:
            return True
        if area is None:
            return False

        perms_qs = PermissionService._area_permissions_for_user(user, tenant, property_obj)
        has_area_scope = perms_qs.exists()
        if role == RoleChoices.OPERATOR and not has_area_scope:
            return True

        return perms_qs.filter(
            area=area,
            can_view=True,
            can_schedule=True,
        ).exists()

    @staticmethod
    def user_can_area_view(user, tenant, property_obj, area):
        role = PermissionService.get_user_role(user, tenant)
        if role in {RoleChoices.SUPER_ADMIN, RoleChoices.ADMIN}:
            return True
        if area is None:
            return False

        perms_qs = PermissionService._area_permissions_for_user(user, tenant, property_obj)
        has_area_scope = perms_qs.exists()
        if role == RoleChoices.OPERATOR and not has_area_scope:
            return True

        return perms_qs.filter(area=area, can_view=True).exists()
