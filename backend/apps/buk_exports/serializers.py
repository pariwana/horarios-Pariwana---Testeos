from rest_framework import serializers


class BukRangeSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    date_from = serializers.DateField()
    date_to = serializers.DateField()


class BukTemplateCompareSerializer(BukRangeSerializer):
    reference_file = serializers.FileField()
    sheet_name = serializers.CharField(required=False, default="Reporte carga BUK")
    download_report = serializers.BooleanField(required=False, default=False)
