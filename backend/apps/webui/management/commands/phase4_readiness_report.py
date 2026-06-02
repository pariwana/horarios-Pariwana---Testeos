from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Genera un reporte Markdown de readiness para cierre de Fase 4."

    def add_arguments(self, parser):
        parser.add_argument("--output-file", default=None)
        parser.add_argument("--run-local-qa", action="store_true")
        parser.add_argument("--bootstrap-demo-password", default=None)
        parser.add_argument("--bootstrap-demo-days", type=int, default=15)
        parser.add_argument("--manual-qa-approved", action="store_true")
        parser.add_argument("--buk-final-approved", action="store_true")

    def _resolve_output_file(self, output_file):
        if output_file:
            path = Path(output_file)
            if not path.is_absolute():
                path = settings.BASE_DIR.parent / path
            return path
        suffix = timezone.localdate().isoformat()
        return settings.BASE_DIR.parent / "docs" / f"phase4_readiness_report_{suffix}.md"

    def _run_check(self, command_name, *args, **kwargs):
        try:
            call_command(command_name, *args, **kwargs)
        except CommandError as exc:
            return "FAIL", str(exc)
        return "PASS", ""

    def handle(self, *args, **options):
        output_file = self._resolve_output_file(options.get("output_file"))
        output_file.parent.mkdir(parents=True, exist_ok=True)

        bootstrap_status = "SKIPPED"
        bootstrap_error = "No ejecutado."
        if options.get("bootstrap_demo_password"):
            bootstrap_status, bootstrap_error = self._run_check(
                "bootstrap_local_demo",
                password=options["bootstrap_demo_password"],
                days=options["bootstrap_demo_days"],
            )

        makemigrations_status, makemigrations_error = self._run_check("makemigrations", check=True, dry_run=True)
        security_status, security_error = self._run_check("security_preflight", path=str(settings.BASE_DIR.parent))

        local_qa_status = "SKIPPED"
        local_qa_error = "No ejecutado. Usar --run-local-qa para incluir qa_check_local."
        if options["run_local_qa"]:
            local_qa_status, local_qa_error = self._run_check("qa_check_local")

        manual_qa_status = "PASS" if options["manual_qa_approved"] else "PENDING"
        buk_final_status = "PASS" if options["buk_final_approved"] else "PENDING"

        blocking_items = []
        if bootstrap_status == "FAIL":
            blocking_items.append("Bootstrap demo fallido.")
        if makemigrations_status != "PASS":
            blocking_items.append("Migraciones pendientes o invalidas.")
        if security_status != "PASS":
            blocking_items.append("Security preflight fallido: revisar secretos accidentales.")
        if local_qa_status == "FAIL":
            blocking_items.append("QA local automatizado fallido.")
        if manual_qa_status != "PASS":
            blocking_items.append("QA manual por rol pendiente de aprobacion.")
        if buk_final_status != "PASS":
            blocking_items.append("Validacion final BUK con archivo operativo real pendiente.")

        if not blocking_items:
            readiness_percent = 100
            phase_status = "READY_FOR_SIGNOFF"
        elif manual_qa_status == "PASS" or buk_final_status == "PASS":
            readiness_percent = 95
            phase_status = "FINAL_VALIDATION_PENDING"
        else:
            readiness_percent = 90
            phase_status = "TECHNICALLY_READY_PENDING_BUSINESS_QA"

        now_iso = timezone.now().isoformat()
        report = [
            "# Fase 4 - Readiness report",
            "",
            f"- Ejecutado: {now_iso}",
            f"- Estado: **{phase_status}**",
            f"- Avance estimado: **{readiness_percent}%**",
            "",
            "## Checks automaticos",
            f"- bootstrap_local_demo: **{bootstrap_status}**",
            f"- makemigrations --check: **{makemigrations_status}**",
            f"- security_preflight: **{security_status}**",
            f"- qa_check_local: **{local_qa_status}**",
            "",
            "## Aprobaciones manuales",
            f"- QA manual por rol: **{manual_qa_status}**",
            f"- Validacion final BUK real: **{buk_final_status}**",
            "",
            "## Bloqueantes para 100%",
        ]
        if blocking_items:
            report.extend([f"- {item}" for item in blocking_items])
        else:
            report.append("- Sin bloqueantes.")

        report.extend(
            [
                "",
                "## Criterio de cierre",
                "- Tests relevantes en verde.",
                "- Sin migraciones pendientes.",
                "- Flujos criticos revisados por rol: Asignacion, Control 15 dias, Reporte BUK, Cierre de mes.",
                "- XLSX BUK validado contra operacion real.",
                "",
                "## Notas",
                "- Este reporte no reemplaza la revision visual en navegador.",
                "- Para marcar 100%, ejecutar con `--manual-qa-approved --buk-final-approved` solo despues de aprobacion real.",
            ]
        )
        if bootstrap_error or makemigrations_error or security_error or local_qa_error:
            report.extend(
                [
                    "",
                    "## Detalles de checks",
                    "```text",
                    "\n".join(
                        item for item in [bootstrap_error, makemigrations_error, security_error, local_qa_error] if item
                    ),
                    "```",
                ]
            )

        output_file.write_text("\n".join(report), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Readiness report generado: {output_file}"))
