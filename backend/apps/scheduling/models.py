from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel
from apps.tenants.models import Property, Tenant
from apps.workers.models import Shift, SpecialState, Worker


class ScheduleAssignment(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="assignments")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="assignments")
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name="assignments")
    date = models.DateField()
    shift = models.ForeignKey(Shift, null=True, blank=True, on_delete=models.PROTECT, related_name="assignments")
    special_state = models.ForeignKey(
        SpecialState,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_assignments",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_assignments",
    )

    class Meta:
        unique_together = [("worker", "property", "date")]
        ordering = ["date", "worker__last_name", "worker__first_name"]

    def clean(self):
        if self.shift and self.special_state:
            raise ValidationError("Una asignación diaria no puede tener turno y estado especial al mismo tiempo.")
        if not self.shift and not self.special_state:
            raise ValidationError("Una asignación diaria debe tener turno o estado especial.")
        if self.worker.property_id != self.property_id:
            raise ValidationError("El trabajador no pertenece a la sede seleccionada.")
        if self.shift and self.shift.property_id != self.property_id:
            raise ValidationError("El turno no pertenece a la sede seleccionada.")
        if self.special_state and self.special_state.property_id != self.property_id:
            raise ValidationError("El estado especial no pertenece a la sede seleccionada.")
