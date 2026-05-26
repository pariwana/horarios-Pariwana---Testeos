from rest_framework import mixins, viewsets
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.common.access import ensure_module_enabled, ensure_property_action, ensure_tenant_roles, resolve_access_context
from apps.users.services import PermissionService


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AuditLog.objects.select_related("tenant", "property", "user").all()
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        if self.action == "retrieve" and "tenant_id" not in self.request.query_params:
            return super().get_queryset()
        ctx = resolve_access_context(self.request, require_property=False)
        ensure_tenant_roles(self.request, ctx.tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(self.request, ctx.tenant, "audit")
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
        log = self.get_object()
        ensure_tenant_roles(request, log.tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(request, log.tenant, "audit")
        if log.property_id:
            ensure_property_action(request, log.tenant, log.property, "can_access")
        return Response(AuditLogSerializer(log).data)
