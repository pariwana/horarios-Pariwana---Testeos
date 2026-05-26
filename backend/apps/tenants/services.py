from django.utils import timezone

from apps.audit.services import AuditService
from apps.tenants.models import TenantSupportAccessSession


class TenantSupportService:
    @staticmethod
    def start_session(*, tenant, property_obj, user, reason):
        session = TenantSupportAccessSession.objects.create(
            tenant=tenant,
            property=property_obj,
            started_by=user,
            reason=reason or "",
        )
        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=user,
            action="support_access_start",
            entity_type="TenantSupportAccessSession",
            entity_id=session.id,
            before={},
            after={
                "tenant_id": tenant.id,
                "property_id": property_obj.id if property_obj else None,
                "reason": reason or "",
            },
        )
        return session

    @staticmethod
    def stop_session(*, session, user, reason):
        if session.ended_at is not None:
            return session
        session.ended_at = timezone.now()
        session.ended_by = user
        session.end_reason = reason or ""
        session.save(update_fields=["ended_at", "ended_by", "end_reason", "updated_at"])
        AuditService.log(
            tenant=session.tenant,
            property_obj=session.property,
            user=user,
            action="support_access_stop",
            entity_type="TenantSupportAccessSession",
            entity_id=session.id,
            before={},
            after={"end_reason": reason or ""},
        )
        return session
