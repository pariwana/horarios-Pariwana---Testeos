import json
from datetime import date, datetime, time

from apps.buk_exports.models import BukExportConfig
from apps.month_closure.models import MonthClosure, MonthClosureStatus
from apps.scheduling.models import ScheduleAssignment
from apps.workers.models import Area, Shift, SpecialState, Worker


class BackupRestoreService:
    @staticmethod
    def _serialize_date(value):
        return value.isoformat() if value else None

    @staticmethod
    def _serialize_time(value):
        return value.strftime("%H:%M:%S") if value else None

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _parse_time(value):
        if not value:
            return None
        if isinstance(value, time):
            return value
        text = str(value).strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(text, fmt).time()
            except ValueError:
                continue
        return None

    @staticmethod
    def create_backup_payload(*, tenant, property_obj):
        areas = list(Area.objects.filter(tenant=tenant, property=property_obj).order_by("name"))
        states = list(SpecialState.objects.filter(tenant=tenant, property=property_obj).order_by("name"))
        shifts = list(
            Shift.objects.filter(tenant=tenant, property=property_obj)
            .select_related("area")
            .order_by("area__name", "name")
        )
        workers = list(
            Worker.objects.filter(tenant=tenant, property=property_obj)
            .select_related("area")
            .order_by("last_name", "first_name")
        )
        assignments = list(
            ScheduleAssignment.objects.filter(tenant=tenant, property=property_obj)
            .select_related("worker", "shift", "special_state")
            .order_by("date", "worker__last_name", "worker__first_name")
        )
        closures = list(
            MonthClosure.objects.filter(tenant=tenant, property=property_obj)
            .order_by("year", "month")
        )
        config = BukExportConfig.objects.filter(tenant=tenant, property=property_obj).first()

        payload = {
            "meta": {
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "tenant_slug": tenant.slug,
                "property_slug": property_obj.slug,
                "property_name": property_obj.name,
            },
            "areas": [
                {"name": item.name, "type": item.type, "active": item.active}
                for item in areas
            ],
            "special_states": [
                {"name": item.name, "buk_code": item.buk_code, "active": item.active}
                for item in states
            ],
            "shifts": [
                {
                    "area_name": item.area.name,
                    "name": item.name,
                    "buk_code": item.buk_code,
                    "start_time": BackupRestoreService._serialize_time(item.start_time),
                    "end_time": BackupRestoreService._serialize_time(item.end_time),
                    "break_start": BackupRestoreService._serialize_time(item.break_start),
                    "break_end": BackupRestoreService._serialize_time(item.break_end),
                    "is_night_shift": item.is_night_shift,
                    "active": item.active,
                }
                for item in shifts
            ],
            "workers": [
                {
                    "document_number": item.document_number,
                    "first_name": item.first_name,
                    "last_name": item.last_name,
                    "area_name": item.area.name,
                    "active": item.active,
                    "start_date": BackupRestoreService._serialize_date(item.start_date),
                    "end_date": BackupRestoreService._serialize_date(item.end_date),
                    "buk_employee_code": item.buk_employee_code,
                    "metadata": item.metadata or {},
                }
                for item in workers
            ],
            "assignments": [
                {
                    "document_number": item.worker.document_number,
                    "date": item.date.isoformat(),
                    "shift_name": item.shift.name if item.shift_id else None,
                    "special_state_name": item.special_state.name if item.special_state_id else None,
                }
                for item in assignments
            ],
            "month_closures": [
                {
                    "year": item.year,
                    "month": item.month,
                    "status": item.status,
                }
                for item in closures
            ],
            "buk_export_config": (
                {
                    "sheet_name": config.sheet_name,
                    "date_format": config.date_format,
                    "include_area": config.include_area,
                    "include_worker_name": config.include_worker_name,
                    "document_column_name": config.document_column_name,
                    "name_column_name": config.name_column_name,
                    "area_column_name": config.area_column_name,
                    "header_row": config.header_row,
                    "first_data_row": config.first_data_row,
                    "export_format": config.export_format,
                    "other_settings": config.other_settings or {},
                }
                if config
                else None
            ),
        }
        return payload

    @staticmethod
    def payload_to_json_bytes(payload):
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    @staticmethod
    def preview_restore_from_payload(*, tenant, property_obj, payload, sync_mode=False):
        created = {"areas": 0, "special_states": 0, "shifts": 0, "workers": 0, "assignments": 0, "month_closures": 0}
        updated = {"areas": 0, "special_states": 0, "shifts": 0, "workers": 0, "assignments": 0, "month_closures": 0}
        skipped = {"areas": 0, "special_states": 0, "shifts": 0, "workers": 0, "assignments": 0, "month_closures": 0}

        existing_areas = {
            item.name.strip().lower()
            for item in Area.objects.filter(tenant=tenant, property=property_obj)
        }
        existing_states = {
            item.name.strip().lower()
            for item in SpecialState.objects.filter(tenant=tenant, property=property_obj)
        }
        existing_shifts = {
            (item.area.name.strip().lower(), item.name.strip().lower())
            for item in Shift.objects.filter(tenant=tenant, property=property_obj).select_related("area")
        }
        existing_workers = {
            item.document_number.strip()
            for item in Worker.objects.filter(tenant=tenant, property=property_obj)
        }
        existing_closures = {
            (item.year, item.month)
            for item in MonthClosure.objects.filter(tenant=tenant, property=property_obj)
        }

        incoming_areas = set()
        for item in payload.get("areas", []):
            area_name = str(item.get("name", "")).strip()
            if not area_name:
                skipped["areas"] += 1
                continue
            key = area_name.lower()
            incoming_areas.add(key)
            if key in existing_areas:
                updated["areas"] += 1
            else:
                created["areas"] += 1

        available_areas = existing_areas.union(incoming_areas)

        incoming_states = set()
        for item in payload.get("special_states", []):
            state_name = str(item.get("name", "")).strip()
            if not state_name:
                skipped["special_states"] += 1
                continue
            key = state_name.lower()
            incoming_states.add(key)
            if key in existing_states:
                updated["special_states"] += 1
            else:
                created["special_states"] += 1

        available_states = existing_states.union(incoming_states)

        incoming_shifts = set()
        for item in payload.get("shifts", []):
            area_name = str(item.get("area_name", "")).strip().lower()
            shift_name = str(item.get("name", "")).strip().lower()
            if not area_name or not shift_name or area_name not in available_areas:
                skipped["shifts"] += 1
                continue
            key = (area_name, shift_name)
            incoming_shifts.add(key)
            if key in existing_shifts:
                updated["shifts"] += 1
            else:
                created["shifts"] += 1

        available_shifts = existing_shifts.union(incoming_shifts)

        incoming_workers = set()
        worker_area_by_doc = {}
        for item in payload.get("workers", []):
            document_number = str(item.get("document_number", "")).strip()
            area_name = str(item.get("area_name", "")).strip().lower()
            if not document_number or area_name not in available_areas:
                skipped["workers"] += 1
                continue
            incoming_workers.add(document_number)
            worker_area_by_doc[document_number] = area_name
            if document_number in existing_workers:
                updated["workers"] += 1
            else:
                created["workers"] += 1

        available_workers = existing_workers.union(incoming_workers)

        existing_assignments = {
            (item.worker.document_number.strip(), item.date.isoformat())
            for item in ScheduleAssignment.objects.filter(tenant=tenant, property=property_obj).select_related("worker")
        }
        for item in payload.get("assignments", []):
            document_number = str(item.get("document_number", "")).strip()
            assignment_date = str(item.get("date", "")).strip()
            if not document_number or not assignment_date or document_number not in available_workers:
                skipped["assignments"] += 1
                continue

            has_state = bool(str(item.get("special_state_name", "")).strip())
            has_shift = bool(str(item.get("shift_name", "")).strip())
            if has_state:
                if str(item.get("special_state_name", "")).strip().lower() not in available_states:
                    skipped["assignments"] += 1
                    continue
            elif has_shift:
                area_name = worker_area_by_doc.get(document_number)
                if area_name is None:
                    # worker existed previamente: buscamos area en DB
                    worker_obj = Worker.objects.filter(
                        tenant=tenant,
                        property=property_obj,
                        document_number=document_number,
                    ).select_related("area").first()
                    area_name = worker_obj.area.name.strip().lower() if worker_obj else None
                shift_key = (area_name, str(item.get("shift_name", "")).strip().lower())
                if not area_name or shift_key not in available_shifts:
                    skipped["assignments"] += 1
                    continue
            else:
                skipped["assignments"] += 1
                continue

            key = (document_number, assignment_date)
            if key in existing_assignments:
                updated["assignments"] += 1
            else:
                created["assignments"] += 1

        for item in payload.get("month_closures", []):
            try:
                year = int(item.get("year"))
                month = int(item.get("month"))
            except (TypeError, ValueError):
                skipped["month_closures"] += 1
                continue
            key = (year, month)
            if key in existing_closures:
                updated["month_closures"] += 1
            else:
                created["month_closures"] += 1

        deactivated = {"workers": 0, "shifts": 0, "special_states": 0}
        if sync_mode:
            if "workers" in payload:
                incoming_worker_docs = {
                    str(item.get("document_number", "")).strip()
                    for item in payload.get("workers", [])
                    if str(item.get("document_number", "")).strip()
                }
                deactivated["workers"] = Worker.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    active=True,
                ).exclude(document_number__in=incoming_worker_docs).count()

            if "shifts" in payload:
                incoming_shift_keys = set()
                for item in payload.get("shifts", []):
                    area_name = str(item.get("area_name", "")).strip().lower()
                    shift_name = str(item.get("name", "")).strip().lower()
                    if area_name and shift_name:
                        incoming_shift_keys.add((area_name, shift_name))
                for item in Shift.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    active=True,
                ).select_related("area"):
                    key = (item.area.name.strip().lower(), item.name.strip().lower())
                    if key not in incoming_shift_keys:
                        deactivated["shifts"] += 1

            if "special_states" in payload:
                incoming_state_names = {
                    str(item.get("name", "")).strip().lower()
                    for item in payload.get("special_states", [])
                    if str(item.get("name", "")).strip()
                }
                deactivated["special_states"] = SpecialState.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    active=True,
                ).exclude(name__in=incoming_state_names).count()

        return {"created": created, "updated": updated, "skipped": skipped, "deactivated": deactivated}

    @staticmethod
    def restore_from_payload(*, tenant, property_obj, payload, sync_mode=False):
        created = {"areas": 0, "special_states": 0, "shifts": 0, "workers": 0, "assignments": 0, "month_closures": 0}
        updated = {"areas": 0, "special_states": 0, "shifts": 0, "workers": 0, "assignments": 0, "month_closures": 0}

        area_map = {}
        for item in payload.get("areas", []):
            obj, was_created = Area.objects.update_or_create(
                tenant=tenant,
                property=property_obj,
                name=item.get("name", ""),
                defaults={
                    "type": item.get("type", ""),
                    "active": bool(item.get("active", True)),
                },
            )
            area_map[obj.name.lower()] = obj
            created["areas"] += 1 if was_created else 0
            updated["areas"] += 0 if was_created else 1

        state_map = {}
        for item in payload.get("special_states", []):
            obj, was_created = SpecialState.objects.update_or_create(
                tenant=tenant,
                property=property_obj,
                name=item.get("name", ""),
                defaults={
                    "buk_code": item.get("buk_code", ""),
                    "active": bool(item.get("active", True)),
                },
            )
            state_map[obj.name.lower()] = obj
            created["special_states"] += 1 if was_created else 0
            updated["special_states"] += 0 if was_created else 1

        shift_map = {}
        for item in payload.get("shifts", []):
            area_name = str(item.get("area_name", "")).strip().lower()
            area_obj = area_map.get(area_name)
            if area_obj is None:
                continue
            obj, was_created = Shift.objects.update_or_create(
                tenant=tenant,
                property=property_obj,
                area=area_obj,
                name=item.get("name", ""),
                defaults={
                    "buk_code": item.get("buk_code", ""),
                    "start_time": BackupRestoreService._parse_time(item.get("start_time")) or time(0, 0),
                    "end_time": BackupRestoreService._parse_time(item.get("end_time")) or time(0, 0),
                    "break_start": BackupRestoreService._parse_time(item.get("break_start")),
                    "break_end": BackupRestoreService._parse_time(item.get("break_end")),
                    "is_night_shift": bool(item.get("is_night_shift", False)),
                    "active": bool(item.get("active", True)),
                },
            )
            shift_map[(area_obj.name.lower(), obj.name.lower())] = obj
            created["shifts"] += 1 if was_created else 0
            updated["shifts"] += 0 if was_created else 1

        worker_map = {}
        incoming_worker_docs = set()
        for item in payload.get("workers", []):
            area_name = str(item.get("area_name", "")).strip().lower()
            area_obj = area_map.get(area_name)
            if area_obj is None:
                continue
            document_number = str(item.get("document_number", "")).strip()
            if not document_number:
                continue
            incoming_worker_docs.add(document_number)
            obj, was_created = Worker.objects.update_or_create(
                tenant=tenant,
                property=property_obj,
                document_number=document_number,
                defaults={
                    "first_name": item.get("first_name", ""),
                    "last_name": item.get("last_name", ""),
                    "area": area_obj,
                    "active": bool(item.get("active", True)),
                    "start_date": BackupRestoreService._parse_date(item.get("start_date")),
                    "end_date": BackupRestoreService._parse_date(item.get("end_date")),
                    "buk_employee_code": item.get("buk_employee_code"),
                    "metadata": item.get("metadata") or {},
                },
            )
            worker_map[obj.document_number] = obj
            created["workers"] += 1 if was_created else 0
            updated["workers"] += 0 if was_created else 1

        for item in payload.get("assignments", []):
            document_number = str(item.get("document_number", "")).strip()
            worker = worker_map.get(document_number)
            if worker is None:
                continue

            shift = None
            special_state = None
            if item.get("special_state_name"):
                special_state = state_map.get(str(item["special_state_name"]).strip().lower())
            elif item.get("shift_name"):
                shift = shift_map.get((worker.area.name.lower(), str(item["shift_name"]).strip().lower()))

            if shift is None and special_state is None:
                continue

            obj, was_created = ScheduleAssignment.objects.update_or_create(
                tenant=tenant,
                property=property_obj,
                worker=worker,
                date=BackupRestoreService._parse_date(item.get("date")),
                defaults={
                    "shift": shift,
                    "special_state": special_state,
                },
            )
            created["assignments"] += 1 if was_created else 0
            updated["assignments"] += 0 if was_created else 1

        for item in payload.get("month_closures", []):
            status = str(item.get("status", MonthClosureStatus.OPEN))
            if status not in {MonthClosureStatus.OPEN, MonthClosureStatus.CLOSED}:
                status = MonthClosureStatus.OPEN
            obj, was_created = MonthClosure.objects.update_or_create(
                tenant=tenant,
                property=property_obj,
                year=int(item.get("year")),
                month=int(item.get("month")),
                defaults={"status": status},
            )
            created["month_closures"] += 1 if was_created else 0
            updated["month_closures"] += 0 if was_created else 1

        config_payload = payload.get("buk_export_config")
        if config_payload:
            BukExportConfig.objects.update_or_create(
                tenant=tenant,
                property=property_obj,
                defaults={
                    "sheet_name": config_payload.get("sheet_name", "Reporte carga BUK"),
                    "date_format": config_payload.get("date_format", "%d-%m-%Y"),
                    "include_area": bool(config_payload.get("include_area", True)),
                    "include_worker_name": bool(config_payload.get("include_worker_name", True)),
                    "document_column_name": config_payload.get("document_column_name", "RUT"),
                    "name_column_name": config_payload.get("name_column_name", "Nombre"),
                    "area_column_name": config_payload.get("area_column_name", "Área"),
                    "header_row": int(config_payload.get("header_row", 2)),
                    "first_data_row": int(config_payload.get("first_data_row", 3)),
                    "export_format": config_payload.get("export_format", "xlsx"),
                    "other_settings": config_payload.get("other_settings") or {},
                },
            )

        deactivated = {"workers": 0, "shifts": 0, "special_states": 0}
        if sync_mode:
            if "workers" in payload:
                deactivated["workers"] = Worker.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    active=True,
                ).exclude(document_number__in=incoming_worker_docs).update(active=False)

            if "shifts" in payload:
                incoming_shift_keys = set()
                for item in payload.get("shifts", []):
                    area_name = str(item.get("area_name", "")).strip().lower()
                    shift_name = str(item.get("name", "")).strip().lower()
                    if area_name and shift_name:
                        incoming_shift_keys.add((area_name, shift_name))
                deactivate_shift_ids = []
                for item in Shift.objects.filter(tenant=tenant, property=property_obj, active=True).select_related("area"):
                    key = (item.area.name.strip().lower(), item.name.strip().lower())
                    if key not in incoming_shift_keys:
                        deactivate_shift_ids.append(item.id)
                if deactivate_shift_ids:
                    deactivated["shifts"] = Shift.objects.filter(id__in=deactivate_shift_ids).update(active=False)

            if "special_states" in payload:
                incoming_state_names = {
                    str(item.get("name", "")).strip()
                    for item in payload.get("special_states", [])
                    if str(item.get("name", "")).strip()
                }
                deactivated["special_states"] = SpecialState.objects.filter(
                    tenant=tenant,
                    property=property_obj,
                    active=True,
                ).exclude(name__in=incoming_state_names).update(active=False)

        return {"created": created, "updated": updated, "deactivated": deactivated}
