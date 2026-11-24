class ApiNoStoreMiddleware:
    """Never let browsers/proxies cache API responses (they contain personal/sensitive data)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
        return response


class LanguageMiddleware:
    """Request language from `Accept-Language` (fa | en). Everything below this layer reads it via `core.i18n.lang()`."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from core import i18n
        token = i18n.set_lang(i18n.parse_accept_language(request.headers.get("Accept-Language")))
        try:
            response = self.get_response(request)
            response["Content-Language"] = i18n.lang()
            return response
        finally:
            i18n._lang.reset(token)
