from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side

from apps.scheduling.models import ScheduleAssignment
from apps.workers.models import Worker

from apps.buk_exports.models import BukExportLog


@dataclass
class ValidationIssue:
    date: str
    property_name: str
    area_name: str
    worker_name: str
    problem: str
    severity: str
    suggested_action: str


class BukValidationService:
    @staticmethod
    def validate_assignments(*, tenant, property_obj, date_from, date_to):
        issues = []
        assignments = ScheduleAssignment.objects.filter(
            tenant=tenant,
            property=property_obj,
            date__gte=date_from,
            date__lte=date_to,
        ).select_related("worker", "worker__area", "shift", "special_state")

        for assignment in assignments:
            if assignment.worker.active and not assignment.worker.document_number:
                issues.append(
                    ValidationIssue(
                        date=assignment.date.isoformat(),
                        property_name=property_obj.name,
                        area_name=assignment.worker.area.name,
                        worker_name=f"{assignment.worker.first_name} {assignment.worker.last_name}",
                        problem="Trabajador activo sin documento.",
                        severity="error",
                        suggested_action="Completar documento del trabajador.",
                    )
                )
        return issues


class BukExportService:
    @staticmethod
    def _date_range(date_from, date_to):
        dates = []
        cursor = date_from
        while cursor <= date_to:
            dates.append(cursor)
            cursor = cursor + timedelta(days=1)
        return dates

    @staticmethod
    def _build_day_code_index(*, tenant, property_obj, date_from, date_to):
        assignments = ScheduleAssignment.objects.filter(
            tenant=tenant,
            property=property_obj,
            date__gte=date_from,
            date__lte=date_to,
        ).select_related("worker", "shift", "special_state")
        index = {}
        for assignment in assignments:
            if assignment.special_state_id:
                code = "D"
            elif assignment.shift_id:
                code = assignment.shift.buk_code
            else:
                code = ""
            index[(assignment.worker_id, assignment.date)] = code
        return index

    @staticmethod
    def build_preview_rows(*, tenant, property_obj, date_from, date_to):
        workers = Worker.objects.filter(
            tenant=tenant,
            property=property_obj,
            active=True,
        ).select_related("area").order_by("last_name", "first_name")
        day_codes = BukExportService._build_day_code_index(
            tenant=tenant,
            property_obj=property_obj,
            date_from=date_from,
            date_to=date_to,
        )
        dates = BukExportService._date_range(date_from, date_to)
        row_map = {}
        for worker in workers:
            row_map[worker.id] = {
                "document": worker.document_number,
                "name": f"{worker.first_name} {worker.last_name}".strip(),
                "area": worker.area.name if worker.area_id else "",
                "days": {d.isoformat(): day_codes.get((worker.id, d), "") for d in dates},
            }
        return list(row_map.values())

    @staticmethod
    def generate_xlsx_bytes(*, tenant, property_obj, date_from, date_to):
        preview_rows = BukExportService.build_preview_rows(
            tenant=tenant,
            property_obj=property_obj,
            date_from=date_from,
            date_to=date_to,
        )
        dates = BukExportService._date_range(date_from, date_to)

        workbook = Workbook()
        ws = workbook.active
        ws.title = "Reporte carga BUK"

        ws.cell(1, 1, "Trabajadores")
        ws.cell(2, 1, "RUT")
        ws.cell(2, 2, "Nombre")
        ws.cell(2, 3, "Área")

        month_label = date_from.strftime("%m-%Y")
        for idx, current_date in enumerate(dates, start=4):
            ws.cell(1, idx, month_label)
            ws.cell(2, idx, current_date.strftime("%d-%m-%Y"))

        for row_idx, item in enumerate(preview_rows, start=3):
            ws.cell(row_idx, 1, item["document"])
            ws.cell(row_idx, 2, item["name"])
            ws.cell(row_idx, 3, item["area"])
            for col_idx, current_date in enumerate(dates, start=4):
                ws.cell(row_idx, col_idx, item["days"].get(current_date.isoformat(), ""))

        # Minimal style compatible with template readability.
        bold = Font(bold=True)
        center = Alignment(horizontal="center", vertical="center")
        thin = Side(style="thin")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        for cell in ws[1]:
            cell.font = bold
            cell.alignment = center
            cell.border = border
        for cell in ws[2]:
            cell.font = bold
            cell.alignment = center
            cell.border = border
        for row in ws.iter_rows(min_row=3, max_row=2 + len(preview_rows), min_col=1, max_col=3 + len(dates)):
            for cell in row:
                cell.border = border

        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 28
        ws.column_dimensions["C"].width = 18
        for col_idx in range(4, 4 + len(dates)):
            ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = 12
        ws.freeze_panes = "D3"

        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    @staticmethod
    def generate_csv_text(*, tenant, property_obj, date_from, date_to):
        preview_rows = BukExportService.build_preview_rows(
            tenant=tenant,
            property_obj=property_obj,
            date_from=date_from,
            date_to=date_to,
        )
        dates = BukExportService._date_range(date_from, date_to)
        headers = ["RUT", "Nombre", "Área"] + [d.strftime("%d-%m-%Y") for d in dates]
        lines = [",".join(headers)]
        for row in preview_rows:
            day_values = [row["days"].get(d.isoformat(), "") for d in dates]
            values = [str(row["document"] or ""), row["name"], row["area"]] + day_values
            escaped = [f"\"{v.replace('\"', '\"\"')}\"" if "," in v or "\"" in v else v for v in values]
            lines.append(",".join(escaped))
        return "\n".join(lines)

    @staticmethod
    def log_export(*, tenant, property_obj, date_from, date_to, generated_by, file_name, validation_issues):
        error_count = sum(1 for issue in validation_issues if issue.severity == "error")
        warning_count = sum(1 for issue in validation_issues if issue.severity == "warning")
        return BukExportLog.objects.create(
            tenant=tenant,
            property=property_obj,
            date_from=date_from,
            date_to=date_to,
            generated_by=generated_by,
            file_name=file_name,
            validation_status="ok" if error_count == 0 else "error",
            errors_count=error_count,
            warnings_count=warning_count,
        )
