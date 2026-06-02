from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from apps.tenants.models import Property, Tenant
from apps.users.models import User


class Command(BaseCommand):
    help = "Run basic WebUI smoke checks by role (admin/operator/supervisor)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", default="pariwana-hostels")
        parser.add_argument("--property-slug", default="pariwana-cusco")
        parser.add_argument("--admin-email", default="admin.demo@pariwana.local")
        parser.add_argument("--operator-email", default="operador.demo@pariwana.local")
        parser.add_argument("--supervisor-email", default="supervisor.demo@pariwana.local")

    @staticmethod
    def _resolve_http_host():
        hosts = [str(item).strip() for item in getattr(settings, "ALLOWED_HOSTS", []) if str(item).strip()]
        for host in hosts:
            if host not in {"*", "testserver"}:
                return host
        return "localhost"

    @staticmethod
    def _build_client(*, user, tenant, property_obj, http_host):
        client = Client()
        client.defaults["HTTP_HOST"] = http_host
        client.force_login(user)
        session = client.session
        session["ui_tenant_id"] = tenant.id
        session["ui_property_id"] = property_obj.id
        session.save()
        return client

    @staticmethod
    def _run_check(*, client, path, status_code=200, must_contain=None, must_not_contain=None, http_host="localhost"):
        response = client.get(path, follow=True, HTTP_HOST=http_host)
        body = response.content.decode("utf-8", errors="ignore")
        errors = []
        if response.status_code != status_code:
            errors.append(f"{path} status={response.status_code} expected={status_code}")
        if must_contain and must_contain not in body:
            errors.append(f"{path} missing text: {must_contain}")
        if must_not_contain and must_not_contain in body:
            errors.append(f"{path} unexpected text: {must_not_contain}")
        return errors

    def handle(self, *args, **options):
        tenant_slug = str(options["tenant_slug"]).strip().lower()
        property_slug = str(options["property_slug"]).strip().lower()
        admin_email = str(options["admin_email"]).strip().lower()
        operator_email = str(options["operator_email"]).strip().lower()
        supervisor_email = str(options["supervisor_email"]).strip().lower()

        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        if tenant is None:
            raise CommandError(f"Tenant not found: {tenant_slug}")
        property_obj = Property.objects.filter(tenant=tenant, slug=property_slug).first()
        if property_obj is None:
            raise CommandError(f"Property not found: {property_slug}")

        admin_user = User.objects.filter(email=admin_email).first()
        operator_user = User.objects.filter(email=operator_email).first()
        supervisor_user = User.objects.filter(email=supervisor_email).first()
        if admin_user is None or operator_user is None or supervisor_user is None:
            raise CommandError("Demo users missing. Run bootstrap_local_demo or seed_demo_users first.")
        http_host = self._resolve_http_host()

        checks = [
            (
                "admin",
                admin_user,
                [
                    ("/app/", 200, None, "No tienes permisos"),
                    ("/app/scheduling/", 200, None, "No tienes permisos"),
                    ("/app/imports/", 200, None, "No tienes permisos"),
                    ("/app/buk-report/", 200, None, "No tienes permisos"),
                    ("/app/month-closure/", 200, None, "No tienes permisos"),
                    ("/app/users-permissions/", 200, None, "Solo administradores pueden gestionar usuarios."),
                ],
            ),
            (
                "operator",
                operator_user,
                [
                    ("/app/scheduling/", 200, None, "No tienes permisos"),
                    ("/app/imports/", 200, None, "No tienes permisos"),
                    ("/app/control/", 200, None, "No tienes permisos"),
                    ("/app/buk-report/", 200, None, "No tienes permisos"),
                    ("/app/users-permissions/", 200, "Solo administradores pueden gestionar usuarios.", None),
                ],
            ),
            (
                "supervisor",
                supervisor_user,
                [
                    ("/app/scheduling/", 200, None, "No tienes permisos"),
                    ("/app/buk-report/", 200, None, "No tienes permisos"),
                    ("/app/control/", 200, "No tienes permisos para usar Control en esta sede.", None),
                    ("/app/imports/", 200, "No tienes permisos para gestionar importaciones en esta sede.", None),
                ],
            ),
        ]

        all_errors = []
        total_checks = 0
        for role_name, user, role_checks in checks:
            client = self._build_client(user=user, tenant=tenant, property_obj=property_obj, http_host=http_host)
            for path, status_code, must_contain, must_not_contain in role_checks:
                total_checks += 1
                errors = self._run_check(
                    client=client,
                    path=path,
                    status_code=status_code,
                    must_contain=must_contain,
                    must_not_contain=must_not_contain,
                    http_host=http_host,
                )
                if errors:
                    all_errors.extend([f"[{role_name}] {item}" for item in errors])

        if all_errors:
            for item in all_errors:
                self.stdout.write(self.style.ERROR(item))
            raise CommandError(f"WebUI smoke checks failed ({len(all_errors)} issues).")

        self.stdout.write(
            self.style.SUCCESS(
                f"WebUI smoke checks passed: roles=3, checks={total_checks}, tenant={tenant.slug}, property={property_obj.slug}, host={http_host}."
            )
        )
