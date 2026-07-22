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

    def test_admin_cannot_reassign_permission_record_to_user_from_another_tenant_by_id(self):
        local_permission = UserPropertyPermission.objects.create(
            user=self.target,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_manage_workers=False,
        )
        foreign_tenant = Tenant.objects.create(name="Tenant externo API", slug="tenant-externo-api")
        foreign_user = User.objects.create_user(email="foreign-api@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=foreign_user, tenant=foreign_tenant, role=RoleChoices.OPERATOR)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/api/user-property-permissions/{local_permission.id}/?tenant_id={self.tenant.id}",
            {"user": foreign_user.id, "can_manage_workers": True},
            format="json",
        )

        local_permission.refresh_from_db()
        self.assertIn(response.status_code, {400, 403, 404})
        self.assertEqual(local_permission.user_id, self.target.id)
        self.assertEqual(local_permission.tenant_id, self.tenant.id)
        self.assertEqual(local_permission.property_id, self.property.id)
        self.assertFalse(local_permission.can_manage_workers)
        self.assertFalse(
            UserPropertyPermission.objects.filter(user=foreign_user, tenant=self.tenant).exists()
        )


class ResultingAuthorizationUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Tenant autorizado", slug="tenant-autorizado")
        self.property = Property.objects.create(tenant=self.tenant, name="Sede autorizada", slug="sede-autorizada")
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Area autorizada")
        self.admin = User.objects.create_user(email="result-admin@pariwana.test", password="StrongPass123")
        self.target = User.objects.create_user(email="result-target@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=self.admin, tenant=self.tenant, role=RoleChoices.ADMIN)
        self.target_role = UserTenantRole.objects.create(
            user=self.target,
            tenant=self.tenant,
            role=RoleChoices.OPERATOR,
        )
        self.area_permission = UserAreaPermission.objects.create(
            user=self.target,
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            can_view=True,
            can_schedule=False,
        )
        ModuleActivation.objects.create(tenant=self.tenant, module_key="users_permissions", is_enabled=True)

        self.foreign_tenant = Tenant.objects.create(name="Tenant externo", slug="tenant-externo-result")
        self.foreign_property = Property.objects.create(
            tenant=self.foreign_tenant,
            name="Sede externa",
            slug="sede-externa-result",
        )
        self.foreign_area = Area.objects.create(
            tenant=self.foreign_tenant,
            property=self.foreign_property,
            name="Area externa",
        )
        self.foreign_user = User.objects.create_user(email="result-foreign@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(
            user=self.foreign_user,
            tenant=self.foreign_tenant,
            role=RoleChoices.OPERATOR,
        )
        self.client.force_authenticate(user=self.admin)

    def _assert_role_unchanged(self):
        self.target_role.refresh_from_db()
        self.assertEqual(self.target_role.user_id, self.target.id)
        self.assertEqual(self.target_role.tenant_id, self.tenant.id)
        self.assertEqual(self.target_role.role, RoleChoices.OPERATOR)

    def _assert_area_permission_unchanged(self):
        self.area_permission.refresh_from_db()
        self.assertEqual(self.area_permission.user_id, self.target.id)
        self.assertEqual(self.area_permission.tenant_id, self.tenant.id)
        self.assertEqual(self.area_permission.property_id, self.property.id)
        self.assertEqual(self.area_permission.area_id, self.area.id)
        self.assertFalse(self.area_permission.can_schedule)

    def test_user_tenant_role_patch_rejects_unauthorized_resulting_tenant(self):
        response = self.client.patch(
            f"/api/user-tenant-roles/{self.target_role.id}/?tenant_id={self.tenant.id}",
            {"tenant": self.foreign_tenant.id, "role": RoleChoices.ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self._assert_role_unchanged()

    def test_user_tenant_role_put_rejects_unauthorized_resulting_tenant(self):
        response = self.client.put(
            f"/api/user-tenant-roles/{self.target_role.id}/?tenant_id={self.tenant.id}",
            {"user": self.target.id, "tenant": self.foreign_tenant.id, "role": RoleChoices.ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self._assert_role_unchanged()

    def test_user_tenant_role_patch_rejects_external_resulting_user(self):
        response = self.client.patch(
            f"/api/user-tenant-roles/{self.target_role.id}/?tenant_id={self.tenant.id}",
            {"user": self.foreign_user.id, "role": RoleChoices.ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self._assert_role_unchanged()

    def test_user_tenant_role_put_rejects_external_resulting_user(self):
        response = self.client.put(
            f"/api/user-tenant-roles/{self.target_role.id}/?tenant_id={self.tenant.id}",
            {"user": self.foreign_user.id, "tenant": self.tenant.id, "role": RoleChoices.ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self._assert_role_unchanged()

    def test_user_tenant_role_admin_can_patch_within_authorized_tenant(self):
        response = self.client.patch(
            f"/api/user-tenant-roles/{self.target_role.id}/?tenant_id={self.tenant.id}",
            {"role": RoleChoices.SUPERVISOR},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.target_role.refresh_from_db()
        self.assertEqual(self.target_role.role, RoleChoices.SUPERVISOR)

    def test_user_tenant_role_super_admin_can_put_across_tenants(self):
        super_admin = User.objects.create_user(
            email="result-super@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        self.client.force_authenticate(user=super_admin)
        response = self.client.put(
            f"/api/user-tenant-roles/{self.target_role.id}/?tenant_id={self.tenant.id}",
            {"user": self.target.id, "tenant": self.foreign_tenant.id, "role": RoleChoices.ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.target_role.refresh_from_db()
        self.assertEqual(self.target_role.tenant_id, self.foreign_tenant.id)
        self.assertEqual(self.target_role.role, RoleChoices.ADMIN)

    def test_user_area_permission_patch_rejects_unauthorized_resulting_tenant(self):
        response = self.client.patch(
            f"/api/user-area-permissions/{self.area_permission.id}/?tenant_id={self.tenant.id}",
            {
                "tenant": self.foreign_tenant.id,
                "property": self.foreign_property.id,
                "area": self.foreign_area.id,
                "user": self.foreign_user.id,
                "can_schedule": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self._assert_area_permission_unchanged()

    def test_user_area_permission_put_rejects_unauthorized_resulting_tenant(self):
        response = self.client.put(
            f"/api/user-area-permissions/{self.area_permission.id}/?tenant_id={self.tenant.id}",
            {
                "user": self.foreign_user.id,
                "tenant": self.foreign_tenant.id,
                "property": self.foreign_property.id,
                "area": self.foreign_area.id,
                "can_view": True,
                "can_schedule": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self._assert_area_permission_unchanged()

    def test_user_area_permission_patch_rejects_external_resulting_user(self):
        response = self.client.patch(
            f"/api/user-area-permissions/{self.area_permission.id}/?tenant_id={self.tenant.id}",
            {"user": self.foreign_user.id, "can_schedule": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self._assert_area_permission_unchanged()

    def test_user_area_permission_patch_rejects_incoherent_property_and_area(self):
        response = self.client.patch(
            f"/api/user-area-permissions/{self.area_permission.id}/?tenant_id={self.tenant.id}",
            {"property": self.foreign_property.id, "area": self.foreign_area.id, "can_schedule": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self._assert_area_permission_unchanged()

    def test_user_area_permission_put_rejects_external_property_and_area(self):
        response = self.client.put(
            f"/api/user-area-permissions/{self.area_permission.id}/?tenant_id={self.tenant.id}",
            {
                "user": self.target.id,
                "tenant": self.tenant.id,
                "property": self.foreign_property.id,
                "area": self.foreign_area.id,
                "can_view": True,
                "can_schedule": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self._assert_area_permission_unchanged()

    def test_user_area_permission_admin_can_patch_within_authorized_tenant(self):
        response = self.client.patch(
            f"/api/user-area-permissions/{self.area_permission.id}/?tenant_id={self.tenant.id}",
            {"can_schedule": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.area_permission.refresh_from_db()
        self.assertTrue(self.area_permission.can_schedule)

    def test_user_area_permission_super_admin_can_put_across_tenants(self):
        super_admin = User.objects.create_user(
            email="area-result-super@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        self.client.force_authenticate(user=super_admin)
        response = self.client.put(
            f"/api/user-area-permissions/{self.area_permission.id}/?tenant_id={self.tenant.id}",
            {
                "user": self.foreign_user.id,
                "tenant": self.foreign_tenant.id,
                "property": self.foreign_property.id,
                "area": self.foreign_area.id,
                "can_view": True,
                "can_schedule": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.area_permission.refresh_from_db()
        self.assertEqual(self.area_permission.tenant_id, self.foreign_tenant.id)
        self.assertEqual(self.area_permission.user_id, self.foreign_user.id)
        self.assertEqual(self.area_permission.property_id, self.foreign_property.id)
        self.assertEqual(self.area_permission.area_id, self.foreign_area.id)
        self.assertTrue(self.area_permission.can_schedule)


class CriticalUserPrivilegeEscalationRegressionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Tenant API", slug="tenant-api")
        self.property = Property.objects.create(tenant=self.tenant, name="Sede API", slug="sede-api")
        self.admin = User.objects.create_user(email="tenant-admin@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=self.admin, tenant=self.tenant, role=RoleChoices.ADMIN)
        ModuleActivation.objects.create(tenant=self.tenant, module_key="users_permissions", is_enabled=True)
        self.client.force_authenticate(user=self.admin)

    def test_tenant_admin_cannot_create_super_admin_or_staff_user_via_api(self):
        response = self.client.post(
            f"/api/users/?tenant_id={self.tenant.id}",
            {
                "email": "escalated-create@pariwana.test",
                "password": "StrongPass123",
                "is_super_admin": True,
                "is_staff": True,
            },
            format="json",
        )

        created = User.objects.filter(email="escalated-create@pariwana.test").first()
        if created is None:
            self.assertIn(response.status_code, {400, 403})
        else:
            self.assertFalse(created.is_super_admin)
            self.assertFalse(created.is_staff)

    def test_tenant_admin_cannot_promote_existing_user_to_super_admin_or_staff_via_api(self):
        target = User.objects.create_user(email="escalated-update@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=target, tenant=self.tenant, role=RoleChoices.OPERATOR)

        response = self.client.patch(
            f"/api/users/{target.id}/?tenant_id={self.tenant.id}",
            {"is_super_admin": True, "is_staff": True},
            format="json",
        )

        target.refresh_from_db()
        self.assertIn(response.status_code, {200, 400, 403})
        self.assertFalse(target.is_super_admin)
        self.assertFalse(target.is_staff)
        self.assertTrue(UserTenantRole.objects.filter(user=target, tenant=self.tenant).exists())


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
