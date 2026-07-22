from django.contrib.auth import login, logout
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.access import ensure_module_enabled, ensure_tenant_roles, resolve_access_context
from apps.tenants.models import Tenant, TenantSupportAccessSession
from apps.users.models import User, UserAreaPermission, UserPropertyPermission, UserTenantRole
from apps.users.serializers import (
    LoginSerializer,
    UserAreaPermissionSerializer,
    UserPropertyPermissionSerializer,
    UserSerializer,
    UserTenantRoleSerializer,
)
from apps.users.services import PermissionService


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        login(request, serializer.validated_data["user"])
        return Response({"detail": "Sesion iniciada."})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"detail": "Sesion cerrada."}, status=status.HTTP_200_OK)


class MeView(APIView):
    def get(self, request):
        user = request.user
        payload = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_super_admin": user.is_super_admin,
        }

        if user.is_super_admin:
            sessions = list(
                TenantSupportAccessSession.objects.filter(
                    started_by=user,
                    ended_at__isnull=True,
                )
                .select_related("tenant", "property")
                .order_by("-created_at")
            )
            by_id = {str(session.id): session for session in sessions}
            header_session_id = request.headers.get("X-Support-Session-Id")
            current_session = by_id.get(str(header_session_id)) if header_session_id else None
            if current_session is None and sessions:
                current_session = sessions[0]

            payload["support"] = {
                "header_session_id": header_session_id,
                "current_session": (
                    {
                        "id": current_session.id,
                        "tenant_id": current_session.tenant_id,
                        "tenant_name": current_session.tenant.name,
                        "property_id": current_session.property_id,
                        "property_name": current_session.property.name if current_session.property_id else None,
                        "reason": current_session.reason,
                        "created_at": current_session.created_at,
                    }
                    if current_session
                    else None
                ),
                "active_sessions": [
                    {
                        "id": session.id,
                        "tenant_id": session.tenant_id,
                        "tenant_name": session.tenant.name,
                        "property_id": session.property_id,
                        "property_name": session.property.name if session.property_id else None,
                        "reason": session.reason,
                        "created_at": session.created_at,
                    }
                    for session in sessions
                ],
            }

        return Response(payload)


class TenantAdminScopedViewSet(viewsets.ModelViewSet):
    tenant_param = "tenant_id"

    def _get_tenant(self):
        tenant_id = self.request.query_params.get(self.tenant_param) or self.request.data.get("tenant_id")
        if tenant_id:
            return Tenant.objects.filter(pk=tenant_id).first()
        if PermissionService.is_super_admin(self.request.user):
            try:
                ctx = resolve_access_context(self.request, require_property=False)
                return ctx.tenant
            except ValidationError:
                return None
        return None

    def _ensure_manage(self, tenant):
        if PermissionService.is_super_admin(self.request.user):
            return
        ensure_tenant_roles(self.request, tenant, ["admin"])
        ensure_module_enabled(self.request, tenant, "users_permissions")


class UserViewSet(TenantAdminScopedViewSet):
    queryset = User.objects.all().order_by("email")
    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = self._get_tenant()
        if PermissionService.is_super_admin(self.request.user):
            if tenant:
                user_ids = UserTenantRole.objects.filter(tenant=tenant).values_list("user_id", flat=True)
                queryset = queryset.filter(id__in=user_ids)
            return queryset
        if tenant is None:
            return queryset.none()
        self._ensure_manage(tenant)
        user_ids = UserTenantRole.objects.filter(tenant=tenant).values_list("user_id", flat=True)
        return queryset.filter(id__in=user_ids)

    def perform_create(self, serializer):
        tenant = self._get_tenant()
        if tenant is None:
            raise PermissionDenied("tenant_id es requerido para crear usuarios.")
        self._ensure_manage(tenant)
        serializer.save()

    def perform_update(self, serializer):
        tenant = self._get_tenant()
        if tenant is None and not PermissionService.is_super_admin(self.request.user):
            raise PermissionDenied("tenant_id es requerido para editar usuarios.")
        if tenant:
            self._ensure_manage(tenant)
            if (
                not PermissionService.is_super_admin(self.request.user)
                and UserTenantRole.objects.filter(user=serializer.instance).exclude(tenant=tenant).exists()
            ):
                raise PermissionDenied("No se puede modificar globalmente una cuenta compartida entre tenants.")
        serializer.save()

    def perform_destroy(self, instance):
        tenant = self._get_tenant()
        if tenant:
            self._ensure_manage(tenant)
            if (
                not PermissionService.is_super_admin(self.request.user)
                and UserTenantRole.objects.filter(user=instance).exclude(tenant=tenant).exists()
            ):
                raise PermissionDenied("No se puede eliminar globalmente una cuenta compartida entre tenants.")
        elif not PermissionService.is_super_admin(self.request.user):
            raise PermissionDenied("tenant_id es requerido para eliminar usuarios.")
        instance.delete()


class UserTenantRoleViewSet(TenantAdminScopedViewSet):
    queryset = UserTenantRole.objects.select_related("tenant", "user").all()
    serializer_class = UserTenantRoleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = self._get_tenant()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
            if not PermissionService.is_super_admin(self.request.user):
                self._ensure_manage(tenant)
        elif not PermissionService.is_super_admin(self.request.user):
            return queryset.none()
        return queryset

    def perform_create(self, serializer):
        self._ensure_manage(serializer.validated_data["tenant"])
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_manage(serializer.instance.tenant)
        target_tenant = serializer.validated_data.get("tenant", serializer.instance.tenant)
        target_user = serializer.validated_data.get("user", serializer.instance.user)
        self._ensure_manage(target_tenant)
        if (
            target_user != serializer.instance.user
            and not PermissionService.is_super_admin(self.request.user)
            and not UserTenantRole.objects.filter(user=target_user, tenant=target_tenant).exists()
        ):
            raise PermissionDenied("El usuario no pertenece al tenant.")
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_manage(instance.tenant)
        instance.delete()


class UserPropertyPermissionViewSet(TenantAdminScopedViewSet):
    queryset = UserPropertyPermission.objects.select_related("tenant", "property", "user").all()
    serializer_class = UserPropertyPermissionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = self._get_tenant()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
            if not PermissionService.is_super_admin(self.request.user):
                self._ensure_manage(tenant)
        elif not PermissionService.is_super_admin(self.request.user):
            return queryset.none()
        return queryset

    def perform_create(self, serializer):
        self._ensure_manage(serializer.validated_data["tenant"])
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_manage(serializer.instance.tenant)
        target_tenant = serializer.validated_data.get("tenant", serializer.instance.tenant)
        self._ensure_manage(target_tenant)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_manage(instance.tenant)
        instance.delete()


class UserAreaPermissionViewSet(TenantAdminScopedViewSet):
    queryset = UserAreaPermission.objects.select_related("tenant", "property", "area", "user").all()
    serializer_class = UserAreaPermissionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = self._get_tenant()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
            if not PermissionService.is_super_admin(self.request.user):
                self._ensure_manage(tenant)
        elif not PermissionService.is_super_admin(self.request.user):
            return queryset.none()
        return queryset

    def perform_create(self, serializer):
        self._ensure_manage(serializer.validated_data["tenant"])
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_manage(serializer.instance.tenant)
        target_tenant = serializer.validated_data.get("tenant", serializer.instance.tenant)
        target_property = serializer.validated_data.get("property", serializer.instance.property)
        target_area = serializer.validated_data.get("area", serializer.instance.area)
        target_user = serializer.validated_data.get("user", serializer.instance.user)
        self._ensure_manage(target_tenant)
        if not UserTenantRole.objects.filter(user=target_user, tenant=target_tenant).exists():
            raise ValidationError("El usuario no pertenece al tenant.")
        if target_property.tenant_id != target_tenant.id:
            raise ValidationError("La sede no pertenece al tenant.")
        if target_area.tenant_id != target_tenant.id or target_area.property_id != target_property.id:
            raise ValidationError("El area no pertenece al tenant/sede indicada.")
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_manage(instance.tenant)
        instance.delete()
