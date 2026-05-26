from datetime import timedelta

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.access import (
    ensure_area_schedule,
    ensure_module_enabled,
    ensure_property_action,
    ensure_tenant_roles,
    resolve_access_context,
)
from apps.month_closure.services import MonthClosureService
from apps.scheduling.models import ScheduleAssignment
from apps.scheduling.serializers import ControlQuerySerializer, ScheduleAssignmentSerializer
from apps.scheduling.services import ScheduleAssignmentService
from apps.tenants.models import Property
from apps.users.services import PermissionService
from apps.workers.models import Worker


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
        date = serializer.validated_data["date"]
        ensure_tenant_roles(request, tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(request, tenant, self.module_key)
        ensure_property_action(request, tenant, property_obj, "can_schedule")

        worker = serializer.validated_data["worker"]
        if worker.property_id != property_obj.id:
            raise PermissionDenied("Worker no pertenece a la sede seleccionada.")
        ensure_area_schedule(request, tenant, property_obj, worker.area)

        if MonthClosureService.is_closed(
            tenant=tenant,
            property_obj=property_obj,
            year=date.year,
            month=date.month,
        ):
            return Response(
                {"detail": "El mes está cerrado para esta sede."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = ScheduleAssignmentService.upsert_assignment(
            tenant=tenant,
            property_obj=property_obj,
            worker=worker,
            date=date,
            shift=serializer.validated_data.get("shift"),
            special_state=serializer.validated_data.get("special_state"),
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
        if MonthClosureService.is_closed(
            tenant=tenant,
            property_obj=property_obj,
            year=instance.date.year,
            month=instance.date.month,
        ):
            raise PermissionDenied("El mes está cerrado para esta sede.")
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
            raise PermissionDenied("El mes está cerrado para esta sede.")
        instance.delete()

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
            index = {(a.worker_id, a.date): a for a in assignments}
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
