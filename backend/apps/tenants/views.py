from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.common.access import ensure_tenant_roles, resolve_support_session
from apps.tenants.models import Property, Tenant, TenantSupportAccessSession
from apps.tenants.serializers import PropertySerializer, TenantSerializer, TenantSupportAccessSessionSerializer
from apps.tenants.services import TenantSupportService
from apps.users.services import PermissionService


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all().order_by("name")
    serializer_class = TenantSerializer

    def get_queryset(self):
        support_session = resolve_support_session(self.request)
        user = self.request.user
        if PermissionService.is_super_admin(user):
            queryset = super().get_queryset()
            if support_session is not None:
                queryset = queryset.filter(id=support_session.tenant_id)
            return queryset
        tenant_ids = list(user.tenant_roles.values_list("tenant_id", flat=True))
        return super().get_queryset().filter(id__in=tenant_ids)

    def perform_create(self, serializer):
        if not PermissionService.is_super_admin(self.request.user):
            raise PermissionDenied("Solo Super Administrador puede crear tenants.")
        serializer.save()

    def perform_update(self, serializer):
        if not PermissionService.is_super_admin(self.request.user):
            raise PermissionDenied("Solo Super Administrador puede editar tenants.")
        serializer.save()

    def perform_destroy(self, instance):
        if not PermissionService.is_super_admin(self.request.user):
            raise PermissionDenied("Solo Super Administrador puede eliminar tenants.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="support-access/start")
    def start_support_access(self, request, pk=None):
        if not PermissionService.is_super_admin(request.user):
            raise PermissionDenied("Solo Super Administrador puede iniciar soporte.")
        tenant = self.get_object()
        property_id = request.data.get("property_id")
        reason = str(request.data.get("reason", "")).strip()
        property_obj = None
        if property_id:
            property_obj = Property.objects.filter(pk=property_id, tenant=tenant).first()
            if property_obj is None:
                raise ValidationError("La sede no pertenece al tenant.")
        session = TenantSupportService.start_session(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user,
            reason=reason,
        )
        return Response(TenantSupportAccessSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="support-access/stop")
    def stop_support_access(self, request, pk=None):
        if not PermissionService.is_super_admin(request.user):
            raise PermissionDenied("Solo Super Administrador puede cerrar soporte.")
        tenant = self.get_object()
        session_id = request.data.get("session_id")
        reason = str(request.data.get("reason", "")).strip()
        queryset = TenantSupportAccessSession.objects.filter(tenant=tenant, ended_at__isnull=True)
        if session_id:
            queryset = queryset.filter(id=session_id)
        session = queryset.order_by("-created_at").first()
        if session is None:
            raise ValidationError("No existe sesion activa de soporte para cerrar.")
        session = TenantSupportService.stop_session(session=session, user=request.user, reason=reason)
        return Response(TenantSupportAccessSessionSerializer(session).data)

    @action(detail=True, methods=["get"], url_path="support-access/sessions")
    def support_sessions(self, request, pk=None):
        tenant = self.get_object()
        if not PermissionService.is_super_admin(request.user):
            ensure_tenant_roles(request, tenant, ["admin"])
        sessions = TenantSupportAccessSession.objects.filter(tenant=tenant).select_related(
            "property", "started_by", "ended_by"
        )
        return Response(TenantSupportAccessSessionSerializer(sessions, many=True).data)

    @action(detail=False, methods=["get"], url_path="support-access/active")
    def active_support_access(self, request):
        if not PermissionService.is_super_admin(request.user):
            raise PermissionDenied("Solo Super Administrador puede ver sesiones activas de soporte.")
        tenant_id = request.query_params.get("tenant_id")
        sessions = TenantSupportAccessSession.objects.filter(
            started_by=request.user,
            ended_at__isnull=True,
        ).select_related("tenant", "property", "started_by", "ended_by")
        if tenant_id:
            tenant = Tenant.objects.filter(pk=tenant_id).first()
            if tenant is None:
                raise ValidationError("Tenant no encontrado.")
            sessions = sessions.filter(tenant=tenant)
        sessions = sessions.order_by("-created_at")
        first_session = sessions.first()
        return Response(
            {
                "active_count": sessions.count(),
                "active_session": (
                    TenantSupportAccessSessionSerializer(first_session).data if first_session is not None else None
                ),
                "sessions": TenantSupportAccessSessionSerializer(sessions, many=True).data,
            }
        )

    @action(detail=False, methods=["post"], url_path="support-access/stop-all")
    def stop_all_support_access(self, request):
        if not PermissionService.is_super_admin(request.user):
            raise PermissionDenied("Solo Super Administrador puede cerrar sesiones de soporte.")
        tenant_id = request.data.get("tenant_id")
        reason = str(request.data.get("reason", "")).strip()
        sessions = TenantSupportAccessSession.objects.filter(
            started_by=request.user,
            ended_at__isnull=True,
        ).select_related("tenant", "property")
        if tenant_id:
            tenant = Tenant.objects.filter(pk=tenant_id).first()
            if tenant is None:
                raise ValidationError("Tenant no encontrado.")
            sessions = sessions.filter(tenant=tenant)
        closed_ids = []
        for session in sessions.order_by("-created_at"):
            TenantSupportService.stop_session(session=session, user=request.user, reason=reason)
            closed_ids.append(session.id)
        return Response(
            {
                "closed_count": len(closed_ids),
                "closed_session_ids": closed_ids,
            }
        )


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.select_related("tenant").all().order_by("name")
    serializer_class = PropertySerializer

    def get_queryset(self):
        support_session = resolve_support_session(self.request)
        user = self.request.user
        tenant_id = self.request.query_params.get("tenant_id")
        queryset = super().get_queryset()
        if support_session is not None:
            queryset = queryset.filter(tenant_id=support_session.tenant_id)
            if support_session.property_id:
                queryset = queryset.filter(id=support_session.property_id)
        elif tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if PermissionService.is_super_admin(user):
            return queryset
        allowed_tenants = list(user.tenant_roles.values_list("tenant_id", flat=True))
        return queryset.filter(tenant_id__in=allowed_tenants)

    def _ensure_can_manage(self, tenant):
        if PermissionService.is_super_admin(self.request.user):
            return
        ensure_tenant_roles(self.request, tenant, ["admin"])

    def perform_create(self, serializer):
        tenant = serializer.validated_data["tenant"]
        self._ensure_can_manage(tenant)
        serializer.save()

    def perform_update(self, serializer):
        tenant = serializer.instance.tenant
        self._ensure_can_manage(tenant)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_can_manage(instance.tenant)
        instance.delete()
