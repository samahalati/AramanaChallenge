from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from hr import activity, services
from hr.models import Contract, Credential
from hr.serializers import (AssignmentSerializer, ContractSerializer, CredentialSerializer, LifecycleActionSerializer, LifecycleEventSerializer,
                            DevelopmentSerializer, PractitionerCreateSerializer, PractitionerListSerializer, ProfilePatchSerializer)


def validated(serializer_cls, request, **kw):
    s = serializer_cls(data=request.data, **kw)
    s.is_valid(raise_exception=True)
    return s.validated_data


class PractitionerViewSet(viewsets.ViewSet):
    bodies = {"create": PractitionerCreateSerializer, "development": DevelopmentSerializer, "profile": ProfilePatchSerializer, "lifecycle": LifecycleActionSerializer, "credentials": CredentialSerializer, "contracts": ContractSerializer}
    perms = {"list": "hr:read", "retrieve": "hr:read", "activity": "hr:read", "*": "hr:write"}

    def list(self, request):
        qs, q = services.practitioners().order_by("full_name"), request.query_params
        for field in ("role", "status"):
            qs = qs.filter(**{field: q[field]}) if q.get(field) else qs
        if q.get("org_unit_id"):
            qs = qs.filter(profile__org_unit_id=q["org_unit_id"])
        if q.get("q"):
            qs = qs.filter(full_name__icontains=q["q"]) | qs.filter(email__icontains=q["q"])
        return Response(PractitionerListSerializer(qs, many=True).data)

    def create(self, request):
        user = services.create_practitioner(request.user, validated(PractitionerCreateSerializer, request))
        return Response(PractitionerListSerializer(user).data, status=201)

    def retrieve(self, request, pk):
        user = services.get_practitioner(int(pk))
        profile = user.profile
        return Response({
            "user": PractitionerListSerializer(user).data,
            "profile": {"specialization": profile.specialization, "org_unit": profile.org_unit.name if profile.org_unit else None, "org_unit_id": profile.org_unit_id,
                        "employment_type": profile.employment_type, "hire_date": profile.hire_date, "capacity_weekly_sessions": profile.capacity_weekly_sessions, "bio": profile.bio},
            "credentials": CredentialSerializer(user.credentials.order_by("expires_on"), many=True).data,
            "contracts": ContractSerializer(user.contracts.order_by("-start_date"), many=True).data,
            "lifecycle": LifecycleEventSerializer(user.lifecycle.order_by("-id"), many=True).data,
            "assignments": [a for a in services.assignments_list(current_only=False) if user.id in (a["supervisor_id"], a["supervisee_id"])],
        })

    @action(detail=True, methods=["get"])
    def activity(self, request, pk):
        """Aggregated activity, quality, participation and development indicators (no clinical content)."""
        return Response(activity.practitioner_activity(request.user, services.get_practitioner(int(pk))))

    @action(detail=True, methods=["post"])
    def development(self, request, pk):
        item = services.add_development(request.user, int(pk), validated(DevelopmentSerializer, request))
        return Response(DevelopmentSerializer(item).data, status=201)

    @action(detail=True, methods=["patch"])
    def profile(self, request, pk):
        services.update_profile(request.user, int(pk), validated(ProfilePatchSerializer, request))
        return self.retrieve(request, pk)

    @action(detail=True, methods=["post"])
    def lifecycle(self, request, pk):
        d = validated(LifecycleActionSerializer, request)
        user = services.change_lifecycle(request.user, int(pk), d["action"], d["reason"], d.get("effective_date"))
        return Response({"id": user.id, "status": user.status})

    @action(detail=True, methods=["post"])
    def credentials(self, request, pk):
        return self._create_child(request, pk, CredentialSerializer, "credential_edit")

    @action(detail=True, methods=["post"])
    def contracts(self, request, pk):
        return self._create_child(request, pk, ContractSerializer, "contract_edit")

    def _create_child(self, request, pk, serializer_cls, audit_action):   # DRY: credential + contract share one path
        user = services.get_practitioner(int(pk))
        ser = serializer_cls(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(user=user)
        services.record_change(request.user, audit_action, user.id, "add", record=obj.id)
        return Response({"id": obj.id}, status=201)


class AuditedUpdateView(generics.UpdateAPIView):
    """PATCH one child record of a practitioner and log it as an administrative activity."""
    perms = {"patch": "hr:write", "put": "hr:write"}
    audit_action = ""

    def perform_update(self, serializer):
        obj = serializer.save()
        services.record_change(self.request.user, self.audit_action, obj.user_id, "update", record=obj.id,
                               after={k: str(v) for k, v in serializer.validated_data.items()})


class CredentialUpdateView(AuditedUpdateView):
    queryset, serializer_class, audit_action = Credential.objects.all(), CredentialSerializer, "credential_edit"


class ContractUpdateView(AuditedUpdateView):
    queryset, serializer_class, audit_action = Contract.objects.all(), ContractSerializer, "contract_edit"


class AssignmentView(APIView):
    bodies = {"post": AssignmentSerializer}
    perms = {"get": "hr:read", "post": "hr:write"}

    def get(self, request):
        return Response(services.assignments_list(request.query_params.get("current_only", "true") != "false"))

    def post(self, request):
        return Response({"id": services.assign_supervisor(request.user, validated(AssignmentSerializer, request)).id}, status=201)


class DashboardView(APIView):
    perms = {"get": "hr:read"}

    def get(self, request):
        return Response(services.dashboard())


class OrgUnitView(APIView):
    perms = {"get": "hr:read"}

    def get(self, request):
        return Response(services.org_tree())
