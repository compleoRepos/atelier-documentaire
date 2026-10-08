"""Charge bornée réelle : PDF natifs français synthétiques, une session de fixture partagée.

Mesure des clients virtuels concurrents, pas 100 identités bancaires distinctes.
Aucune donnée réelle, aucun modèle public, aucune extrapolation OCR/GPU.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

import fitz
import httpx

TERMINAL = {"APPROVED", "REJECTED", "FAILED", "REVIEW_REQUIRED"}


def synthetic_pdf(pages: int) -> bytes:
    document = fitz.open()
    for number in range(pages):
        page = document.new_page(width=595.32, height=841.92)
        page.insert_text(
            (54, 72), f"Attestation de travail synthétique — page {number + 1}", fontsize=12
        )
        page.insert_textbox(
            (54, 100, 540, 180),
            "Document de test créé localement. Aucune donnée réelle de production.",
            fontsize=10,
        )
    content = document.tobytes()
    document.close()
    return content


async def one_run(
    client: httpx.AsyncClient, pdf: bytes, headers: dict[str, str], poll_timeout: float
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = await client.post(
            "/api/documents",
            headers=headers,
            files={"file": ("synthetic-load.pdf", pdf, "application/pdf")},
        )
        response.raise_for_status()
        identity = response.json().get("id")
        if not identity:
            raise RuntimeError("Réponse upload sans identifiant")
        deadline = time.monotonic() + poll_timeout
        requested_translation = False
        while time.monotonic() < deadline:
            status_response = await client.get(f"/api/documents/{identity}", headers=headers)
            status_response.raise_for_status()
            item = status_response.json()
            status = item.get("status")
            if status == "ANALYZED" and not requested_translation:
                translation = await client.post(
                    f"/api/documents/{identity}/translate", headers=headers
                )
                translation.raise_for_status()
                requested_translation = True
            if status in TERMINAL:
                quality = item.get("quality") or {}
                return {
                    "ok": status != "FAILED",
                    "status": status,
                    "document_id": identity,
                    "seconds": time.perf_counter() - started,
                    "ocr_seconds": quality.get("ocr_seconds"),
                    "llm_seconds": quality.get("llm_seconds"),
                    "gpu_seconds": quality.get("gpu_seconds"),
                }
            await asyncio.sleep(0.5)
        return {
            "ok": False,
            "status": "TIMEOUT",
            "document_id": identity,
            "seconds": time.perf_counter() - started,
        }
    except (httpx.HTTPError, KeyError, RuntimeError, ValueError) as error:
        return {
            "ok": False,
            "status": "ERROR",
            "seconds": time.perf_counter() - started,
            "error": str(error),
        }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    username, password = os.getenv("LOAD_TEST_USERNAME", ""), os.getenv("LOAD_TEST_PASSWORD", "")
    if not username or not password:
        raise SystemExit(
            "LOAD_TEST_USERNAME et LOAD_TEST_PASSWORD requis ; aucun compte par défaut."
        )
    pdf = synthetic_pdf(args.pages)
    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), limits=limits, timeout=args.timeout, trust_env=False
    ) as client:
        login = await client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        started = time.perf_counter()
        results = await asyncio.gather(
            *(one_run(client, pdf, headers, args.timeout) for _ in range(args.users))
        )
        elapsed = time.perf_counter() - started
    durations = sorted(result["seconds"] for result in results)
    successes = sum(result["ok"] for result in results)
    return {
        "base_url": args.base_url,
        "synthetic_only": True,
        "scope": "native/français/offline ; une session de fixture, clients virtuels concurrents",
        "users": args.users,
        "pages_per_document": args.pages,
        "requests": len(results),
        "successes": successes,
        "errors": len(results) - successes,
        "total_seconds": elapsed,
        "average_seconds": statistics.mean(durations),
        "p95_seconds": durations[max(0, min(len(durations) - 1, int(len(durations) * 0.95) - 1))],
        "throughput_documents_per_second": successes / elapsed if elapsed else None,
        "ocr_seconds": None,
        "llm_seconds": None,
        "gpu_seconds": None,
        "results": results,
        "note": "Chronométrage complet upload/analyse/traduction hors ligne jusqu'à REVIEW_REQUIRED. Pas de certification linguistique ou GPU.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=os.getenv("LOAD_TEST_BASE_URL", "http://127.0.0.1:8080")
    )
    parser.add_argument("--users", type=int, default=1)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.users <= 100 or not 1 <= args.pages <= 200 or args.timeout <= 0:
        parser.error("clients 1..100, pages 1..200, timeout positif requis")
    result = asyncio.run(run(args))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
