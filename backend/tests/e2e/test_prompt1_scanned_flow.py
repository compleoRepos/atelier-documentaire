from __future__ import annotations

import hashlib

import fitz

from ..integration.conftest import login


def test_scanned_upload_processing_review_preserves_original_and_snapshots(client):
    document = fitz.open()
    page = document.new_page(width=400,height=300)
    for i in range(10):
        page.insert_text((20,30+i*22),"Employment document quality control 1234",fontsize=11)
    source = page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).tobytes("png")
    document.close()
    headers = login(client,"admin-a","Admin-A-password-12")
    uploaded = client.post("/api/documents",headers=headers,files={"file":("scan.png",source,"image/png")})
    assert uploaded.status_code == 200
    document_id = uploaded.json()["id"]
    detail = client.get(f"/api/documents/{document_id}",headers=headers).json()
    meta = detail["analysis"]["pages"][0]["preprocessing"]
    assert meta["processing_image_path"].startswith("storage://")
    assert meta["PreprocessingQualityScore"]["cer"] is None
    assert meta["PreprocessingQualityScore"]["validated"] is False
    enhanced = client.get(f"/api/documents/{document_id}/preview/enhanced/1",headers=headers)
    assert enhanced.status_code == 200
    assert enhanced.content.startswith(b"\x89PNG")
    translated = client.post(f"/api/documents/{document_id}/translate",headers=headers)
    assert translated.status_code == 200
    detail = client.get(f"/api/documents/{document_id}",headers=headers).json()
    assert detail["status"] == "REVIEW_REQUIRED"
    assert detail["translation"]["untranslated_blocks"]
    version = detail["review_version"]
    assert version == 1
    snapshot = client.get(f"/api/documents/{document_id}/preview/enhanced/1?version={version}",headers=headers)
    assert snapshot.content == enhanced.content
    original = client.get(f"/api/documents/{document_id}/artifact/original",headers=headers)
    assert hashlib.sha256(original.content).hexdigest() == hashlib.sha256(source).hexdigest()
    assert client.get(f"/api/documents/{document_id}/artifact/final",headers=headers).status_code == 403
    assert client.post(f"/api/documents/{document_id}/analyze",headers=headers).status_code == 200
    assert client.get(f"/api/documents/{document_id}/preview/enhanced/1?version={version}",headers=headers).content == enhanced.content
