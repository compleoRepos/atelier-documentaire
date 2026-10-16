from __future__ import annotations

from app.core.models import Document

from .conftest import login


def pdf_bytes() -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.insert_text((20, 40), "Bonjour chantier 1234", fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def test_enhanced_preview_is_authenticated_cross_tenant_and_version_isolated(client):
    owner = login(client, "admin-a", "Admin-A-password-12")
    other = login(client, "user-b", "User-B-password-12")
    uploaded = client.post(
        "/api/documents",
        headers=owner,
        files={"file": ("source.pdf", pdf_bytes(), "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["id"]
    assert client.post(f"/api/documents/{document_id}/translate", headers=owner).status_code == 200
    detail = client.get(f"/api/documents/{document_id}", headers=owner).json()
    version = detail["review_version"]
    assert len(detail["stages"]) == 9
    assert any(stage["state"] == "pending" for stage in detail["stages"])
    assert (
        client.get(
            f"/api/documents/{document_id}/preview/enhanced/1?version={version}",
            headers=owner,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/documents/{document_id}/preview/enhanced/1?version={version}",
            headers=other,
        ).status_code
        == 404
    )

    # Delete only the immutable version copy while leaving the analysis/current copy:
    # an explicit version must fail rather than fall back to current analysis bytes.
    app = client.app
    with app.state.session_factory() as db:
        document = db.get(Document, document_id)
        version_key = f"{document.tenant_id}/{document_id}/versions/{version}/previews/enhanced-001.png"
    version_path = app.state.settings.data_dir / "objects" / version_key
    assert version_path.is_file()
    version_path.unlink()
    assert (
        client.get(
            f"/api/documents/{document_id}/preview/enhanced/1?version={version}",
            headers=owner,
        ).status_code
        == 404
    )
