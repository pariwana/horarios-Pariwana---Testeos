from rest_framework import serializers

from apps.tenants.models import Property, Tenant, TenantSupportAccessSession


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "status", "settings", "created_at", "updated_at"]


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = [
            "id",
            "tenant",
            "name",
            "slug",
            "location",
            "status",
            "created_at",
            "updated_at",
        ]


class TenantSupportAccessSessionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = TenantSupportAccessSession
        fields = [
            "id",
            "tenant",
            "property",
            "started_by",
            "reason",
            "ended_at",
            "ended_by",
            "end_reason",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_is_active(self, obj):
        return obj.ended_at is None
