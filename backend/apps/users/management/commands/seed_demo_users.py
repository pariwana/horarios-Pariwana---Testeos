from django.core.management.base import BaseCommand, CommandError

from apps.tenants.models import Property, Tenant
from apps.users.models import RoleChoices, User, UserAreaPermission, UserPropertyPermission, UserTenantRole
from apps.workers.models import Area


class Command(BaseCommand):
    help = "Create/update demo users for local QA by role (admin/operator/supervisor)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", default="pariwana-hostels")
        parser.add_argument("--property-slug", default="pariwana-cusco")
        parser.add_argument("--password", required=True, help="Shared password for all demo users.")
        parser.add_argument("--admin-email", default="admin.demo@pariwana.local")
        parser.add_argument("--operator-email", default="operador.demo@pariwana.local")
        parser.add_argument("--supervisor-email", default="supervisor.demo@pariwana.local")
        parser.add_argument(
            "--supervisor-areas",
            default="Recepcion,Housekeeping",
            help="Comma-separated area names for supervisor scope.",
        )

    def _upsert_user(self, *, email, password, first_name, last_name):
        user, created = User.objects.get_or_create(
            email=email.strip().lower(),
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
                "is_staff": False,
                "is_super_admin": False,
            },
        )
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.set_password(password)
        user.save()
        return user, created

    def _assign_role_and_property_permissions(
        self,
        *,
        user,
        tenant,
        property_obj,
        role,
        can_access,
        can_schedule,
        can_export_buk,
        can_manage_workers,
        can_manage_shifts,
        can_manage_areas=False,
        can_manage_users=False,
        can_view_reports=False,
        can_use_control=False,
    ):
        UserTenantRole.objects.update_or_create(
            user=user,
            tenant=tenant,
            defaults={"role": role},
        )
        UserPropertyPermission.objects.update_or_create(
            user=user,
            tenant=tenant,
            property=property_obj,
            defaults={
                "can_access": can_access,
                "can_schedule": can_schedule,
                "can_export_buk": can_export_buk,
                "can_manage_workers": can_manage_workers,
                "can_manage_shifts": can_manage_shifts,
                "can_manage_areas": can_manage_areas,
                "can_manage_users": can_manage_users,
                "can_view_reports": can_view_reports,
                "can_use_control": can_use_control,
            },
        )

    def handle(self, *args, **options):
        tenant_slug = str(options["tenant_slug"]).strip().lower()
        property_slug = str(options["property_slug"]).strip().lower()
        shared_password = str(options["password"]).strip()
        if not shared_password:
            raise CommandError("Password cannot be empty.")

        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        if tenant is None:
            raise CommandError(f"Tenant not found: {tenant_slug}")

        property_obj = Property.objects.filter(tenant=tenant, slug=property_slug).first()
        if property_obj is None:
            raise CommandError(f"Property not found in tenant {tenant_slug}: {property_slug}")

        area_queryset = Area.objects.filter(tenant=tenant, property=property_obj, active=True).order_by("name")
        if not area_queryset.exists():
            raise CommandError("No active areas found in target property. Seed areas first.")

        admin_user, admin_created = self._upsert_user(
            email=options["admin_email"],
            password=shared_password,
            first_name="Admin",
            last_name="Demo",
        )
        operator_user, operator_created = self._upsert_user(
            email=options["operator_email"],
            password=shared_password,
            first_name="Operador",
            last_name="Demo",
        )
        supervisor_user, supervisor_created = self._upsert_user(
            email=options["supervisor_email"],
            password=shared_password,
            first_name="Supervisor",
            last_name="Demo",
        )

        self._assign_role_and_property_permissions(
            user=admin_user,
            tenant=tenant,
            property_obj=property_obj,
            role=RoleChoices.ADMIN,
            can_access=True,
            can_schedule=True,
            can_export_buk=True,
            can_manage_workers=True,
            can_manage_shifts=True,
            can_manage_areas=True,
            can_manage_users=True,
            can_view_reports=True,
            can_use_control=True,
        )
        self._assign_role_and_property_permissions(
            user=operator_user,
            tenant=tenant,
            property_obj=property_obj,
            role=RoleChoices.OPERATOR,
            can_access=True,
            can_schedule=True,
            can_export_buk=True,
            can_manage_workers=True,
            can_manage_shifts=True,
            can_manage_areas=False,
            can_manage_users=False,
            can_view_reports=True,
            can_use_control=True,
        )
        self._assign_role_and_property_permissions(
            user=supervisor_user,
            tenant=tenant,
            property_obj=property_obj,
            role=RoleChoices.SUPERVISOR,
            can_access=True,
            can_schedule=True,
            can_export_buk=True,
            can_manage_workers=False,
            can_manage_shifts=False,
            can_manage_areas=False,
            can_manage_users=False,
            can_view_reports=True,
            can_use_control=False,
        )

        # Operator gets explicit area permissions on all active areas.
        operator_area_ids = list(area_queryset.values_list("id", flat=True))
        UserAreaPermission.objects.filter(
            user=operator_user,
            tenant=tenant,
            property=property_obj,
        ).exclude(area_id__in=operator_area_ids).delete()
        for area in area_queryset:
            UserAreaPermission.objects.update_or_create(
                user=operator_user,
                tenant=tenant,
                property=property_obj,
                area=area,
                defaults={"can_view": True, "can_schedule": True},
            )

        supervisor_area_names = [x.strip() for x in str(options["supervisor_areas"]).split(",") if x.strip()]
        supervisor_areas = list(
            Area.objects.filter(
                tenant=tenant,
                property=property_obj,
                active=True,
                name__in=supervisor_area_names,
            ).order_by("name")
        )
        if not supervisor_areas:
            raise CommandError("No supervisor areas matched. Check --supervisor-areas values.")

        supervisor_area_ids = [item.id for item in supervisor_areas]
        UserAreaPermission.objects.filter(
            user=supervisor_user,
            tenant=tenant,
            property=property_obj,
        ).exclude(area_id__in=supervisor_area_ids).delete()
        for area in supervisor_areas:
            UserAreaPermission.objects.update_or_create(
                user=supervisor_user,
                tenant=tenant,
                property=property_obj,
                area=area,
                defaults={"can_view": True, "can_schedule": True},
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo users ready: "
                f"admin={admin_user.email} ({'created' if admin_created else 'updated'}), "
                f"operator={operator_user.email} ({'created' if operator_created else 'updated'}), "
                f"supervisor={supervisor_user.email} ({'created' if supervisor_created else 'updated'})",
            )
        )
