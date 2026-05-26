from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.access import ensure_module_enabled, ensure_property_action, ensure_tenant_roles, resolve_access_context
from apps.imports.models import ImportBatch
from apps.imports.serializers import (
    ExcelPreviewRequestSerializer,
    ImportBatchSerializer,
    ImportPreviewRowSerializer,
    WorkerPreviewRequestSerializer,
)
from apps.imports.services import ExcelImportApplyService, ExcelImportService, WorkerImportService
from apps.tenants.models import Property
from apps.users.services import PermissionService


class ImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ImportBatch.objects.select_related("tenant", "property", "created_by").all()
    serializer_class = ImportBatchSerializer

    def get_queryset(self):
        if self.action in {"retrieve", "rows", "confirm", "cancel"} and "tenant_id" not in self.request.query_params:
            return super().get_queryset()
        ctx = resolve_access_context(self.request, require_property=False)
        ensure_tenant_roles(self.request, ctx.tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(self.request, ctx.tenant, "excel_import")
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
        return queryset

    def retrieve(self, request, *args, **kwargs):
        batch = self.get_object()
        ensure_tenant_roles(request, batch.tenant, ["admin", "operator", "supervisor"])
        ensure_module_enabled(request, batch.tenant, "excel_import")
        ensure_property_action(request, batch.tenant, batch.property, "can_access")
        return Response(ImportBatchSerializer(batch).data)

    @action(detail=True, methods=["get"], url_path="rows")
    def rows(self, request, pk=None):
        batch = self.get_object()
        ensure_module_enabled(request, batch.tenant, "excel_import")
        ensure_property_action(request, batch.tenant, batch.property, "can_access")
        serializer = ImportPreviewRowSerializer(batch.preview_rows.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        batch = self.get_object()
        ensure_module_enabled(request, batch.tenant, "excel_import")
        ensure_property_action(request, batch.tenant, batch.property, "can_manage_workers")
        if batch.status != "preview":
            return Response({"detail": "El lote ya no está en preview."}, status=status.HTTP_400_BAD_REQUEST)

        if batch.source_type == "workers":
            batch = WorkerImportService.confirm_worker_import(batch=batch)
        elif batch.source_type == "excel_original":
            batch = ExcelImportApplyService.apply_preview_batch(batch=batch)
        else:
            batch.status = "confirmed"
            batch.save(update_fields=["status", "updated_at"])
        return Response(ImportBatchSerializer(batch).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        batch = self.get_object()
        ensure_module_enabled(request, batch.tenant, "excel_import")
        ensure_property_action(request, batch.tenant, batch.property, "can_manage_workers")
        batch.status = "cancelled"
        batch.save(update_fields=["status", "updated_at"])
        return Response(ImportBatchSerializer(batch).data)

    @action(detail=False, methods=["post"], url_path="excel-preview")
    def excel_preview(self, request):
        serializer = ExcelPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ctx = resolve_access_context(request, require_property=True)
        tenant = ctx.tenant
        property_obj = ctx.property
        ensure_tenant_roles(request, tenant, ["admin", "operator"])
        ensure_module_enabled(request, tenant, "excel_import")
        ensure_property_action(request, tenant, property_obj, "can_manage_workers")
        uploaded_file = serializer.validated_data["file"]
        batch = ExcelImportService.create_preview(
            tenant=tenant,
            property_obj=property_obj,
            file_name=uploaded_file.name,
            file_bytes=uploaded_file.read(),
            user=request.user if request.user.is_authenticated else None,
        )
        return Response(ImportBatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="workers-preview")
    def workers_preview(self, request):
        serializer = WorkerPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ctx = resolve_access_context(request, require_property=False)
        tenant = ctx.tenant
        ensure_tenant_roles(request, tenant, ["admin", "operator"])
        ensure_module_enabled(request, tenant, "excel_import")

        property_id = serializer.validated_data.get("property_id")
        fallback_property = None
        if ctx.property:
            fallback_property = ctx.property
            ensure_property_action(request, tenant, fallback_property, "can_manage_workers")
        elif property_id:
            fallback_property = Property.objects.get(pk=property_id, tenant=tenant)
            ensure_property_action(request, tenant, fallback_property, "can_manage_workers")
        elif tenant.properties.exists():
            fallback_property = tenant.properties.order_by("id").first()
            ensure_property_action(request, tenant, fallback_property, "can_manage_workers")
        else:
            return Response(
                {"detail": "El tenant no tiene sedes configuradas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = serializer.validated_data["file"]
        try:
            batch = WorkerImportService.create_worker_preview(
                tenant=tenant,
                fallback_property=fallback_property,
                file_name=uploaded_file.name,
                file_bytes=uploaded_file.read(),
                user=request.user if request.user.is_authenticated else None,
                create_missing_areas=serializer.validated_data["create_missing_areas"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ImportBatchSerializer(batch).data, status=status.HTTP_201_CREATED)
