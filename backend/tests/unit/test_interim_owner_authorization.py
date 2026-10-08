"""Owner-authorised real-document scope for the temporary Interim provider.

All requests go to an httpx.MockTransport: no network, no real document.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.ai.translation.interim import InterimTranslationEngine
from app.ai.translation.interim_guard import authorize_interim_owner_document
from app.ai.translation.service import translate_blocks
from app.core.settings import Settings


class GPTDouble:
    def encode(self, value, **kwargs):
        return list(range(max(1, len(value) // 4)))


SOURCE = b"owner-authorised test document bytes"
SHA = hashlib.sha256(SOURCE).hexdigest()


def ir(sha=SHA):
    return {
        "language": "en",
        "domain": "HR",
        "versions": {"source_sha256": sha},
        "pages": [{"number": 1, "blocks": [{"id": "b1", "text": "Employment certificate.", "language": "en"}]}],
    }


def authorization(tmp_path, **overrides):
    now = datetime.now(UTC)
    record = {
        "authorization_id": "AUTH-TEST-001",
        "authorized_by": "Data owner (test)",
        "decided_at": (now - timedelta(minutes=5)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "decision": "Test: send listed documents to Interim",
        "provider": "interim",
        "model": "gpt-5-mini",
        "document_sha256": [SHA],
        **overrides,
    }
    path = tmp_path / "owner-authorization.json"
    path.write_text(json.dumps(record))
    return path


def options(tmp_path, transport=None, **values):
    auth_path = values.pop("auth_path", None)
    if auth_path is None:
        auth_path = authorization(tmp_path)
    return {
        "engine": "interim",
        "interim_data_scope": "owner_authorized_document",
        "interim_owner_authorization_file": str(auth_path),
        "source_sha256": values.pop("source_sha256", SHA),
        "interim_api_base": "https://interim.test/v1",
        "tokenizer": GPTDouble(),
        "transport": transport or httpx.MockTransport(lambda r: (_ for _ in ()).throw(AssertionError("no HTTP"))),
        "interim_capability_proof": "MOCK_ONLY_CAP_CONTRACT",
        "_corpus_input_dir": tmp_path / "no-corpus",
        **values,
    }


def ok_response(seen):
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        assert body["model"] == "gpt-5-mini"
        assert body["max_completion_tokens"] <= 8000
        content = json.dumps({"translations": [{"id": "b1", "text": "Attestation de travail."}]})
        return httpx.Response(200, json={
            "model": "gpt-5-mini",
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 10, "total_tokens": 130,
                      "completion_tokens_details": {"reasoning_tokens": 0}},
        })
    return handler


@pytest.mark.asyncio
async def test_listed_document_is_sent_once_with_traced_owner_authorization(tmp_path):
    seen = []
    result = await translate_blocks(ir(), options(tmp_path, httpx.MockTransport(ok_response(seen))))
    assert len(seen) == 1
    assert not [i for i in result["issues"] if i["severity"] == "critical"]
    assert result["translations"]["b1"] == "Attestation de travail."
    telemetry = result["translation_telemetry"]
    assert telemetry["data_scope"] == "owner_authorized_real_document"
    assert telemetry["data_boundary"] == "outside_private_cloud"
    assert telemetry["owner_authorization"]["authorization_id"] == "AUTH-TEST-001"
    assert telemetry["reference_validated"] is False
    for chunk in telemetry["chunks"]:
        assert chunk["reserved_total_tokens"] <= 32768


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"document_sha256": ["0" * 64]}, "INTERIM_OWNER_DOCUMENT_NOT_AUTHORIZED"),
        ({"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
          "decided_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat()}, "INTERIM_OWNER_AUTHORIZATION_EXPIRED"),
        ({"provider": "openai"}, "INTERIM_OWNER_AUTHORIZATION_PROVIDER_MISMATCH"),
        ({"model": "other-model"}, "INTERIM_OWNER_AUTHORIZATION_PROVIDER_MISMATCH"),
        ({"authorized_by": ""}, "INTERIM_OWNER_AUTHORIZATION_INVALID"),
        ({"document_sha256": ["not-a-sha"]}, "INTERIM_OWNER_AUTHORIZATION_INVALID"),
        ({"decided_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}, "INTERIM_OWNER_AUTHORIZATION_INVALID"),
    ],
)
async def test_invalid_authorization_blocks_before_any_request(tmp_path, change, code):
    result = await translate_blocks(ir(), options(tmp_path, auth_path=authorization(tmp_path, **change)))
    assert result["issues"][0]["code"] == code
    assert result["translation_telemetry"]["requests_sent"] == 0
    assert result["translations"]["b1"] == "Employment certificate."


@pytest.mark.asyncio
async def test_missing_or_corrupt_authorization_file_blocks(tmp_path):
    missing = await translate_blocks(ir(), options(tmp_path, auth_path=tmp_path / "absent.json"))
    assert missing["issues"][0]["code"] == "INTERIM_OWNER_AUTHORIZATION_REQUIRED"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    corrupt = await translate_blocks(ir(), options(tmp_path, auth_path=bad))
    assert corrupt["issues"][0]["code"] == "INTERIM_OWNER_AUTHORIZATION_INVALID"


@pytest.mark.asyncio
async def test_hash_mismatch_between_analysis_and_job_blocks(tmp_path):
    result = await translate_blocks(ir(), options(tmp_path, source_sha256="f" * 64))
    assert result["issues"][0]["code"] == "INTERIM_OWNER_SOURCE_HASH_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["production", "prod", "private"])
async def test_owner_authorization_never_unlocks_private_or_production(tmp_path, environment):
    result = await translate_blocks(ir(), options(tmp_path, environment=environment))
    assert result["issues"][0]["code"] == "INTERIM_FORBIDDEN_IN_PRIVATE_PRODUCTION"


def test_guard_requires_owner_scope(tmp_path):
    opts = options(tmp_path)
    opts["interim_data_scope"] = "synthetic_fixture"
    code, record, sha = authorize_interim_owner_document(ir(), opts)
    assert code == "INTERIM_OWNER_AUTHORIZATION_REQUIRED" and record is None and sha is None


@pytest.mark.asyncio
async def test_engine_rechecks_owner_binding_before_http():
    seen = []
    engine = InterimTranslationEngine(
        base_url="https://interim.test/v1", tokenizer=GPTDouble(), data_scope="owner_authorized_document",
        fixture_sha256=SHA, allowed_fixture_sha256=["0" * 64], owner_authorization_id="AUTH-TEST-001",
        capability_proof="MOCK_ONLY_CAP_CONTRACT", transport=httpx.MockTransport(lambda r: seen.append(r)),
    )
    result = await engine.translate_chunk([{"role": "user", "content": "x"}], ["b1"], max_output=64)
    assert seen == []
    assert result.issues[0]["code"] == "INTERIM_OWNER_DOCUMENT_NOT_AUTHORIZED"
    no_id = InterimTranslationEngine(
        base_url="https://interim.test/v1", tokenizer=GPTDouble(), data_scope="owner_authorized_document",
        fixture_sha256=SHA, allowed_fixture_sha256=[SHA], capability_proof="MOCK_ONLY_CAP_CONTRACT",
        transport=httpx.MockTransport(lambda r: seen.append(r)),
    )
    result = await no_id.translate_chunk([{"role": "user", "content": "x"}], ["b1"], max_output=64)
    assert seen == []
    assert result.issues[0]["code"] == "INTERIM_OWNER_AUTHORIZATION_REQUIRED"


def test_settings_require_authorization_file_for_owner_scope(tmp_path):
    with pytest.raises(ValueError):
        Settings(engine="interim", interim_data_scope="owner_authorized_document")
    settings = Settings(engine="interim", interim_data_scope="owner_authorized_document",
                        interim_owner_authorization_file=str(authorization(tmp_path)))
    assert settings.interim_owner_authorization_file is not None
