from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_human_reference_does_not_cross_tenant_boundaries(tmp_path):
    loader = module("golden_references")
    sha = "a" * 64
    path = tmp_path / "tenant-a" / sha / "v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "approved": True,
                "source_sha256": sha,
                "tenant_id": "tenant-a",
                "reviewer_id": "synthetic-reviewer",
                "validated_at": "2026-10-07T12:00:00Z",
                "version": 1,
                "target_text": "Texte synthétique",
            }
        )
    )
    assert loader.load_reference(tmp_path, sha, "tenant-a") is not None
    assert loader.load_reference(tmp_path, sha, "tenant-b") is None
    assert loader.load_reference(tmp_path, sha, None) is None


def test_unapproved_reference_is_not_loaded(tmp_path):
    loader = module("golden_references")
    sha = "a" * 64
    (tmp_path / f"{sha}.json").write_text(
        json.dumps(
            {
                "approved": False,
                "source_sha256": sha,
                "reviewer_id": "synthetic-reviewer",
                "validated_at": "2026-10-07T12:00:00Z",
                "version": 1,
            }
        )
    )
    assert loader.load_reference(tmp_path, sha) is None


@pytest.mark.asyncio
async def test_load_client_requests_translation_after_analysis(monkeypatch):
    load = module("load_test")
    monkeypatch.setattr(load.asyncio, "sleep", AsyncMock())
    requested = []

    def handler(request):
        requested.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/api/documents":
            return httpx.Response(200, json={"id": "synthetic-doc"})
        if request.url.path.endswith("/translate"):
            return httpx.Response(200, json={"status": "TRANSLATING"})
        translated = ("POST", "/api/documents/synthetic-doc/translate") in requested
        return httpx.Response(
            200, json={"status": "REVIEW_REQUIRED" if translated else "ANALYZED", "quality": {}}
        )

    async with httpx.AsyncClient(
        base_url="https://synthetic.invalid", transport=httpx.MockTransport(handler)
    ) as client:
        result = await load.one_run(
            client, load.synthetic_pdf(1), {"Authorization": "Bearer synthetic"}, 2
        )
    assert result["ok"] is True
    assert requested.count(("POST", "/api/documents/synthetic-doc/translate")) == 1
