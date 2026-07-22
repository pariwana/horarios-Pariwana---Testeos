from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.access import (
    ensure_module_enabled,
    ensure_property_action,
    ensure_tenant_roles,
    resolve_access_context,
)
from apps.users.services import PermissionService
from apps.workers.models import Area, Shift, SpecialState, Worker
from apps.workers.serializers import AreaSerializer, ShiftSerializer, SpecialStateSerializer, WorkerSerializer


class TenantPropertyFilteredViewSet(viewsets.ModelViewSet):
    module_key = None
    read_action = "can_access"
    write_action = "can_manage_workers"
    allow_roles = ["admin", "operator", "supervisor"]

    def _resolve_and_check(self, *, require_property=False, write=False):
        ctx = resolve_access_context(self.request, require_property=require_property)
        ensure_tenant_roles(self.request, ctx.tenant, self.allow_roles)
        if self.module_key:
            ensure_module_enabled(self.request, ctx.tenant, self.module_key)
        if ctx.property:
            ensure_property_action(
                self.request,
                ctx.tenant,
                ctx.property,
                self.write_action if write else self.read_action,
            )
        return ctx

    def get_queryset(self):
        queryset = super().get_queryset()
        ctx = self._resolve_and_check(require_property=False, write=False)
        queryset = queryset.filter(tenant=ctx.tenant)
        if ctx.property:
            queryset = queryset.filter(property=ctx.property)
        elif not PermissionService.is_super_admin(self.request.user):
            allowed_property_ids = PermissionService.get_accessible_property_ids(
                self.request.user,
                ctx.tenant,
                action=self.read_action,
            )
            queryset = queryset.filter(property_id__in=allowed_property_ids)
        return queryset

    def perform_create(self, serializer):
        tenant = serializer.validated_data["tenant"]
        property_obj = serializer.validated_data["property"]
        ensure_tenant_roles(self.request, tenant, self.allow_roles)
        if self.module_key:
            ensure_module_enabled(self.request, tenant, self.module_key)
        ensure_property_action(self.request, tenant, property_obj, self.write_action)
        serializer.save()

    def perform_update(self, serializer):
        tenant = serializer.instance.tenant
        property_obj = serializer.instance.property
        ensure_tenant_roles(self.request, tenant, self.allow_roles)
        if self.module_key:
            ensure_module_enabled(self.request, tenant, self.module_key)
        ensure_property_action(self.request, tenant, property_obj, self.write_action)
        serializer.save()

    def perform_destroy(self, instance):
        ensure_tenant_roles(self.request, instance.tenant, self.allow_roles)
        if self.module_key:
            ensure_module_enabled(self.request, instance.tenant, self.module_key)
        ensure_property_action(self.request, instance.tenant, instance.property, self.write_action)
        instance.delete()


class AreaViewSet(TenantPropertyFilteredViewSet):
    queryset = Area.objects.select_related("tenant", "property").all()
    serializer_class = AreaSerializer
    module_key = "areas"
    write_action = "can_manage_workers"


class WorkerViewSet(TenantPropertyFilteredViewSet):
    queryset = Worker.objects.select_related("tenant", "property", "area").all()
    serializer_class = WorkerSerializer
    module_key = "workers"
    write_action = "can_manage_workers"

    def get_queryset(self):
        queryset = super().get_queryset()
        area_ids = PermissionService.get_accessible_area_ids(
            self.request.user,
            self.request.tenant,
            self.request.property,
            action="can_view",
        )
        return queryset.filter(area_id__in=area_ids)

    def _validate_target_scope(self, serializer):
        tenant = serializer.validated_data.get("tenant", serializer.instance.tenant if serializer.instance else None)
        property_obj = serializer.validated_data.get(
            "property", serializer.instance.property if serializer.instance else None
        )
        area = serializer.validated_data.get("area", serializer.instance.area if serializer.instance else None)
        if tenant is None or property_obj is None or area is None:
            raise ValidationError("Tenant, sede y area son requeridos.")
        if property_obj.tenant_id != tenant.id or area.tenant_id != tenant.id or area.property_id != property_obj.id:
            raise ValidationError("El tenant, la sede y el area del trabajador no son coherentes.")
        ensure_tenant_roles(self.request, tenant, self.allow_roles)
        ensure_module_enabled(self.request, tenant, self.module_key)
        ensure_property_action(self.request, tenant, property_obj, self.write_action)
        if not PermissionService.user_can_area_view(self.request.user, tenant, property_obj, area):
            raise PermissionDenied("No tienes permisos para gestionar trabajadores en esta area.")

    def perform_create(self, serializer):
        self._validate_target_scope(serializer)
        serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        ensure_tenant_roles(self.request, instance.tenant, self.allow_roles)
        ensure_module_enabled(self.request, instance.tenant, self.module_key)
        ensure_property_action(self.request, instance.tenant, instance.property, self.write_action)
        if not PermissionService.user_can_area_view(
            self.request.user, instance.tenant, instance.property, instance.area
        ):
            raise PermissionDenied("No tienes permisos para gestionar trabajadores en esta area.")
        self._validate_target_scope(serializer)
        serializer.save()


class ShiftViewSet(TenantPropertyFilteredViewSet):
    queryset = Shift.objects.select_related("tenant", "property", "area").all()
    serializer_class = ShiftSerializer
    module_key = "shifts"
    write_action = "can_manage_shifts"


class SpecialStateViewSet(TenantPropertyFilteredViewSet):
    queryset = SpecialState.objects.select_related("tenant", "property").all()
    serializer_class = SpecialStateSerializer
    module_key = "special_states"
    write_action = "can_manage_shifts"
