from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.modules.models import ModuleActivation
from apps.tenants.models import Property, Tenant, TenantSupportAccessSession
from apps.users.models import RoleChoices, User, UserAreaPermission, UserPropertyPermission, UserTenantRole
from apps.users.services import PermissionService
from apps.workers.models import Area


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="admin@pariwana.test", password="StrongPass123")

    def test_login(self):
        response = self.client.post(
            reverse("login"),
            {"email": "admin@pariwana.test", "password": "StrongPass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_me_includes_support_context_for_super_admin(self):
        super_admin = User.objects.create_user(
            email="super-me@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        property_obj = Property.objects.create(tenant=tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        session = TenantSupportAccessSession.objects.create(
            tenant=tenant,
            property=property_obj,
            started_by=super_admin,
            reason="test me endpoint",
        )
        self.client.force_authenticate(user=super_admin)
        response = self.client.get(
            reverse("me"),
            HTTP_X_SUPPORT_SESSION_ID=str(session.id),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("support", data)
        self.assertEqual(data["support"]["current_session"]["id"], session.id)
        self.assertEqual(len(data["support"]["active_sessions"]), 1)


class PermissionServiceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.property_2 = Property.objects.create(tenant=self.tenant, name="Pariwana Lima", slug="pariwana-lima")
        self.user = User.objects.create_user(email="supervisor@pariwana.test", password="StrongPass123")
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepción")
        self.area_2 = Area.objects.create(tenant=self.tenant, property=self.property, name="Housekeeping")

    def test_supervisor_limited_by_area(self):
        UserTenantRole.objects.create(user=self.user, tenant=self.tenant, role=RoleChoices.SUPERVISOR)
        UserPropertyPermission.objects.create(
            user=self.user,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_schedule=True,
        )
        UserAreaPermission.objects.create(
            user=self.user,
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            can_view=True,
            can_schedule=True,
        )

        self.assertTrue(
            PermissionService.user_can_property_action(
                user=self.user,
                tenant=self.tenant,
                property_obj=self.property,
                action="can_schedule",
            )
        )
        self.assertTrue(
            PermissionService.user_can_area_schedule(
                user=self.user,
                tenant=self.tenant,
                property_obj=self.property,
                area=self.area,
            )
        )
        self.assertFalse(
            PermissionService.user_can_area_view(
                user=self.user,
                tenant=self.tenant,
                property_obj=self.property,
                area=self.area_2,
            )
        )

    def test_operator_without_area_permissions_can_schedule_all_areas(self):
        operator = User.objects.create_user(email="operator-all@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=operator, tenant=self.tenant, role=RoleChoices.OPERATOR)
        UserPropertyPermission.objects.create(
            user=operator,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_schedule=True,
        )
        self.assertTrue(
            PermissionService.user_can_area_view(
                user=operator,
                tenant=self.tenant,
                property_obj=self.property,
                area=self.area,
            )
        )
        self.assertTrue(
            PermissionService.user_can_area_schedule(
                user=operator,
                tenant=self.tenant,
                property_obj=self.property,
                area=self.area_2,
            )
        )

    def test_operator_with_area_permissions_is_limited_to_configured_areas(self):
        operator = User.objects.create_user(email="operator-limited@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=operator, tenant=self.tenant, role=RoleChoices.OPERATOR)
        UserPropertyPermission.objects.create(
            user=operator,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_schedule=True,
        )
        UserAreaPermission.objects.create(
            user=operator,
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            can_view=True,
            can_schedule=True,
        )
        self.assertTrue(
            PermissionService.user_can_area_schedule(
                user=operator,
                tenant=self.tenant,
                property_obj=self.property,
                area=self.area,
            )
        )
        self.assertFalse(
            PermissionService.user_can_area_view(
                user=operator,
                tenant=self.tenant,
                property_obj=self.property,
                area=self.area_2,
            )
        )
        self.assertFalse(
            PermissionService.user_can_area_schedule(
                user=operator,
                tenant=self.tenant,
                property_obj=self.property,
                area=self.area_2,
            )
        )

    def test_admin_with_all_properties_access_sees_new_properties(self):
        admin = User.objects.create_user(email="admin-all@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(
            user=admin,
            tenant=self.tenant,
            role=RoleChoices.ADMIN,
            all_properties_access=True,
            property_permissions_template={"can_access": True},
        )
        future_property = Property.objects.create(
            tenant=self.tenant,
            name="Pariwana Miraflores",
            slug="pariwana-miraflores",
        )

        accessible_ids = PermissionService.get_accessible_property_ids(admin, self.tenant)
        self.assertIn(self.property.id, accessible_ids)
        self.assertIn(self.property_2.id, accessible_ids)
        self.assertIn(future_property.id, accessible_ids)
        self.assertTrue(PermissionService.user_can_property_action(admin, self.tenant, future_property, "can_manage_users"))

    def test_operator_with_all_properties_access_uses_permission_template_for_new_properties(self):
        operator = User.objects.create_user(email="operator-all-sites@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(
            user=operator,
            tenant=self.tenant,
            role=RoleChoices.OPERATOR,
            all_properties_access=True,
            property_permissions_template={
                "can_access": True,
                "can_schedule": True,
                "can_export_buk": False,
            },
        )
        future_property = Property.objects.create(
            tenant=self.tenant,
            name="Pariwana Miraflores",
            slug="pariwana-miraflores",
        )

        self.assertIn(future_property.id, PermissionService.get_accessible_property_ids(operator, self.tenant))
        self.assertTrue(PermissionService.user_can_property_action(operator, self.tenant, future_property, "can_schedule"))
        self.assertFalse(PermissionService.user_can_property_action(operator, self.tenant, future_property, "can_export_buk"))


class ApiPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="viewer@pariwana.test", password="StrongPass123")
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        Area.objects.create(tenant=self.tenant, property=self.property, name="Recepción")
        self.client.force_authenticate(user=self.user)

    def test_workers_endpoint_denies_without_tenant_role(self):
        response = self.client.get(f"/api/workers/?tenant_id={self.tenant.id}&property_id={self.property.id}")
        self.assertEqual(response.status_code, 403)


class UserManagementApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.admin = User.objects.create_user(email="admin2@pariwana.test", password="StrongPass123")
        self.viewer = User.objects.create_user(email="viewer2@pariwana.test", password="StrongPass123")
        self.target = User.objects.create_user(email="target@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=self.admin, tenant=self.tenant, role=RoleChoices.ADMIN)
        UserTenantRole.objects.create(user=self.viewer, tenant=self.tenant, role=RoleChoices.SUPERVISOR)
        ModuleActivation.objects.create(tenant=self.tenant, module_key="users_permissions", is_enabled=True)

    def test_non_admin_cannot_create_property_permission(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(
            "/api/user-property-permissions/",
            {
                "user": self.target.id,
                "tenant": self.tenant.id,
                "property": self.property.id,
                "can_access": True,
                "can_schedule": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_property_permission(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/user-property-permissions/?tenant_id={self.tenant.id}",
            {
                "user": self.target.id,
                "tenant": self.tenant.id,
                "property": self.property.id,
                "can_access": True,
                "can_schedule": True,
                "can_export_buk": True,
                "can_manage_workers": True,
                "can_manage_shifts": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)


class SupportContextUserViewsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.super_admin = User.objects.create_user(
            email="super-users@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        self.target = User.objects.create_user(email="target-users@pariwana.test", password="StrongPass123")
        UserPropertyPermission.objects.create(
            user=self.target,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_schedule=False,
            can_export_buk=False,
            can_manage_workers=False,
            can_manage_shifts=False,
        )
        self.support_session = TenantSupportAccessSession.objects.create(
            tenant=self.tenant,
            property=self.property,
            started_by=self.super_admin,
            reason="support users module",
        )

    def test_super_admin_can_list_user_property_permissions_with_support_session(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(
            "/api/user-property-permissions/",
            HTTP_X_SUPPORT_SESSION_ID=str(self.support_session.id),
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tenant"], self.tenant.id)


class SeedDemoUsersCommandTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.area_1 = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepción")
        self.area_2 = Area.objects.create(tenant=self.tenant, property=self.property, name="Housekeeping")
        self.area_3 = Area.objects.create(tenant=self.tenant, property=self.property, name="Bar")

    def test_seed_demo_users_creates_roles_and_permissions(self):
        call_command(
            "seed_demo_users",
            password="StrongPass123",
            supervisor_areas="Recepción,Housekeeping",
        )

        admin = User.objects.get(email="admin.demo@pariwana.local")
        operator = User.objects.get(email="operador.demo@pariwana.local")
        supervisor = User.objects.get(email="supervisor.demo@pariwana.local")

        self.assertTrue(admin.is_super_admin)
        self.assertTrue(UserTenantRole.objects.filter(user=admin, tenant=self.tenant, role=RoleChoices.ADMIN).exists())
        self.assertTrue(
            UserPropertyPermission.objects.filter(
                user=admin,
                tenant=self.tenant,
                property=self.property,
                can_manage_workers=True,
                can_manage_shifts=True,
            ).exists()
        )
        self.assertTrue(UserTenantRole.objects.filter(user=operator, tenant=self.tenant, role=RoleChoices.OPERATOR).exists())
        self.assertEqual(
            UserAreaPermission.objects.filter(user=operator, tenant=self.tenant, property=self.property).count(),
            3,
        )
        self.assertTrue(UserTenantRole.objects.filter(user=supervisor, tenant=self.tenant, role=RoleChoices.SUPERVISOR).exists())
        self.assertEqual(
            UserAreaPermission.objects.filter(user=supervisor, tenant=self.tenant, property=self.property).count(),
            2,
        )
        self.assertTrue(
            UserAreaPermission.objects.filter(
                user=supervisor,
                tenant=self.tenant,
                property=self.property,
                area=self.area_1,
            ).exists()
        )

    def test_seed_demo_users_is_idempotent(self):
        call_command("seed_demo_users", password="StrongPass123")
        call_command("seed_demo_users", password="StrongPass123")

        self.assertEqual(User.objects.filter(email__endswith="@pariwana.local").count(), 3)
        self.assertEqual(UserTenantRole.objects.filter(tenant=self.tenant).count(), 3)


class ValidateDemoSetupCommandTests(TestCase):
    def test_validate_demo_setup_passes_after_bootstrap(self):
        call_command(
            "bootstrap_local_demo",
            password="StrongPass123",
            days=7,
            supervisor_areas="Recepción,Housekeeping",
        )
        call_command("validate_demo_setup")

    def test_validate_demo_setup_fails_when_supervisor_missing(self):
        call_command(
            "bootstrap_local_demo",
            password="StrongPass123",
            days=5,
            supervisor_areas="Recepción,Housekeeping",
        )
        User.objects.filter(email="supervisor.demo@pariwana.local").delete()
        with self.assertRaises(CommandError):
            call_command("validate_demo_setup")
