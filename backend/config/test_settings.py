from config.settings import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]   # fast hashing in tests only
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
LLM = {"provider": "none", "api_key": "", "model": "", "base_url": ""}
