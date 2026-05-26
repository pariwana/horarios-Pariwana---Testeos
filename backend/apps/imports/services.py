import csv
from datetime import date, datetime, time
from io import BytesIO, StringIO

from openpyxl import load_workbook

from apps.audit.services import AuditService
from apps.imports.models import ImportBatch, ImportPreviewRow
from apps.scheduling.models import ScheduleAssignment
from apps.workers.models import Area, Shift, SpecialState, Worker


class ExcelImportService:
    MONTH_SHEETS = {
        "Enero 2026",
        "Febrero 2026",
        "Marzo 2026",
        "Abril 2026",
        "Mayo 2026",
        "Junio 2026",
        "Julio 2026",
        "Agosto 2026",
        "Septiembre 2026",
        "Octubre 2026",
        "Noviembre 2026",
        "Diciembre 2026",
    }

    @staticmethod
    def _normalize_text(value):
        return "" if value is None else str(value).strip()

    @staticmethod
    def _parse_time(value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.time()
        text = str(value).strip()
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).time()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_time_range(value):
        text = ExcelImportService._normalize_text(value)
        if "-" not in text:
            return None, None
        left, right = text.split("-", 1)
        return ExcelImportService._parse_time(left), ExcelImportService._parse_time(right)

    @staticmethod
    def _serialize_time(value):
        if value is None:
            return None
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        return str(value)

    @staticmethod
    def create_preview(*, tenant, property_obj, file_name, file_bytes, user):
        workbook = load_workbook(BytesIO(file_bytes), data_only=False)
        workbook_values = load_workbook(BytesIO(file_bytes), data_only=True)

        sheets_summary = []
        for ws in workbook.worksheets:
            sheets_summary.append(
                {
                    "name": ws.title,
                    "max_row": ws.max_row,
                    "max_col": ws.max_column,
                    "merged_ranges": len(ws.merged_cells.ranges),
                    "has_formulas": any(
                        isinstance(cell.value, str) and cell.value.startswith("=")
                        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 30))
                        for cell in row
                    ),
                }
            )

        batch = ImportBatch.objects.create(
            tenant=tenant,
            property=property_obj,
            source_type="excel_original",
            file_name=file_name,
            created_by=user,
            summary={
                "sheets": sheets_summary,
                "detected": {
                    "areas": 0,
                    "workers": 0,
                    "shifts": 0,
                    "special_states": 0,
                    "assignments": 0,
                },
                "new": {"areas": 0, "workers": 0, "shifts": 0, "special_states": 0, "assignments": 0},
                "updates": {"workers": 0, "shifts": 0, "special_states": 0},
                "warnings": 0,
                "errors": 0,
                "skipped": 0,
                "uninterpreted_sheets": [],
            },
        )

        for item in sheets_summary:
            ImportPreviewRow.objects.create(
                batch=batch,
                sheet_name=item["name"],
                row_number=0,
                action="inspect",
                status="ok",
                payload=item,
            )

        areas_by_name = {
            area.name.lower(): area
            for area in Area.objects.filter(tenant=tenant, property=property_obj)
        }
        special_by_name = {
            state.name.lower(): state
            for state in SpecialState.objects.filter(tenant=tenant, property=property_obj)
        }

        # Datos sheet: areas + special states.
        if "Datos" in workbook_values.sheetnames:
            ws = workbook_values["Datos"]
            for row_num in range(6, 19):
                area_name = ExcelImportService._normalize_text(ws.cell(row_num, 3).value)
                if not area_name:
                    continue
                batch.summary["detected"]["areas"] += 1
                exists = area_name.lower() in areas_by_name
                if not exists:
                    batch.summary["new"]["areas"] += 1
                ImportPreviewRow.objects.create(
                    batch=batch,
                    sheet_name="Datos",
                    row_number=row_num * 10 + 1,
                    action="update" if exists else "create",
                    status="ok",
                    payload={"entity": "area", "name": area_name, "property_id": property_obj.id},
                )

            for row_num in range(6, 20):
                state_name = ExcelImportService._normalize_text(ws.cell(row_num, 8).value)
                if not state_name:
                    continue
                batch.summary["detected"]["special_states"] += 1
                exists = state_name.lower() in special_by_name
                if exists:
                    batch.summary["updates"]["special_states"] += 1
                else:
                    batch.summary["new"]["special_states"] += 1
                ImportPreviewRow.objects.create(
                    batch=batch,
                    sheet_name="Datos",
                    row_number=row_num * 10 + 2,
                    action="update" if exists else "create",
                    status="ok",
                    payload={
                        "entity": "special_state",
                        "name": state_name,
                        "buk_code": "D",
                        "property_id": property_obj.id,
                    },
                )

        # Worker registry.
        if "Reg. de trabajadores x area" in workbook_values.sheetnames:
            ws = workbook_values["Reg. de trabajadores x area"]
            for row_num in range(4, ws.max_row + 1):
                doc = WorkerImportService.normalize_document(ws.cell(row_num, 1).value)
                if not doc:
                    continue
                first_name = ExcelImportService._normalize_text(ws.cell(row_num, 2).value)
                last_name = ExcelImportService._normalize_text(ws.cell(row_num, 3).value)
                area_name = ExcelImportService._normalize_text(ws.cell(row_num, 4).value)
                batch.summary["detected"]["workers"] += 1
                if not area_name:
                    batch.summary["errors"] += 1
                    ImportPreviewRow.objects.create(
                        batch=batch,
                        sheet_name="Reg. de trabajadores x area",
                        row_number=row_num,
                        action="skip",
                        status="error",
                        message="Worker row without area.",
                        payload={"entity": "worker", "document_number": doc},
                    )
                    continue
                exists = Worker.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    document_number=doc,
                ).exists()
                if exists:
                    batch.summary["updates"]["workers"] += 1
                else:
                    batch.summary["new"]["workers"] += 1
                ImportPreviewRow.objects.create(
                    batch=batch,
                    sheet_name="Reg. de trabajadores x area",
                    row_number=row_num,
                    action="update" if exists else "create",
                    status="ok",
                    payload={
                        "entity": "worker",
                        "document_number": doc,
                        "first_name": first_name,
                        "last_name": last_name,
                        "area_name": area_name,
                        "property_id": property_obj.id,
                    },
                )

        # Shift registry.
        shift_sheet_name = next((name for name in workbook_values.sheetnames if name.startswith("Reg. Horarios x")), None)
        shift_by_area_schedule = {}
        if shift_sheet_name:
            ws = workbook_values[shift_sheet_name]
            for row_num in range(4, ws.max_row + 1):
                shift_name = ExcelImportService._normalize_text(ws.cell(row_num, 1).value)
                if not shift_name:
                    continue
                buk_code = ExcelImportService._normalize_text(ws.cell(row_num, 2).value)
                area_name = ExcelImportService._normalize_text(ws.cell(row_num, 3).value)
                schedule_text = ExcelImportService._normalize_text(ws.cell(row_num, 4).value)
                break_text = ExcelImportService._normalize_text(ws.cell(row_num, 5).value)

                batch.summary["detected"]["shifts"] += 1
                exists = Shift.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    area__name__iexact=area_name,
                    name=shift_name,
                ).exists()
                if exists:
                    batch.summary["updates"]["shifts"] += 1
                else:
                    batch.summary["new"]["shifts"] += 1

                start_time, end_time = ExcelImportService._parse_time_range(schedule_text)
                break_start, break_end = ExcelImportService._parse_time_range(break_text)
                shift_by_area_schedule[(area_name.lower(), schedule_text.lower())] = shift_name

                ImportPreviewRow.objects.create(
                    batch=batch,
                    sheet_name=shift_sheet_name,
                    row_number=row_num,
                    action="update" if exists else "create",
                    status="ok",
                    payload={
                        "entity": "shift",
                        "name": shift_name,
                        "buk_code": buk_code,
                        "area_name": area_name,
                        "start_time": ExcelImportService._serialize_time(start_time),
                        "end_time": ExcelImportService._serialize_time(end_time),
                        "break_start": ExcelImportService._serialize_time(break_start),
                        "break_end": ExcelImportService._serialize_time(break_end),
                        "schedule_text": schedule_text,
                        "property_id": property_obj.id,
                    },
                )

        # Monthly assignments.
        interpreted_sheets = {"Datos", "Reg. de trabajadores x area", shift_sheet_name, "Reporte carga BUK"}
        for sheet_name in workbook_values.sheetnames:
            if sheet_name not in ExcelImportService.MONTH_SHEETS:
                if sheet_name not in interpreted_sheets:
                    batch.summary["uninterpreted_sheets"].append(sheet_name)
                continue

            ws = workbook_values[sheet_name]
            date_headers = {}
            for col in range(4, ws.max_column + 1):
                cell_value = ws.cell(5, col).value
                if isinstance(cell_value, datetime):
                    date_headers[col] = cell_value.date()
            current_area = ""
            for row_num in range(6, ws.max_row + 1):
                col_a = ExcelImportService._normalize_text(ws.cell(row_num, 1).value)
                col_b = ExcelImportService._normalize_text(ws.cell(row_num, 2).value)
                col_c = ExcelImportService._normalize_text(ws.cell(row_num, 3).value)
                if col_a and not col_b and not col_c:
                    current_area = col_a
                    continue
                if col_c.upper() != "TURNO":
                    continue
                worker_document = WorkerImportService.normalize_document(ws.cell(row_num, 1).value)
                if not worker_document:
                    continue

                for col, assignment_date in date_headers.items():
                    assignment_value = ExcelImportService._normalize_text(ws.cell(row_num, col).value)
                    if not assignment_value:
                        continue

                    batch.summary["detected"]["assignments"] += 1
                    payload = {
                        "entity": "assignment",
                        "document_number": worker_document,
                        "date": assignment_date.isoformat(),
                        "property_id": property_obj.id,
                    }
                    status = "ok"
                    if assignment_value.upper() in {"OFF", "VACACIONES", "LICENCIA"}:
                        payload["special_state_name"] = assignment_value.upper()
                    else:
                        payload["area_name"] = current_area
                        payload["schedule_text"] = assignment_value
                        payload["shift_name"] = shift_by_area_schedule.get(
                            (current_area.lower(), assignment_value.lower())
                        )
                        if payload["shift_name"] is None:
                            status = "warning"
                            batch.summary["warnings"] += 1

                    ImportPreviewRow.objects.create(
                        batch=batch,
                        sheet_name=sheet_name,
                        row_number=row_num * 1000 + col,
                        action="upsert",
                        status=status,
                        payload=payload,
                    )

        batch.save(update_fields=["summary", "updated_at"])
        return batch


class WorkerImportService:
    REQUIRED_COLUMNS = {"dni", "nombre", "apellido", "area"}

    @staticmethod
    def normalize_document(value):
        if value is None:
            return ""
        text = str(value).strip()
        return text.replace(".0", "") if text.endswith(".0") else text

    @staticmethod
    def _normalize_header(header):
        text = str(header or "").strip().lower()
        mapping = {
            "dni": "dni",
            "documento": "dni",
            "nro documento": "dni",
            "numero de documento": "dni",
            "número de documento": "dni",
            "nombre": "nombre",
            "nombres": "nombre",
            "apellido": "apellido",
            "apellidos": "apellido",
            "area": "area",
            "área": "area",
            "sede": "sede",
            "property": "sede",
        }
        return mapping.get(text, text)

    @staticmethod
    def _read_worker_rows(file_name, file_bytes):
        lower = file_name.lower()
        if lower.endswith(".csv"):
            text = file_bytes.decode("utf-8-sig")
            reader = csv.DictReader(StringIO(text))
            headers = [WorkerImportService._normalize_header(h) for h in (reader.fieldnames or [])]
            rows = []
            for raw_row in reader:
                row = {}
                for key, value in raw_row.items():
                    row[WorkerImportService._normalize_header(key)] = value
                rows.append(row)
            return headers, rows

        wb = load_workbook(BytesIO(file_bytes), data_only=True)
        ws = wb.active
        raw_headers = [ws.cell(1, i).value for i in range(1, ws.max_column + 1)]
        headers = [WorkerImportService._normalize_header(h) for h in raw_headers]
        rows = []
        for row_num in range(2, ws.max_row + 1):
            payload = {}
            has_any_value = False
            for col_num, key in enumerate(headers, start=1):
                value = ws.cell(row_num, col_num).value
                payload[key] = value
                if value not in (None, ""):
                    has_any_value = True
            if has_any_value:
                rows.append(payload)
        return headers, rows

    @staticmethod
    def create_worker_preview(
        *,
        tenant,
        fallback_property,
        file_name,
        file_bytes,
        user,
        create_missing_areas=False,
    ):
        headers, rows = WorkerImportService._read_worker_rows(file_name, file_bytes)
        missing = WorkerImportService.REQUIRED_COLUMNS - set(headers)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

        batch = ImportBatch.objects.create(
            tenant=tenant,
            property=fallback_property,
            source_type="workers",
            file_name=file_name,
            created_by=user,
            summary={},
        )

        properties_by_name = {prop.name.strip().lower(): prop for prop in tenant.properties.all()}
        multiple_properties = len(properties_by_name) > 1
        summary = {
            "detected_rows": len(rows),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "new_areas": 0,
            "unknown_properties": 0,
            "warnings": 0,
        }

        for row_index, row in enumerate(rows, start=2):
            document = WorkerImportService.normalize_document(row.get("dni"))
            first_name = str(row.get("nombre") or "").strip()
            last_name = str(row.get("apellido") or "").strip()
            area_name = str(row.get("area") or "").strip()
            property_name = str(row.get("sede") or "").strip()

            status = "ok"
            action = "skip"
            message = ""

            if not document or not first_name or not last_name or not area_name:
                status = "error"
                message = "document, first name, last name and area are required"

            if status == "ok" and multiple_properties and not property_name:
                status = "error"
                message = "sede is required when file has mixed properties"

            property_obj = fallback_property
            if status == "ok" and property_name:
                property_obj = properties_by_name.get(property_name.lower())
                if property_obj is None:
                    status = "error"
                    message = f"unknown property: {property_name}"
                    summary["unknown_properties"] += 1

            if status == "ok":
                area_obj = Area.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    name__iexact=area_name,
                ).first()
                if area_obj is None and not create_missing_areas:
                    status = "error"
                    message = f"area does not exist: {area_name}"
                elif area_obj is None:
                    action = "create_area"
                    summary["new_areas"] += 1

            if status == "ok":
                exists = Worker.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    document_number=document,
                ).exists()
                action = "update" if exists else "create"
                if exists:
                    summary["updated"] += 1
                else:
                    summary["created"] += 1
            else:
                summary["errors"] += 1

            ImportPreviewRow.objects.create(
                batch=batch,
                sheet_name="workers_import",
                row_number=row_index,
                action=action,
                status=status,
                message=message,
                payload={
                    "document_number": document,
                    "first_name": first_name,
                    "last_name": last_name,
                    "area_name": area_name,
                    "property_name": property_name,
                    "property_id": property_obj.id if property_obj else None,
                },
            )

        batch.summary = summary
        batch.save(update_fields=["summary", "updated_at"])
        return batch

    @staticmethod
    def confirm_worker_import(*, batch):
        created = 0
        updated = 0
        new_areas = 0
        actor = batch.created_by
        rows = batch.preview_rows.filter(status="ok").order_by("row_number")
        for row in rows:
            payload = row.payload
            property_id = payload.get("property_id")
            if not property_id:
                continue
            area, area_created = Area.objects.get_or_create(
                tenant=batch.tenant,
                property_id=property_id,
                name=payload["area_name"],
                defaults={"type": "", "active": True},
            )
            if area_created:
                new_areas += 1
            worker, worker_created = Worker.objects.update_or_create(
                tenant=batch.tenant,
                property_id=property_id,
                document_number=payload["document_number"],
                defaults={
                    "first_name": payload["first_name"],
                    "last_name": payload["last_name"],
                    "area": area,
                    "active": True,
                },
            )
            if worker_created:
                created += 1
                if actor:
                    AuditService.log(
                        tenant=batch.tenant,
                        property_obj=worker.property,
                        user=actor,
                        action="worker_create_from_import",
                        entity_type="Worker",
                        entity_id=worker.id,
                        before={},
                        after={"document_number": worker.document_number},
                    )
            else:
                updated += 1
                if actor:
                    AuditService.log(
                        tenant=batch.tenant,
                        property_obj=worker.property,
                        user=actor,
                        action="worker_update_from_import",
                        entity_type="Worker",
                        entity_id=worker.id,
                        before={},
                        after={"document_number": worker.document_number},
                    )
        batch.summary = {
            **batch.summary,
            "applied_created": created,
            "applied_updated": updated,
            "applied_new_areas": new_areas,
        }
        batch.status = "confirmed"
        batch.save(update_fields=["summary", "status", "updated_at"])
        return batch


class ExcelImportApplyService:
    @staticmethod
    def _as_date(value):
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def apply_preview_batch(*, batch):
        created = {"areas": 0, "workers": 0, "shifts": 0, "special_states": 0, "assignments": 0}
        updated = {"workers": 0, "shifts": 0, "special_states": 0, "assignments": 0}
        warnings = 0

        rows = list(
            batch.preview_rows.filter(status__in=["ok", "warning"])
            .exclude(action="inspect")
        )
        stage_order = {"area": 1, "special_state": 2, "worker": 3, "shift": 4, "assignment": 5}
        rows.sort(
            key=lambda row: (
                stage_order.get((row.payload or {}).get("entity"), 99),
                row.sheet_name,
                row.row_number,
                row.id,
            )
        )
        for row in rows:
            payload = row.payload
            entity = payload.get("entity")
            property_id = payload.get("property_id") or batch.property_id

            if entity == "area":
                _, was_created = Area.objects.get_or_create(
                    tenant=batch.tenant,
                    property_id=property_id,
                    name=payload["name"],
                    defaults={"type": "", "active": True},
                )
                if was_created:
                    created["areas"] += 1

            elif entity == "special_state":
                _, was_created = SpecialState.objects.update_or_create(
                    tenant=batch.tenant,
                    property_id=property_id,
                    name=payload["name"],
                    defaults={"buk_code": payload.get("buk_code", "D"), "active": True},
                )
                if was_created:
                    created["special_states"] += 1
                else:
                    updated["special_states"] += 1

            elif entity == "worker":
                area, _ = Area.objects.get_or_create(
                    tenant=batch.tenant,
                    property_id=property_id,
                    name=payload["area_name"],
                    defaults={"type": "", "active": True},
                )
                _, was_created = Worker.objects.update_or_create(
                    tenant=batch.tenant,
                    property_id=property_id,
                    document_number=payload["document_number"],
                    defaults={
                        "first_name": payload["first_name"],
                        "last_name": payload["last_name"],
                        "area": area,
                        "active": True,
                    },
                )
                if was_created:
                    created["workers"] += 1
                else:
                    updated["workers"] += 1

            elif entity == "shift":
                area, _ = Area.objects.get_or_create(
                    tenant=batch.tenant,
                    property_id=property_id,
                    name=payload["area_name"],
                    defaults={"type": "", "active": True},
                )
                defaults = {
                    "buk_code": payload.get("buk_code", ""),
                    "start_time": ExcelImportService._parse_time(payload.get("start_time")) or time(0, 0),
                    "end_time": ExcelImportService._parse_time(payload.get("end_time")) or time(0, 0),
                    "break_start": ExcelImportService._parse_time(payload.get("break_start")),
                    "break_end": ExcelImportService._parse_time(payload.get("break_end")),
                    "is_night_shift": False,
                    "active": True,
                }
                _, was_created = Shift.objects.update_or_create(
                    tenant=batch.tenant,
                    property_id=property_id,
                    area=area,
                    name=payload["name"],
                    defaults=defaults,
                )
                if was_created:
                    created["shifts"] += 1
                else:
                    updated["shifts"] += 1

            elif entity == "assignment":
                worker = Worker.objects.filter(
                    tenant=batch.tenant,
                    property_id=property_id,
                    document_number=payload.get("document_number"),
                ).first()
                if not worker:
                    warnings += 1
                    continue

                shift = None
                special_state = None
                if payload.get("special_state_name"):
                    special_state = SpecialState.objects.filter(
                        tenant=batch.tenant,
                        property_id=property_id,
                        name__iexact=payload["special_state_name"],
                    ).first()
                    if special_state is None:
                        special_state = SpecialState.objects.create(
                            tenant=batch.tenant,
                            property_id=property_id,
                            name=payload["special_state_name"],
                            buk_code="D",
                            active=True,
                        )
                else:
                    area_name = payload.get("area_name", worker.area.name)
                    shift_name = payload.get("shift_name")
                    if shift_name:
                        shift = Shift.objects.filter(
                            tenant=batch.tenant,
                            property_id=property_id,
                            area__name__iexact=area_name,
                            name__iexact=shift_name,
                        ).first()
                    if not shift:
                        warnings += 1
                        continue

                _, was_created = ScheduleAssignment.objects.update_or_create(
                    tenant=batch.tenant,
                    property_id=property_id,
                    worker=worker,
                    date=ExcelImportApplyService._as_date(payload["date"]),
                    defaults={"shift": shift, "special_state": special_state, "updated_by": batch.created_by},
                )
                if was_created:
                    created["assignments"] += 1
                else:
                    updated["assignments"] += 1

        batch.status = "confirmed"
        batch.summary = {
            **batch.summary,
            "applied_created": created,
            "applied_updated": updated,
            "applied_warnings": warnings,
        }
        batch.save(update_fields=["status", "summary", "updated_at"])
        return batch
