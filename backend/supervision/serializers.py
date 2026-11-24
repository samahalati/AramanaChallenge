from rest_framework import serializers


class MeetingSerializer(serializers.Serializer):
    supervisee_id = serializers.IntegerField()
    scheduled_at = serializers.DateTimeField()


class MeetingPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(["completed", "missed", "scheduled"])


class ReviewCreateSerializer(serializers.Serializer):
    supervisee_id = serializers.IntegerField()
    session_id = serializers.IntegerField(required=False, allow_null=True)
    due_date = serializers.DateField()


class ReviewDecisionSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(["approved", "needs_changes"])
    notes = serializers.CharField(min_length=3, max_length=4000)
    feedback = serializers.CharField(min_length=3, max_length=4000)
    performance_score = serializers.IntegerField(min_value=1, max_value=5)
    has_documentation = serializers.BooleanField()
    minutes_spent = serializers.FloatField(min_value=0, max_value=600, required=False, allow_null=True)


class CorrectiveActionSerializer(serializers.Serializer):
    description = serializers.CharField(min_length=5, max_length=1000)
    due_date = serializers.DateField()


class CorrectivePatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(["completed", "cancelled"])


class CloseReviewSerializer(serializers.Serializer):
    monitoring_plan = serializers.CharField(max_length=1000, required=False, allow_null=True, allow_blank=True)


class QualityIssueSerializer(serializers.Serializer):
    practitioner_id = serializers.IntegerField()
    category = serializers.ChoiceField(["operational", "clinical", "misconduct"])
    title = serializers.CharField(min_length=5, max_length=200)
    detail = serializers.CharField(max_length=2000, required=False, allow_null=True)
    severity = serializers.ChoiceField(["low", "medium", "high"], default="medium")


class EscalateSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=1000)
