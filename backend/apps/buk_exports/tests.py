from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from apps.modules.models import ModuleActivation
from apps.tenants.models import Property, Tenant, TenantSupportAccessSession
from apps.users.models import RoleChoices, User, UserPropertyPermission, UserTenantRole
from apps.workers.models import Area, Shift, Worker
from apps.scheduling.models import ScheduleAssignment


class BukExportApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="op@pariwana.test", password="StrongPass123")
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepción")
        self.shift = Shift.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Mañana",
            buk_code="REC-M",
            start_time=time(6, 0),
            end_time=time(14, 45),
        )
        worker = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="12345678",
            first_name="Ana",
            last_name="Quispe",
            area=self.area,
        )
        ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=worker,
            date=date(2026, 4, 2),
            shift=self.shift,
        )
        UserTenantRole.objects.create(user=self.user, tenant=self.tenant, role=RoleChoices.OPERATOR)
        UserPropertyPermission.objects.create(
            user=self.user,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_export_buk=True,
        )
        ModuleActivation.objects.create(tenant=self.tenant, module_key="buk_export", is_enabled=False)
        ModuleActivation.objects.create(tenant=self.tenant, module_key="buk_preview", is_enabled=True)
        ModuleActivation.objects.create(tenant=self.tenant, module_key="buk_validator", is_enabled=True)
        self.client.force_authenticate(user=self.user)

    def test_export_denies_when_module_disabled(self):
        response = self.client.post(
            "/api/buk/export/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "date_from": "2026-04-02",
                "date_to": "2026-04-02",
                "format": "xlsx",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class BukExportSupportContextTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.super_admin = User.objects.create_user(
            email="super-buk@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepcion")
        self.shift = Shift.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Manana",
            buk_code="REC-M",
            start_time=time(6, 0),
            end_time=time(14, 45),
        )
        worker = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="88888888",
            first_name="Luis",
            last_name="Rojas",
            area=self.area,
        )
        ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=worker,
            date=date(2026, 4, 5),
            shift=self.shift,
        )
        ModuleActivation.objects.create(tenant=self.tenant, module_key="buk_preview", is_enabled=True)
        self.support_session = TenantSupportAccessSession.objects.create(
            tenant=self.tenant,
            property=self.property,
            started_by=self.super_admin,
            reason="support buk preview",
        )
        self.client.force_authenticate(user=self.super_admin)

    def test_preview_works_with_support_session_without_tenant_id(self):
        response = self.client.post(
            "/api/buk/preview/",
            {
                "property_id": self.property.id,
                "date_from": "2026-04-05",
                "date_to": "2026-04-05",
            },
            format="json",
            HTTP_X_SUPPORT_SESSION_ID=str(self.support_session.id),
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertIn("rows", response.json())
