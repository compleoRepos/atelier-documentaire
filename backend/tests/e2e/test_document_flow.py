from __future__ import annotations

import hashlib

import fitz

from ..integration.conftest import login


def make_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page(width=320, height=220)
    page.insert_text((20, 45), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def test_french_native_pdf_review_approval_preserves_original(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    source = make_pdf(
        "Le présent document décrit les travaux de construction et la sécurité du chantier 1234."
    )
    uploaded = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("rapport.pdf", source, "application/pdf")},
    )
    document_id = uploaded.json()["id"]
    assert (
        client.post(f"/api/documents/{document_id}/translate", headers=headers).status_code == 200
    )
    detail = client.get(f"/api/documents/{document_id}", headers=headers).json()
    version = detail["review_version"]
    approved = client.post(
        f"/api/documents/{document_id}/review",
        headers=headers,
        json={
            "action": "approve",
            "attest_review": True,
            "expected_version": version,
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    final = client.get(f"/api/documents/{document_id}/artifact/final", headers=headers)
    assert final.status_code == 200
    assert final.content.startswith(b"%PDF-")
    assert (
        hashlib.sha256(source).hexdigest()
        == hashlib.sha256(
            client.get(f"/api/documents/{document_id}/artifact/original", headers=headers).content
        ).hexdigest()
    )


def test_unknown_blocks_need_correction_and_corrections_create_new_version(client):
    headers = login(client, "admin-a", "Admin-A-password-12")
    uploaded = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("english.pdf", make_pdf("Unknown English amount 1234"), "application/pdf")},
    )
    document_id = uploaded.json()["id"]
    client.post(f"/api/documents/{document_id}/translate", headers=headers)
    detail = client.get(f"/api/documents/{document_id}", headers=headers).json()
    assert (
        client.post(
            f"/api/documents/{document_id}/review",
            headers=headers,
            json={"action": "approve", "attest_review": True},
        ).status_code
        == 422
    )
    blocks = [block for page in detail["analysis"]["pages"] for block in page["blocks"]]
    corrections = {block["id"]: "Montant anglais 1234" for block in blocks}
    corrected = client.post(
        f"/api/documents/{document_id}/review",
        headers=headers,
        json={"action": "correct", "corrections": corrections},
    )
    assert corrected.status_code == 200, corrected.text
    new_detail = client.get(f"/api/documents/{document_id}", headers=headers).json()
    assert new_detail["review_version"] == detail["review_version"] + 1
    assert (
        client.post(
            f"/api/documents/{document_id}/review",
            headers=headers,
            json={
                "action": "approve",
                "attest_review": True,
                "promote_golden": True,
                "expected_version": new_detail["review_version"],
            },
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/documents/{document_id}/artifact/final", headers=headers).status_code
        == 200
    )
    assert client.post(f"/api/documents/{document_id}/analyze", headers=headers).status_code == 200
    assert (
        client.get(f"/api/documents/{document_id}/artifact/final", headers=headers).status_code
        == 403
    )
