from __future__ import annotations

import io
import zipfile

import fitz
from PIL import Image

from .conftest import login


def pdf_bytes(text: str = "Bonjour chantier 1234") -> bytes:
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.insert_text((20, 40), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def test_upload_analyse_translate_persists_previews_and_artifact_headers(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    response = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("source.pdf", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()["id"]
    detail = client.get(f"/api/documents/{document_id}", headers=headers).json()
    assert detail["status"] == "ANALYZED"
    assert (
        client.get(f"/api/documents/{document_id}/preview/original/1", headers=headers).status_code
        == 200
    )
    assert (
        client.post(f"/api/documents/{document_id}/translate", headers=headers).status_code == 200
    )
    detail = client.get(f"/api/documents/{document_id}", headers=headers).json()
    assert detail["status"] == "REVIEW_REQUIRED"
    assert (
        client.get(
            f"/api/documents/{document_id}/preview/translated/1", headers=headers
        ).status_code
        == 200
    )
    candidate = client.get(f"/api/documents/{document_id}/artifact/candidate", headers=headers)
    assert candidate.status_code == 200
    assert candidate.headers["content-type"].startswith("application/pdf")
    assert ".pdf" in candidate.headers["content-disposition"]


def test_cross_tenant_documents_and_artifacts_are_not_visible(client):
    owner = login(client, "admin-a", "Admin-A-password-12")
    other = login(client, "user-b", "User-B-password-12")
    uploaded = client.post(
        "/api/documents",
        headers=owner,
        files={"file": ("private.pdf", pdf_bytes(), "application/pdf")},
    )
    document_id = uploaded.json()["id"]
    assert client.get(f"/api/documents/{document_id}", headers=other).status_code == 404
    assert (
        client.get(f"/api/documents/{document_id}/artifact/original", headers=other).status_code
        == 404
    )
    assert (
        client.get(f"/api/documents/{document_id}/preview/original/1", headers=other).status_code
        == 404
    )
    assert client.get("/api/documents", headers=other).json() == []


def test_validation_rejects_mime_spoof_and_docx_external_relationship(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    spoof = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("spoof.pdf", b"not a pdf", "application/pdf")},
    )
    assert spoof.status_code in {415, 422}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr("word/_rels/document.xml.rels", "<Relationship TargetMode='External'/>")
    malicious = client.post(
        "/api/documents",
        headers=headers,
        files={
            "file": (
                "bad.docx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert malicious.status_code == 422


def test_png_candidate_is_pdf_with_correct_mime(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    image = io.BytesIO()
    Image.new("RGB", (220, 100), "white").save(image, format="PNG")
    uploaded = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("scan.png", image.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["id"]
    assert (
        client.post(f"/api/documents/{document_id}/translate", headers=headers).status_code == 200
    )
    candidate = client.get(f"/api/documents/{document_id}/artifact/candidate", headers=headers)
    assert candidate.status_code == 200
    assert candidate.headers["content-type"].startswith("application/pdf")
    assert ".pdf" in candidate.headers["content-disposition"]
