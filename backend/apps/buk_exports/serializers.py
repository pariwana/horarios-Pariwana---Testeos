from rest_framework import serializers


class BukRangeSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    date_from = serializers.DateField()
    date_to = serializers.DateField()
