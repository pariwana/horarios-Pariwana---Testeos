from django.utils import timezone

from apps.audit.services import AuditService
from apps.month_closure.models import MonthClosure, MonthClosureStatus


class MonthClosureService:
    @staticmethod
    def is_closed(*, tenant, property_obj, year, month):
        closure = MonthClosure.objects.filter(
            tenant=tenant,
            property=property_obj,
            year=year,
            month=month,
        ).first()
        if not closure:
            return False
        return closure.status == MonthClosureStatus.CLOSED

    @staticmethod
    def close_month(*, tenant, property_obj, year, month, user):
        closure, _ = MonthClosure.objects.get_or_create(
            tenant=tenant,
            property=property_obj,
            year=year,
            month=month,
        )
        before = {
            "status": closure.status,
            "closed_at": closure.closed_at.isoformat() if closure.closed_at else None,
            "reopened_at": closure.reopened_at.isoformat() if closure.reopened_at else None,
        }
        closure.status = MonthClosureStatus.CLOSED
        closure.closed_by = user
        closure.closed_at = timezone.now()
        closure.save()
        if user is not None:
            AuditService.log(
                tenant=tenant,
                property_obj=property_obj,
                user=user,
                action="month_close",
                entity_type="MonthClosure",
                entity_id=closure.id,
                before=before,
                after={
                    "status": closure.status,
                    "closed_at": closure.closed_at.isoformat() if closure.closed_at else None,
                    "reopened_at": closure.reopened_at.isoformat() if closure.reopened_at else None,
                },
            )
        return closure

    @staticmethod
    def reopen_month(*, tenant, property_obj, year, month, user):
        closure, _ = MonthClosure.objects.get_or_create(
            tenant=tenant,
            property=property_obj,
            year=year,
            month=month,
        )
        before = {
            "status": closure.status,
            "closed_at": closure.closed_at.isoformat() if closure.closed_at else None,
            "reopened_at": closure.reopened_at.isoformat() if closure.reopened_at else None,
        }
        closure.status = MonthClosureStatus.OPEN
        closure.reopened_by = user
        closure.reopened_at = timezone.now()
        closure.save()
        if user is not None:
            AuditService.log(
                tenant=tenant,
                property_obj=property_obj,
                user=user,
                action="month_reopen",
                entity_type="MonthClosure",
                entity_id=closure.id,
                before=before,
                after={
                    "status": closure.status,
                    "closed_at": closure.closed_at.isoformat() if closure.closed_at else None,
                    "reopened_at": closure.reopened_at.isoformat() if closure.reopened_at else None,
                },
            )
        return closure
