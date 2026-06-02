from django.core.management.base import BaseCommand, CommandError

from apps.modules.models import ModuleActivation
from apps.scheduling.models import ScheduleAssignment
from apps.tenants.models import Property, Tenant
from apps.users.models import RoleChoices, User, UserAreaPermission, UserPropertyPermission, UserTenantRole
from apps.users.services import PermissionService
from apps.workers.models import Area, Shift, SpecialState, Worker


class Command(BaseCommand):
    help = "Validate local demo setup (tenant/property/users/permissions/core data)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", default="pariwana-hostels")
        parser.add_argument("--property-slug", default="pariwana-cusco")
        parser.add_argument("--admin-email", default="admin.demo@pariwana.local")
        parser.add_argument("--operator-email", default="operador.demo@pariwana.local")
        parser.add_argument("--supervisor-email", default="supervisor.demo@pariwana.local")
        parser.add_argument("--min-workers", type=int, default=10)
        parser.add_argument("--min-shifts", type=int, default=6)
        parser.add_argument("--min-states", type=int, default=2)
        parser.add_argument("--min-assignments", type=int, default=30)

    def _ensure(self, condition, message):
        if not condition:
            raise CommandError(message)

    def handle(self, *args, **options):
        tenant_slug = str(options["tenant_slug"]).strip().lower()
        property_slug = str(options["property_slug"]).strip().lower()
        admin_email = str(options["admin_email"]).strip().lower()
        operator_email = str(options["operator_email"]).strip().lower()
        supervisor_email = str(options["supervisor_email"]).strip().lower()

        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        self._ensure(tenant is not None, f"Tenant not found: {tenant_slug}")

        property_obj = Property.objects.filter(tenant=tenant, slug=property_slug).first()
        self._ensure(property_obj is not None, f"Property not found: {property_slug}")

        admin_user = User.objects.filter(email=admin_email).first()
        operator_user = User.objects.filter(email=operator_email).first()
        supervisor_user = User.objects.filter(email=supervisor_email).first()
        self._ensure(admin_user is not None, f"Admin demo user not found: {admin_email}")
        self._ensure(operator_user is not None, f"Operator demo user not found: {operator_email}")
        self._ensure(supervisor_user is not None, f"Supervisor demo user not found: {supervisor_email}")

        self._ensure(
            UserTenantRole.objects.filter(user=admin_user, tenant=tenant, role=RoleChoices.ADMIN).exists(),
            "Admin demo role mismatch.",
        )
        self._ensure(
            UserTenantRole.objects.filter(user=operator_user, tenant=tenant, role=RoleChoices.OPERATOR).exists(),
            "Operator demo role mismatch.",
        )
        self._ensure(
            UserTenantRole.objects.filter(user=supervisor_user, tenant=tenant, role=RoleChoices.SUPERVISOR).exists(),
            "Supervisor demo role mismatch.",
        )

        admin_perm = UserPropertyPermission.objects.filter(
            user=admin_user,
            tenant=tenant,
            property=property_obj,
        ).first()
        operator_perm = UserPropertyPermission.objects.filter(
            user=operator_user,
            tenant=tenant,
            property=property_obj,
        ).first()
        supervisor_perm = UserPropertyPermission.objects.filter(
            user=supervisor_user,
            tenant=tenant,
            property=property_obj,
        ).first()
        self._ensure(admin_perm is not None, "Admin property permission missing.")
        self._ensure(operator_perm is not None, "Operator property permission missing.")
        self._ensure(supervisor_perm is not None, "Supervisor property permission missing.")

        self._ensure(admin_perm.can_manage_workers and admin_perm.can_manage_shifts, "Admin manage permissions invalid.")
        self._ensure(operator_perm.can_manage_workers and operator_perm.can_manage_shifts, "Operator manage permissions invalid.")
        self._ensure(not supervisor_perm.can_manage_workers and not supervisor_perm.can_manage_shifts, "Supervisor manage permissions invalid.")
        self._ensure(admin_perm.can_manage_areas and admin_perm.can_manage_users, "Admin extended permissions invalid.")
        self._ensure(operator_perm.can_use_control and operator_perm.can_view_reports, "Operator control/report permissions invalid.")
        self._ensure(not operator_perm.can_manage_areas and not operator_perm.can_manage_users, "Operator restricted permissions invalid.")
        self._ensure(supervisor_perm.can_view_reports and not supervisor_perm.can_use_control, "Supervisor report/control permissions invalid.")

        supervisor_areas = UserAreaPermission.objects.filter(
            user=supervisor_user,
            tenant=tenant,
            property=property_obj,
            can_view=True,
            can_schedule=True,
        )
        self._ensure(supervisor_areas.exists(), "Supervisor area permissions missing.")

        areas = list(Area.objects.filter(tenant=tenant, property=property_obj, active=True))
        self._ensure(len(areas) > 0, "No active areas found.")
        for area in areas:
            self._ensure(
                PermissionService.user_can_area_view(operator_user, tenant, property_obj, area),
                f"Operator cannot view area: {area.name}",
            )
        blocked_areas = [
            area.name
            for area in areas
            if not PermissionService.user_can_area_view(supervisor_user, tenant, property_obj, area)
        ]
        self._ensure(len(blocked_areas) >= 1, "Supervisor should be restricted to subset of areas.")

        required_modules = [
            "workers",
            "shifts",
            "special_states",
            "scheduling",
            "control",
            "buk_export",
            "excel_import",
            "month_closure",
        ]
        for module_key in required_modules:
            self._ensure(
                ModuleActivation.objects.filter(tenant=tenant, module_key=module_key, is_enabled=True).exists(),
                f"Required module disabled: {module_key}",
            )

        min_workers = int(options["min_workers"])
        min_shifts = int(options["min_shifts"])
        min_states = int(options["min_states"])
        min_assignments = int(options["min_assignments"])
        workers_count = Worker.objects.filter(tenant=tenant, property=property_obj, active=True).count()
        shifts_count = Shift.objects.filter(tenant=tenant, property=property_obj, active=True).count()
        states_count = SpecialState.objects.filter(tenant=tenant, property=property_obj, active=True).count()
        assignments_count = ScheduleAssignment.objects.filter(tenant=tenant, property=property_obj).count()
        self._ensure(workers_count >= min_workers, f"Workers below expected minimum ({workers_count} < {min_workers}).")
        self._ensure(shifts_count >= min_shifts, f"Shifts below expected minimum ({shifts_count} < {min_shifts}).")
        self._ensure(states_count >= min_states, f"Special states below expected minimum ({states_count} < {min_states}).")
        self._ensure(
            assignments_count >= min_assignments,
            f"Assignments below expected minimum ({assignments_count} < {min_assignments}).",
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo setup validation passed: "
                f"tenant={tenant.slug}, property={property_obj.slug}, "
                f"workers={workers_count}, shifts={shifts_count}, states={states_count}, assignments={assignments_count}.",
            )
        )
