from apps.audit.models import AuditLog


class AuditService:
    @staticmethod
    def log(*, tenant, property_obj=None, user=None, action, entity_type, entity_id, before=None, after=None):
        return AuditLog.objects.create(
            tenant=tenant,
            property=property_obj,
            user=user,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            before=before or {},
            after=after or {},
        )
