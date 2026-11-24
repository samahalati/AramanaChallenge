from rest_framework import serializers

from accounts.models import User
from core.constants import Role, UserStatus


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "status", "created_at"]


class AccountSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    full_name = serializers.CharField(min_length=2, max_length=255)
    role = serializers.ChoiceField(Role.choices)
    password = serializers.CharField(min_length=10, max_length=200, write_only=True)


class RoleChangeSerializer(serializers.Serializer):
    role = serializers.ChoiceField(Role.choices)
    reason = serializers.CharField(min_length=5, max_length=500)


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField([UserStatus.ACTIVE, UserStatus.SUSPENDED])
    reason = serializers.CharField(min_length=5, max_length=500)


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(max_length=200)
