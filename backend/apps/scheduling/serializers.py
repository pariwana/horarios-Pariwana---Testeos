from rest_framework import serializers

from apps.scheduling.models import ScheduleAssignment


class ScheduleAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleAssignment
        fields = "__all__"


class ControlQuerySerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
