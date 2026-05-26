from django.test import TestCase
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook

from apps.imports.services import ExcelImportApplyService, ExcelImportService, WorkerImportService
from apps.scheduling.models import ScheduleAssignment
from apps.tenants.models import Property, Tenant
from apps.users.models import User
from apps.workers.models import Area, Shift, SpecialState, Worker


class WorkerImportServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ops@pariwana.test", password="StrongPass123")
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepción")
        Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="11111111",
            first_name="Nombre",
            last_name="Original",
            area=self.area,
        )

    def test_preview_and_confirm_csv_worker_import(self):
        csv_content = (
            "DNI,Nombre,Apellido,Area,Sede\n"
            "11111111,Nombre,Nuevo,Recepción,Pariwana Cusco\n"
            "22222222,Ana,Perez,Housekeeping,Pariwana Cusco\n"
        ).encode("utf-8")
        batch = WorkerImportService.create_worker_preview(
            tenant=self.tenant,
            fallback_property=self.property,
            file_name="workers.csv",
            file_bytes=csv_content,
            user=self.user,
            create_missing_areas=True,
        )
        self.assertEqual(batch.summary["detected_rows"], 2)
        self.assertEqual(batch.summary["errors"], 0)

        WorkerImportService.confirm_worker_import(batch=batch)
        self.assertTrue(
            Worker.objects.filter(
                tenant=self.tenant,
                property=self.property,
                document_number="22222222",
            ).exists()
        )


class ExcelImportServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ops2@pariwana.test", password="StrongPass123")
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")

    def _build_excel_bytes(self):
        wb = Workbook()
        ws_datos = wb.active
        ws_datos.title = "Datos"
        ws_datos.cell(6, 3).value = "Recepcion"
        ws_datos.cell(6, 8).value = "OFF"

        ws_workers = wb.create_sheet("Reg. de trabajadores x area")
        ws_workers.cell(4, 1).value = "12345678"
        ws_workers.cell(4, 2).value = "Ana"
        ws_workers.cell(4, 3).value = "Quispe"
        ws_workers.cell(4, 4).value = "Recepcion"

        ws_shifts = wb.create_sheet("Reg. Horarios x area")
        ws_shifts.cell(4, 1).value = "REC-M"
        ws_shifts.cell(4, 2).value = "REC-M"
        ws_shifts.cell(4, 3).value = "Recepcion"
        ws_shifts.cell(4, 4).value = "06:00 - 14:45"

        ws_month = wb.create_sheet("Abril 2026")
        ws_month.cell(5, 4).value = datetime(2026, 4, 1)
        ws_month.cell(5, 4).number_format = "yyyy-mm-dd"
        ws_month.cell(6, 1).value = "Recepcion"
        ws_month.cell(7, 1).value = "12345678"
        ws_month.cell(7, 2).value = "Ana Quispe"
        ws_month.cell(7, 3).value = "TURNO"
        ws_month.cell(7, 4).value = "06:00 - 14:45"

        buffer = BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def test_excel_preview_and_apply(self):
        file_bytes = self._build_excel_bytes()
        batch = ExcelImportService.create_preview(
            tenant=self.tenant,
            property_obj=self.property,
            file_name="source.xlsx",
            file_bytes=file_bytes,
            user=self.user,
        )
        self.assertGreater(batch.preview_rows.count(), 0)

        batch = ExcelImportApplyService.apply_preview_batch(batch=batch)
        self.assertEqual(batch.status, "confirmed")
        self.assertTrue(Area.objects.filter(tenant=self.tenant, property=self.property, name="Recepcion").exists())
        self.assertTrue(Worker.objects.filter(tenant=self.tenant, property=self.property, document_number="12345678").exists())
        self.assertTrue(Shift.objects.filter(tenant=self.tenant, property=self.property, name="REC-M").exists())
        self.assertTrue(SpecialState.objects.filter(tenant=self.tenant, property=self.property, name="OFF").exists())
        self.assertTrue(ScheduleAssignment.objects.filter(tenant=self.tenant, property=self.property).exists())
