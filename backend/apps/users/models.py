from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.common.models import TimestampedModel
from apps.tenants.models import Property, Tenant
from apps.users.managers import UserManager


class User(TimestampedModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_super_admin = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email


class RoleChoices(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Administrador"
    ADMIN = "admin", "Administrador"
    OPERATOR = "operator", "Operador"
    SUPERVISOR = "supervisor", "Supervisor"


class UserTenantRole(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_roles")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="user_roles")
    role = models.CharField(max_length=20, choices=RoleChoices.choices)

    class Meta:
        unique_together = [("user", "tenant")]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.tenant.slug} - {self.role}"


class UserPropertyPermission(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="property_permissions")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="property_permissions")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="user_permissions")
    can_access = models.BooleanField(default=True)
    can_schedule = models.BooleanField(default=False)
    can_export_buk = models.BooleanField(default=False)
    can_manage_workers = models.BooleanField(default=False)
    can_manage_shifts = models.BooleanField(default=False)

    class Meta:
        unique_together = [("user", "tenant", "property")]


class UserAreaPermission(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="area_permissions")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="area_permissions")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="area_permissions")
    area = models.ForeignKey("workers.Area", on_delete=models.CASCADE, related_name="user_permissions")
    can_view = models.BooleanField(default=True)
    can_schedule = models.BooleanField(default=False)

    class Meta:
        unique_together = [("user", "tenant", "property", "area")]
