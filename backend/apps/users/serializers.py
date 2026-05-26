from django.contrib.auth import authenticate
from rest_framework import serializers

from apps.users.models import User, UserAreaPermission, UserPropertyPermission, UserTenantRole


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError("Credenciales invalidas.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_super_admin",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserTenantRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTenantRole
        fields = "__all__"


class UserPropertyPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPropertyPermission
        fields = "__all__"

    def validate(self, attrs):
        tenant = attrs.get("tenant") or self.instance.tenant
        property_obj = attrs.get("property") or self.instance.property
        if property_obj.tenant_id != tenant.id:
            raise serializers.ValidationError("La sede no pertenece al tenant.")
        return attrs


class UserAreaPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAreaPermission
        fields = "__all__"

    def validate(self, attrs):
        tenant = attrs.get("tenant") or self.instance.tenant
        property_obj = attrs.get("property") or self.instance.property
        area = attrs.get("area") or self.instance.area
        if property_obj.tenant_id != tenant.id:
            raise serializers.ValidationError("La sede no pertenece al tenant.")
        if area.tenant_id != tenant.id or area.property_id != property_obj.id:
            raise serializers.ValidationError("El area no pertenece al tenant/sede indicada.")
        return attrs
