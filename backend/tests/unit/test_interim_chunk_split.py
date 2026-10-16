"""Interim requests refused (prompt bound) or rejected (IDs/cardinality) are split
into smaller requests; rejected output is never accepted. MockTransport only."""

from __future__ import annotations

import json

import httpx
import pytest
from test_interim_owner_authorization import SHA, options

from app.ai.translation.service import translate_blocks

SHA_IR_IDS = [f"b{i}" for i in range(1, 7)]


def ir_many(ids=SHA_IR_IDS):
    return {
        "language": "en",
        "domain": "HR",
        "versions": {"source_sha256": SHA},
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {"id": i, "text": f"Employment certificate line {i}.", "language": "en"} for i in ids
                ],
            }
        ],
    }


def handler_factory(seen, drop_above: int | None):
    def handler(request):
        body = json.loads(request.content)
        ids = [b["id"] for b in json.loads(body["messages"][1]["content"])["blocks"]]
        seen.append(ids)
        answered = ids[:-1] if drop_above is not None and len(ids) > drop_above else ids
        content = json.dumps({"translations": [{"id": i, "text": f"Attestation ligne {i}."} for i in answered]})
        return httpx.Response(
            200,
            json={
                "model": "gpt-5-mini",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 10, "total_tokens": 130,
                          "completion_tokens_details": {"reasoning_tokens": 0}},
            },
        )

    return handler


@pytest.mark.asyncio
async def test_rejected_output_is_split_and_never_accepted(tmp_path):
    seen: list[list[str]] = []
    result = await translate_blocks(
        ir_many(), options(tmp_path, httpx.MockTransport(handler_factory(seen, drop_above=2)))
    )
    assert seen[0] == SHA_IR_IDS  # first request covers the whole chunk and is rejected
    assert len(seen) > 1 and all(len(ids) < len(SHA_IR_IDS) for ids in seen[1:])
    for block_id in SHA_IR_IDS:
        assert result["translations"][block_id] == f"Attestation ligne {block_id}."
    codes = [i["code"] for i in result["issues"]]
    assert "INTERIM_CHUNK_SPLIT_RETRY" in codes
    assert not [i for i in result["issues"] if i.get("severity") == "critical" and "INTERIM" in i["code"]]
    assert not result["untranslated_blocks"]


@pytest.mark.asyncio
async def test_split_depth_is_bounded_and_failures_stay_critical(tmp_path):
    seen: list[list[str]] = []
    # Every multi-block request and every single block is rejected.
    result = await translate_blocks(
        ir_many(), options(tmp_path, httpx.MockTransport(handler_factory(seen, drop_above=0)))
    )
    assert len(seen) <= 2 * len(SHA_IR_IDS)  # binary split, bounded
    assert set(result["untranslated_blocks"]) == set(SHA_IR_IDS)
    for block_id in SHA_IR_IDS:
        assert result["translations"][block_id] == f"Employment certificate line {block_id}."
    assert any(i.get("severity") == "critical" for i in result["issues"])


@pytest.mark.asyncio
async def test_proactive_block_cap_per_request(tmp_path):
    seen: list[list[str]] = []
    result = await translate_blocks(
        ir_many(),
        options(
            tmp_path,
            httpx.MockTransport(handler_factory(seen, drop_above=None)),
            interim_max_blocks_per_request=2,
        ),
    )
    assert seen and all(len(ids) <= 2 for ids in seen)
    assert sorted(i for ids in seen for i in ids) == sorted(SHA_IR_IDS)
    assert "INTERIM_CHUNK_SPLIT_RETRY" not in [i["code"] for i in result["issues"]]
    assert not result["untranslated_blocks"]
