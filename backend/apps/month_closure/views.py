from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.access import ensure_module_enabled, ensure_property_action, ensure_tenant_roles, resolve_access_context
from apps.month_closure.models import MonthClosure
from apps.month_closure.serializers import MonthClosureSerializer
from apps.month_closure.services import MonthClosureService
from apps.users.services import PermissionService


class MonthClosureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MonthClosure.objects.select_related("tenant", "property").all()
    serializer_class = MonthClosureSerializer

    def get_queryset(self):
        if self.action == "retrieve" and "tenant_id" not in self.request.query_params:
            return super().get_queryset()
        ctx = resolve_access_context(self.request, require_property=False)
        ensure_tenant_roles(self.request, ctx.tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(self.request, ctx.tenant, "month_closure")
        queryset = super().get_queryset().filter(tenant=ctx.tenant)
        if ctx.property:
            ensure_property_action(self.request, ctx.tenant, ctx.property, "can_access")
            queryset = queryset.filter(property=ctx.property)
        elif not PermissionService.is_super_admin(self.request.user):
            property_ids = PermissionService.get_accessible_property_ids(
                self.request.user,
                ctx.tenant,
                action="can_access",
            )
            queryset = queryset.filter(property_id__in=property_ids)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        closure = self.get_object()
        ensure_tenant_roles(request, closure.tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(request, closure.tenant, "month_closure")
        ensure_property_action(request, closure.tenant, closure.property, "can_access")
        return Response(MonthClosureSerializer(closure).data)

    @action(detail=False, methods=["post"], url_path="close")
    def close(self, request):
        ctx = resolve_access_context(request, require_property=True)
        tenant = ctx.tenant
        property_obj = ctx.property
        ensure_tenant_roles(request, tenant, ["admin"])
        ensure_module_enabled(request, tenant, "month_closure")
        ensure_property_action(request, tenant, property_obj, "can_schedule")
        closure = MonthClosureService.close_month(
            tenant=tenant,
            property_obj=property_obj,
            year=int(request.data.get("year")),
            month=int(request.data.get("month")),
            user=request.user if request.user.is_authenticated else None,
        )
        return Response(MonthClosureSerializer(closure).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="reopen")
    def reopen(self, request):
        ctx = resolve_access_context(request, require_property=True)
        tenant = ctx.tenant
        property_obj = ctx.property
        ensure_tenant_roles(request, tenant, ["admin"])
        ensure_module_enabled(request, tenant, "month_closure")
        ensure_property_action(request, tenant, property_obj, "can_schedule")
        closure = MonthClosureService.reopen_month(
            tenant=tenant,
            property_obj=property_obj,
            year=int(request.data.get("year")),
            month=int(request.data.get("month")),
            user=request.user if request.user.is_authenticated else None,
        )
        return Response(MonthClosureSerializer(closure).data, status=status.HTTP_200_OK)
