"""Bearer-JWT authentication. The user is re-loaded on every request, so suspending an account revokes access at once."""
from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from core.constants import UserStatus


def issue_token(user) -> str:
    exp = timezone.now() + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, settings.SECRET_KEY, algorithm="HS256")


class JWTAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != b"bearer":
            return None
        try:
            payload = jwt.decode(parts[1], settings.SECRET_KEY, algorithms=["HS256"])
            user = get_user_model().objects.get(pk=int(payload["sub"]))
        except (jwt.PyJWTError, get_user_model().DoesNotExist, ValueError):
            raise AuthenticationFailed("Invalid or expired token")
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationFailed("Account not active")
        return user, parts[1].decode()


try:   # API documentation: tell Swagger how requests authenticate, so the "Authorize" button appears (documentation only, no runtime effect)
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class JWTScheme(OpenApiAuthenticationExtension):
        target_class = "core.auth.JWTAuthentication"
        name = "bearerAuth"

        def get_security_definition(self, auto_schema):
            return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT", "description": "Token from POST /api/auth/login"}
except ImportError:   # pragma: no cover
    pass
