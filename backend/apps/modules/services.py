from django.utils import timezone

from apps.audit.services import AuditService
from apps.modules.models import ModuleActivation


class ModuleActivationService:
    @staticmethod
    def set_state(*, tenant=None, tenant_id=None, module_key, is_enabled, user=None):
        if tenant is None and tenant_id is None:
            raise ValueError("tenant o tenant_id es requerido")
        filters = {"module_key": module_key}
        if tenant is not None:
            filters["tenant"] = tenant
        else:
            filters["tenant_id"] = tenant_id
        activation, _ = ModuleActivation.objects.get_or_create(
            **filters,
            defaults={"is_enabled": is_enabled},
        )
        activation.is_enabled = is_enabled
        activation.enabled_by = user
        activation.enabled_at = timezone.now() if is_enabled else None
        activation.save(update_fields=["is_enabled", "enabled_by", "enabled_at", "updated_at"])
        if user is not None:
            AuditService.log(
                tenant=activation.tenant,
                property_obj=None,
                user=user,
                action="module_activation_change",
                entity_type="ModuleActivation",
                entity_id=activation.id,
                before={},
                after={"module_key": module_key, "is_enabled": is_enabled},
            )
        return activation
