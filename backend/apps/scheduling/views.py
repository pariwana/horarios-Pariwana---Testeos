import calendar
from datetime import date, timedelta

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.audit.services import AuditService
from apps.common.access import (
    ensure_area_schedule,
    ensure_module_enabled,
    ensure_property_action,
    ensure_tenant_roles,
    resolve_access_context,
)
from apps.month_closure.services import MonthClosureService
from apps.scheduling.models import ScheduleAssignment, SchedulePatternTemplate
from apps.scheduling.serializers import (
    ApplyWeekPatternTemplateSerializer,
    BulkWeekPatternSerializer,
    BulkRangeStateSerializer,
    BulkSundaysStateSerializer,
    ControlQuerySerializer,
    CopyPreviousMonthSerializer,
    CopyWeekSerializer,
    DeleteWeekPatternTemplateSerializer,
    SaveWeekPatternTemplateSerializer,
    ScheduleAssignmentSerializer,
    UpdateWeekPatternTemplateSerializer,
)
from apps.scheduling.services import ScheduleAssignmentService
from apps.tenants.models import Property
from apps.users.services import PermissionService
from apps.workers.models import Area, Shift, SpecialState, Worker

WEEK_PATTERN_KEYS = [
    ("monday", 0),
    ("tuesday", 1),
    ("wednesday", 2),
    ("thursday", 3),
    ("friday", 4),
    ("saturday", 5),
    ("sunday", 6),
]


class ScheduleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = ScheduleAssignment.objects.select_related(
        "tenant",
        "property",
        "worker",
        "worker__area",
        "shift",
        "special_state",
    ).all()
    serializer_class = ScheduleAssignmentSerializer
    module_key = "scheduling"

    def get_queryset(self):
        ctx = resolve_access_context(self.request, require_property=False)
        ensure_tenant_roles(self.request, ctx.tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(self.request, ctx.tenant, self.module_key)

        queryset = super().get_queryset().filter(tenant=ctx.tenant)
        if ctx.property:
            ensure_property_action(self.request, ctx.tenant, ctx.property, "can_access")
            queryset = queryset.filter(property=ctx.property)
        elif not PermissionService.is_super_admin(self.request.user):
            property_ids = PermissionService.get_accessible_property_ids(
                self.request.user,
                ctx.tenant,
                action="can_access",
            )
            queryset = queryset.filter(property_id__in=property_ids)

        area_ids = PermissionService.get_accessible_area_ids(
            self.request.user,
            ctx.tenant,
            ctx.property,
            action="can_view",
        )
        queryset = queryset.filter(worker__area_id__in=area_ids)

        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.validated_data["tenant"]
        property_obj = serializer.validated_data["property"]
        assignment_date = serializer.validated_data["date"]
        ensure_tenant_roles(request, tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(request, tenant, self.module_key)
        ensure_property_action(request, tenant, property_obj, "can_schedule")

        worker = serializer.validated_data["worker"]
        shift = serializer.validated_data.get("shift")
        special_state = serializer.validated_data.get("special_state")
        if property_obj.tenant_id != tenant.id:
            raise ValidationError("La sede no pertenece al tenant seleccionado.")
        if worker.tenant_id != tenant.id or worker.property_id != property_obj.id:
            raise PermissionDenied("El trabajador no pertenece al tenant y sede seleccionados.")
        if shift and (shift.tenant_id != tenant.id or shift.property_id != property_obj.id):
            raise PermissionDenied("El turno no pertenece al tenant y sede seleccionados.")
        if special_state and (
            special_state.tenant_id != tenant.id or special_state.property_id != property_obj.id
        ):
            raise PermissionDenied("El estado especial no pertenece al tenant y sede seleccionados.")
        ensure_area_schedule(request, tenant, property_obj, worker.area)
        if shift:
            ensure_area_schedule(request, tenant, property_obj, shift.area)

        if MonthClosureService.is_closed(
            tenant=tenant,
            property_obj=property_obj,
            year=assignment_date.year,
            month=assignment_date.month,
        ):
            return Response(
                {"detail": "El mes esta cerrado para esta sede."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = ScheduleAssignmentService.upsert_assignment(
            tenant=tenant,
            property_obj=property_obj,
            worker=worker,
            date=assignment_date,
            shift=shift,
            special_state=special_state,
            user=request.user if request.user.is_authenticated else None,
        )
        return Response(
            self.get_serializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        tenant = instance.tenant
        property_obj = instance.property
        ensure_tenant_roles(self.request, tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(self.request, tenant, self.module_key)
        ensure_property_action(self.request, tenant, property_obj, "can_schedule")
        ensure_area_schedule(self.request, tenant, property_obj, instance.worker.area)

        target_tenant = serializer.validated_data.get("tenant", instance.tenant)
        target_property = serializer.validated_data.get("property", instance.property)
        target_worker = serializer.validated_data.get("worker", instance.worker)
        target_shift = serializer.validated_data.get("shift", instance.shift)
        target_special_state = serializer.validated_data.get("special_state", instance.special_state)
        target_date = serializer.validated_data.get("date", instance.date)
        if target_property.tenant_id != target_tenant.id:
            raise ValidationError("La sede no pertenece al tenant seleccionado.")
        if target_worker.tenant_id != target_tenant.id or target_worker.property_id != target_property.id:
            raise ValidationError("El trabajador no pertenece al tenant y sede seleccionados.")
        if target_shift and (
            target_shift.tenant_id != target_tenant.id or target_shift.property_id != target_property.id
        ):
            raise ValidationError("El turno no pertenece al tenant y sede seleccionados.")
        if target_special_state and (
            target_special_state.tenant_id != target_tenant.id
            or target_special_state.property_id != target_property.id
        ):
            raise ValidationError("El estado especial no pertenece al tenant y sede seleccionados.")
        ensure_tenant_roles(self.request, target_tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(self.request, target_tenant, self.module_key)
        ensure_property_action(self.request, target_tenant, target_property, "can_schedule")
        ensure_area_schedule(self.request, target_tenant, target_property, target_worker.area)
        if target_shift:
            ensure_area_schedule(self.request, target_tenant, target_property, target_shift.area)
        if MonthClosureService.is_closed(
            tenant=target_tenant,
            property_obj=target_property,
            year=target_date.year,
            month=target_date.month,
        ):
            raise PermissionDenied("El mes esta cerrado para esta sede.")
        serializer.save(updated_by=self.request.user if self.request.user.is_authenticated else None)

    def perform_destroy(self, instance):
        ensure_tenant_roles(self.request, instance.tenant, ["admin", "operator"])
        ensure_module_enabled(self.request, instance.tenant, self.module_key)
        ensure_property_action(self.request, instance.tenant, instance.property, "can_schedule")
        if MonthClosureService.is_closed(
            tenant=instance.tenant,
            property_obj=instance.property,
            year=instance.date.year,
            month=instance.date.month,
        ):
            raise PermissionDenied("El mes esta cerrado para esta sede.")
        instance.delete()

    def _resolve_bulk_context(self, request):
        ctx = resolve_access_context(request, require_property=True)
        tenant = ctx.tenant
        property_obj = ctx.property
        ensure_tenant_roles(request, tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(request, tenant, self.module_key)
        ensure_property_action(request, tenant, property_obj, "can_schedule")
        return tenant, property_obj

    @staticmethod
    def _is_any_month_closed(*, tenant, property_obj, start_date, end_date):
        cursor = start_date
        while cursor <= end_date:
            if MonthClosureService.is_closed(
                tenant=tenant,
                property_obj=property_obj,
                year=cursor.year,
                month=cursor.month,
            ):
                return True
            next_month = cursor.replace(day=28) + timedelta(days=4)
            cursor = next_month.replace(day=1)
        return False

    def _get_target_workers(self, *, request, tenant, property_obj, area_id=None, worker_ids=None):
        workers = Worker.objects.select_related("area").filter(
            tenant=tenant,
            property=property_obj,
            active=True,
        )
        if area_id:
            workers = workers.filter(area_id=area_id)
        if worker_ids:
            workers = workers.filter(id__in=worker_ids)
        visible_workers = []
        for worker in workers:
            if PermissionService.user_can_area_schedule(request.user, tenant, property_obj, worker.area):
                visible_workers.append(worker)
        return visible_workers

    @staticmethod
    def _copy_assignment(*, tenant, property_obj, worker, target_date, source_assignment, user, copy_kind="all"):
        if source_assignment is None:
            return False
        shift, special_state = ScheduleAssignmentViewSet._resolve_copy_payload(
            source_assignment=source_assignment,
            copy_kind=copy_kind,
        )
        if shift is None and special_state is None:
            return False
        ScheduleAssignmentService.upsert_assignment(
            tenant=tenant,
            property_obj=property_obj,
            worker=worker,
            date=target_date,
            shift=shift,
            special_state=special_state,
            user=user,
        )
        return True

    @staticmethod
    def _resolve_copy_payload(*, source_assignment, copy_kind):
        shift = None
        special_state = None
        if copy_kind == "shift":
            if source_assignment.shift_id is None:
                return None, None
            shift = source_assignment.shift
        elif copy_kind == "state":
            if source_assignment.special_state_id is None:
                return None, None
            special_state = source_assignment.special_state
        else:
            shift = source_assignment.shift
            special_state = source_assignment.special_state
        return shift, special_state

    @staticmethod
    def _summarize_assignment_plans(*, tenant, property_obj, plans):
        if not plans:
            return {"total": 0, "to_create": 0, "to_update": 0, "unchanged": 0}
        worker_ids = sorted({item["worker"].id for item in plans.values()})
        min_date = min(item["date"] for item in plans.values())
        max_date = max(item["date"] for item in plans.values())
        existing_map = {
            (item.worker_id, item.date): item
            for item in ScheduleAssignment.objects.filter(
                tenant=tenant,
                property=property_obj,
                worker_id__in=worker_ids,
                date__gte=min_date,
                date__lte=max_date,
            )
        }
        to_create = 0
        to_update = 0
        unchanged = 0
        for key, plan in plans.items():
            current = existing_map.get(key)
            target_shift_id = plan["shift"].id if plan["shift"] is not None else None
            target_state_id = plan["special_state"].id if plan["special_state"] is not None else None
            if current is None:
                to_create += 1
                continue
            if current.shift_id == target_shift_id and current.special_state_id == target_state_id:
                unchanged += 1
            else:
                to_update += 1
        return {
            "total": len(plans),
            "to_create": to_create,
            "to_update": to_update,
            "unchanged": unchanged,
        }

    @staticmethod
    def _extract_week_pattern_from_validated(validated_data):
        pattern = {}
        has_any_value = False
        for key, weekday in WEEK_PATTERN_KEYS:
            value = str(validated_data.get(f"{key}_value", "")).strip()
            pattern[weekday] = value
            if value:
                has_any_value = True
        return pattern, has_any_value

    @staticmethod
    def _serialize_week_pattern(pattern):
        serialized = {}
        for key, weekday in WEEK_PATTERN_KEYS:
            serialized[key] = str(pattern.get(weekday, "")).strip()
        return serialized

    @staticmethod
    def _deserialize_week_pattern(pattern_dict):
        source = pattern_dict or {}
        parsed = {}
        for key, weekday in WEEK_PATTERN_KEYS:
            parsed[weekday] = str(source.get(key, "")).strip()
        return parsed

    @staticmethod
    def _resolve_assignment_value_for_worker(*, assignment_value, worker, shifts_map, states_map):
        raw_value = str(assignment_value or "").strip()
        if not raw_value:
            return None, None, "empty"
        if raw_value.startswith("shift:"):
            shift_id = raw_value.split(":", 1)[1].strip()
            if not shift_id.isdigit():
                return None, None, "invalid"
            shift = shifts_map.get(int(shift_id))
            if shift is None or shift.area_id != worker.area_id:
                return None, None, "invalid"
            return shift, None, None
        if raw_value.startswith("state:"):
            state_id = raw_value.split(":", 1)[1].strip()
            if not state_id.isdigit():
                return None, None, "invalid"
            state = states_map.get(int(state_id))
            if state is None:
                return None, None, "invalid"
            return None, state, None
        return None, None, "invalid"

    @action(detail=False, methods=["post"], url_path="bulk-range-state")
    def bulk_range_state(self, request):
        serializer = BulkRangeStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        special_state = SpecialState.objects.filter(
            id=serializer.validated_data["special_state_id"],
            tenant=tenant,
            property=property_obj,
            active=True,
        ).first()
        if special_state is None:
            return Response({"detail": "Estado especial invalido."}, status=status.HTTP_400_BAD_REQUEST)

        date_from = serializer.validated_data["date_from"]
        date_to = serializer.validated_data["date_to"]
        if self._is_any_month_closed(
            tenant=tenant,
            property_obj=property_obj,
            start_date=date_from,
            end_date=date_to,
        ):
            return Response(
                {"detail": "El rango incluye un mes cerrado para esta sede."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        area_id = serializer.validated_data.get("area_id")
        worker_ids = serializer.validated_data.get("worker_ids") or []
        workers = self._get_target_workers(
            request=request,
            tenant=tenant,
            property_obj=property_obj,
            area_id=area_id,
            worker_ids=worker_ids,
        )

        plans = {}
        total_days = (date_to - date_from).days + 1
        for worker in workers:
            for offset in range(total_days):
                target_date = date_from + timedelta(days=offset)
                plans[(worker.id, target_date)] = {
                    "worker": worker,
                    "date": target_date,
                    "shift": None,
                    "special_state": special_state,
                }

        dry_run = bool(serializer.validated_data.get("dry_run", False))
        stats = self._summarize_assignment_plans(tenant=tenant, property_obj=property_obj, plans=plans)
        if dry_run:
            return Response(
                {
                    "dry_run": True,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "special_state_id": special_state.id,
                    "impact": stats,
                }
            )

        applied = 0
        for plan in plans.values():
            ScheduleAssignmentService.upsert_assignment(
                tenant=tenant,
                property_obj=property_obj,
                worker=plan["worker"],
                date=plan["date"],
                shift=plan["shift"],
                special_state=plan["special_state"],
                user=request.user if request.user.is_authenticated else None,
            )
            applied += 1

        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="scheduling_bulk_range_state_apply",
            entity_type="ScheduleAssignment",
            entity_id=f"{property_obj.id}:{date_from.isoformat()}:{date_to.isoformat()}",
            before={},
            after={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "special_state_id": special_state.id,
                "special_state_code": special_state.buk_code or "",
                "applied": applied,
                "impact": stats,
                "selected_workers": len(worker_ids),
                "area_filter": area_id,
            },
        )
        return Response(
            {
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "special_state_id": special_state.id,
                "applied": applied,
            }
        )

    @action(detail=False, methods=["post"], url_path="bulk-sundays-state")
    def bulk_sundays_state(self, request):
        serializer = BulkSundaysStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        year = serializer.validated_data["year"]
        month = serializer.validated_data["month"]
        if MonthClosureService.is_closed(
            tenant=tenant,
            property_obj=property_obj,
            year=year,
            month=month,
        ):
            return Response({"detail": "El mes esta cerrado para esta sede."}, status=status.HTTP_400_BAD_REQUEST)

        special_state = SpecialState.objects.filter(
            id=serializer.validated_data["special_state_id"],
            tenant=tenant,
            property=property_obj,
            active=True,
        ).first()
        if special_state is None:
            return Response({"detail": "Estado especial invalido."}, status=status.HTTP_400_BAD_REQUEST)

        _, total_days = calendar.monthrange(year, month)
        sunday_dates = [
            date(year, month, day)
            for day in range(1, total_days + 1)
            if date(year, month, day).weekday() == 6
        ]

        area_id = serializer.validated_data.get("area_id")
        worker_ids = serializer.validated_data.get("worker_ids") or []
        workers = self._get_target_workers(
            request=request,
            tenant=tenant,
            property_obj=property_obj,
            area_id=area_id,
            worker_ids=worker_ids,
        )

        plans = {}
        for worker in workers:
            for sunday_date in sunday_dates:
                plans[(worker.id, sunday_date)] = {
                    "worker": worker,
                    "date": sunday_date,
                    "shift": None,
                    "special_state": special_state,
                }

        dry_run = bool(serializer.validated_data.get("dry_run", False))
        stats = self._summarize_assignment_plans(tenant=tenant, property_obj=property_obj, plans=plans)
        if dry_run:
            return Response(
                {
                    "dry_run": True,
                    "year": year,
                    "month": month,
                    "special_state_id": special_state.id,
                    "sundays": len(sunday_dates),
                    "applied": len(plans),
                    "impact": stats,
                }
            )

        applied = 0
        for plan in plans.values():
            ScheduleAssignmentService.upsert_assignment(
                tenant=tenant,
                property_obj=property_obj,
                worker=plan["worker"],
                date=plan["date"],
                shift=plan["shift"],
                special_state=plan["special_state"],
                user=request.user if request.user.is_authenticated else None,
            )
            applied += 1

        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="scheduling_bulk_sundays_state_apply",
            entity_type="ScheduleAssignment",
            entity_id=f"{property_obj.id}:{year:04d}-{month:02d}",
            before={},
            after={
                "year": year,
                "month": month,
                "special_state_id": special_state.id,
                "special_state_code": special_state.buk_code or "",
                "sundays": len(sunday_dates),
                "applied": applied,
                "impact": stats,
                "selected_workers": len(worker_ids),
                "area_filter": area_id,
            },
        )
        return Response(
            {
                "year": year,
                "month": month,
                "special_state_id": special_state.id,
                "sundays": len(sunday_dates),
                "applied": applied,
            }
        )

    @action(detail=False, methods=["post"], url_path="copy-week")
    def copy_week(self, request):
        serializer = CopyWeekSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        source_start = serializer.validated_data["source_week_start"]
        target_start = serializer.validated_data["target_week_start"]
        target_end = target_start + timedelta(days=6)
        if self._is_any_month_closed(
            tenant=tenant,
            property_obj=property_obj,
            start_date=target_start,
            end_date=target_end,
        ):
            return Response(
                {"detail": "La semana destino incluye un mes cerrado para esta sede."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        area_id = serializer.validated_data.get("area_id")
        worker_ids = serializer.validated_data.get("worker_ids") or []
        workers = self._get_target_workers(
            request=request,
            tenant=tenant,
            property_obj=property_obj,
            area_id=area_id,
            worker_ids=worker_ids,
        )

        source_end = source_start + timedelta(days=6)
        source_assignments = ScheduleAssignment.objects.select_related("shift", "special_state").filter(
            tenant=tenant,
            property=property_obj,
            worker_id__in=[worker.id for worker in workers],
            date__gte=source_start,
            date__lte=source_end,
        )
        source_index = {(item.worker_id, item.date): item for item in source_assignments}

        plans = {}
        copy_kind = serializer.validated_data.get("copy_kind", "all")
        for worker in workers:
            for offset in range(7):
                from_date = source_start + timedelta(days=offset)
                to_date = target_start + timedelta(days=offset)
                source_assignment = source_index.get((worker.id, from_date))
                if source_assignment is None:
                    continue
                shift, special_state = self._resolve_copy_payload(
                    source_assignment=source_assignment,
                    copy_kind=copy_kind,
                )
                if shift is None and special_state is None:
                    continue
                plans[(worker.id, to_date)] = {
                    "worker": worker,
                    "date": to_date,
                    "shift": shift,
                    "special_state": special_state,
                }

        dry_run = bool(serializer.validated_data.get("dry_run", False))
        stats = self._summarize_assignment_plans(tenant=tenant, property_obj=property_obj, plans=plans)
        if dry_run:
            return Response(
                {
                    "dry_run": True,
                    "source_week_start": source_start.isoformat(),
                    "target_week_start": target_start.isoformat(),
                    "copy_kind": copy_kind,
                    "copied": len(plans),
                    "impact": stats,
                }
            )

        copied = 0
        for plan in plans.values():
            ScheduleAssignmentService.upsert_assignment(
                tenant=tenant,
                property_obj=property_obj,
                worker=plan["worker"],
                date=plan["date"],
                shift=plan["shift"],
                special_state=plan["special_state"],
                user=request.user if request.user.is_authenticated else None,
            )
            copied += 1

        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="scheduling_copy_week_apply",
            entity_type="ScheduleAssignment",
            entity_id=f"{property_obj.id}:{source_start.isoformat()}:{target_start.isoformat()}",
            before={},
            after={
                "source_week_start": source_start.isoformat(),
                "target_week_start": target_start.isoformat(),
                "copy_kind": copy_kind,
                "copied": copied,
                "impact": stats,
                "selected_workers": len(worker_ids),
                "area_filter": area_id,
            },
        )
        return Response(
            {
                "source_week_start": source_start.isoformat(),
                "target_week_start": target_start.isoformat(),
                "copy_kind": copy_kind,
                "copied": copied,
            }
        )

    @action(detail=False, methods=["post"], url_path="copy-previous-month")
    def copy_previous_month(self, request):
        serializer = CopyPreviousMonthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        year = serializer.validated_data["target_year"]
        month = serializer.validated_data["target_month"]
        if MonthClosureService.is_closed(
            tenant=tenant,
            property_obj=property_obj,
            year=year,
            month=month,
        ):
            return Response({"detail": "El mes esta cerrado para esta sede."}, status=status.HTTP_400_BAD_REQUEST)

        first_day = date(year, month, 1)
        prev_month_last_day = first_day - timedelta(days=1)
        prev_year = prev_month_last_day.year
        prev_month = prev_month_last_day.month
        _, target_days = calendar.monthrange(year, month)
        _, source_days = calendar.monthrange(prev_year, prev_month)

        area_id = serializer.validated_data.get("area_id")
        worker_ids = serializer.validated_data.get("worker_ids") or []
        workers = self._get_target_workers(
            request=request,
            tenant=tenant,
            property_obj=property_obj,
            area_id=area_id,
            worker_ids=worker_ids,
        )

        source_start = date(prev_year, prev_month, 1)
        source_end = date(prev_year, prev_month, source_days)
        source_assignments = ScheduleAssignment.objects.select_related("shift", "special_state").filter(
            tenant=tenant,
            property=property_obj,
            worker_id__in=[worker.id for worker in workers],
            date__gte=source_start,
            date__lte=source_end,
        )
        source_index = {(item.worker_id, item.date): item for item in source_assignments}

        plans = {}
        copy_kind = serializer.validated_data.get("copy_kind", "all")
        for worker in workers:
            max_day = min(target_days, source_days)
            for day in range(1, max_day + 1):
                from_date = date(prev_year, prev_month, day)
                to_date = date(year, month, day)
                source_assignment = source_index.get((worker.id, from_date))
                if source_assignment is None:
                    continue
                shift, special_state = self._resolve_copy_payload(
                    source_assignment=source_assignment,
                    copy_kind=copy_kind,
                )
                if shift is None and special_state is None:
                    continue
                plans[(worker.id, to_date)] = {
                    "worker": worker,
                    "date": to_date,
                    "shift": shift,
                    "special_state": special_state,
                }

        dry_run = bool(serializer.validated_data.get("dry_run", False))
        stats = self._summarize_assignment_plans(tenant=tenant, property_obj=property_obj, plans=plans)
        if dry_run:
            return Response(
                {
                    "dry_run": True,
                    "target_year": year,
                    "target_month": month,
                    "source_year": prev_year,
                    "source_month": prev_month,
                    "copy_kind": copy_kind,
                    "copied": len(plans),
                    "impact": stats,
                }
            )

        copied = 0
        for plan in plans.values():
            ScheduleAssignmentService.upsert_assignment(
                tenant=tenant,
                property_obj=property_obj,
                worker=plan["worker"],
                date=plan["date"],
                shift=plan["shift"],
                special_state=plan["special_state"],
                user=request.user if request.user.is_authenticated else None,
            )
            copied += 1

        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="scheduling_copy_previous_month_apply",
            entity_type="ScheduleAssignment",
            entity_id=f"{property_obj.id}:{year:04d}-{month:02d}",
            before={},
            after={
                "target_year": year,
                "target_month": month,
                "source_year": prev_year,
                "source_month": prev_month,
                "copy_kind": copy_kind,
                "copied": copied,
                "impact": stats,
                "selected_workers": len(worker_ids),
                "area_filter": area_id,
            },
        )
        return Response(
            {
                "target_year": year,
                "target_month": month,
                "source_year": prev_year,
                "source_month": prev_month,
                "copy_kind": copy_kind,
                "copied": copied,
            }
        )

    @action(detail=False, methods=["get"], url_path="week-pattern-templates")
    def week_pattern_templates(self, request):
        tenant, property_obj = self._resolve_bulk_context(request)
        area_id_raw = str(request.query_params.get("area_id", "")).strip()
        templates = SchedulePatternTemplate.objects.filter(
            tenant=tenant,
            property=property_obj,
        ).select_related("area", "updated_by")
        if area_id_raw.isdigit():
            templates = templates.filter(area_id=int(area_id_raw))
        rows = [
            {
                "id": item.id,
                "name": item.name,
                "active": item.active,
                "area_id": item.area_id,
                "area_name": item.area.name if item.area_id else None,
                "pattern": item.pattern,
                "updated_by": item.updated_by.email if item.updated_by_id else None,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in templates.order_by("name", "id")
        ]
        return Response({"results": rows})

    @action(detail=False, methods=["post"], url_path="save-week-pattern-template")
    def save_week_pattern_template(self, request):
        serializer = SaveWeekPatternTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        template_name = serializer.validated_data["template_name"].strip()
        area_obj = None
        area_id = serializer.validated_data.get("area_id")
        if area_id is not None:
            area_obj = Area.objects.filter(
                id=area_id,
                tenant=tenant,
                property=property_obj,
                active=True,
            ).first()
            if area_obj is None:
                return Response({"detail": "Area invalida para guardar plantilla."}, status=status.HTTP_400_BAD_REQUEST)

        day_pattern, has_any_value = self._extract_week_pattern_from_validated(serializer.validated_data)
        if not has_any_value:
            return Response(
                {"detail": "Debe seleccionar al menos un turno/estado para guardar plantilla."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        template, created = SchedulePatternTemplate.objects.get_or_create(
            tenant=tenant,
            property=property_obj,
            area=area_obj,
            name=template_name,
            defaults={
                "pattern": self._serialize_week_pattern(day_pattern),
                "created_by": request.user if request.user.is_authenticated else None,
                "updated_by": request.user if request.user.is_authenticated else None,
            },
        )
        before = self._serialize_week_pattern(template.pattern)
        template.pattern = self._serialize_week_pattern(day_pattern)
        template.updated_by = request.user if request.user.is_authenticated else None
        template.active = True
        template.full_clean()
        template.save()

        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="schedule_pattern_template_save",
            entity_type="SchedulePatternTemplate",
            entity_id=template.id,
            before=before,
            after=template.pattern,
        )
        return Response(
            {
                "id": template.id,
                "name": template.name,
                "active": template.active,
                "area_id": template.area_id,
                "created": created,
            }
        )

    @action(detail=False, methods=["post"], url_path="update-week-pattern-template")
    def update_week_pattern_template(self, request):
        serializer = UpdateWeekPatternTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        template = SchedulePatternTemplate.objects.filter(
            id=serializer.validated_data["template_id"],
            tenant=tenant,
            property=property_obj,
        ).first()
        if template is None:
            return Response({"detail": "Plantilla no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        before = {
            "name": template.name,
            "active": template.active,
            "pattern": template.pattern,
        }
        template.name = serializer.validated_data["template_name"].strip()
        if "active" in serializer.validated_data:
            template.active = bool(serializer.validated_data["active"])
        template.updated_by = request.user if request.user.is_authenticated else None
        try:
            template.full_clean()
            template.save()
        except (IntegrityError, ValueError):
            return Response(
                {"detail": "No se pudo actualizar la plantilla (nombre duplicado o invalido)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="schedule_pattern_template_update",
            entity_type="SchedulePatternTemplate",
            entity_id=template.id,
            before=before,
            after={
                "name": template.name,
                "active": template.active,
                "pattern": template.pattern,
            },
        )
        return Response(
            {
                "id": template.id,
                "name": template.name,
                "active": template.active,
            }
        )

    @action(detail=False, methods=["post"], url_path="delete-week-pattern-template")
    def delete_week_pattern_template(self, request):
        serializer = DeleteWeekPatternTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        template = SchedulePatternTemplate.objects.filter(
            id=serializer.validated_data["template_id"],
            tenant=tenant,
            property=property_obj,
        ).first()
        if template is None:
            return Response({"detail": "Plantilla no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        before = {
            "name": template.name,
            "active": template.active,
            "pattern": template.pattern,
        }
        template_id = template.id
        template.delete()
        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="schedule_pattern_template_delete",
            entity_type="SchedulePatternTemplate",
            entity_id=template_id,
            before=before,
            after={},
        )
        return Response({"deleted": True, "id": template_id})

    @action(detail=False, methods=["post"], url_path="apply-week-pattern-template")
    def apply_week_pattern_template(self, request):
        serializer = ApplyWeekPatternTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        template = SchedulePatternTemplate.objects.filter(
            id=serializer.validated_data["template_id"],
            tenant=tenant,
            property=property_obj,
            active=True,
        ).first()
        if template is None:
            return Response({"detail": "Plantilla no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        area_id = serializer.validated_data.get("area_id")
        if template.area_id and area_id != template.area_id:
            return Response(
                {"detail": "Esta plantilla requiere filtrar por su area antes de aplicarla."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_from = serializer.validated_data["date_from"]
        date_to = serializer.validated_data["date_to"]
        if self._is_any_month_closed(
            tenant=tenant,
            property_obj=property_obj,
            start_date=date_from,
            end_date=date_to,
        ):
            return Response(
                {"detail": "El rango incluye un mes cerrado para esta sede."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        worker_ids = serializer.validated_data.get("worker_ids") or []
        workers = self._get_target_workers(
            request=request,
            tenant=tenant,
            property_obj=property_obj,
            area_id=area_id,
            worker_ids=worker_ids,
        )
        day_pattern = self._deserialize_week_pattern(template.pattern)
        shifts_map = {
            item.id: item
            for item in Shift.objects.filter(tenant=tenant, property=property_obj, active=True).select_related("area")
        }
        states_map = {
            item.id: item
            for item in SpecialState.objects.filter(tenant=tenant, property=property_obj, active=True)
        }

        plans = {}
        skipped_invalid = 0
        total_days = (date_to - date_from).days + 1
        for worker in workers:
            for offset in range(total_days):
                target_date = date_from + timedelta(days=offset)
                assignment_value = day_pattern.get(target_date.weekday(), "")
                shift, special_state, error = self._resolve_assignment_value_for_worker(
                    assignment_value=assignment_value,
                    worker=worker,
                    shifts_map=shifts_map,
                    states_map=states_map,
                )
                if error == "empty":
                    continue
                if error is not None:
                    skipped_invalid += 1
                    continue
                plans[(worker.id, target_date)] = {
                    "worker": worker,
                    "date": target_date,
                    "shift": shift,
                    "special_state": special_state,
                }

        dry_run = bool(serializer.validated_data.get("dry_run", False))
        stats = self._summarize_assignment_plans(tenant=tenant, property_obj=property_obj, plans=plans)
        if dry_run:
            return Response(
                {
                    "dry_run": True,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "applied": len(plans),
                    "skipped_invalid": skipped_invalid,
                    "impact": stats,
                }
            )

        applied = 0
        for plan in plans.values():
            ScheduleAssignmentService.upsert_assignment(
                tenant=tenant,
                property_obj=property_obj,
                worker=plan["worker"],
                date=plan["date"],
                shift=plan["shift"],
                special_state=plan["special_state"],
                user=request.user if request.user.is_authenticated else None,
            )
            applied += 1

        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="schedule_pattern_template_apply",
            entity_type="SchedulePatternTemplate",
            entity_id=template.id,
            before={},
            after={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "applied": applied,
                "skipped_invalid": skipped_invalid,
                "impact": stats,
            },
        )
        return Response(
            {
                "template_id": template.id,
                "applied": applied,
                "skipped_invalid": skipped_invalid,
                "impact": stats,
            }
        )

    @action(detail=False, methods=["post"], url_path="bulk-week-pattern")
    def bulk_week_pattern(self, request):
        serializer = BulkWeekPatternSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant, property_obj = self._resolve_bulk_context(request)

        date_from = serializer.validated_data["date_from"]
        date_to = serializer.validated_data["date_to"]
        if self._is_any_month_closed(
            tenant=tenant,
            property_obj=property_obj,
            start_date=date_from,
            end_date=date_to,
        ):
            return Response(
                {"detail": "El rango incluye un mes cerrado para esta sede."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        day_pattern, has_any_value = self._extract_week_pattern_from_validated(serializer.validated_data)
        if not has_any_value:
            return Response(
                {"detail": "Debe seleccionar al menos un turno/estado en el patron semanal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        area_id = serializer.validated_data.get("area_id")
        worker_ids = serializer.validated_data.get("worker_ids") or []
        workers = self._get_target_workers(
            request=request,
            tenant=tenant,
            property_obj=property_obj,
            area_id=area_id,
            worker_ids=worker_ids,
        )
        shifts_map = {
            item.id: item
            for item in Shift.objects.filter(tenant=tenant, property=property_obj, active=True).select_related("area")
        }
        states_map = {
            item.id: item
            for item in SpecialState.objects.filter(tenant=tenant, property=property_obj, active=True)
        }

        plans = {}
        skipped_invalid = 0
        total_days = (date_to - date_from).days + 1
        for worker in workers:
            for offset in range(total_days):
                target_date = date_from + timedelta(days=offset)
                assignment_value = day_pattern.get(target_date.weekday(), "")
                shift, special_state, error = self._resolve_assignment_value_for_worker(
                    assignment_value=assignment_value,
                    worker=worker,
                    shifts_map=shifts_map,
                    states_map=states_map,
                )
                if error == "empty":
                    continue
                if error is not None:
                    skipped_invalid += 1
                    continue
                plans[(worker.id, target_date)] = {
                    "worker": worker,
                    "date": target_date,
                    "shift": shift,
                    "special_state": special_state,
                }

        dry_run = bool(serializer.validated_data.get("dry_run", False))
        stats = self._summarize_assignment_plans(tenant=tenant, property_obj=property_obj, plans=plans)
        if dry_run:
            return Response(
                {
                    "dry_run": True,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "applied": len(plans),
                    "skipped_invalid": skipped_invalid,
                    "impact": stats,
                }
            )

        applied = 0
        for plan in plans.values():
            ScheduleAssignmentService.upsert_assignment(
                tenant=tenant,
                property_obj=property_obj,
                worker=plan["worker"],
                date=plan["date"],
                shift=plan["shift"],
                special_state=plan["special_state"],
                user=request.user if request.user.is_authenticated else None,
            )
            applied += 1

        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="scheduling_bulk_week_pattern_apply",
            entity_type="ScheduleAssignment",
            entity_id=f"{property_obj.id}:{date_from.isoformat()}:{date_to.isoformat()}",
            before={},
            after={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "applied": applied,
                "skipped_invalid": skipped_invalid,
                "impact": stats,
                "selected_workers": len(worker_ids),
                "area_filter": area_id,
            },
        )
        return Response(
            {
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "applied": applied,
                "skipped_invalid": skipped_invalid,
                "impact": stats,
            }
        )

    @action(detail=False, methods=["get"], url_path="control-next-15-days")
    def control_next_15_days(self, request):
        serializer = ControlQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        ctx = resolve_access_context(request, require_property=False)
        tenant = ctx.tenant
        ensure_tenant_roles(request, tenant, ["admin", "operator"])
        ensure_module_enabled(request, tenant, "control")

        properties = Property.objects.filter(tenant=tenant, status="active")
        if ctx.property:
            properties = properties.filter(pk=ctx.property.id)
        else:
            property_id = serializer.validated_data.get("property_id")
            if property_id:
                properties = properties.filter(pk=property_id)
        if not PermissionService.is_super_admin(request.user):
            allowed_property_ids = PermissionService.get_accessible_property_ids(
                request.user,
                tenant,
                action="can_schedule",
            )
            properties = properties.filter(id__in=allowed_property_ids)

        start = timezone.localdate()
        end = start + timedelta(days=14)
        report = []

        for property_obj in properties:
            workers = Worker.objects.filter(
                tenant=tenant,
                property=property_obj,
                active=True,
            ).select_related("area")
            assignments = ScheduleAssignment.objects.filter(
                tenant=tenant,
                property=property_obj,
                date__gte=start,
                date__lte=end,
            ).select_related("worker")
            index = {(item.worker_id, item.date): item for item in assignments}
            pending_rows = []
            for worker in workers:
                for offset in range(15):
                    day = start + timedelta(days=offset)
                    assignment = index.get((worker.id, day))
                    if not assignment or (not assignment.shift_id and not assignment.special_state_id):
                        pending_rows.append(
                            {
                                "date": day.isoformat(),
                                "worker_id": worker.id,
                                "worker_name": f"{worker.first_name} {worker.last_name}",
                                "document_number": worker.document_number,
                                "area": worker.area.name,
                            }
                        )
            report.append(
                {
                    "property_id": property_obj.id,
                    "property_name": property_obj.name,
                    "pending_count": len(pending_rows),
                    "rows": pending_rows,
                }
            )

        return Response(
            {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "properties": report,
            }
        )
