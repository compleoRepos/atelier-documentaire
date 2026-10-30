"""Aides de tests DICE (RAG) : client HTTP réel, deux tenants, flux humain complet.

Aucune donnée réelle : termes génériques fabriqués pour les tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

PASSWORDS = {
    "admin-a": "Admin-A-password-12",
    "reviewer-a": "Reviewer-A-pass-12",
    "uploader-a": "Uploader-A-pass-12",
    "admin-b": "Admin-B-password-12",
    "user-b": "User-B-password-12",
}

TERMS_EN_FR = [
    {
        "source_language": "en",
        "source_term": "gross salary",
        "target_language": "fr",
        "target_term": "salaire brut",
        "domain": "hr",
        "provenance": "test-synthetique",
    },
    {
        "source_language": "en",
        "source_term": "notice period",
        "target_language": "fr",
        "target_term": "préavis",
        "domain": "hr",
        "provenance": "test-synthetique",
    },
    {
        "source_language": "en",
        "source_term": "pay slip",
        "target_language": "fr",
        "target_term": "bulletin de paie",
        "provenance": "test-synthetique",
    },
]


def make_rag_client(monkeypatch, *, mode: str = "SHADOW", admin: bool = True, engine=None):
    from app.core.models import Tenant, User
    from app.core.security import hash_password
    from app.core.settings import get_settings
    from app.main import create_app

    monkeypatch.setenv("TRANSLATOR_RAG_MODE", mode)
    monkeypatch.setenv("TRANSLATOR_RAG_ADMIN_ENABLED", "true" if admin else "false")
    if engine:
        monkeypatch.setenv("TRANSLATOR_ENGINE", engine)
    get_settings.cache_clear()
    app = create_app()
    factory = app.state.session_factory
    ids: dict[str, str] = {}
    with factory() as db:
        tenant_a, tenant_b = Tenant(name="tenant-a"), Tenant(name="tenant-b")
        db.add_all([tenant_a, tenant_b])
        db.flush()
        users = [
            ("admin-a", tenant_a, "admin"),
            ("reviewer-a", tenant_a, "reviewer"),
            ("uploader-a", tenant_a, "uploader"),
            ("admin-b", tenant_b, "admin"),
            ("user-b", tenant_b, "uploader"),
        ]
        rows = []
        for name, tenant, role in users:
            row = User(
                username=name,
                password_hash=hash_password(PASSWORDS[name]),
                tenant_id=tenant.id,
                role=role,
            )
            rows.append(row)
        db.add_all(rows)
        db.commit()
        ids = {row.username: row.id for row in rows}
        ids["tenant-a"], ids["tenant-b"] = tenant_a.id, tenant_b.id
    return TestClient(app), app, ids


def headers(client: TestClient, username: str) -> dict:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORDS[username]}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def grant(client: TestClient, by: str, user_id: str, role: str) -> None:
    response = client.post(
        "/api/rag-admin/roles", headers=headers(client, by), json={"user_id": user_id, "role": role}
    )
    assert response.status_code == 200, response.text


def publish_referential(
    client: TestClient,
    ids: dict,
    *,
    tenant: str = "a",
    entries: list[dict] | None = None,
    name: str = "RH test",
    max_mode: str | None = None,
) -> dict:
    """Flux humain complet : brouillon -> soumission -> validation (4 yeux) -> publication."""
    author, checker = ("admin-a", "reviewer-a") if tenant == "a" else ("admin-b", "user-b")
    grant(client, author, ids[author], "rag_admin")
    grant(client, author, ids[author], "terminology_manager")
    grant(client, author, ids[checker], "terminology_manager")
    h_author, h_checker = headers(client, author), headers(client, checker)
    created = client.post(
        "/api/rag-admin/referentials",
        headers=h_author,
        json={"kind": "linguistic", "name": name, "languages": ["en", "fr"]},
    )
    assert created.status_code == 200, created.text
    referential = created.json()
    draft = client.post(
        f"/api/rag-admin/referentials/{referential['id']}/versions", headers=h_author, json={}
    )
    assert draft.status_code == 200, draft.text
    version = draft.json()
    added = client.post(
        f"/api/rag-admin/versions/{version['id']}/entries",
        headers=h_author,
        json={"entries": entries or TERMS_EN_FR},
    )
    assert added.status_code == 200, added.text
    for who, action in ((h_author, "submit"), (h_checker, "validate"), (h_author, "publish")):
        moved = client.post(
            f"/api/rag-admin/versions/{version['id']}/transitions",
            headers=who,
            json={"action": action},
        )
        assert moved.status_code == 200, (action, moved.text)
    active = client.post(
        f"/api/rag-admin/referentials/{referential['id']}/active",
        headers=h_author,
        json={"active": True},
    )
    assert active.status_code == 200, active.text
    if max_mode:
        mode = client.post("/api/rag-admin/tenant", headers=h_author, json={"max_mode": max_mode})
        assert mode.status_code == 200, mode.text
    return {"referential": referential, "version": version}
