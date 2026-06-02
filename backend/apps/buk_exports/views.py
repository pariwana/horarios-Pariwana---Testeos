import json
from datetime import date
from io import StringIO
import csv

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import AuditService
from apps.buk_exports.models import BukTemplateCompareLog
from apps.buk_exports.serializers import BukRangeSerializer, BukTemplateCompareSerializer
from apps.buk_exports.services import BukExportService, BukValidationService
from apps.common.access import ensure_module_enabled, ensure_property_action, ensure_tenant_roles, resolve_access_context
from apps.users.services import PermissionService


class BukExportViewSet(viewsets.ViewSet):
    @staticmethod
    def _as_bool(value):
        return str(value).strip().lower() in {"1", "true", "on", "yes"}

    @staticmethod
    def _area_ids_from_request(request):
        values = request.data.get("area_ids")
        if values is None:
            return []
        if isinstance(values, (list, tuple)):
            raw_items = values
        else:
            raw_items = [values]
        result = []
        for item in raw_items:
            text = str(item).strip()
            if text.isdigit():
                result.append(int(text))
        return result

    @staticmethod
    def _worker_ids_from_request(request):
        values = request.data.get("worker_ids")
        if values is None:
            return []
        if isinstance(values, (list, tuple)):
            raw_items = values
        else:
            raw_items = [values]
        result = []
        for item in raw_items:
            text = str(item).strip()
            if text.isdigit():
                result.append(int(text))
        return result

    @staticmethod
    def _is_compatible_filter(raw_value):
        value = str(raw_value or "").strip().lower()
        if value in {"1", "true", "yes", "compatible"}:
            return True
        if value in {"0", "false", "no", "incompatible"}:
            return False
        return None

    @staticmethod
    def _parse_iso_date(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    def _build_compare_logs_queryset(self, request, *, tenant, property_obj):
        queryset = BukTemplateCompareLog.objects.filter(
            tenant=tenant,
            property=property_obj,
        ).select_related("compared_by")
        compatible_value = self._is_compatible_filter(request.query_params.get("is_compatible"))
        if compatible_value is not None:
            queryset = queryset.filter(is_compatible=compatible_value)
        user_query = str(request.query_params.get("user", "")).strip()
        if user_query:
            queryset = queryset.filter(compared_by__email__icontains=user_query)
        compared_from = self._parse_iso_date(request.query_params.get("compared_from"))
        compared_to = self._parse_iso_date(request.query_params.get("compared_to"))
        if compared_from:
            queryset = queryset.filter(compared_at__date__gte=compared_from)
        if compared_to:
            queryset = queryset.filter(compared_at__date__lte=compared_to)
        return queryset, compatible_value, user_query, compared_from, compared_to

    def _resolve(self, request, serializer_class=BukRangeSerializer):
        serializer = serializer_class(data=request.data)
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
        area_ids = self._area_ids_from_request(request)
        worker_ids = self._worker_ids_from_request(request)
        issues = BukValidationService.validate_assignments(
            tenant=tenant,
            property_obj=property_obj,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
            area_ids=area_ids,
            worker_ids=worker_ids,
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
        area_ids = self._area_ids_from_request(request)
        worker_ids = self._worker_ids_from_request(request)
        rows = BukExportService.build_preview_rows(
            tenant=tenant,
            property_obj=property_obj,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
            area_ids=area_ids,
            worker_ids=worker_ids,
        )
        return Response({"rows": rows})

    @action(detail=False, methods=["post"], url_path="export")
    def export(self, request):
        serializer, tenant, property_obj = self._resolve(request)
        ensure_module_enabled(request, tenant, "buk_export")

        output_format = str(request.data.get("format", "xlsx")).strip().lower()
        export_with_observations = self._as_bool(request.data.get("export_with_observations"))
        area_ids = self._area_ids_from_request(request)
        worker_ids = self._worker_ids_from_request(request)
        issues = BukValidationService.validate_assignments(
            tenant=tenant,
            property_obj=property_obj,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
            area_ids=area_ids,
            worker_ids=worker_ids,
        )
        blocking_errors = [issue for issue in issues if issue.severity == "error"]
        if blocking_errors:
            is_admin = PermissionService.user_can_tenant_role(request.user, tenant, ["admin"])
            if export_with_observations and not is_admin:
                return Response(
                    {"detail": "Solo administradores pueden exportar con observaciones."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if export_with_observations and is_admin:
                pass
            else:
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
                area_ids=area_ids,
                worker_ids=worker_ids,
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
                area_ids=area_ids,
                worker_ids=worker_ids,
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
            export_with_observations=export_with_observations,
        )
        response["X-Buk-Export-Log-Id"] = str(log.id)
        return response

    @action(detail=False, methods=["post"], url_path="compare-template")
    def compare_template(self, request):
        serializer, tenant, property_obj = self._resolve(request, serializer_class=BukTemplateCompareSerializer)
        ensure_module_enabled(request, tenant, "buk_preview")
        area_ids = self._area_ids_from_request(request)
        worker_ids = self._worker_ids_from_request(request)
        candidate = BukExportService.generate_xlsx_bytes(
            tenant=tenant,
            property_obj=property_obj,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
            area_ids=area_ids,
            worker_ids=worker_ids,
        )
        reference_file = serializer.validated_data["reference_file"]
        reference_file_name = getattr(reference_file, "name", "") or ""
        reference_file_bytes = reference_file.read()
        sheet_name = serializer.validated_data.get("sheet_name", "Reporte carga BUK")
        result = BukExportService.compare_template_compatibility(
            reference_file_bytes=reference_file_bytes,
            candidate_file_bytes=candidate,
            sheet_name=sheet_name,
        )
        compare_log = BukExportService.log_template_compare(
            tenant=tenant,
            property_obj=property_obj,
            compared_by=request.user if request.user.is_authenticated else None,
            date_from=serializer.validated_data["date_from"],
            date_to=serializer.validated_data["date_to"],
            sheet_name=sheet_name,
            reference_file_name=reference_file_name,
            reference_file_bytes=reference_file_bytes,
            result=result,
        )
        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="buk_compare_template",
            entity_type="BukTemplateCompareLog",
            entity_id=compare_log.id,
            before={},
            after={
                "date_from": serializer.validated_data["date_from"].isoformat(),
                "date_to": serializer.validated_data["date_to"].isoformat(),
                "sheet_name": sheet_name,
                "reference_file_name": reference_file_name,
                "is_compatible": bool(result.get("is_compatible", False)),
                "errors_count": len(result.get("errors") or []),
                "warnings_count": len(result.get("warnings") or []),
            },
        )
        result["compare_log_id"] = compare_log.id
        if serializer.validated_data.get("download_report", False):
            payload = {
                "tenant": tenant.slug,
                "property": property_obj.slug,
                "date_from": serializer.validated_data["date_from"].isoformat(),
                "date_to": serializer.validated_data["date_to"].isoformat(),
                "sheet_name": sheet_name,
                "result": result,
            }
            file_name = (
                f"buk_template_compare_{property_obj.slug}_"
                f"{serializer.validated_data['date_from']}_{serializer.validated_data['date_to']}.json"
            )
            response = HttpResponse(
                json.dumps(payload, ensure_ascii=False, indent=2),
                content_type="application/json; charset=utf-8",
            )
            response["Content-Disposition"] = f'attachment; filename="{file_name}"'
            return response
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="compare-template-logs")
    def compare_template_logs(self, request):
        ctx = resolve_access_context(request, require_property=True)
        tenant = ctx.tenant
        property_obj = ctx.property
        ensure_tenant_roles(request, tenant, ["admin", "operator", "supervisor"])
        ensure_property_action(request, tenant, property_obj, "can_export_buk")
        ensure_module_enabled(request, tenant, "buk_preview")

        queryset, compatible_value, user_query, compared_from, compared_to = self._build_compare_logs_queryset(
            request,
            tenant=tenant,
            property_obj=property_obj,
        )

        page_size_raw = str(request.query_params.get("page_size", "")).strip()
        if page_size_raw.isdigit():
            page_size = max(1, min(int(page_size_raw), 200))
        else:
            limit_raw = str(request.query_params.get("limit", "20")).strip()
            page_size = int(limit_raw) if limit_raw.isdigit() else 20
            page_size = max(1, min(page_size, 200))
        page_raw = str(request.query_params.get("page", "1")).strip()
        page = int(page_raw) if page_raw.isdigit() else 1
        page = max(1, page)

        total = queryset.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * page_size

        rows = []
        for item in queryset.order_by("-compared_at", "-id")[offset : offset + page_size]:
            rows.append(
                {
                    "id": item.id,
                    "compared_at": item.compared_at.isoformat(),
                    "date_from": item.date_from.isoformat(),
                    "date_to": item.date_to.isoformat(),
                    "sheet_name": item.sheet_name,
                    "reference_file_name": item.reference_file_name,
                    "reference_file_sha256": item.reference_file_sha256,
                    "reference_file_size_bytes": item.reference_file_size_bytes,
                    "is_compatible": item.is_compatible,
                    "errors_count": item.errors_count,
                    "warnings_count": item.warnings_count,
                    "compared_by": item.compared_by.email if item.compared_by_id else None,
                }
            )
        return Response(
            {
                "results": rows,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": total_pages,
                },
                "filters": {
                    "is_compatible": compatible_value,
                    "user": user_query,
                    "compared_from": compared_from.isoformat() if compared_from else None,
                    "compared_to": compared_to.isoformat() if compared_to else None,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="compare-template-logs/export-csv")
    def compare_template_logs_export_csv(self, request):
        ctx = resolve_access_context(request, require_property=True)
        tenant = ctx.tenant
        property_obj = ctx.property
        ensure_tenant_roles(request, tenant, ["admin", "operator", "supervisor"])
        ensure_property_action(request, tenant, property_obj, "can_export_buk")
        ensure_module_enabled(request, tenant, "buk_preview")

        queryset, _, _, _, _ = self._build_compare_logs_queryset(request, tenant=tenant, property_obj=property_obj)
        rows = queryset.order_by("-compared_at", "-id")[:5000]

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "compared_at",
                "date_from",
                "date_to",
                "sheet_name",
                "reference_file_name",
                "reference_file_sha256",
                "reference_file_size_bytes",
                "is_compatible",
                "errors_count",
                "warnings_count",
                "compared_by",
            ]
        )
        for item in rows:
            writer.writerow(
                [
                    item.id,
                    item.compared_at.isoformat(),
                    item.date_from.isoformat(),
                    item.date_to.isoformat(),
                    item.sheet_name,
                    item.reference_file_name,
                    item.reference_file_sha256,
                    item.reference_file_size_bytes,
                    "1" if item.is_compatible else "0",
                    item.errors_count,
                    item.warnings_count,
                    item.compared_by.email if item.compared_by_id else "",
                ]
            )
        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="buk_compare_template_logs_export_csv",
            entity_type="BukTemplateCompareLog",
            entity_id=f"{property_obj.id}:csv",
            before={},
            after={"rows_exported": len(rows)},
        )
        file_name = f"buk_template_compare_logs_{property_obj.slug}.csv"
        response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response

    @action(detail=False, methods=["get"], url_path=r"compare-template-logs/(?P<log_id>\d+)/download")
    def download_compare_template_log(self, request, log_id=None):
        ctx = resolve_access_context(request, require_property=True)
        tenant = ctx.tenant
        property_obj = ctx.property
        ensure_tenant_roles(request, tenant, ["admin", "operator", "supervisor"])
        ensure_property_action(request, tenant, property_obj, "can_export_buk")
        ensure_module_enabled(request, tenant, "buk_preview")
        item = (
            BukTemplateCompareLog.objects.filter(
                id=log_id,
                tenant=tenant,
                property=property_obj,
            )
            .select_related("compared_by")
            .first()
        )
        if item is None:
            return Response({"detail": "Log de comparacion no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        payload = {
            "compare_log_id": item.id,
            "tenant": tenant.slug,
            "property": property_obj.slug,
            "date_from": item.date_from.isoformat(),
            "date_to": item.date_to.isoformat(),
            "sheet_name": item.sheet_name,
            "reference_file_name": item.reference_file_name,
            "reference_file_sha256": item.reference_file_sha256,
            "reference_file_size_bytes": item.reference_file_size_bytes,
            "is_compatible": item.is_compatible,
            "errors_count": item.errors_count,
            "warnings_count": item.warnings_count,
            "compared_by": item.compared_by.email if item.compared_by_id else None,
            "result": item.result_payload,
        }
        AuditService.log(
            tenant=tenant,
            property_obj=property_obj,
            user=request.user if request.user.is_authenticated else None,
            action="buk_compare_template_log_download_json",
            entity_type="BukTemplateCompareLog",
            entity_id=item.id,
            before={},
            after={
                "date_from": item.date_from.isoformat(),
                "date_to": item.date_to.isoformat(),
                "is_compatible": item.is_compatible,
            },
        )
        file_name = f"buk_template_compare_log_{item.id}.json"
        response = HttpResponse(
            json.dumps(payload, ensure_ascii=False, indent=2),
            content_type="application/json; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response
