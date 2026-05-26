from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel
from apps.tenants.models import Property, Tenant


class ImportBatchStatus(models.TextChoices):
    PREVIEW = "preview", "Preview"
    CONFIRMED = "confirmed", "Confirmed"
    CANCELLED = "cancelled", "Cancelled"
    FAILED = "failed", "Failed"


class ImportBatch(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="import_batches")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="import_batches")
    source_type = models.CharField(max_length=40)
    file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=ImportBatchStatus.choices, default=ImportBatchStatus.PREVIEW)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_import_batches",
    )
    summary = models.JSONField(default=dict, blank=True)


class ImportPreviewRow(TimestampedModel):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="preview_rows")
    sheet_name = models.CharField(max_length=120)
    row_number = models.PositiveIntegerField()
    action = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default="ok")
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("batch", "sheet_name", "row_number")]
