"""Errors: reuse DRF's exceptions; add Conflict; map DB integrity errors to 409. One handler for the whole API."""
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler

from core import i18n


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict"


def exception_handler(exc, context):
    response = Response({"detail": "Conflicting or invalid data"}, status=409) if isinstance(exc, IntegrityError) else drf_handler(exc, context)
    if response is not None and i18n.lang() == "fa":
        response.data = i18n.translate_payload(response.data)
    return response
