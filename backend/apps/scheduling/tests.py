from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.month_closure.models import MonthClosure, MonthClosureStatus
from apps.modules.models import ModuleActivation
from apps.scheduling.models import ScheduleAssignment, SchedulePatternTemplate
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
        self.worker_allowed = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="77777777",
            first_name="Permitido",
            last_name="Area",
            area=self.area_allowed,
            active=True,
        )
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
        self.shift_allowed = Shift.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area_allowed,
            name="Recepcion-M",
            buk_code="REC-M",
            start_time=time(8, 0),
            end_time=time(16, 0),
        )
        self.assignment_allowed = ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker_allowed,
            date=date(2026, 4, 4),
            shift=self.shift_allowed,
        )
        self.assignment_blocked = ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker_blocked,
            date=date(2026, 4, 4),
            shift=self.shift_blocked,
        )
        self.foreign_tenant = Tenant.objects.create(name="Tenant externo", slug="tenant-externo")
        self.foreign_property = Property.objects.create(
            tenant=self.foreign_tenant,
            name="Sede externa",
            slug="sede-externa",
        )
        self.foreign_area = Area.objects.create(
            tenant=self.foreign_tenant,
            property=self.foreign_property,
            name="Area externa",
        )
        self.foreign_worker = Worker.objects.create(
            tenant=self.foreign_tenant,
            property=self.foreign_property,
            document_number="99999999",
            first_name="Trabajador",
            last_name="Externo",
            area=self.foreign_area,
            active=True,
        )
        self.foreign_shift = Shift.objects.create(
            tenant=self.foreign_tenant,
            property=self.foreign_property,
            area=self.foreign_area,
            name="Externo-M",
            buk_code="EXT-M",
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
            can_manage_workers=True,
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
        ModuleActivation.objects.create(tenant=self.tenant, module_key="workers", is_enabled=True)
        self.client.force_authenticate(user=self.supervisor)

    def test_supervisor_worker_list_only_contains_permitted_area(self):
        response = self.client.get(
            f"/api/workers/?tenant_id={self.tenant.id}&property_id={self.property.id}"
        )

        self.assertEqual(response.status_code, 200, msg=response.content)
        rows = response.json()
        self.assertEqual({row["id"] for row in rows}, {self.worker_allowed.id})
        self.assertTrue(all(row["tenant"] == self.tenant.id for row in rows))
        self.assertTrue(all(row["property"] == self.property.id for row in rows))
        self.assertTrue(all(row["area"] == self.area_allowed.id for row in rows))

    def test_supervisor_assignment_list_only_contains_permitted_area(self):
        response = self.client.get(
            f"/api/assignments/?tenant_id={self.tenant.id}&property_id={self.property.id}"
        )

        self.assertEqual(response.status_code, 200, msg=response.content)
        rows = response.json()
        self.assertEqual({row["id"] for row in rows}, {self.assignment_allowed.id})
        self.assertTrue(all(row["tenant"] == self.tenant.id for row in rows))
        self.assertTrue(all(row["property"] == self.property.id for row in rows))
        self.assertTrue(all(row["worker"] == self.worker_allowed.id for row in rows))

    def test_supervisor_cannot_modify_worker_in_unpermitted_area_by_direct_endpoint(self):
        response = self.client.patch(
            f"/api/workers/{self.worker_blocked.id}/?tenant_id={self.tenant.id}&property_id={self.property.id}",
            {"first_name": "Alterado"},
            format="json",
        )

        self.worker_blocked.refresh_from_db()
        self.assertIn(response.status_code, {403, 404})
        self.assertEqual(self.worker_blocked.first_name, "Bloq")
        self.assertEqual(self.worker_blocked.area_id, self.area_blocked.id)
        self.assertEqual(self.worker_blocked.tenant_id, self.tenant.id)
        self.assertEqual(self.worker_blocked.property_id, self.property.id)

    def test_supervisor_cannot_modify_assignment_in_unpermitted_area_by_direct_endpoint(self):
        response = self.client.patch(
            f"/api/assignments/{self.assignment_blocked.id}/?tenant_id={self.tenant.id}&property_id={self.property.id}",
            {"date": "2026-04-05"},
            format="json",
        )

        self.assignment_blocked.refresh_from_db()
        self.assertIn(response.status_code, {403, 404})
        self.assertEqual(self.assignment_blocked.date, date(2026, 4, 4))
        self.assertEqual(self.assignment_blocked.worker_id, self.worker_blocked.id)
        self.assertEqual(self.assignment_blocked.tenant_id, self.tenant.id)
        self.assertEqual(self.assignment_blocked.property_id, self.property.id)

    def test_worker_update_cannot_move_record_to_unauthorized_tenant_property_and_area(self):
        response = self.client.patch(
            f"/api/workers/{self.worker_allowed.id}/?tenant_id={self.tenant.id}&property_id={self.property.id}",
            {
                "tenant": self.foreign_tenant.id,
                "property": self.foreign_property.id,
                "area": self.foreign_area.id,
            },
            format="json",
        )

        self.worker_allowed.refresh_from_db()
        self.assertIn(response.status_code, {400, 403, 404})
        self.assertEqual(self.worker_allowed.tenant_id, self.tenant.id)
        self.assertEqual(self.worker_allowed.property_id, self.property.id)
        self.assertEqual(self.worker_allowed.area_id, self.area_allowed.id)

    def test_worker_update_cannot_move_record_to_unpermitted_area(self):
        response = self.client.patch(
            f"/api/workers/{self.worker_allowed.id}/?tenant_id={self.tenant.id}&property_id={self.property.id}",
            {"area": self.area_blocked.id},
            format="json",
        )

        self.worker_allowed.refresh_from_db()
        self.assertIn(response.status_code, {400, 403, 404})
        self.assertEqual(self.worker_allowed.tenant_id, self.tenant.id)
        self.assertEqual(self.worker_allowed.property_id, self.property.id)
        self.assertEqual(self.worker_allowed.area_id, self.area_allowed.id)

    def test_assignment_update_cannot_move_record_to_unauthorized_tenant_property_and_area(self):
        response = self.client.patch(
            f"/api/assignments/{self.assignment_allowed.id}/?tenant_id={self.tenant.id}&property_id={self.property.id}",
            {
                "tenant": self.foreign_tenant.id,
                "property": self.foreign_property.id,
                "worker": self.foreign_worker.id,
                "shift": self.foreign_shift.id,
            },
            format="json",
        )

        self.assignment_allowed.refresh_from_db()
        self.assertIn(response.status_code, {400, 403, 404})
        self.assertEqual(self.assignment_allowed.tenant_id, self.tenant.id)
        self.assertEqual(self.assignment_allowed.property_id, self.property.id)
        self.assertEqual(self.assignment_allowed.worker_id, self.worker_allowed.id)
        self.assertEqual(self.assignment_allowed.shift_id, self.shift_allowed.id)

    def test_assignment_update_cannot_move_record_to_unpermitted_area(self):
        response = self.client.patch(
            f"/api/assignments/{self.assignment_allowed.id}/?tenant_id={self.tenant.id}&property_id={self.property.id}",
            {
                "worker": self.worker_blocked.id,
                "shift": self.shift_blocked.id,
                "date": "2026-04-05",
            },
            format="json",
        )

        self.assignment_allowed.refresh_from_db()
        self.assertIn(response.status_code, {400, 403, 404})
        self.assertEqual(self.assignment_allowed.tenant_id, self.tenant.id)
        self.assertEqual(self.assignment_allowed.property_id, self.property.id)
        self.assertEqual(self.assignment_allowed.worker_id, self.worker_allowed.id)
        self.assertEqual(self.assignment_allowed.shift_id, self.shift_allowed.id)
        self.assertEqual(self.assignment_allowed.date, date(2026, 4, 4))

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


class SchedulingBulkActionsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepcion")
        self.worker = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            document_number="10101010",
            first_name="Ana",
            last_name="Rojas",
            active=True,
        )
        self.shift = Shift.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Manana",
            buk_code="REC-M",
            start_time=time(6, 0),
            end_time=time(14, 45),
        )
        self.state = SpecialState.objects.create(
            tenant=self.tenant,
            property=self.property,
            name="OFF",
            buk_code="OFF",
        )
        self.user = User.objects.create_user(email="bulk-api@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=self.user, tenant=self.tenant, role=RoleChoices.ADMIN)
        UserPropertyPermission.objects.create(
            user=self.user,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_schedule=True,
        )
        ModuleActivation.objects.create(tenant=self.tenant, module_key="scheduling", is_enabled=True)
        self.client.force_authenticate(user=self.user)

    def test_bulk_range_state_creates_assignments_and_audit(self):
        response = self.client.post(
            "/api/assignments/bulk-range-state/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "date_from": "2026-06-10",
                "date_to": "2026-06-12",
                "special_state_id": self.state.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["applied"], 3)
        self.assertEqual(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                special_state=self.state,
                date__gte="2026-06-10",
                date__lte="2026-06-12",
            ).count(),
            3,
        )
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                property=self.property,
                user=self.user,
                action="scheduling_bulk_range_state_apply",
            ).exists()
        )

    def test_bulk_sundays_state_creates_assignments(self):
        response = self.client.post(
            "/api/assignments/bulk-sundays-state/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "year": 2026,
                "month": 6,
                "special_state_id": self.state.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["sundays"], 4)
        self.assertEqual(response.json()["applied"], 4)
        self.assertEqual(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                special_state=self.state,
            ).count(),
            4,
        )

    def test_bulk_sundays_state_dry_run_returns_impact_without_writes(self):
        response = self.client.post(
            "/api/assignments/bulk-sundays-state/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "year": 2026,
                "month": 6,
                "special_state_id": self.state.id,
                "dry_run": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        payload = response.json()
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["sundays"], 4)
        self.assertEqual(payload["applied"], 4)
        self.assertEqual(payload["impact"]["total"], 4)
        self.assertEqual(payload["impact"]["to_create"], 4)
        self.assertEqual(payload["impact"]["to_update"], 0)
        self.assertEqual(payload["impact"]["unchanged"], 0)
        self.assertEqual(ScheduleAssignment.objects.count(), 0)

    def test_copy_week_copies_assignments(self):
        ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker,
            date="2026-06-01",
            shift=self.shift,
        )
        ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker,
            date="2026-06-03",
            special_state=self.state,
        )
        response = self.client.post(
            "/api/assignments/copy-week/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "source_week_start": "2026-06-01",
                "target_week_start": "2026-06-08",
                "copy_kind": "all",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["copied"], 2)
        self.assertTrue(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                date="2026-06-08",
                shift=self.shift,
            ).exists()
        )
        self.assertTrue(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                date="2026-06-10",
                special_state=self.state,
            ).exists()
        )

    def test_copy_previous_month_copies_assignments(self):
        ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker,
            date="2026-05-05",
            shift=self.shift,
        )
        response = self.client.post(
            "/api/assignments/copy-previous-month/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "target_year": 2026,
                "target_month": 6,
                "copy_kind": "all",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["copied"], 1)
        self.assertTrue(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                date="2026-06-05",
                shift=self.shift,
            ).exists()
        )

    def test_bulk_range_state_blocked_when_month_closed(self):
        MonthClosure.objects.create(
            tenant=self.tenant,
            property=self.property,
            year=2026,
            month=6,
            status=MonthClosureStatus.CLOSED,
        )
        response = self.client.post(
            "/api/assignments/bulk-range-state/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "date_from": "2026-06-10",
                "date_to": "2026-06-12",
                "special_state_id": self.state.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertFalse(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                date__gte="2026-06-10",
                date__lte="2026-06-12",
            ).exists()
        )

    def test_bulk_range_state_dry_run_returns_impact_without_writes(self):
        response = self.client.post(
            "/api/assignments/bulk-range-state/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "date_from": "2026-06-10",
                "date_to": "2026-06-12",
                "special_state_id": self.state.id,
                "dry_run": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        payload = response.json()
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["impact"]["total"], 3)
        self.assertEqual(payload["impact"]["to_create"], 3)
        self.assertEqual(payload["impact"]["to_update"], 0)
        self.assertEqual(payload["impact"]["unchanged"], 0)
        self.assertEqual(ScheduleAssignment.objects.count(), 0)
        self.assertFalse(
            AuditLog.objects.filter(
                tenant=self.tenant,
                property=self.property,
                user=self.user,
                action="scheduling_bulk_range_state_apply",
            ).exists()
        )

    def test_bulk_week_pattern_applies_shift_and_state(self):
        response = self.client.post(
            "/api/assignments/bulk-week-pattern/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "date_from": "2026-06-01",
                "date_to": "2026-06-07",
                "monday_value": f"shift:{self.shift.id}",
                "sunday_value": f"state:{self.state.id}",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["applied"], 2)
        self.assertTrue(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                date="2026-06-01",
                shift=self.shift,
            ).exists()
        )
        self.assertTrue(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                date="2026-06-07",
                special_state=self.state,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                property=self.property,
                user=self.user,
                action="scheduling_bulk_week_pattern_apply",
            ).exists()
        )

    def test_bulk_week_pattern_blocked_when_month_closed(self):
        MonthClosure.objects.create(
            tenant=self.tenant,
            property=self.property,
            year=2026,
            month=6,
            status=MonthClosureStatus.CLOSED,
        )
        response = self.client.post(
            "/api/assignments/bulk-week-pattern/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "date_from": "2026-06-01",
                "date_to": "2026-06-07",
                "monday_value": f"shift:{self.shift.id}",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, msg=response.content)

    def test_bulk_week_pattern_dry_run_returns_impact_without_writes(self):
        response = self.client.post(
            "/api/assignments/bulk-week-pattern/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "date_from": "2026-06-01",
                "date_to": "2026-06-07",
                "monday_value": f"shift:{self.shift.id}",
                "sunday_value": f"state:{self.state.id}",
                "dry_run": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        payload = response.json()
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["applied"], 2)
        self.assertEqual(payload["impact"]["total"], 2)
        self.assertEqual(payload["impact"]["to_create"], 2)
        self.assertEqual(payload["impact"]["to_update"], 0)
        self.assertEqual(payload["impact"]["unchanged"], 0)
        self.assertEqual(ScheduleAssignment.objects.count(), 0)

    def test_copy_week_dry_run_returns_impact_without_writes(self):
        ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker,
            date="2026-06-01",
            shift=self.shift,
        )
        response = self.client.post(
            "/api/assignments/copy-week/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "source_week_start": "2026-06-01",
                "target_week_start": "2026-06-08",
                "copy_kind": "all",
                "dry_run": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        payload = response.json()
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["copied"], 1)
        self.assertEqual(payload["impact"]["total"], 1)
        self.assertEqual(payload["impact"]["to_create"], 1)
        self.assertEqual(payload["impact"]["to_update"], 0)
        self.assertEqual(payload["impact"]["unchanged"], 0)
        self.assertEqual(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                date="2026-06-08",
            ).count(),
            0,
        )


class SchedulingPatternTemplateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepcion")
        self.worker = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            document_number="20202020",
            first_name="Luis",
            last_name="Perez",
            active=True,
        )
        self.shift = Shift.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Manana",
            buk_code="REC-M",
            start_time=time(6, 0),
            end_time=time(14, 45),
        )
        self.state = SpecialState.objects.create(
            tenant=self.tenant,
            property=self.property,
            name="OFF",
            buk_code="OFF",
        )
        self.user = User.objects.create_user(email="pattern-api@pariwana.test", password="StrongPass123")
        UserTenantRole.objects.create(user=self.user, tenant=self.tenant, role=RoleChoices.ADMIN)
        UserPropertyPermission.objects.create(
            user=self.user,
            tenant=self.tenant,
            property=self.property,
            can_access=True,
            can_schedule=True,
        )
        ModuleActivation.objects.create(tenant=self.tenant, module_key="scheduling", is_enabled=True)
        self.client.force_authenticate(user=self.user)

    def test_save_week_pattern_template_creates_template(self):
        response = self.client.post(
            "/api/assignments/save-week-pattern-template/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "template_name": "OFF domingos + manana",
                "area_id": self.area.id,
                "monday_value": f"shift:{self.shift.id}",
                "sunday_value": f"state:{self.state.id}",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        payload = response.json()
        self.assertTrue(payload["created"])
        template = SchedulePatternTemplate.objects.get(id=payload["id"])
        self.assertEqual(template.name, "OFF domingos + manana")
        self.assertEqual(template.area_id, self.area.id)
        self.assertEqual(template.pattern["monday"], f"shift:{self.shift.id}")
        self.assertEqual(template.pattern["sunday"], f"state:{self.state.id}")
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                property=self.property,
                user=self.user,
                action="schedule_pattern_template_save",
                entity_id=str(template.id),
            ).exists()
        )

    def test_apply_week_pattern_template_creates_assignments(self):
        template = SchedulePatternTemplate.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Plantilla 1",
            pattern={
                "monday": f"shift:{self.shift.id}",
                "tuesday": "",
                "wednesday": "",
                "thursday": "",
                "friday": "",
                "saturday": "",
                "sunday": f"state:{self.state.id}",
            },
            active=True,
            created_by=self.user,
            updated_by=self.user,
        )
        response = self.client.post(
            "/api/assignments/apply-week-pattern-template/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "template_id": template.id,
                "area_id": self.area.id,
                "date_from": "2026-06-01",
                "date_to": "2026-06-07",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["applied"], 2)
        self.assertTrue(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                date="2026-06-01",
                shift=self.shift,
            ).exists()
        )
        self.assertTrue(
            ScheduleAssignment.objects.filter(
                tenant=self.tenant,
                property=self.property,
                worker=self.worker,
                date="2026-06-07",
                special_state=self.state,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                property=self.property,
                user=self.user,
                action="schedule_pattern_template_apply",
                entity_id=str(template.id),
            ).exists()
        )

    def test_apply_week_pattern_template_dry_run_returns_impact_without_writes(self):
        template = SchedulePatternTemplate.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Plantilla Dry Run",
            pattern={
                "monday": f"shift:{self.shift.id}",
                "tuesday": "",
                "wednesday": "",
                "thursday": "",
                "friday": "",
                "saturday": "",
                "sunday": f"state:{self.state.id}",
            },
            active=True,
            created_by=self.user,
            updated_by=self.user,
        )
        response = self.client.post(
            "/api/assignments/apply-week-pattern-template/",
            {
                "tenant_id": self.tenant.id,
                "property_id": self.property.id,
                "template_id": template.id,
                "area_id": self.area.id,
                "date_from": "2026-06-01",
                "date_to": "2026-06-07",
                "dry_run": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        payload = response.json()
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["applied"], 2)
        self.assertEqual(payload["impact"]["total"], 2)
        self.assertEqual(payload["impact"]["to_create"], 2)
        self.assertEqual(payload["impact"]["to_update"], 0)
        self.assertEqual(payload["impact"]["unchanged"], 0)
        self.assertEqual(ScheduleAssignment.objects.count(), 0)
        self.assertFalse(
            AuditLog.objects.filter(
                tenant=self.tenant,
                property=self.property,
                user=self.user,
                action="schedule_pattern_template_apply",
            ).exists()
        )

    def test_week_pattern_templates_list_returns_saved_templates(self):
        SchedulePatternTemplate.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Plantilla Lista",
            pattern={"monday": f"shift:{self.shift.id}", "tuesday": "", "wednesday": "", "thursday": "", "friday": "", "saturday": "", "sunday": ""},
            active=True,
        )
        response = self.client.get(
            f"/api/assignments/week-pattern-templates/?tenant_id={self.tenant.id}&property_id={self.property.id}"
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["name"], "Plantilla Lista")
