from __future__ import annotations

import io

from ..integration.conftest import login


def test_missing_invalid_and_expired_authentication_is_rejected(client):
    assert client.get("/api/documents").status_code == 401
    assert (
        client.get("/api/documents", headers={"Authorization": "Bearer not-a-jwt"}).status_code
        == 401
    )


def test_disabled_tenant_invalidates_existing_token(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    from app.core.models import Tenant

    app = client.app
    with app.state.session_factory() as db:
        tenant = db.query(Tenant).filter(Tenant.name == "tenant-a").one()
        tenant.enabled = False
        db.commit()
    assert client.get("/api/documents", headers=headers).status_code == 401


def test_invalid_image_is_rejected(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    response = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("fake.png", io.BytesIO(b"bad"), "image/png")},
    )
    assert response.status_code in {415, 422}
