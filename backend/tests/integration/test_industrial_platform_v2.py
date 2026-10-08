from __future__ import annotations

import hashlib
import json

import fitz
from sqlalchemy import select

from app.core.models import Document, DocumentVersion, Tenant, User
from app.core.security import hash_password

from .conftest import login


def pdf_bytes(text="Bonjour 1234"):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    result = doc.tobytes()
    doc.close()
    return result


def test_cookie_session_csrf_and_persistent_logout(client):
    result = client.post(
        "/api/auth/login", json={"username": "admin-a", "password": "Admin-A-password-12"}
    )
    assert result.status_code == 200
    assert "HttpOnly" in result.headers.get_list("set-cookie")[0]
    assert "SameSite=strict" in result.headers.get_list("set-cookie")[0]
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 403
    csrf = client.cookies["translator_csrf"]
    token = result.json()["access_token"]
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )


def test_cookie_cross_origin_mutation_rejected(client):
    client.post("/api/auth/login", json={"username": "admin-a", "password": "Admin-A-password-12"})
    csrf = client.cookies["translator_csrf"]
    result = client.post(
        "/api/auth/logout", headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"}
    )
    assert result.status_code == 403


def test_cookie_production_transport_never_exposes_jwt(client):
    client.app.state.settings.auth_mode = "cookie"
    result = client.post(
        "/api/auth/login", json={"username": "admin-a", "password": "Admin-A-password-12"}
    )
    assert result.status_code == 200
    assert "access_token" not in result.json()
    assert result.json()["token_type"] == "cookie"


def test_same_tenant_uploader_cannot_read_another_users_document(client):
    admin = login(client, "admin-a", "Admin-A-password-12")
    original = pdf_bytes()
    upload = client.post(
        "/api/documents",
        files={"file": ("synthetic.pdf", original, "application/pdf")},
        headers=admin,
    )
    assert upload.status_code == 200, upload.text
    document_id = upload.json()["id"]
    with client.app.state.session_factory() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.name == "tenant-a"))
        db.add(
            User(
                username="uploader-a",
                tenant_id=tenant.id,
                role="uploader",
                password_hash=hash_password("Uploader-A-password-12"),
            )
        )
        db.commit()
    own = login(client, "uploader-a", "Uploader-A-password-12")
    assert client.get(f"/api/documents/{document_id}", headers=own).status_code == 404
    assert client.get("/api/documents", headers=own).json() == []
    assert (
        client.get(f"/api/documents/{document_id}/artifact/original", headers=own).status_code
        == 404
    )


def test_translation_keeps_analysis_snapshot_and_measured_duration(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    original = pdf_bytes()
    upload = client.post(
        "/api/documents",
        files={"file": ("synthetic.pdf", original, "application/pdf")},
        headers=headers,
    )
    document_id = upload.json()["id"]
    translated = client.post(f"/api/documents/{document_id}/translate", headers=headers)
    assert translated.status_code == 200, translated.text
    detail = client.get(f"/api/documents/{document_id}", headers=headers).json()
    assert detail["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert detail["timings"]["analyze_seconds"] >= 0
    assert detail["timings"]["translate_seconds"] >= 0
    assert detail["timings"]["gpu_seconds"] is None
    with client.app.state.session_factory() as db:
        version = db.scalar(
            select(DocumentVersion).where(DocumentVersion.document_id == document_id)
        )
        snapshot = json.dumps(version.analysis_snapshot, sort_keys=True)
        assert version.analysis_key and version.source_sha256 == detail["source_sha256"]
        document = db.get(Document, document_id)
        document.analysis_json = {"pages": []}
        db.commit()
    with client.app.state.session_factory() as db:
        version = db.scalar(
            select(DocumentVersion).where(DocumentVersion.document_id == document_id)
        )
        assert json.dumps(version.analysis_snapshot, sort_keys=True) == snapshot


def test_metrics_normalize_routes_and_do_not_label_document_ids(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    client.get("/api/documents/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", headers=headers)
    result = client.get("/metrics")
    assert result.status_code == 200
    assert "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" not in result.text
    assert 'route="/api/documents/{doc_id}"' in result.text
    assert "translator_http_requests_total" in result.text


def test_readiness_detects_database_failure(client, monkeypatch):
    assert client.get("/api/health").status_code == 200

    def unavailable():
        raise ConnectionError("synthetic database outage")

    # Les routes capturent la factory ; son moteur indisponible est simulé proprement.
    monkeypatch.setattr(client.app.state.engine, "connect", unavailable)
    result = client.get("/api/health")
    assert result.status_code == 503
    assert result.json()["checks"]["database"] is False
