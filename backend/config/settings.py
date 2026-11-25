"""Django settings – 12-factor: everything configurable via environment (see backend/.env.example)."""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT = BASE_DIR.parent


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (no dependency): KEY=VALUE lines; real environment variables always win."""
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() and not key.lstrip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv(BASE_DIR / ".env")
env = os.environ.get

SECRET_KEY = env("SECRET_KEY", "dev-only-secret-key-change-me-dev-only-secret-key")
DEBUG = env("DEBUG", "1") == "1"
ALLOWED_HOSTS = env("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.staticfiles",
    "rest_framework", "drf_spectacular",
    "core", "accounts", "hr", "clinical", "supervision", "monitoring",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ApiNoStoreMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "core.middleware.LanguageMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True, "OPTIONS": {}}]   # needed by the Swagger UI page
AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'aramana.sqlite3'}"))}
LANGUAGE_CODE, TIME_ZONE, USE_TZ = "en-us", "UTC", True
STATIC_URL = "/static/"
SECURE_REFERRER_POLICY = "no-referrer"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:                                  # production: HTTPS only (TLS is terminated by the reverse proxy in front of the app)
    SECURE_HSTS_SECONDS, SECURE_HSTS_INCLUDE_SUBDOMAINS = 31_536_000, True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {   # application log: one line per event on stdout (collected by the container runtime); security events have their own logger
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "loggers": {"aramana": {"handlers": ["console"], "level": "INFO", "propagate": False}, "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.auth.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["core.permissions.RolePermission"],   # secure by default: every view declares `perms`
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "core.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "core.openapi.ArmanaSchema",
    "UNAUTHENTICATED_USER": None,
}
SPECTACULAR_SETTINGS = {"TITLE": "ARAMANA governance API", "VERSION": "2.0.0", "SERVE_INCLUDE_SCHEMA": False}

# Domain settings
ACCESS_TOKEN_MINUTES = int(env("ACCESS_TOKEN_MINUTES", "60"))
MAX_FAILED_LOGINS = int(env("MAX_FAILED_LOGINS", "5"))
LOCKOUT_MINUTES = int(env("LOCKOUT_MINUTES", "15"))
LLM = {"provider": env("LLM_PROVIDER", "none"), "api_key": env("LLM_API_KEY", ""), "model": env("LLM_MODEL", ""), "base_url": env("LLM_BASE_URL", "")}
DETECTION_CONFIG = env("DETECTION_CONFIG", str(BASE_DIR / "detection" / "config.yaml"))
GROUND_TRUTH_PATH = env("GROUND_TRUTH_PATH", str(ROOT / "data" / "ground_truth.json"))
FRONTEND_DIST = ROOT / "frontend" / "dist"
