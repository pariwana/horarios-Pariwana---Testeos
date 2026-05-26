from rest_framework import serializers

from apps.month_closure.models import MonthClosure


class MonthClosureSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthClosure
        fields = "__all__"
