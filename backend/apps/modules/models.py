from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel
from apps.tenants.models import Tenant


class ModuleActivation(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="modules")
    module_key = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=False)
    enabled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="enabled_modules",
    )
    enabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("tenant", "module_key")]

    def __str__(self):
        return f"{self.tenant.slug}:{self.module_key}:{self.is_enabled}"
