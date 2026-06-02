import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.buk_exports.services import BukExportService
from apps.tenants.models import Property, Tenant


class Command(BaseCommand):
    help = (
        "Genera un XLSX BUK para un rango y compara su estructura contra un "
        "archivo de referencia (hoja 'Reporte carga BUK' por defecto)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", default="pariwana-hostels")
        parser.add_argument("--property-slug", required=True)
        parser.add_argument("--date-from", required=True)
        parser.add_argument("--date-to", required=True)
        parser.add_argument("--reference-file", required=True)
        parser.add_argument("--sheet-name", default="Reporte carga BUK")
        parser.add_argument(
            "--strict-warnings",
            action="store_true",
            help="Retorna error si existen warnings de compatibilidad.",
        )
        parser.add_argument(
            "--output-json",
            required=False,
            help="Ruta opcional para guardar el resultado JSON.",
        )

    def _parse_date(self, raw_value, option_name):
        try:
            return date.fromisoformat(raw_value)
        except ValueError as exc:
            raise CommandError(f"{option_name} invalida. Usar formato YYYY-MM-DD.") from exc

    def handle(self, *args, **options):
        tenant_slug = options["tenant_slug"]
        property_slug = options["property_slug"]
        date_from = self._parse_date(options["date_from"], "--date-from")
        date_to = self._parse_date(options["date_to"], "--date-to")
        reference_file = Path(options["reference_file"])
        sheet_name = options["sheet_name"] or "Reporte carga BUK"
        strict_warnings = bool(options["strict_warnings"])
        output_json = options.get("output_json")

        if date_from > date_to:
            raise CommandError("--date-from no puede ser mayor que --date-to.")
        if not reference_file.exists():
            raise CommandError(f"No existe archivo de referencia: {reference_file}")

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

        reference_bytes = reference_file.read_bytes()
        candidate_bytes = BukExportService.generate_xlsx_bytes(
            tenant=tenant,
            property_obj=property_obj,
            date_from=date_from,
            date_to=date_to,
        )
        result = BukExportService.compare_template_compatibility(
            reference_file_bytes=reference_bytes,
            candidate_file_bytes=candidate_bytes,
            sheet_name=sheet_name,
        )
        payload = {
            "tenant_slug": tenant_slug,
            "property_slug": property_slug,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "sheet_name": sheet_name,
            **result,
        }

        json_text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        self.stdout.write(json_text)

        if output_json:
            output_path = Path(output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_text, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"JSON guardado en: {output_path}"))

        has_errors = bool(result.get("errors"))
        has_warnings = bool(result.get("warnings"))
        if has_errors or (strict_warnings and has_warnings):
            raise CommandError(
                "Compatibilidad NO valida: "
                f"errors={len(result.get('errors', []))}, warnings={len(result.get('warnings', []))}."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Compatibilidad valida: "
                f"errors={len(result.get('errors', []))}, warnings={len(result.get('warnings', []))}."
            )
        )

