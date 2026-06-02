from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Genera un snapshot Markdown de estado para cierre funcional de Fase 4."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", default="pariwana-hostels")
        parser.add_argument("--property-slug", default="pariwana-cusco")
        parser.add_argument("--date-from", default=None)
        parser.add_argument("--date-to", default=None)
        parser.add_argument("--reference-file", required=True)
        parser.add_argument("--sheet-name", default="Reporte carga BUK")
        parser.add_argument("--output-file", default=None)
        parser.add_argument(
            "--skip-local-qa",
            action="store_true",
            help="Omite qa_check_local (usa solo comparacion BUK).",
        )

    def _parse_date(self, raw_value, option_name):
        if raw_value is None:
            return None
        try:
            return date.fromisoformat(raw_value)
        except ValueError as exc:
            raise CommandError(f"{option_name} invalida. Usar formato YYYY-MM-DD.") from exc

    def _resolve_output_file(self, output_file):
        if output_file:
            path = Path(output_file)
            if not path.is_absolute():
                path = settings.BASE_DIR.parent / path
            return path
        suffix = timezone.localdate().isoformat()
        return settings.BASE_DIR.parent / "docs" / f"phase4_acceptance_snapshot_{suffix}.md"

    def handle(self, *args, **options):
        today = timezone.localdate()
        date_from = self._parse_date(options.get("date_from"), "--date-from") or today
        date_to = self._parse_date(options.get("date_to"), "--date-to") or (date_from + timedelta(days=14))
        if date_from > date_to:
            raise CommandError("--date-from no puede ser mayor que --date-to.")

        reference_file = Path(options["reference_file"])
        if not reference_file.exists():
            raise CommandError(f"No existe archivo de referencia: {reference_file}")

        output_file = self._resolve_output_file(options.get("output_file"))
        output_file.parent.mkdir(parents=True, exist_ok=True)
        compare_json_path = output_file.with_suffix(".json")

        qa_status = "SKIPPED"
        qa_output = ""
        if not options.get("skip_local_qa"):
            qa_stdout = StringIO()
            qa_stderr = StringIO()
            try:
                call_command("qa_check_local", stdout=qa_stdout, stderr=qa_stderr)
                qa_status = "PASS"
            except CommandError:
                qa_status = "FAIL"
            qa_output = (qa_stdout.getvalue() + "\n" + qa_stderr.getvalue()).strip()

        compare_status = "FAIL"
        compare_output = ""
        compare_error = ""
        compare_stdout = StringIO()
        compare_stderr = StringIO()
        try:
            call_command(
                "check_buk_template_compatibility",
                tenant_slug=options["tenant_slug"],
                property_slug=options["property_slug"],
                date_from=date_from.isoformat(),
                date_to=date_to.isoformat(),
                reference_file=str(reference_file),
                sheet_name=options["sheet_name"],
                output_json=str(compare_json_path),
                stdout=compare_stdout,
                stderr=compare_stderr,
            )
            compare_status = "PASS"
        except CommandError as exc:
            compare_status = "FAIL"
            compare_error = str(exc)
        compare_output = (compare_stdout.getvalue() + "\n" + compare_stderr.getvalue()).strip()

        global_status = "PASS"
        if qa_status == "FAIL" or compare_status == "FAIL":
            global_status = "FAIL"

        now_iso = timezone.now().isoformat()
        report = [
            "# Fase 4 - Snapshot de aceptacion",
            "",
            f"- Ejecutado: {now_iso}",
            f"- Tenant: {options['tenant_slug']}",
            f"- Sede: {options['property_slug']}",
            f"- Rango evaluado: {date_from.isoformat()} a {date_to.isoformat()}",
            f"- Referencia BUK: `{reference_file}`",
            f"- Estado global: **{global_status}**",
            "",
            "## Resultado checks",
            f"- qa_check_local: **{qa_status}**",
            f"- check_buk_template_compatibility: **{compare_status}**",
            "",
            "## Evidencia",
            f"- JSON comparacion: `{compare_json_path}`",
            "",
            "## Salida qa_check_local",
            "```text",
            qa_output or "(sin salida o no ejecutado)",
            "```",
            "",
            "## Salida check_buk_template_compatibility",
            "```text",
            compare_output or "(sin salida)",
            "```",
        ]
        if compare_error:
            report.extend(
                [
                    "",
                    "## Error comparacion BUK",
                    "```text",
                    compare_error,
                    "```",
                ]
            )

        output_file.write_text("\n".join(report), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Snapshot generado: {output_file}"))

        if global_status != "PASS":
            raise CommandError("Snapshot con fallas: revisar reporte generado.")

