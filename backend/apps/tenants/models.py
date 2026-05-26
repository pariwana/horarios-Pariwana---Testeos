from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel


class TenantStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class Tenant(TimestampedModel):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=180, unique=True)
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
    )
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Property(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="properties")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
    )

    class Meta:
        ordering = ["tenant__name", "name"]
        unique_together = [("tenant", "slug"), ("tenant", "name")]

    def __str__(self) -> str:
        return f"{self.tenant.name} - {self.name}"


class TenantSupportAccessSession(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="support_sessions")
    property = models.ForeignKey(
        Property,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_sessions",
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="started_support_sessions",
    )
    reason = models.TextField(blank=True, default="")
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ended_support_sessions",
    )
    end_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
