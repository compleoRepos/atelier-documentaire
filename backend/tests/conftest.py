from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Suite historique de non-régression : Tesseract reste la référence EXPLICITE.
# Le défaut produit est Surya ; il est couvert par des tests dédiés (transport
# HTTP simulé) et par la recette réelle sur le service local, jamais en silence.
os.environ.setdefault("TRANSLATOR_OCR_BACKEND", "tesseract")


@pytest.fixture
def app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRANSLATOR_JWT_SECRET", "integration-secret-0123456789-abcdef")
    monkeypatch.setenv("TRANSLATOR_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("TRANSLATOR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRANSLATOR_EXECUTION_MODE", "inline")
    monkeypatch.setenv("TRANSLATOR_EXPECTED_DIR", str(tmp_path / "expected"))
    monkeypatch.setenv("TRANSLATOR_REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("TRANSLATOR_ENGINE", "offline")
    monkeypatch.delenv("TRANSLATOR_PRIVATE_AI_API_KEY", raising=False)
    from app.core.settings import get_settings

    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def client(app_env):
    from app.core.models import Tenant, User
    from app.core.security import hash_password
    from app.main import create_app

    app = create_app()
    factory = app.state.session_factory
    with factory() as db:
        tenant_a = Tenant(name="tenant-a")
        tenant_b = Tenant(name="tenant-b")
        db.add_all([tenant_a, tenant_b])
        db.flush()
        db.add_all(
            [
                User(
                    username="admin-a",
                    password_hash=hash_password("Admin-A-password-12"),
                    tenant_id=tenant_a.id,
                    role="admin",
                ),
                User(
                    username="reviewer-a",
                    password_hash=hash_password("Reviewer-A-pass-12"),
                    tenant_id=tenant_a.id,
                    role="reviewer",
                ),
                User(
                    username="user-b",
                    password_hash=hash_password("User-B-password-12"),
                    tenant_id=tenant_b.id,
                    role="uploader",
                ),
            ]
        )
        db.commit()
    return TestClient(app)


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
