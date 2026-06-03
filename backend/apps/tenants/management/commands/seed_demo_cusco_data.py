from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.modules.models import ModuleActivation
from apps.scheduling.services import ScheduleAssignmentService
from apps.tenants.models import Property, Tenant, TenantStatus
from apps.workers.models import Area, Shift, SpecialState, Worker


INITIAL_MODULES = [
    "tenants",
    "properties",
    "users_permissions",
    "module_activation",
    "workers",
    "areas",
    "shifts",
    "special_states",
    "scheduling",
    "control",
    "buk_validator",
    "buk_preview",
    "buk_export",
    "excel_import",
    "audit",
    "month_closure",
]

AREAS = [
    ("Recepción", "operativa"),
    ("Housekeeping", "operativa"),
    ("Bar", "operativa"),
    ("Cocina", "operativa"),
]

SPECIAL_STATES = [
    ("OFF", "OFF"),
    ("VACACIONES", "VAC"),
    ("DESCANSO MEDICO", "DM"),
]

SHIFT_DEFINITIONS = [
    ("Recepción", "Recepción_Manana", "REC-M", "07:00", "15:00"),
    ("Recepción", "Recepción_Tarde", "REC-T", "15:00", "23:00"),
    ("Recepción", "Recepción_Noche", "REC-N", "23:00", "07:00"),
    ("Housekeeping", "Housekeeping_Manana", "HK-M", "08:00", "16:45"),
    ("Housekeeping", "Housekeeping_Tarde", "HK-T", "13:30", "22:15"),
    ("Bar", "Bar_Tarde", "BAR-T", "15:15", "00:00"),
    ("Cocina", "Cocina_Manana", "COC-M", "06:00", "14:45"),
    ("Cocina", "Cocina_Tarde", "COC-T", "14:45", "23:00"),
]

WORKERS = [
    ("70100101", "Ana", "Quispe", "Recepción"),
    ("70100102", "Luis", "Rojas", "Recepción"),
    ("70100103", "Mariela", "Puma", "Recepción"),
    ("70100201", "Karla", "Huaman", "Housekeeping"),
    ("70100202", "Jorge", "Solis", "Housekeeping"),
    ("70100203", "Martha", "Mamani", "Housekeeping"),
    ("70100301", "Diego", "Flores", "Bar"),
    ("70100302", "Camila", "Paredes", "Bar"),
    ("70100303", "Jose", "Vasquez", "Bar"),
    ("70100401", "Rocio", "Lopez", "Cocina"),
    ("70100402", "Enzo", "Paz", "Cocina"),
    ("70100403", "Luz", "Suarez", "Cocina"),
]


class Command(BaseCommand):
    help = "Seed demo operational data for Pariwana Cusco (areas, shifts, workers, assignments)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-date",
            default=None,
            help="Start date in YYYY-MM-DD. Default: server local date.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=15,
            help="Number of days to generate assignments from start date (default: 15).",
        )

    def handle(self, *args, **options):
        start_date = timezone.localdate()
        start_date_raw = options.get("start_date")
        if start_date_raw:
            start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
        days = max(1, int(options.get("days") or 15))

        tenant, _ = Tenant.objects.get_or_create(
            slug="pariwana-hostels",
            defaults={
                "name": "Pariwana Hostels",
                "status": TenantStatus.ACTIVE,
                "settings": {},
            },
        )

        for property_name in ["Pariwana Lima", "Pariwana Cusco"]:
            Property.objects.get_or_create(
                tenant=tenant,
                slug=slugify(property_name),
                defaults={"name": property_name, "status": TenantStatus.ACTIVE, "location": ""},
            )

        for module_key in INITIAL_MODULES:
            ModuleActivation.objects.get_or_create(
                tenant=tenant,
                module_key=module_key,
                defaults={"is_enabled": True},
            )

        cusco = Property.objects.get(tenant=tenant, slug="pariwana-cusco")

        areas_map = {}
        for area_name, area_type in AREAS:
            area, _ = Area.objects.update_or_create(
                tenant=tenant,
                property=cusco,
                name=area_name,
                defaults={"type": area_type, "active": True},
            )
            areas_map[area_name] = area

        states_map = {}
        for state_name, buk_code in SPECIAL_STATES:
            state, _ = SpecialState.objects.update_or_create(
                tenant=tenant,
                property=cusco,
                name=state_name,
                defaults={"buk_code": buk_code, "active": True},
            )
            states_map[state_name] = state

        shifts_by_area = {}
        for area_name, shift_name, buk_code, start_time, end_time in SHIFT_DEFINITIONS:
            area = areas_map[area_name]
            start_time_value = datetime.strptime(start_time, "%H:%M").time()
            end_time_value = datetime.strptime(end_time, "%H:%M").time()
            shift = Shift.objects.filter(
                tenant=tenant,
                property=cusco,
                buk_code=buk_code,
            ).first()
            if shift is None:
                shift = Shift.objects.filter(
                    tenant=tenant,
                    property=cusco,
                    area=area,
                    name=shift_name,
                ).first()

            if shift is None:
                shift = Shift.objects.create(
                    tenant=tenant,
                    property=cusco,
                    area=area,
                    name=shift_name,
                    buk_code=buk_code,
                    start_time=start_time_value,
                    end_time=end_time_value,
                    is_night_shift=end_time_value <= start_time_value,
                    active=True,
                )
            else:
                shift.area = area
                shift.name = shift_name
                # Evita colisionar con otro turno existente que ya usa este codigo.
                same_code_other = (
                    Shift.objects.filter(
                        tenant=tenant,
                        property=cusco,
                        buk_code=buk_code,
                    )
                    .exclude(id=shift.id)
                    .exists()
                )
                if not same_code_other:
                    shift.buk_code = buk_code
                shift.start_time = start_time_value
                shift.end_time = end_time_value
                shift.is_night_shift = end_time_value <= start_time_value
                shift.active = True
                shift.save()
            shifts_by_area.setdefault(area_name, []).append(shift)

        worker_rows = []
        for document_number, first_name, last_name, area_name in WORKERS:
            area = areas_map[area_name]
            worker, _ = Worker.objects.update_or_create(
                tenant=tenant,
                property=cusco,
                document_number=document_number,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "area": area,
                    "active": True,
                    "metadata": {},
                },
            )
            worker_rows.append((worker, area_name))

        off_state = states_map["OFF"]
        created_or_updated = 0
        for worker, area_name in worker_rows:
            area_shifts = shifts_by_area.get(area_name, [])
            if not area_shifts:
                continue
            for offset in range(days):
                target_date = start_date + timedelta(days=offset)
                if target_date.weekday() == 6:
                    ScheduleAssignmentService.upsert_assignment(
                        tenant=tenant,
                        property_obj=cusco,
                        worker=worker,
                        date=target_date,
                        shift=None,
                        special_state=off_state,
                        user=None,
                    )
                    created_or_updated += 1
                    continue
                shift = area_shifts[offset % len(area_shifts)]
                ScheduleAssignmentService.upsert_assignment(
                    tenant=tenant,
                    property_obj=cusco,
                    worker=worker,
                    date=target_date,
                    shift=shift,
                    special_state=None,
                    user=None,
                )
                created_or_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo seed ready: tenant={tenant.slug}, property={cusco.slug}, "
                f"workers={len(worker_rows)}, assignments_upserted={created_or_updated}, "
                f"range={start_date.isoformat()}..{(start_date + timedelta(days=days - 1)).isoformat()}",
            )
        )
