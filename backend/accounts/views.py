from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import services
from accounts.models import User
from accounts.serializers import (AccountSerializer, LoginSerializer, RoleChangeSerializer, StatusChangeSerializer, UserSerializer)
from core.auth import JWTAuthentication, issue_token
from core.models import AdminActivity
from core.permissions import AUTHENTICATED


class LoginView(APIView):
    bodies = {"post": LoginSerializer}
    permission_classes, authentication_classes = [AllowAny], [JWTAuthentication]   # authenticator supplies the 401 challenge header

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.authenticate(**data.validated_data, ip=request.META.get("REMOTE_ADDR"))
        return Response({"access_token": issue_token(user), "token_type": "bearer", "user": services.profile(user)})


class MeView(APIView):
    perms = {"get": AUTHENTICATED}

    def get(self, request):
        return Response(services.profile(request.user))


class AdminUserViewSet(viewsets.ViewSet):
    """Platform account administration (no HR/clinical content)."""
    bodies = {"create": AccountSerializer, "role": RoleChangeSerializer, "set_status": StatusChangeSerializer}
    perms = {"*": "users:manage"}

    def list(self, request):
        return Response(UserSerializer(User.objects.order_by("id"), many=True).data)

    def create(self, request):
        data = AccountSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(UserSerializer(services.create_account(request.user, **data.validated_data)).data, status=201)

    @action(detail=True, methods=["patch"])
    def role(self, request, pk):
        data = RoleChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(UserSerializer(services.change_role(request.user, int(pk), **data.validated_data)).data)

    @action(detail=True, methods=["patch"], url_path="status")
    def set_status(self, request, pk):
        data = StatusChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(UserSerializer(services.change_status(request.user, int(pk), **data.validated_data)).data)


class AdminActivityView(APIView):
    perms = {"get": ("users:manage", "audit:read")}

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 100)), 500)
        rows = AdminActivity.objects.order_by("-id").values("id", "ts", "actor_id", "action", "target_user_id", "detail")[:limit]
        return Response(list(rows))
