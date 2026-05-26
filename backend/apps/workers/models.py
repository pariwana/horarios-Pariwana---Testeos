from django.db import models

from apps.common.models import TimestampedModel
from apps.tenants.models import Property, Tenant


class Area(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="areas")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="areas")
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=80, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("tenant", "property", "name")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Worker(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="workers")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="workers")
    document_number = models.CharField(max_length=32)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="workers")
    active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    buk_employee_code = models.CharField(max_length=80, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("tenant", "property", "document_number")]
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.document_number} - {self.first_name} {self.last_name}"


class Shift(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="shifts")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="shifts")
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="shifts")
    name = models.CharField(max_length=120)
    buk_code = models.CharField(max_length=80)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    is_night_shift = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("tenant", "property", "area", "name"), ("tenant", "property", "buk_code")]
        ordering = ["area__name", "name"]

    def __str__(self):
        return f"{self.area.name} - {self.name}"


class SpecialState(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="special_states")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="special_states")
    name = models.CharField(max_length=120)
    buk_code = models.CharField(max_length=80, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("tenant", "property", "name")]
        ordering = ["name"]

    def __str__(self):
        return self.name
