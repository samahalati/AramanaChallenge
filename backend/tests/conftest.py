"""Fixtures: the synthetic world is generated and analysed ONCE per session; every test then runs in its own rolled-back
transaction on top of it (isolation without copying databases)."""
import tempfile
from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from accounts.models import User
from monitoring.services.runs import run_detection
from seed.generate import DEMO_PASSWORD, generate


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    settings.GROUND_TRUTH_PATH = str(Path(tempfile.mkdtemp()) / "ground_truth.json")
    with django_db_blocker.unblock():
        gt = generate(42, settings.GROUND_TRUTH_PATH)
        run_detection()
    settings._gt = gt


@pytest.fixture
def gt(db):
    return settings._gt


class Api:
    """Tiny client wrapper: api.get('/hr/dashboard', 'hr@aramana.test') -> response (JSON via .json())."""
    def __init__(self):
        self.client, self.tokens = APIClient(), {}

    def token(self, email: str) -> str:
        if email not in self.tokens:
            r = self.client.post("/api/auth/login", {"email": email, "password": DEMO_PASSWORD}, format="json")
            assert r.status_code == 200, r.content
            self.tokens[email] = r.json()["access_token"]
        return self.tokens[email]

    def call(self, method: str, path: str, who: str | None = None, **body):
        extra = {"HTTP_AUTHORIZATION": f"Bearer {self.token(who)}"} if who else {}
        return getattr(self.client, method)(f"/api{path}", body or None, format="json", **extra)

    get = lambda self, path, who=None, **kw: self.call("get", path, who, **kw)        # noqa: E731
    post = lambda self, path, who=None, **kw: self.call("post", path, who, **kw)      # noqa: E731
    patch = lambda self, path, who=None, **kw: self.call("patch", path, who, **kw)    # noqa: E731

    def me(self, email: str) -> int:
        return User.objects.get(email=email).id


@pytest.fixture(scope="session")
def _api():
    return Api()


@pytest.fixture
def api(_api, db):
    return _api


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """Tests never call a real provider, even when a developer's backend/.env holds a key (tests that need one set settings.LLM themselves)."""
    monkeypatch.setattr(settings, "LLM", {"provider": "none", "api_key": "", "model": "", "base_url": ""})
