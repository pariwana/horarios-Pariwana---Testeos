from django.utils import timezone

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
        closure.status = MonthClosureStatus.CLOSED
        closure.closed_by = user
        closure.closed_at = timezone.now()
        closure.save()
        return closure

    @staticmethod
    def reopen_month(*, tenant, property_obj, year, month, user):
        closure, _ = MonthClosure.objects.get_or_create(
            tenant=tenant,
            property=property_obj,
            year=year,
            month=month,
        )
        closure.status = MonthClosureStatus.OPEN
        closure.reopened_by = user
        closure.reopened_at = timezone.now()
        closure.save()
        return closure
