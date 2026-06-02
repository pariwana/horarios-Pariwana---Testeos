from rest_framework import serializers

from apps.scheduling.models import ScheduleAssignment


class ScheduleAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleAssignment
        fields = "__all__"


class ControlQuerySerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)


class BulkRangeStateSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    special_state_id = serializers.IntegerField()
    area_id = serializers.IntegerField(required=False)
    worker_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    dry_run = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError("date_from no puede ser mayor a date_to.")
        return attrs


class BulkSundaysStateSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)
    special_state_id = serializers.IntegerField()
    area_id = serializers.IntegerField(required=False)
    worker_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    dry_run = serializers.BooleanField(required=False, default=False)


class CopyWeekSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    source_week_start = serializers.DateField()
    target_week_start = serializers.DateField()
    copy_kind = serializers.ChoiceField(choices=["all", "shift", "state"], default="all", required=False)
    area_id = serializers.IntegerField(required=False)
    worker_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    dry_run = serializers.BooleanField(required=False, default=False)


class CopyPreviousMonthSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    target_year = serializers.IntegerField(min_value=2000, max_value=2100)
    target_month = serializers.IntegerField(min_value=1, max_value=12)
    copy_kind = serializers.ChoiceField(choices=["all", "shift", "state"], default="all", required=False)
    area_id = serializers.IntegerField(required=False)
    worker_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    dry_run = serializers.BooleanField(required=False, default=False)


class WeekPatternSerializerMixin(serializers.Serializer):
    monday_value = serializers.CharField(required=False, allow_blank=True, max_length=64)
    tuesday_value = serializers.CharField(required=False, allow_blank=True, max_length=64)
    wednesday_value = serializers.CharField(required=False, allow_blank=True, max_length=64)
    thursday_value = serializers.CharField(required=False, allow_blank=True, max_length=64)
    friday_value = serializers.CharField(required=False, allow_blank=True, max_length=64)
    saturday_value = serializers.CharField(required=False, allow_blank=True, max_length=64)
    sunday_value = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate(self, attrs):
        values = [
            attrs.get("monday_value", "").strip(),
            attrs.get("tuesday_value", "").strip(),
            attrs.get("wednesday_value", "").strip(),
            attrs.get("thursday_value", "").strip(),
            attrs.get("friday_value", "").strip(),
            attrs.get("saturday_value", "").strip(),
            attrs.get("sunday_value", "").strip(),
        ]
        if not any(values):
            raise serializers.ValidationError("Debe seleccionar al menos un turno/estado en el patron semanal.")
        return attrs


class SaveWeekPatternTemplateSerializer(WeekPatternSerializerMixin):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    template_name = serializers.CharField(max_length=120)
    area_id = serializers.IntegerField(required=False)


class UpdateWeekPatternTemplateSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    template_id = serializers.IntegerField(min_value=1)
    template_name = serializers.CharField(max_length=120)
    active = serializers.BooleanField(required=False)


class DeleteWeekPatternTemplateSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    template_id = serializers.IntegerField(min_value=1)


class ApplyWeekPatternTemplateSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    template_id = serializers.IntegerField(min_value=1)
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    area_id = serializers.IntegerField(required=False)
    worker_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    dry_run = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError("date_from no puede ser mayor a date_to.")
        return attrs


class BulkWeekPatternSerializer(WeekPatternSerializerMixin):
    tenant_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    area_id = serializers.IntegerField(required=False)
    worker_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    dry_run = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError("date_from no puede ser mayor a date_to.")
        return attrs
