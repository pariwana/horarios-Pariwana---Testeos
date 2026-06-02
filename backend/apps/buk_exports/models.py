from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel
from apps.tenants.models import Property, Tenant


class BukExportConfig(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="buk_configs")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="buk_configs")
    sheet_name = models.CharField(max_length=160, default="Reporte carga BUK")
    date_format = models.CharField(max_length=30, default="%d-%m-%Y")
    include_area = models.BooleanField(default=True)
    include_worker_name = models.BooleanField(default=True)
    document_column_name = models.CharField(max_length=100, default="RUT")
    name_column_name = models.CharField(max_length=100, default="Nombre")
    area_column_name = models.CharField(max_length=100, default="Área")
    header_row = models.PositiveIntegerField(default=2)
    first_data_row = models.PositiveIntegerField(default=3)
    export_format = models.CharField(max_length=20, default="xlsx")
    other_settings = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("tenant", "property")]


class BukExportLog(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="buk_export_logs")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="buk_export_logs")
    date_from = models.DateField()
    date_to = models.DateField()
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_buk_exports",
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    validation_status = models.CharField(max_length=30, default="unknown")
    errors_count = models.PositiveIntegerField(default=0)
    warnings_count = models.PositiveIntegerField(default=0)


class BukTemplateCompareLog(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="buk_template_compare_logs")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="buk_template_compare_logs")
    compared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="buk_template_compare_logs",
    )
    compared_at = models.DateTimeField(auto_now_add=True)
    date_from = models.DateField()
    date_to = models.DateField()
    sheet_name = models.CharField(max_length=160, default="Reporte carga BUK")
    reference_file_name = models.CharField(max_length=255, blank=True)
    reference_file_sha256 = models.CharField(max_length=64, blank=True)
    reference_file_size_bytes = models.PositiveIntegerField(default=0)
    is_compatible = models.BooleanField(default=False)
    errors_count = models.PositiveIntegerField(default=0)
    warnings_count = models.PositiveIntegerField(default=0)
    result_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-compared_at", "-id"]
