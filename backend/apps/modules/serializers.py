from rest_framework import serializers

from apps.modules.models import ModuleActivation


class ModuleActivationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleActivation
        fields = [
            "id",
            "tenant",
            "module_key",
            "is_enabled",
            "enabled_by",
            "enabled_at",
            "created_at",
            "updated_at",
        ]
