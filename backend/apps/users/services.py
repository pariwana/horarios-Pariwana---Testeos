from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import AuditService
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


class UserAccessService:
    VALID_ROLES = {RoleChoices.ADMIN, RoleChoices.OPERATOR, RoleChoices.SUPERVISOR}

    @staticmethod
    def snapshot(*, user, tenant):
        assignment = (
            UserTenantRole.objects.filter(user=user, tenant=tenant)
            .select_related("role_profile")
            .first()
        )
        property_permissions = list(
            UserPropertyPermission.objects.filter(user=user, tenant=tenant)
            .select_related("property")
            .order_by("property__name")
        )
        area_permissions = list(
            UserAreaPermission.objects.filter(user=user, tenant=tenant)
            .select_related("property", "area")
            .order_by("property__name", "area__name")
        )
        areas_by_property = {}
        for item in area_permissions:
            areas_by_property.setdefault(str(item.property_id), []).append(
                {"id": item.area_id, "name": item.area.name}
            )
        return {
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
            },
            "type": {
                "role": assignment.role if assignment else None,
                "role_profile_id": assignment.role_profile_id if assignment else None,
                "role_profile_name": assignment.role_profile.name if assignment and assignment.role_profile_id else None,
            },
            "properties": [
                {"id": item.property_id, "name": item.property.name}
                for item in property_permissions
                if item.can_access
            ],
            "permissions": {
                str(item.property_id): RoleProfileService.normalize_permissions(
                    {key: getattr(item, key) for key in PROPERTY_PERMISSION_KEYS}
                )
                for item in property_permissions
            },
            "areas": {
                str(item.property_id): {
                    "mode": "specific" if str(item.property_id) in areas_by_property else "all",
                    "selected": areas_by_property.get(str(item.property_id), []),
                }
                for item in property_permissions
                if item.can_access
            },
        }

    @staticmethod
    @transaction.atomic
    def sync(
        *,
        user,
        tenant,
        role_profile,
        property_ids,
        permission_payload,
        area_scopes,
        actor,
        audit_property,
        before_snapshot=None,
        allowed_property_ids=None,
    ):
        if role_profile is None or role_profile.tenant_id != tenant.id or not role_profile.active:
            raise ValidationError("Selecciona un tipo de usuario válido.")
        if role_profile.base_role not in UserAccessService.VALID_ROLES:
            raise ValidationError("El tipo de usuario no tiene un rol base válido.")

        normalized_property_ids = {int(item) for item in property_ids}
        properties = list(
            Property.objects.filter(tenant=tenant, id__in=normalized_property_ids).order_by("name")
        )
        if not properties:
            raise ValidationError("Selecciona al menos una sede permitida.")
        if {item.id for item in properties} != normalized_property_ids:
            raise ValidationError("Una de las sedes seleccionadas no pertenece al tenant autorizado.")
        if allowed_property_ids is not None and not normalized_property_ids.issubset(
            {int(item) for item in allowed_property_ids}
        ):
            raise ValidationError("No puedes asignar una sede fuera de tu alcance autorizado.")

        from apps.workers.models import Area

        normalized_area_scopes = {}
        for property_obj in properties:
            scope = area_scopes.get(property_obj.id)
            if scope is None:
                normalized_area_scopes[property_obj.id] = None
                continue
            area_ids = {int(item) for item in scope}
            valid_area_ids = set(
                Area.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    active=True,
                    id__in=area_ids,
                ).values_list("id", flat=True)
            )
            if not area_ids or valid_area_ids != area_ids:
                raise ValidationError(
                    f"Selecciona áreas válidas de {property_obj.name} o usa “Todas las áreas”."
                )
            normalized_area_scopes[property_obj.id] = valid_area_ids

        before = (
            before_snapshot
            if before_snapshot is not None
            else UserAccessService.snapshot(user=user, tenant=tenant)
        )
        normalized_permissions = RoleProfileService.normalize_permissions(permission_payload)
        normalized_permissions["can_access"] = True

        assignment, _ = UserTenantRole.objects.update_or_create(
            user=user,
            tenant=tenant,
            defaults={
                "role": role_profile.base_role,
                "role_profile": role_profile,
                "all_properties_access": False,
                "property_permissions_template": normalized_permissions,
            },
        )

        selected_property_ids = {item.id for item in properties}
        UserPropertyPermission.objects.filter(user=user, tenant=tenant).exclude(
            property_id__in=selected_property_ids
        ).delete()
        UserAreaPermission.objects.filter(user=user, tenant=tenant).exclude(
            property_id__in=selected_property_ids
        ).delete()

        for property_obj in properties:
            UserPropertyPermission.objects.update_or_create(
                user=user,
                tenant=tenant,
                property=property_obj,
                defaults=normalized_permissions,
            )
            UserAreaPermission.objects.filter(
                user=user,
                tenant=tenant,
                property=property_obj,
            ).delete()
            selected_area_ids = normalized_area_scopes[property_obj.id]
            if selected_area_ids is not None:
                UserAreaPermission.objects.bulk_create(
                    [
                        UserAreaPermission(
                            user=user,
                            tenant=tenant,
                            property=property_obj,
                            area_id=area_id,
                            can_view=True,
                            can_schedule=normalized_permissions["can_schedule"],
                        )
                        for area_id in selected_area_ids
                    ]
                )

        after = UserAccessService.snapshot(user=user, tenant=tenant)
        AuditService.log(
            tenant=tenant,
            property_obj=audit_property,
            user=actor,
            action="create" if before == {} else "update",
            entity_type="User",
            entity_id=user.id,
            before=before,
            after=after,
        )
        return assignment


class PermissionService:
    @staticmethod
    def _tenant_role_assignment(user, tenant):
        return UserTenantRole.objects.filter(user=user, tenant=tenant).first()

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
        assignment = PermissionService._tenant_role_assignment(user, tenant)
        return assignment.role if assignment else None

    @staticmethod
    def user_can_property_action(user, tenant, property_obj, action):
        if PermissionService.is_super_admin(user):
            return True
        assignment = PermissionService._tenant_role_assignment(user, tenant)
        role = assignment.role if assignment else None
        if role == RoleChoices.SUPER_ADMIN:
            return True
        if (
            role in {RoleChoices.ADMIN, RoleChoices.OPERATOR}
            and assignment
            and assignment.all_properties_access
            and property_obj.tenant_id == tenant.id
        ):
            if role == RoleChoices.ADMIN:
                return True
            template = RoleProfileService.normalize_permissions(assignment.property_permissions_template)
            return bool(template.get(action))

        perm = UserPropertyPermission.objects.filter(
            user=user,
            tenant=tenant,
            property=property_obj,
            can_access=True,
        ).first()
        if not perm:
            return False
        if role == RoleChoices.ADMIN:
            return True
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
        assignment = PermissionService._tenant_role_assignment(user, tenant)
        if assignment and assignment.all_properties_access and assignment.role in {RoleChoices.ADMIN, RoleChoices.OPERATOR}:
            if assignment.role == RoleChoices.ADMIN or action == "can_access":
                return list(Property.objects.filter(tenant=tenant).values_list("id", flat=True))
            template = RoleProfileService.normalize_permissions(assignment.property_permissions_template)
            if template.get(action):
                return list(Property.objects.filter(tenant=tenant).values_list("id", flat=True))
            return []
        perms = UserPropertyPermission.objects.filter(
            user=user,
            tenant=tenant,
            can_access=True,
        )
        if action != "can_access" and (assignment is None or assignment.role != RoleChoices.ADMIN):
            perms = perms.filter(**{action: True})
        return list(perms.values_list("property_id", flat=True))

    @staticmethod
    def get_accessible_area_ids(user, tenant, property_obj=None, action="can_view"):
        from apps.workers.models import Area

        role = PermissionService.get_user_role(user, tenant)
        areas = Area.objects.filter(tenant=tenant)
        if property_obj is not None:
            areas = areas.filter(property=property_obj)
        if role == RoleChoices.SUPER_ADMIN:
            return list(areas.values_list("id", flat=True))

        property_ids = (
            [property_obj.id]
            if property_obj is not None
            else PermissionService.get_accessible_property_ids(user, tenant, action="can_access")
        )
        allowed_area_ids = []
        for property_id in property_ids:
            property_instance = property_obj or Property.objects.filter(
                tenant=tenant,
                id=property_id,
            ).first()
            property_action = "can_schedule" if action == "can_schedule" else "can_access"
            if property_instance is None or not PermissionService.user_can_property_action(
                user,
                tenant,
                property_instance,
                property_action,
            ):
                continue
            perms = UserAreaPermission.objects.filter(
                user=user,
                tenant=tenant,
                property_id=property_id,
            )
            if not perms.exists():
                allowed_area_ids.extend(
                    areas.filter(property_id=property_id).values_list("id", flat=True)
                )
                continue
            perms = perms.filter(can_view=True)
            if action == "can_schedule":
                perms = perms.filter(can_schedule=True)
            allowed_area_ids.extend(perms.values_list("area_id", flat=True))
        return allowed_area_ids

    @staticmethod
    def user_can_area_schedule(user, tenant, property_obj, area):
        role = PermissionService.get_user_role(user, tenant)
        if role == RoleChoices.SUPER_ADMIN:
            return True
        if area is None:
            return False
        if area.property_id != property_obj.id or area.tenant_id != tenant.id:
            return False
        if not PermissionService.user_can_property_action(user, tenant, property_obj, "can_schedule"):
            return False

        perms_qs = PermissionService._area_permissions_for_user(user, tenant, property_obj)
        has_area_scope = perms_qs.exists()
        if not has_area_scope:
            return True

        return perms_qs.filter(
            area=area,
            can_view=True,
            can_schedule=True,
        ).exists()

    @staticmethod
    def user_can_area_view(user, tenant, property_obj, area):
        role = PermissionService.get_user_role(user, tenant)
        if role == RoleChoices.SUPER_ADMIN:
            return True
        if area is None:
            return False
        if area.property_id != property_obj.id or area.tenant_id != tenant.id:
            return False
        if not PermissionService.user_can_property_action(user, tenant, property_obj, "can_access"):
            return False

        perms_qs = PermissionService._area_permissions_for_user(user, tenant, property_obj)
        has_area_scope = perms_qs.exists()
        if not has_area_scope:
            return True

        return perms_qs.filter(area=area, can_view=True).exists()
