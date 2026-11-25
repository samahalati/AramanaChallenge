"""OpenAPI schema generation: views declare their request bodies in `bodies`, so the generated docs list every input field.

    class MyView(APIView):
        bodies = {"post": MySerializer}          # key: viewset action, `step`, or lower-case HTTP method

Responses are documented as JSON objects (the services return plain dicts, not serializers).
"""
import re

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes


class ArmanaSchema(AutoSchema):
    def get_operation_id(self):   # unique and readable: method + path (the default collides for list/detail pairs)
        return re.sub(r"\W+", "_", f"{self.method.lower()} {self.path}").strip("_")

    def get_request_serializer(self):
        bodies = getattr(self.view, "bodies", None) or {}
        for key in (getattr(self.view, "action", None), getattr(self.view, "step", None), self.method.lower()):
            if key in bodies:
                return bodies[key]
        return super().get_request_serializer() if hasattr(self.view, "serializer_class") else None

    def get_response_serializers(self):
        if hasattr(self.view, "serializer_class"):
            return super().get_response_serializers()
        return OpenApiTypes.OBJECT
