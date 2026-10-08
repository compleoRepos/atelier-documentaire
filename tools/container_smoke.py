#!/usr/bin/env python3
"""Validation HTTP de laboratoire avec fixture PDF française synthétique uniquement."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import fitz
import httpx


def synthetic_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595.32, height=841.92)
    page.insert_text((54, 72), "Attestation de travail test synthétique 1234", fontsize=14)
    page.insert_textbox(
        (54, 110, 540, 210),
        "Document généré localement pour validation. Aucun dossier réel.",
        fontsize=11,
    )
    data = doc.tobytes()
    doc.close()
    return data


def check(name, status, detail=None):
    item = {"name": name, "status": status}
    if detail is not None:
        item["detail"] = detail
    return item


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=os.getenv("LOAD_TEST_BASE_URL", "http://127.0.0.1:8080"))
    p.add_argument(
        "--credentials-file", type=Path, default=Path("/tmp/translator-lab-credentials.json")
    )
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timeout", type=float, default=300.0)
    args = p.parse_args()
    creds = json.loads(args.credentials_file.read_text(encoding="utf-8"))
    username, password = creds["username"], creds["password"]
    checks = []
    pdf = synthetic_pdf()
    source_sha = hashlib.sha256(pdf).hexdigest()
    started = time.perf_counter()
    doc_id = None
    token = None
    try:
        with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30.0) as c:
            r = c.get("/api/health")
            checks.append(
                check(
                    "api_health_private", "PASS" if r.status_code == 200 else "FAIL", r.status_code
                )
            )
            unauth = c.get("/api/documents")
            checks.append(
                check(
                    "unauthenticated_documents_401",
                    "PASS" if unauth.status_code == 401 else "FAIL",
                    unauth.status_code,
                )
            )
            bad = c.post(
                "/api/auth/login", json={"username": username, "password": "invalid-lab-password"}
            )
            checks.append(
                check(
                    "invalid_login_401",
                    "PASS" if bad.status_code == 401 else "FAIL",
                    bad.status_code,
                )
            )
            login = c.post("/api/auth/login", json={"username": username, "password": password})
            if login.status_code != 200:
                checks.append(check("valid_login_200", "FAIL", login.status_code))
                raise RuntimeError("login échoué")
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            checks.append(check("valid_login_200", "PASS", 200))
            up = c.post(
                "/api/documents",
                headers=headers,
                files={"file": ("attestation-synthetique.pdf", pdf, "application/pdf")},
            )
            if up.status_code not in (200, 201):
                checks.append(check("upload_native_french_pdf", "FAIL", up.status_code))
                raise RuntimeError(f"upload HTTP {up.status_code}")
            body = up.json()
            doc_id = body.get("id")
            checks.append(
                check(
                    "upload_native_french_pdf",
                    "PASS",
                    {"document_id": doc_id, "sha256": source_sha},
                )
            )
            deadline = time.monotonic() + args.timeout
            status_history = []
            current = body.get("status")
            while time.monotonic() < deadline and current not in {
                "ANALYZED",
                "REVIEW_REQUIRED",
                "FAILED",
                "APPROVED",
            }:
                time.sleep(1)
                got = c.get(f"/api/documents/{doc_id}", headers=headers)
                got.raise_for_status()
                item = got.json()
                current = item.get("status")
                status_history.append(current)
            checks.append(
                check(
                    "analyze_celery_bounded",
                    "PASS" if current == "ANALYZED" else "FAIL",
                    {"status": current, "history": status_history[-20:]},
                )
            )
            if current != "ANALYZED":
                raise RuntimeError(f"analyse non terminée: {current}")
            tr = c.post(f"/api/documents/{doc_id}/translate", headers=headers)
            checks.append(
                check(
                    "translate_queued_celery",
                    "PASS" if tr.status_code in (200, 201) else "FAIL",
                    tr.status_code,
                )
            )
            deadline = time.monotonic() + args.timeout
            status_history = []
            while time.monotonic() < deadline:
                time.sleep(1)
                got = c.get(f"/api/documents/{doc_id}", headers=headers)
                got.raise_for_status()
                item = got.json()
                current = item.get("status")
                status_history.append(current)
                if current in {"REVIEW_REQUIRED", "FAILED", "APPROVED"}:
                    break
            checks.append(
                check(
                    "translation_review_required",
                    "PASS" if current == "REVIEW_REQUIRED" else "FAIL",
                    {"status": current, "history": status_history[-30:]},
                )
            )
            if current != "REVIEW_REQUIRED":
                raise RuntimeError(f"traduction non revue: {current}")
            for kind in ("original", "translated", "diff"):
                pr = c.get(f"/api/documents/{doc_id}/preview/{kind}/1", headers=headers)
                checks.append(
                    check(
                        f"preview_{kind}_png_200",
                        "PASS"
                        if pr.status_code == 200
                        and pr.headers.get("content-type", "").startswith("image/png")
                        else "FAIL",
                        {
                            "status": pr.status_code,
                            "content_type": pr.headers.get("content-type"),
                            "bytes": len(pr.content),
                        },
                    )
                )
            latest = c.get(f"/api/documents/{doc_id}", headers=headers)
            latest.raise_for_status()
            item = latest.json()
            version = item.get("review_version")
            rev = c.post(
                f"/api/documents/{doc_id}/review",
                headers=headers,
                json={
                    "action": "approve",
                    "attest_review": True,
                    "promote_golden": True,
                    "expected_version": version,
                },
            )
            checks.append(
                check(
                    "approve_attest_review_promote_golden",
                    "PASS" if rev.status_code == 200 else "FAIL",
                    {
                        "status": rev.status_code,
                        "document_status": rev.json().get("status")
                        if rev.headers.get("content-type", "").startswith("application/json")
                        else None,
                    },
                )
            )
            final = c.get(f"/api/documents/{doc_id}/artifact/final", headers=headers)
            final_sha = (
                hashlib.sha256(final.content).hexdigest() if final.status_code == 200 else None
            )
            checks.append(
                check(
                    "download_final_pdf_200",
                    "PASS" if final.status_code == 200 else "FAIL",
                    {"status": final.status_code, "sha256": final_sha, "bytes": len(final.content)},
                )
            )
            original = c.get(f"/api/documents/{doc_id}/artifact/original", headers=headers)
            checks.append(
                check(
                    "original_sha_distinct_from_final_check",
                    "PASS"
                    if original.status_code == 200
                    and hashlib.sha256(original.content).hexdigest() == source_sha
                    else "FAIL",
                    {
                        "status": original.status_code,
                        "sha256": hashlib.sha256(original.content).hexdigest()
                        if original.status_code == 200
                        else None,
                    },
                )
            )
    except Exception as exc:
        checks.append(check("smoke_execution", "FAIL", type(exc).__name__ + ": " + str(exc)))
    statuses = [x["status"] for x in checks]
    result = {
        "method": "HTTP loopback privé via frontend, fixture PDF native française synthétique",
        "scope": "offline/native; aucun OCR, LLM public ou GPU",
        "document_id": doc_id,
        "source_sha256": source_sha,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "checks": checks,
        "status": "FAIL" if "FAIL" in statuses else "PASS",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"status": result["status"], "checks": len(checks), "document_id": doc_id},
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
