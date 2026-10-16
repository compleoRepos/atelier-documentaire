"""RUN26 P0 evidence: request traces, per-block provenance, reconciliation, generation mode.

Synthetic data only. Every HTTP request goes to an httpx.MockTransport: no network, no real document.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.ai.translation.interim import _response_id
from app.ai.translation.service import _record_provenance, translate_blocks

ROOT = Path(__file__).resolve().parents[3]
SOURCE = b"synthetic traceability test bytes"
SHA = hashlib.sha256(SOURCE).hexdigest()


class GPTDouble:
    def encode(self, value, **kwargs):
        return list(range(max(1, len(value) // 4)))


def _ir(second="| |", no_linguistic=True):
    return {
        "language": "en",
        "domain": "HR",
        "versions": {"source_sha256": SHA},
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {"id": "b1", "text": "Synthetic status report.", "language": "en"},
                    {
                        "id": "b2",
                        "text": second,
                        "language": "unknown" if no_linguistic else "en",
                        "no_linguistic_content": no_linguistic,
                    },
                ],
            }
        ],
    }


def _options(tmp_path, transport):
    now = datetime.now(UTC)
    auth = tmp_path / "owner-authorization.json"
    auth.write_text(
        json.dumps(
            {
                "authorization_id": "TEST-TRACE-001",
                "authorized_by": "Data owner (test)",
                "decided_at": (now - timedelta(minutes=5)).isoformat(),
                "expires_at": (now + timedelta(hours=1)).isoformat(),
                "decision": "Test: send listed synthetic documents to Interim",
                "provider": "interim",
                "model": "gpt-5-mini",
                "document_sha256": [SHA],
            }
        )
    )
    return {
        "engine": "interim",
        "interim_data_scope": "owner_authorized_document",
        "interim_owner_authorization_file": str(auth),
        "source_sha256": SHA,
        "interim_api_base": "https://interim.test/v1",
        "tokenizer": GPTDouble(),
        "transport": transport,
        "interim_capability_proof": "MOCK_ONLY_CAP_CONTRACT",
        "_corpus_input_dir": tmp_path / "no-corpus",
    }


def _ok(seen_headers, response_id="resp-0001"):
    def handler(request):
        seen_headers.append(dict(request.headers))
        content = json.dumps(
            {"translations": [{"id": "b1", "text": "Rapport d'état synthétique."}]}
        )
        return httpx.Response(
            200,
            json={
                "id": response_id,
                "model": "gpt-5-mini",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 10,
                    "total_tokens": 130,
                    "completion_tokens_details": {"reasoning_tokens": 0},
                },
            },
        )

    return handler


def test_response_id_keeps_only_short_opaque_tokens():
    assert _response_id({"id": "chatcmpl-abc_1.2:3"}) == "chatcmpl-abc_1.2:3"
    assert _response_id({"id": "x" * 129}) is None
    assert _response_id({"id": "has a space"}) is None
    assert _response_id({"id": 123}) is None
    assert _response_id({}) is None


@pytest.mark.asyncio
async def test_model_call_is_traced_and_reconciled_block_by_block(tmp_path):
    headers = []
    result = await translate_blocks(_ir(), _options(tmp_path, httpx.MockTransport(_ok(headers))))
    telemetry = result["translation_telemetry"]
    assert telemetry["requests_sent"] == 1 == len(headers)
    traces = telemetry["request_trace"]
    assert len(traces) == telemetry["requests_sent"]
    trace = traces[0]
    assert trace["request_index"] == 1
    assert trace["http_status"] == 200
    assert trace["response_id"] == "resp-0001"
    assert trace["served_model"] == "gpt-5-mini"
    assert trace["total_tokens"] == 130
    assert trace["block_ids"] == ["b1"]
    assert headers[0]["x-request-id"] == trace["correlation_id"]
    assert datetime.fromisoformat(trace["completed_at"]) >= datetime.fromisoformat(
        trace["started_at"]
    )
    blocks = telemetry["block_provenance"]["blocks"]
    assert blocks["b1"]["origin"] == "MODEL_CALL"
    assert blocks["b1"]["outcome"] == "CHANGED"
    assert blocks["b1"]["correlation_id"] == trace["correlation_id"]
    assert blocks["b2"] == {"origin": "NOT_SENT"}
    assert {
        i["block_id"] for i in result["issues"] if i["code"] == "NO_LINGUISTIC_CONTENT_KEPT"
    } == {"b2"}
    assert telemetry["block_provenance"]["summary"] == {"MODEL_CALL": 1, "NOT_SENT": 1}
    assert telemetry["generation_mode"] == "NEW_MODEL_GENERATION"
    assert telemetry["model_invoked"] is True
    assert not [i for i in result["issues"] if i["code"] == "EVIDENCE_REQUEST_COUNT_MISMATCH"]


@pytest.mark.asyncio
async def test_split_retry_keeps_one_trace_per_request_and_final_origin_per_block(tmp_path):
    # The model answers only for b1: the chunk is rejected, split and retried block by block.
    headers = []
    result = await translate_blocks(
        _ir(second="12345", no_linguistic=False),
        _options(tmp_path, httpx.MockTransport(_ok(headers))),
    )
    telemetry = result["translation_telemetry"]
    traces = telemetry["request_trace"]
    assert telemetry["requests_sent"] == len(traces) == len(headers) == 3
    assert [t["request_index"] for t in traces] == [1, 2, 3]
    assert [t["block_ids"] for t in traces] == [["b1", "b2"], ["b1"], ["b2"]]
    assert len({t["correlation_id"] for t in traces}) == 3
    blocks = telemetry["block_provenance"]["blocks"]
    assert blocks["b1"]["origin"] == "MODEL_CALL" and blocks["b1"]["request_index"] == 2
    assert blocks["b2"]["origin"] == "MODEL_CALL_FAILED" and blocks["b2"]["request_index"] == 3
    assert result["translations"]["b2"] == "12345"
    assert "INTERIM_INVALID_MODEL_OUTPUT" in {i["code"] for i in result["issues"]}
    assert not [i for i in result["issues"] if i["code"] == "EVIDENCE_REQUEST_COUNT_MISMATCH"]


@pytest.mark.asyncio
async def test_failed_request_is_traced_and_never_counted_as_translated(tmp_path):
    def failing(request):
        return httpx.Response(500, json={"error": "synthetic failure"})

    result = await translate_blocks(_ir(), _options(tmp_path, httpx.MockTransport(failing)))
    telemetry = result["translation_telemetry"]
    assert telemetry["requests_sent"] >= 1
    assert len(telemetry["request_trace"]) == telemetry["requests_sent"]
    assert {t["http_status"] for t in telemetry["request_trace"]} == {500}
    assert all(t["completed_at"] for t in telemetry["request_trace"])
    assert telemetry["block_provenance"]["blocks"]["b1"]["origin"] == "MODEL_CALL_FAILED"
    assert result["translations"]["b1"] == "Synthetic status report."


def _telemetry(sent, traces):
    return {
        "requests_sent": sent,
        "chunks": [
            {
                "ids": [f"b{i}"],
                "usage": {"total_tokens": 10 * i},
                "served_model": "gpt-5-mini",
                "request_trace": {"request_index": i, "correlation_id": f"c{i}"},
            }
            for i in range(1, traces + 1)
        ],
    }


def test_record_provenance_marks_unsent_blocks_and_enriches_traces():
    telemetry, issues = _telemetry(1, 1), []
    origin = {"b1": {"origin": "MODEL_CALL", "request_index": 1, "correlation_id": "c1"}}
    _record_provenance(telemetry, origin, {"b1": "x", "b9": "y"}, "interim", issues)
    assert telemetry["block_provenance"]["blocks"]["b9"] == {"origin": "NOT_SENT"}
    assert telemetry["block_provenance"]["summary"] == {"MODEL_CALL": 1, "NOT_SENT": 1}
    assert telemetry["request_trace"] == [
        {
            "request_index": 1,
            "correlation_id": "c1",
            "block_ids": ["b1"],
            "total_tokens": 10,
            "served_model": "gpt-5-mini",
        }
    ]
    assert telemetry["generation_mode"] == "NEW_MODEL_GENERATION"
    assert issues == []


def test_record_provenance_flags_request_count_mismatch_as_critical():
    telemetry, issues = _telemetry(2, 1), []
    _record_provenance(telemetry, {}, {"b1": "x"}, "interim", issues)
    assert [i["code"] for i in issues] == ["EVIDENCE_REQUEST_COUNT_MISMATCH"]
    assert issues[0]["severity"] == "critical"
    assert issues[0]["requests_sent"] == 2 and issues[0]["request_traces"] == 1


@pytest.mark.parametrize(("mode", "sent"), [("interim", 0), ("offline", None)])
def test_no_request_is_never_presented_as_generation(mode, sent):
    telemetry, issues = {"requests_sent": sent, "chunks": []}, []
    _record_provenance(telemetry, {}, {"b1": "x"}, mode, issues)
    assert telemetry["generation_mode"] == "NO_MODEL_CALL"
    assert telemetry["model_invoked"] is False
    assert telemetry["request_trace"] == []


def _runner():
    spec = importlib.util.spec_from_file_location(
        "interim_owner_corpus_run", ROOT / "tools" / "interim_owner_corpus_run.py"
    )
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


CACHED = {
    "translation_telemetry": {
        "block_provenance": {"blocks": {"b1": {"origin": "MODEL_CALL", "correlation_id": "c7"}}}
    }
}


@pytest.mark.parametrize(
    ("sent", "hits", "mode"),
    [
        (0, {"b1"}, "TRANSLATION_MEMORY_REUSE_ONLY"),
        (1, {"b1"}, "MIXED_MEMORY_AND_NEW_GENERATION"),
        (1, set(), "NEW_MODEL_GENERATION"),
        (0, set(), "NO_MODEL_CALL"),
    ],
)
def test_translation_memory_is_declared_with_its_cached_origin(sent, hits, mode):
    telemetry = {"requests_sent": sent, "block_provenance": {"version": "v", "blocks": {}}}
    _runner()._merge_memory_provenance(telemetry, CACHED, hits, "run-x")
    assert telemetry["generation_mode"] == mode
    assert telemetry["model_invoked"] is bool(sent)
    if hits:
        assert telemetry["block_provenance"]["blocks"]["b1"] == {
            "origin": "TRANSLATION_MEMORY",
            "cache_run": "run-x",
            "cached_origin": "MODEL_CALL",
            "cached_correlation_id": "c7",
        }


def test_memory_without_recorded_origin_is_marked_unknown_not_model_call():
    telemetry = {"requests_sent": 0, "block_provenance": {"version": "v", "blocks": {}}}
    _runner()._merge_memory_provenance(telemetry, {}, {"b1"}, "run-old")
    block = telemetry["block_provenance"]["blocks"]["b1"]
    assert block["origin"] == "TRANSLATION_MEMORY"
    assert block["cached_origin"] == "UNKNOWN_PRE_RUN26"
    assert block["cached_correlation_id"] is None
    assert telemetry["generation_mode"] == "TRANSLATION_MEMORY_REUSE_ONLY"
    assert telemetry["model_invoked"] is False
