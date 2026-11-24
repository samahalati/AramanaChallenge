from rest_framework import serializers

from clinical.models import Session
from core.constants import SPECIALIZATIONS


class SessionSerializer(serializers.ModelSerializer):
    client_ref = serializers.CharField(source="client.client_ref")

    class Meta:
        model = Session
        fields = ["id", "practitioner_id", "client_ref", "group_id", "scheduled_start", "scheduled_end", "status", "mode", "location_code",
                  "reported_duration_min", "checkin_at", "checkout_at", "modification_count"]


class SessionCreateSerializer(serializers.Serializer):
    client_ref = serializers.CharField()
    scheduled_start = serializers.DateTimeField()
    duration_min = serializers.IntegerField(min_value=10, max_value=240, default=50)
    mode = serializers.ChoiceField(["online", "in_person"], default="online")
    location_code = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class SessionPatchSerializer(serializers.Serializer):
    scheduled_start = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(["completed", "cancelled", "no_show"], required=False)
    reported_duration_min = serializers.IntegerField(min_value=0, max_value=300, required=False)


class ReferralCreateSerializer(serializers.Serializer):
    client_ref = serializers.CharField()
    to_practitioner_id = serializers.IntegerField()
    need = serializers.ChoiceField(SPECIALIZATIONS)
