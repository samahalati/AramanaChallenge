class ApiNoStoreMiddleware:
    """Never let browsers/proxies cache API responses (they contain personal/sensitive data)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
        return response


class SecurityHeadersMiddleware:
    """Defence in depth for browsers: a strict Content-Security-Policy (API: nothing may load; app: same-origin only; Swagger UI: its CDN),
    no framing, no sniffing, no referrer, no powerful browser features. HSTS is added by SecurityMiddleware when DEBUG is off."""
    API = "default-src 'none'; frame-ancestors 'none'"
    APP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
           "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    DOCS = ("default-src 'self'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://cdn.jsdelivr.net; connect-src 'self'; frame-ancestors 'none'")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        response.setdefault("Content-Security-Policy", self.DOCS if path.startswith(("/api/docs", "/api/schema")) else self.API if path.startswith("/api/") else self.APP)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
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
