from rest_framework import serializers

from apps.workers.models import Area, Shift, SpecialState, Worker


class AreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Area
        fields = "__all__"


class WorkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worker
        fields = "__all__"


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = "__all__"


class SpecialStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialState
        fields = "__all__"
