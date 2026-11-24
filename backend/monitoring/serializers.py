from rest_framework import serializers

ACTIONS = ["start_review", "assign", "comment", "request_info", "provide_info", "escalate", "false_positive", "close_no_action", "close_substantiated", "reopen"]


class AlertActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(ACTIONS)
    note = serializers.CharField(max_length=4000, required=False, allow_null=True, allow_blank=True)
    assign_to = serializers.IntegerField(required=False, allow_null=True)


class RouteSerializer(serializers.Serializer):
    note = serializers.CharField(min_length=10, max_length=1000)


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(min_length=3, max_length=300)
