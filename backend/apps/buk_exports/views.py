from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.buk_exports.serializers import BukRangeSerializer
from apps.buk_exports.services import BukExportService, BukValidationService
from apps.common.access import ensure_module_enabled, ensure_property_action, ensure_tenant_roles, resolve_access_context


class BukExportViewSet(viewsets.ViewSet):
    def _resolve(self, request):
        serializer = BukRangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ctx = resolve_access_context(request, require_property=True)
        tenant = ctx.tenant
        property_obj = ctx.property
        ensure_tenant_roles(request, tenant, ["admin", "operator", "supervisor"])
        ensure_property_action(request, tenant, property_obj, "can_export_buk")
        return serializer, tenant, property_obj

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_range(self, request):
        serializer, tenant, property_obj = self._resolve(request)
        ensure_module_enabled(request, tenant, "buk_validator")
        issues = BukValidationService.validate_assignments(
            tenant=tenant,
            property_obj=property_obj,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
        )
        return Response(
            {
                "errors": [issue.__dict__ for issue in issues if issue.severity == "error"],
                "warnings": [issue.__dict__ for issue in issues if issue.severity == "warning"],
                "info": [issue.__dict__ for issue in issues if issue.severity == "info"],
            }
        )

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        serializer, tenant, property_obj = self._resolve(request)
        ensure_module_enabled(request, tenant, "buk_preview")
        rows = BukExportService.build_preview_rows(
            tenant=tenant,
            property_obj=property_obj,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
        )
        return Response({"rows": rows})

    @action(detail=False, methods=["post"], url_path="export")
    def export(self, request):
        serializer, tenant, property_obj = self._resolve(request)
        ensure_module_enabled(request, tenant, "buk_export")

        output_format = str(request.data.get("format", "xlsx")).strip().lower()
        issues = BukValidationService.validate_assignments(
            tenant=tenant,
            property_obj=property_obj,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
        )
        blocking_errors = [issue for issue in issues if issue.severity == "error"]
        if blocking_errors:
            return Response(
                {
                    "detail": "No se puede exportar por errores bloqueantes.",
                    "errors": [issue.__dict__ for issue in blocking_errors],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_base = (
            f"buk_{property_obj.slug}_{serializer.validated_data['date_from']}_{serializer.validated_data['date_to']}"
        )
        if output_format == "csv":
            content = BukExportService.generate_csv_text(
                tenant=tenant,
                property_obj=property_obj,
                date_from=serializer.validated_data["date_from"],
                date_to=serializer.validated_data["date_to"],
            )
            response = HttpResponse(content, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{file_base}.csv"'
            file_name = f"{file_base}.csv"
        else:
            content = BukExportService.generate_xlsx_bytes(
                tenant=tenant,
                property_obj=property_obj,
                date_from=serializer.validated_data["date_from"],
                date_to=serializer.validated_data["date_to"],
            )
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{file_base}.xlsx"'
            file_name = f"{file_base}.xlsx"

        log = BukExportService.log_export(
            tenant=tenant,
            property_obj=property_obj,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
            generated_by=request.user if request.user.is_authenticated else None,
            file_name=file_name,
            validation_issues=issues,
        )
        response["X-Buk-Export-Log-Id"] = str(log.id)
        return response
