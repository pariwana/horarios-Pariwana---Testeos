from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.modules.models import ModuleActivation
from apps.scheduling.models import ScheduleAssignment
from apps.audit.models import AuditLog
from apps.tenants.models import Property, Tenant, TenantStatus, TenantSupportAccessSession
from apps.users.models import RoleChoices, User, UserTenantRole
from apps.workers.models import Area, Shift, SpecialState, Worker


class TenantModelTests(TestCase):
    def test_create_tenant_and_properties(self):
        tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels", status=TenantStatus.ACTIVE)
        lima = Property.objects.create(tenant=tenant, name="Pariwana Lima", slug="pariwana-lima")
        cusco = Property.objects.create(tenant=tenant, name="Pariwana Cusco", slug="pariwana-cusco")

        self.assertEqual(tenant.properties.count(), 2)
        self.assertEqual(lima.tenant_id, tenant.id)
        self.assertEqual(cusco.tenant_id, tenant.id)


class TenantSupportAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.other_tenant = Tenant.objects.create(name="Otro Tenant", slug="otro-tenant")
        self.other_property = Property.objects.create(
            tenant=self.other_tenant,
            name="Otra Sede",
            slug="otra-sede",
        )
        self.super_admin = User.objects.create_user(
            email="super@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        self.other_super_admin = User.objects.create_user(
            email="super2@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        self.admin = User.objects.create_user(email="admin@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=self.admin, tenant=self.tenant, role=RoleChoices.ADMIN)
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepcion", type="operativa")
        self.worker = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            document_number="12345678",
            first_name="Ana",
            last_name="Rojas",
            active=True,
        )
        self.other_area = Area.objects.create(
            tenant=self.other_tenant,
            property=self.other_property,
            name="Bar",
            type="operativa",
        )
        self.other_worker = Worker.objects.create(
            tenant=self.other_tenant,
            property=self.other_property,
            area=self.other_area,
            document_number="87654321",
            first_name="Jose",
            last_name="Suarez",
            active=True,
        )

    def test_super_admin_can_start_and_stop_support_with_audit(self):
        self.client.force_authenticate(user=self.super_admin)
        start_response = self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/start/",
            {"property_id": self.property.id, "reason": "debug export issue"},
            format="json",
        )
        self.assertEqual(start_response.status_code, 201)
        session_id = start_response.json()["id"]

        stop_response = self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/stop/",
            {"session_id": session_id, "reason": "resolved"},
            format="json",
        )
        self.assertEqual(stop_response.status_code, 200)

        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                action="support_access_start",
                entity_type="TenantSupportAccessSession",
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                action="support_access_stop",
                entity_type="TenantSupportAccessSession",
            ).exists()
        )

    def test_non_super_admin_cannot_start_support(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/start/",
            {"property_id": self.property.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_support_session_header_allows_context_without_tenant_id(self):
        self.client.force_authenticate(user=self.super_admin)
        start_response = self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/start/",
            {"property_id": self.property.id, "reason": "cross-check workers"},
            format="json",
        )
        self.assertEqual(start_response.status_code, 201)
        session_id = start_response.json()["id"]

        list_response = self.client.get(
            "/api/workers/",
            HTTP_X_SUPPORT_SESSION_ID=str(session_id),
        )
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], self.worker.id)

    def test_missing_context_without_support_header_returns_400(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get("/api/workers/")
        self.assertEqual(response.status_code, 400)

    def test_support_session_cannot_be_used_by_another_super_admin(self):
        self.client.force_authenticate(user=self.super_admin)
        start_response = self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/start/",
            {"property_id": self.property.id},
            format="json",
        )
        self.assertEqual(start_response.status_code, 201)
        session_id = start_response.json()["id"]

        self.client.force_authenticate(user=self.other_super_admin)
        response = self.client.get(
            "/api/workers/",
            HTTP_X_SUPPORT_SESSION_ID=str(session_id),
        )
        self.assertEqual(response.status_code, 403)

    def test_support_session_scopes_super_admin_to_tenant_and_property(self):
        self.client.force_authenticate(user=self.super_admin)
        start_response = self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/start/",
            {"property_id": self.property.id, "reason": "scoped support"},
            format="json",
        )
        self.assertEqual(start_response.status_code, 201)
        session_id = start_response.json()["id"]

        response = self.client.get(
            f"/api/workers/?tenant_id={self.other_tenant.id}&property_id={self.other_property.id}",
            HTTP_X_SUPPORT_SESSION_ID=str(session_id),
        )
        self.assertEqual(response.status_code, 403)

    def test_active_support_access_returns_only_my_active_sessions(self):
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/start/",
            {"property_id": self.property.id, "reason": "t1"},
            format="json",
        )
        self.client.post(
            f"/api/tenants/{self.other_tenant.id}/support-access/start/",
            {"property_id": self.other_property.id, "reason": "t2"},
            format="json",
        )

        self.client.force_authenticate(user=self.other_super_admin)
        self.client.post(
            f"/api/tenants/{self.other_tenant.id}/support-access/start/",
            {"property_id": self.other_property.id, "reason": "other-admin"},
            format="json",
        )

        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get("/api/tenants/support-access/active/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["active_count"], 2)
        self.assertEqual(len(data["sessions"]), 2)

    def test_stop_all_support_access_closes_only_my_sessions(self):
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/start/",
            {"property_id": self.property.id, "reason": "t1"},
            format="json",
        )
        self.client.post(
            f"/api/tenants/{self.other_tenant.id}/support-access/start/",
            {"property_id": self.other_property.id, "reason": "t2"},
            format="json",
        )

        self.client.force_authenticate(user=self.other_super_admin)
        self.client.post(
            f"/api/tenants/{self.other_tenant.id}/support-access/start/",
            {"property_id": self.other_property.id, "reason": "other-admin"},
            format="json",
        )

        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(
            "/api/tenants/support-access/stop-all/",
            {"reason": "finish"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["closed_count"], 2)
        self.assertEqual(
            TenantSupportAccessSession.objects.filter(
                started_by=self.super_admin,
                ended_at__isnull=True,
            ).count(),
            0,
        )
        self.assertEqual(
            TenantSupportAccessSession.objects.filter(
                started_by=self.other_super_admin,
                ended_at__isnull=True,
            ).count(),
            1,
        )

    def test_tenants_and_properties_list_are_scoped_by_support_session(self):
        self.client.force_authenticate(user=self.super_admin)
        start_response = self.client.post(
            f"/api/tenants/{self.tenant.id}/support-access/start/",
            {"property_id": self.property.id, "reason": "scoped list"},
            format="json",
        )
        self.assertEqual(start_response.status_code, 201)
        session_id = start_response.json()["id"]

        tenants_response = self.client.get(
            "/api/tenants/",
            HTTP_X_SUPPORT_SESSION_ID=str(session_id),
        )
        self.assertEqual(tenants_response.status_code, 200)
        tenants_payload = tenants_response.json()
        self.assertEqual(len(tenants_payload), 1)
        self.assertEqual(tenants_payload[0]["id"], self.tenant.id)

        properties_response = self.client.get(
            "/api/properties/",
            HTTP_X_SUPPORT_SESSION_ID=str(session_id),
        )
        self.assertEqual(properties_response.status_code, 200)
        properties_payload = properties_response.json()
        self.assertEqual(len(properties_payload), 1)
        self.assertEqual(properties_payload[0]["id"], self.property.id)


class SeedDemoCuscoDataCommandTests(TestCase):
    def test_seed_demo_cusco_data_creates_operational_dataset(self):
        call_command("seed_demo_cusco_data", days=7)

        tenant = Tenant.objects.get(slug="pariwana-hostels")
        cusco = Property.objects.get(tenant=tenant, slug="pariwana-cusco")
        lima = Property.objects.get(tenant=tenant, slug="pariwana-lima")

        self.assertEqual(cusco.name, "Pariwana Cusco")
        self.assertEqual(lima.name, "Pariwana Lima")
        self.assertTrue(ModuleActivation.objects.filter(tenant=tenant, module_key="scheduling", is_enabled=True).exists())
        self.assertTrue(Area.objects.filter(tenant=tenant, property=cusco, name="Recepción").exists())
        self.assertTrue(Shift.objects.filter(tenant=tenant, property=cusco, buk_code="REC-M").exists())
        self.assertTrue(SpecialState.objects.filter(tenant=tenant, property=cusco, name="OFF").exists())
        self.assertTrue(Worker.objects.filter(tenant=tenant, property=cusco, document_number="70100101").exists())
        self.assertGreaterEqual(
            ScheduleAssignment.objects.filter(tenant=tenant, property=cusco).count(),
            12 * 7,
        )

    def test_seed_demo_cusco_data_is_idempotent(self):
        call_command("seed_demo_cusco_data", days=3)
        call_command("seed_demo_cusco_data", days=3)

        tenant = Tenant.objects.get(slug="pariwana-hostels")
        cusco = Property.objects.get(tenant=tenant, slug="pariwana-cusco")
        self.assertEqual(Worker.objects.filter(tenant=tenant, property=cusco).count(), 12)
        self.assertEqual(Shift.objects.filter(tenant=tenant, property=cusco).count(), 8)
        self.assertEqual(SpecialState.objects.filter(tenant=tenant, property=cusco).count(), 3)

    def test_seed_demo_cusco_data_handles_existing_shift_name_with_other_code(self):
        tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        cusco = Property.objects.create(tenant=tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        area = Area.objects.create(tenant=tenant, property=cusco, name="Recepción")
        Shift.objects.create(
            tenant=tenant,
            property=cusco,
            area=area,
            name="Recepción_Manana",
            buk_code="LEGACY-REC-M",
            start_time="07:00",
            end_time="15:00",
            is_night_shift=False,
            active=True,
        )

        call_command("seed_demo_cusco_data", days=2)
        self.assertTrue(
            Shift.objects.filter(
                tenant=tenant,
                property=cusco,
                name="Recepción_Manana",
            ).exists()
        )


class BootstrapLocalDemoCommandTests(TestCase):
    def test_bootstrap_local_demo_creates_full_minimum_dataset(self):
        call_command(
            "bootstrap_local_demo",
            password="StrongPass123",
            days=5,
            supervisor_areas="Recepción,Housekeeping",
        )

        tenant = Tenant.objects.get(slug="pariwana-hostels")
        cusco = Property.objects.get(tenant=tenant, slug="pariwana-cusco")
        lima = Property.objects.get(tenant=tenant, slug="pariwana-lima")
        self.assertEqual(cusco.name, "Pariwana Cusco")
        self.assertEqual(lima.name, "Pariwana Lima")
        self.assertGreaterEqual(Area.objects.filter(tenant=tenant, property=cusco).count(), 4)
        self.assertGreaterEqual(Worker.objects.filter(tenant=tenant, property=cusco).count(), 10)
        self.assertGreaterEqual(ScheduleAssignment.objects.filter(tenant=tenant, property=cusco).count(), 50)
        self.assertTrue(User.objects.filter(email="admin.demo@pariwana.local").exists())
        self.assertTrue(User.objects.filter(email="operador.demo@pariwana.local").exists())
        self.assertTrue(User.objects.filter(email="supervisor.demo@pariwana.local").exists())

    def test_bootstrap_local_demo_rejects_invalid_days(self):
        with self.assertRaises(CommandError):
            call_command("bootstrap_local_demo", password="StrongPass123", days=0)
