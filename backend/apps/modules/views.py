from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.common.access import ensure_tenant_roles, resolve_access_context, resolve_support_session
from apps.modules.models import ModuleActivation
from apps.modules.serializers import ModuleActivationSerializer
from apps.modules.services import ModuleActivationService
from apps.tenants.models import Tenant
from apps.users.services import PermissionService


class ModuleActivationViewSet(viewsets.ModelViewSet):
    queryset = ModuleActivation.objects.select_related("tenant", "enabled_by").all()
    serializer_class = ModuleActivationSerializer

    def _resolve_tenant(self):
        support_session = resolve_support_session(self.request)
        tenant_id = self.request.query_params.get("tenant_id") or self.request.data.get("tenant_id")
        if support_session is not None:
            if tenant_id and str(tenant_id) != str(support_session.tenant_id):
                raise PermissionDenied("La sesion de soporte esta limitada a otro tenant.")
            return support_session.tenant
        if tenant_id:
            return Tenant.objects.filter(pk=tenant_id).first()
        if PermissionService.is_super_admin(self.request.user):
            try:
                ctx = resolve_access_context(self.request, require_property=False)
                return ctx.tenant
            except ValidationError:
                return None
        return None

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = self._resolve_tenant()
        if tenant is not None:
            queryset = queryset.filter(tenant=tenant)
        if PermissionService.is_super_admin(self.request.user):
            return queryset
        allowed_tenants = list(self.request.user.tenant_roles.values_list("tenant_id", flat=True))
        return queryset.filter(tenant_id__in=allowed_tenants)

    def _ensure_manage_modules(self, tenant):
        if PermissionService.is_super_admin(self.request.user):
            return
        ensure_tenant_roles(self.request, tenant, ["admin"])

    @action(detail=False, methods=["post"], url_path="toggle")
    def toggle(self, request):
        module_key = request.data.get("module_key")
        raw_is_enabled = request.data.get("is_enabled")
        if isinstance(raw_is_enabled, bool):
            is_enabled = raw_is_enabled
        else:
            is_enabled = str(raw_is_enabled).strip().lower() in {"1", "true", "yes", "on"}
        tenant = self._resolve_tenant()
        if not module_key or tenant is None:
            return Response(
                {"detail": "tenant_id (o sesion de soporte) y module_key son requeridos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._ensure_manage_modules(tenant)
        activation = ModuleActivationService.set_state(
            tenant=tenant,
            module_key=module_key,
            is_enabled=is_enabled,
            user=request.user if request.user.is_authenticated else None,
        )
        return Response(ModuleActivationSerializer(activation).data)

    def perform_create(self, serializer):
        tenant = serializer.validated_data["tenant"]
        self._ensure_manage_modules(tenant)
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_manage_modules(serializer.instance.tenant)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_manage_modules(instance.tenant)
        instance.delete()
