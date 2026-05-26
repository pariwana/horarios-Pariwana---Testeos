from rest_framework import serializers

from apps.imports.models import ImportBatch, ImportPreviewRow


class ImportBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportBatch
        fields = "__all__"


class ImportPreviewRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportPreviewRow
        fields = "__all__"


class ExcelPreviewRequestSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    file = serializers.FileField()


class WorkerPreviewRequestSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    create_missing_areas = serializers.BooleanField(default=False)
    file = serializers.FileField()
