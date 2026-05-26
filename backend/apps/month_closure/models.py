from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel
from apps.tenants.models import Property, Tenant


class MonthClosureStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class MonthClosure(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="month_closures")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="month_closures")
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=MonthClosureStatus.choices, default=MonthClosureStatus.OPEN)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_months",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reopened_months",
    )
    reopened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("tenant", "property", "year", "month")]
