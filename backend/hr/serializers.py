from rest_framework import serializers

from accounts.models import User
from core.constants import SPECIALIZATIONS
from hr.models import Contract, Credential, LifecycleEvent

PRACTITIONER_ROLES = ["therapist", "assistant_counselor", "clinical_supervisor"]


def specialization_field():
    return serializers.ChoiceField(SPECIALIZATIONS, allow_null=True, required=False)


class PractitionerListSerializer(serializers.ModelSerializer):
    specialization = serializers.CharField(source="profile.specialization", default=None)
    org_unit = serializers.CharField(source="profile.org_unit.name", default=None)
    employment_type = serializers.CharField(source="profile.employment_type", default=None)
    capacity_weekly_sessions = serializers.IntegerField(source="profile.capacity_weekly_sessions", default=None)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "status", "specialization", "org_unit", "employment_type", "capacity_weekly_sessions"]


class PractitionerCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    full_name = serializers.CharField(min_length=2, max_length=255)
    role = serializers.ChoiceField(PRACTITIONER_ROLES)   # privileged roles can never be created through HR
    specialization = specialization_field()
    org_unit_id = serializers.IntegerField(allow_null=True, required=False)
    employment_type = serializers.ChoiceField(["employee", "contractor", "volunteer"], default="employee")
    hire_date = serializers.DateField(required=False, allow_null=True)
    capacity_weekly_sessions = serializers.IntegerField(min_value=0, max_value=60, default=25)
    initial_password = serializers.CharField(min_length=10, max_length=200)


class ProfilePatchSerializer(serializers.Serializer):
    specialization = specialization_field()
    org_unit_id = serializers.IntegerField(allow_null=True, required=False)
    employment_type = serializers.ChoiceField(["employee", "contractor", "volunteer"], required=False)
    capacity_weekly_sessions = serializers.IntegerField(min_value=0, max_value=60, required=False)
    bio = serializers.CharField(max_length=1000, allow_null=True, required=False)


class CredentialSerializer(serializers.ModelSerializer):
    days_to_expiry = serializers.SerializerMethodField()

    class Meta:
        model = Credential
        fields = ["id", "kind", "title", "number", "issuer", "issued_on", "expires_on", "status", "days_to_expiry"]
        read_only_fields = ["id", "days_to_expiry"]

    def get_days_to_expiry(self, obj):
        from datetime import date
        return (obj.expires_on - date.today()).days if obj.expires_on else None


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ["id", "kind", "start_date", "end_date", "status", "document_ref"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        start, end = attrs.get("start_date", getattr(self.instance, "start_date", None)), attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError("end_date is before start_date")
        return attrs


class LifecycleEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LifecycleEvent
        fields = ["id", "event", "reason", "effective_date", "actor_id", "created_at"]


class LifecycleActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(["activate", "suspend", "reactivate", "terminate"])
    reason = serializers.CharField(min_length=5, max_length=500)
    effective_date = serializers.DateField(required=False, allow_null=True)


class AssignmentSerializer(serializers.Serializer):
    supervisor_id = serializers.IntegerField()
    supervisee_id = serializers.IntegerField()
    effective_from = serializers.DateField(required=False, allow_null=True)
    schedule_every_days = serializers.IntegerField(min_value=1, max_value=90, default=7)
    reason = serializers.CharField(min_length=5, max_length=500)
