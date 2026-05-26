from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.tenants.models import Property, Tenant, TenantSupportAccessSession
from apps.users.models import RoleChoices
from apps.users.services import PermissionService


class AccessContext:
    def __init__(self, tenant, property_obj=None):
        self.tenant = tenant
        self.property = property_obj


def _pick_value(request, key):
    if key in request.data:
        return request.data.get(key)
    return request.query_params.get(key)


def _resolve_support_session(request):
    session_id = (
        request.headers.get("X-Support-Session-Id")
        or _pick_value(request, "support_session_id")
        or _pick_value(request, "support_session")
    )
    if not session_id:
        return None
    if not request.user or not request.user.is_authenticated:
        raise PermissionDenied("Debes iniciar sesion para usar una sesion de soporte.")
    if not PermissionService.is_super_admin(request.user):
        raise PermissionDenied("Solo Super Administrador puede usar sesion de soporte.")

    session = (
        TenantSupportAccessSession.objects.select_related("tenant", "property")
        .filter(pk=session_id, ended_at__isnull=True)
        .first()
    )
    if session is None:
        raise ValidationError("Sesion de soporte no encontrada o inactiva.")
    if session.started_by_id != request.user.id:
        raise PermissionDenied("No puedes usar una sesion de soporte iniciada por otro usuario.")
    return session


def resolve_support_session(request):
    session = _resolve_support_session(request)
    request.support_session = session
    return session


def resolve_access_context(request, require_property=False):
    tenant_id = _pick_value(request, "tenant_id") or _pick_value(request, "tenant")
    property_id = _pick_value(request, "property_id") or _pick_value(request, "property")
    support_session = resolve_support_session(request)
    tenant = None
    property_obj = None

    if tenant_id is None:
        if support_session is None:
            raise ValidationError("tenant_id es requerido.")
        tenant = support_session.tenant
        if support_session.property_id:
            if property_id is not None:
                try:
                    property_id_int = int(property_id)
                except (TypeError, ValueError):
                    raise ValidationError("property_id invalido.")
                if property_id_int != support_session.property_id:
                    raise PermissionDenied("La sesion de soporte esta limitada a otra sede.")
            property_obj = support_session.property
    else:
        tenant = Tenant.objects.filter(pk=tenant_id).first()
        if tenant is None:
            raise ValidationError("Tenant no encontrado.")

    if property_obj is None and property_id is not None:
        property_obj = Property.objects.filter(pk=property_id, tenant=tenant).first()
        if property_obj is None:
            raise ValidationError("Sede no encontrada para ese tenant.")
    if require_property and property_obj is None:
        raise ValidationError("property_id es requerido.")

    request.support_session = support_session
    request.tenant = tenant
    request.property = property_obj
    return AccessContext(tenant=tenant, property_obj=property_obj)


def _ensure_support_scope(request, tenant, property_obj=None):
    session = getattr(request, "support_session", None)
    if session is None:
        return
    if tenant.id != session.tenant_id:
        raise PermissionDenied("La sesion de soporte esta limitada a otro tenant.")
    if session.property_id and property_obj is not None and property_obj.id != session.property_id:
        raise PermissionDenied("La sesion de soporte esta limitada a otra sede.")


def ensure_tenant_roles(request, tenant, roles):
    _ensure_support_scope(request, tenant)
    if PermissionService.is_super_admin(request.user):
        return
    if not PermissionService.user_can_tenant_role(request.user, tenant, roles):
        raise PermissionDenied("No tienes permisos para operar en este tenant.")


def ensure_module_enabled(request, tenant, module_key):
    _ensure_support_scope(request, tenant)
    if PermissionService.is_super_admin(request.user):
        return
    if not PermissionService.user_can_module(request.user, tenant, module_key):
        raise PermissionDenied(f"Modulo desactivado o sin permiso: {module_key}.")


def ensure_property_action(request, tenant, property_obj, action):
    _ensure_support_scope(request, tenant, property_obj)
    if PermissionService.is_super_admin(request.user):
        return
    if not PermissionService.user_can_property_action(request.user, tenant, property_obj, action):
        raise PermissionDenied("No tienes permisos en esta sede para esta accion.")


def ensure_area_schedule(request, tenant, property_obj, area):
    if PermissionService.is_super_admin(request.user):
        return
    role = PermissionService.get_user_role(request.user, tenant)
    if role == RoleChoices.ADMIN:
        return
    if not PermissionService.user_can_area_schedule(request.user, tenant, property_obj, area):
        raise PermissionDenied("No tienes permisos en esta area para asignar horarios.")
