from datetime import date, time
from pathlib import Path
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from openpyxl import Workbook

from apps.buk_exports.services import BukExportService
from apps.scheduling.models import ScheduleAssignment
from apps.tenants.models import Property, Tenant
from apps.workers.models import Area, Shift, Worker


class Phase4AcceptanceSnapshotCommandTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Pariwana Hostels", slug="pariwana-hostels")
        self.property = Property.objects.create(tenant=self.tenant, name="Pariwana Cusco", slug="pariwana-cusco")
        self.area = Area.objects.create(tenant=self.tenant, property=self.property, name="Recepcion")
        self.shift = Shift.objects.create(
            tenant=self.tenant,
            property=self.property,
            area=self.area,
            name="Manana",
            buk_code="REC-M",
            start_time=time(6, 0),
            end_time=time(14, 0),
        )
        self.worker = Worker.objects.create(
            tenant=self.tenant,
            property=self.property,
            document_number="22222222",
            first_name="Ana",
            last_name="Quispe",
            area=self.area,
        )
        ScheduleAssignment.objects.create(
            tenant=self.tenant,
            property=self.property,
            worker=self.worker,
            date=date(2026, 4, 2),
            shift=self.shift,
        )

    def test_command_generates_snapshot_when_reference_is_compatible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reference_path = Path(tmpdir) / "reference.xlsx"
            report_path = Path(tmpdir) / "snapshot.md"
            reference_bytes = BukExportService.generate_xlsx_bytes(
                tenant=self.tenant,
                property_obj=self.property,
                date_from=date(2026, 4, 2),
                date_to=date(2026, 4, 2),
            )
            reference_path.write_bytes(reference_bytes)

            call_command(
                "phase4_acceptance_snapshot",
                tenant_slug="pariwana-hostels",
                property_slug="pariwana-cusco",
                date_from="2026-04-02",
                date_to="2026-04-02",
                reference_file=str(reference_path),
                output_file=str(report_path),
                skip_local_qa=True,
            )

            self.assertTrue(report_path.exists())
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("Estado global: **PASS**", text)
            self.assertIn("check_buk_template_compatibility: **PASS**", text)

    def test_command_fails_when_reference_is_incompatible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reference_path = Path(tmpdir) / "reference_bad.xlsx"
            report_path = Path(tmpdir) / "snapshot_bad.md"
            wb = Workbook()
            ws = wb.active
            ws.title = "Otra hoja"
            ws.cell(1, 1, "x")
            wb.save(reference_path)

            with self.assertRaises(CommandError):
                call_command(
                    "phase4_acceptance_snapshot",
                    tenant_slug="pariwana-hostels",
                    property_slug="pariwana-cusco",
                    date_from="2026-04-02",
                    date_to="2026-04-02",
                    reference_file=str(reference_path),
                    output_file=str(report_path),
                    skip_local_qa=True,
                )

            self.assertTrue(report_path.exists())
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("Estado global: **FAIL**", text)


class Phase4ReadinessReportCommandTests(TestCase):
    def test_command_generates_pending_report_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "readiness.md"

            call_command("phase4_readiness_report", output_file=str(report_path))

            self.assertTrue(report_path.exists())
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("Avance estimado: **90%**", text)
            self.assertIn("security_preflight: **PASS**", text)
            self.assertIn("QA manual por rol: **PENDING**", text)
            self.assertIn("Validacion final BUK real: **PENDING**", text)

    def test_command_can_mark_ready_when_manual_approvals_are_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "readiness_ready.md"

            call_command(
                "phase4_readiness_report",
                output_file=str(report_path),
                manual_qa_approved=True,
                buk_final_approved=True,
            )

            text = report_path.read_text(encoding="utf-8")
            self.assertIn("Estado: **READY_FOR_SIGNOFF**", text)
            self.assertIn("Avance estimado: **100%**", text)
            self.assertIn("security_preflight: **PASS**", text)
            self.assertIn("Sin bloqueantes.", text)


class SecurityPreflightCommandTests(TestCase):
    def test_command_passes_clean_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clean_file = Path(tmpdir) / "README.md"
            clean_file.write_text("sin secretos", encoding="utf-8")

            call_command("security_preflight", path=tmpdir)

    def test_command_fails_when_secret_pattern_is_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad.txt"
            bad_file.write_text("token=" + "ghp" + "_abcdefghijklmnopqrstuvwxyz123456", encoding="utf-8")

            with self.assertRaises(CommandError):
                call_command("security_preflight", path=tmpdir)
