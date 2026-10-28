"""RUN29 F52: the private engine gets the same request policy as Interim.

A corpus pass with a private engine sent one request of several hundred blocks;
the invalid answer was rejected as a whole (fail-closed) and every block of the
chunk stayed in its source language. The Interim path already capped requests at
40 blocks and split rejected requests (bounded depth). These tests pin the same
behaviour for ``engine="private"``. Synthetic engine only, no network.
"""

from __future__ import annotations

import json

import pytest

from app.ai.translation.service import EngineResult, TranslationEngine, translate_blocks


def ir_many(count: int) -> dict:
    return {
        "language": "en",
        "domain": "HR",
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {"id": f"b{i:03d}", "text": f"Synthetic employment line {i}.", "language": "en"}
                    for i in range(count)
                ],
            }
        ],
    }


def target(block_id: str) -> str:
    return f"Ligne d'emploi synthétique {int(block_id[1:])}."


class ScriptedPrivateEngine(TranslationEngine):
    """Answers every request; rejects (like the real engine) above ``reject_above``."""

    def __init__(self, *, reject_above: int | None = None, drop_above: int | None = None):
        self.reject_above = reject_above
        self.drop_above = drop_above
        self.calls: list[list[str]] = []

    async def translate_chunk(self, messages, expected_ids, *, max_output):
        sent = {item["id"]: item["text"] for item in json.loads(messages[1]["content"])["blocks"]}
        ids = list(sent)
        self.calls.append(ids)
        if self.reject_above is not None and len(ids) > self.reject_above:
            # A rejected answer may still carry parsed text: it must never be used.
            return EngineResult(
                translations={i: "TEXTE REJETÉ" for i in ids},
                issues=[
                    {
                        "code": "INVALID_MODEL_OUTPUT",
                        "severity": "critical",
                        "message": "translation IDs/cardinality do not exactly match request",
                    }
                ],
            )
        answered = ids[:-1] if self.drop_above is not None and len(ids) > self.drop_above else ids
        # Translate the text actually sent: protected-entity markers are kept.
        return EngineResult(
            translations={
                i: sent[i].replace("Synthetic employment line", "Ligne d'emploi synthétique")
                for i in answered
            }
        )


def options(engine: TranslationEngine, **extra) -> dict:
    return {"engine": "private", "translation_engine": engine, "target_language": "fr", **extra}


@pytest.mark.asyncio
async def test_private_requests_are_capped_at_forty_blocks_by_default():
    engine = ScriptedPrivateEngine()
    result = await translate_blocks(ir_many(100), options(engine))
    assert engine.calls and max(len(ids) for ids in engine.calls) <= 40
    assert sorted(i for ids in engine.calls for i in ids) == sorted(f"b{i:03d}" for i in range(100))
    assert all(result["translations"][f"b{i:03d}"] == target(f"b{i:03d}") for i in range(100))
    assert not result["untranslated_blocks"]
    assert "PRIVATE_CHUNK_SPLIT_RETRY" not in [i["code"] for i in result["issues"]]


@pytest.mark.asyncio
async def test_private_cap_is_configurable():
    engine = ScriptedPrivateEngine()
    await translate_blocks(ir_many(9), options(engine, private_ai_max_blocks_per_request=2))
    assert all(len(ids) <= 2 for ids in engine.calls)


@pytest.mark.asyncio
async def test_private_rejected_output_is_split_and_never_accepted():
    engine = ScriptedPrivateEngine(reject_above=3)
    result = await translate_blocks(ir_many(12), options(engine))
    assert engine.calls[0] == [f"b{i:03d}" for i in range(12)]  # first request rejected
    accepted = [ids for ids in engine.calls if len(ids) <= 3]
    assert len(engine.calls) > 1
    assert sorted(i for ids in accepted for i in ids) == [f"b{i:03d}" for i in range(12)]
    for i in range(12):
        assert result["translations"][f"b{i:03d}"] == target(f"b{i:03d}")
    assert "TEXTE REJETÉ" not in result["translations"].values()
    codes = [i["code"] for i in result["issues"]]
    assert "PRIVATE_CHUNK_SPLIT_RETRY" in codes
    assert "INTERIM_CHUNK_SPLIT_RETRY" not in codes
    assert not result["untranslated_blocks"]


@pytest.mark.asyncio
async def test_private_missing_ids_are_split_instead_of_failing_the_whole_chunk():
    engine = ScriptedPrivateEngine(drop_above=1)
    result = await translate_blocks(ir_many(6), options(engine))
    assert all(result["translations"][f"b{i:03d}"] == target(f"b{i:03d}") for i in range(6))
    assert not result["untranslated_blocks"]
    assert "PRIVATE_CHUNK_SPLIT_RETRY" in [i["code"] for i in result["issues"]]


@pytest.mark.asyncio
async def test_private_split_depth_is_bounded_and_failures_stay_critical():
    engine = ScriptedPrivateEngine(reject_above=0)  # every request is rejected
    result = await translate_blocks(ir_many(6), options(engine))
    assert len(engine.calls) <= 2 * 6  # binary split, bounded
    assert set(result["untranslated_blocks"]) == {f"b{i:03d}" for i in range(6)}
    for i in range(6):
        assert result["translations"][f"b{i:03d}"] == f"Synthetic employment line {i}."
    assert any(
        i.get("severity") == "critical" and i["code"] == "INVALID_MODEL_OUTPUT"
        for i in result["issues"]
    )
