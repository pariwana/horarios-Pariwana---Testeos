import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.imports.services import ImportSampleService
from apps.tenants.models import Property, Tenant


class Command(BaseCommand):
    help = "Genera archivos CSV/XLSX de muestra para QA manual de importaciones (trabajadores y turnos por area)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", default="pariwana-hostels")
        parser.add_argument("--property-slug", default="pariwana-cusco")
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directorio de salida. Por defecto: docs/qa_import_samples",
        )
        parser.add_argument("--max-workers", type=int, default=12)
        parser.add_argument("--max-shifts", type=int, default=20)

    def _resolve_output_dir(self, output_dir):
        if output_dir:
            path = Path(output_dir)
            if not path.is_absolute():
                path = settings.BASE_DIR.parent / path
            return path
        return settings.BASE_DIR.parent / "docs" / "qa_import_samples"

    def handle(self, *args, **options):
        tenant_slug = options["tenant_slug"]
        property_slug = options["property_slug"]
        max_workers = max(1, int(options["max_workers"]))
        max_shifts = max(1, int(options["max_shifts"]))
        output_dir = self._resolve_output_dir(options.get("output_dir"))
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"No existe tenant con slug '{tenant_slug}'.") from exc

        try:
            property_obj = Property.objects.get(tenant=tenant, slug=property_slug)
        except Property.DoesNotExist as exc:
            raise CommandError(
                f"No existe sede con slug '{property_slug}' para tenant '{tenant_slug}'."
            ) from exc

        payload = ImportSampleService.build_sample_payload(
            tenant=tenant,
            property_obj=property_obj,
            max_workers=max_workers,
            max_shifts=max_shifts,
        )
        workers_rows = payload["workers_rows"]
        shifts_rows = payload["shifts_rows"]
        if not workers_rows:
            raise CommandError("No hay trabajadores activos para generar muestra.")
        if not shifts_rows:
            raise CommandError("No hay turnos activos para generar muestra.")
        workers_headers = payload["workers_headers"]
        shifts_headers = payload["shifts_headers"]

        workers_csv = output_dir / "workers_import_sample.csv"
        shifts_csv = output_dir / "shifts_area_import_sample.csv"
        workers_xlsx = output_dir / "workers_import_sample.xlsx"
        shifts_xlsx = output_dir / "shifts_area_import_sample.xlsx"

        with workers_csv.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(workers_headers)
            writer.writerows(workers_rows)

        with shifts_csv.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(shifts_headers)
            writer.writerows(shifts_rows)

        workers_xlsx.write_bytes(
            ImportSampleService.generate_xlsx_bytes(
                sheet_name="Trabajadores",
                headers=workers_headers,
                rows=workers_rows,
            )
        )
        shifts_xlsx.write_bytes(
            ImportSampleService.generate_xlsx_bytes(
                sheet_name="Turnos",
                headers=shifts_headers,
                rows=shifts_rows,
            )
        )

        self.stdout.write(self.style.SUCCESS("Archivos de muestra generados:"))
        self.stdout.write(f"- {workers_csv}")
        self.stdout.write(f"- {workers_xlsx}")
        self.stdout.write(f"- {shifts_csv}")
        self.stdout.write(f"- {shifts_xlsx}")
