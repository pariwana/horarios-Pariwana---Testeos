from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.modules.models import ModuleActivation
from apps.scheduling.models import ScheduleAssignment
from apps.tenants.models import Property, Tenant, TenantSupportAccessSession
from apps.users.models import RoleChoices, User, UserAreaPermission, UserPropertyPermission, UserTenantRole
from apps.workers.models import Area, Shift, SpecialState, Worker


class SchedulingRulesTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepción")
        self.worker = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="12345678",
            first_name="A",
            last_name="B",
            area=self.area,
        )
        self.shift = Shift.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Mañana",
            buk_code="REC-M",
            start_time=time(6, 0),
            end_time=time(14, 45),
        )
        self.special = SpecialState.objects.create(
            tenant=self.tenant,
            property=self.property,
            name="OFF",
            buk_code="D",
        )

    def test_assignment_must_have_shift_or_state(self):
        assignment = ScheduleAssignment(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker,
            date=date(2026, 4, 2),
        )
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_assignment_cannot_have_shift_and_state(self):
        assignment = ScheduleAssignment(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker,
            date=date(2026, 4, 2),
            shift=self.shift,
            special_state=self.special,
        )
        with self.assertRaises(ValidationError):
            assignment.full_clean()


class ControlModuleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="admin@pariwana.test", password="StrongPass123")
        self.client.force_authenticate(user=self.user)
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        UserTenantRole.objects.create(user=self.user, tenant=self.tenant, role=RoleChoices.OPERATOR)
        UserPropertyPermission.objects.create(
            user=self.user,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_schedule=True,
        )
        ModuleActivation.objects.create(tenant=self.tenant, module_key="control", is_enabled=True)
        ModuleActivation.objects.create(tenant=self.tenant, module_key="scheduling", is_enabled=True)
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepción")
        self.worker = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="99999999",
            first_name="Pendiente",
            last_name="SinTurno",
            area=self.area,
            active=True,
        )

    def test_control_next_15_days_detects_pending_workers(self):
        response = self.client.get(
            f"/api/assignments/control-next-15-days/?tenant_id={self.tenant.id}&property_id={self.property.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["properties"]), 1)
        self.assertEqual(data["properties"][0]["pending_count"], 15)


class ControlModuleSupportContextTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.super_admin = User.objects.create_user(
            email="super-control@pariwana.test",
            password="StrongPass123",
            is_super_admin=True,
            is_staff=True,
        )
        ModuleActivation.objects.create(tenant=self.tenant, module_key="control", is_enabled=True)
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepcion")
        Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="78787878",
            first_name="Sin",
            last_name="Cobertura",
            area=self.area,
            active=True,
        )
        self.support_session = TenantSupportAccessSession.objects.create(
            tenant=self.tenant,
            property=self.property,
            started_by=self.super_admin,
            reason="support control module",
        )
        self.client.force_authenticate(user=self.super_admin)

    def test_control_next_15_days_with_support_session_without_tenant_id(self):
        response = self.client.get(
            "/api/assignments/control-next-15-days/",
            HTTP_X_SUPPORT_SESSION_ID=str(self.support_session.id),
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        data = response.json()
        self.assertEqual(len(data["properties"]), 1)
        self.assertEqual(data["properties"][0]["pending_count"], 15)


class SupervisorAreaRestrictionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.area_allowed = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepcion")
        self.area_blocked = Area.objects.create(tenant=self.tenant, property=self.property, name="Bar")
        self.worker_blocked = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="88888888",
            first_name="Bloq",
            last_name="Area",
            area=self.area_blocked,
            active=True,
        )
        self.shift_blocked = Shift.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area_blocked,
            name="Bar-M",
            buk_code="BAR-M",
            start_time=time(8, 0),
            end_time=time(16, 0),
        )
        self.supervisor = User.objects.create_user(email="sup@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=self.supervisor, tenant=self.tenant, role=RoleChoices.SUPERVISOR)
        UserPropertyPermission.objects.create(
            user=self.supervisor,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_schedule=True,
        )
        UserAreaPermission.objects.create(
            user=self.supervisor,
            tenant=self.tenant,
            property=self.property,
            area=self.area_allowed,
            can_view=True,
            can_schedule=True,
        )
        ModuleActivation.objects.create(tenant=self.tenant, module_key="scheduling", is_enabled=True)
        self.client.force_authenticate(user=self.supervisor)

    def test_supervisor_cannot_assign_in_unpermitted_area(self):
        response = self.client.post(
            "/api/assignments/",
            {
                "tenant": self.tenant.id,
                "property": self.property.id,
                "worker": self.worker_blocked.id,
                "date": "2026-04-03",
                "shift": self.shift_blocked.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
