from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.modules.models import ModuleActivation
from apps.tenants.models import Property, Tenant, TenantStatus


INITIAL_MODULES = [
    "tenants",
    "properties",
    "users_permissions",
    "module_activation",
    "workers",
    "areas",
    "shifts",
    "special_states",
    "scheduling",
    "control",
    "buk_validator",
    "buk_preview",
    "buk_export",
    "excel_import",
    "audit",
    "month_closure",
]


class Command(BaseCommand):
    help = "Seed initial tenant and properties for Pariwana."

    def handle(self, *args, **kwargs):
        tenant, _ = Tenant.objects.get_or_create(
            slug="pariwana-hostels",
            defaults={
                "name": "Pariwana Hostels",
                "status": TenantStatus.ACTIVE,
                "settings": {},
            },
        )

        for property_name in ["Pariwana Lima", "Pariwana Cusco"]:
            Property.objects.get_or_create(
                tenant=tenant,
                slug=slugify(property_name),
                defaults={"name": property_name, "status": TenantStatus.ACTIVE, "location": ""},
            )

        for module_key in INITIAL_MODULES:
            ModuleActivation.objects.get_or_create(
                tenant=tenant,
                module_key=module_key,
                defaults={"is_enabled": True},
            )

        self.stdout.write(self.style.SUCCESS("Initial tenant and properties seeded."))
