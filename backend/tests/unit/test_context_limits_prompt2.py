"""Budget contract only, not private-Qwen tokenizer or live translation evidence."""

from __future__ import annotations

import pytest

from app.ai.context.builder import ContextPackBuilder
from app.ai.translation.service import PrivateQwenEngine, _config


class CountingOnlyTokenizer:
    def __init__(self, tokens):
        self.tokens = tokens

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        return range(self.tokens)


def private_resolver(host, port, **kwargs):
    return [(2, 1, 6, "", ("192.0.2.10", port))]


@pytest.mark.parametrize("tokens", [10000, 20000, 22000, 25000, 30000, 31000, 32000, 32768, 32769])
def test_complete_preflight_boundary_does_not_call_model(tokens):
    engine = PrivateQwenEngine(
        base_url="http://private.internal/api",
        allowed_hosts=["private.internal"],
        model="contract-test-only",
        tokenizer_path=None,
        tokenizer=CountingOnlyTokenizer(tokens),
        resolver=private_resolver,
    )
    total, prompt = engine._preflight([{"role": "system", "content": "Contract only"}])
    assert prompt == tokens
    assert total >= tokens
    assert (total + 8000 + 2768 > 32768) == (tokens > 22000 or total + 10768 > 32768)


@pytest.mark.asyncio
@pytest.mark.parametrize("tokens", [25000, 30000, 31000, 32000, 32768, 32769])
async def test_oversize_input_rejected_before_transport(tokens):
    engine = PrivateQwenEngine(
        base_url="http://private.internal/api",
        allowed_hosts=["private.internal"],
        model="contract-test-only",
        tokenizer_path=None,
        tokenizer=CountingOnlyTokenizer(tokens),
        resolver=private_resolver,
    )
    result = await engine.translate_chunk(
        [{"role": "user", "content": "Oversize contract"}], ["a"], max_output=8000
    )
    assert result.translations == {}
    assert any(issue["code"] == "CONTEXT_OVERFLOW" for issue in result.issues)


def test_ceiling_configuration_cannot_be_raised():
    with pytest.raises(ValueError, match="32768"):
        _config({"max_context": 32769})


def test_docx_table_paragraph_ids_are_atomic_interface_requirement():
    # Existing builder needs block_ids for cell grouping. Prompt-2 supplies both
    # paragraph_ids (OOXML ownership) and block_ids (translation interface).
    ir = {
        "pages": [
            {"number": 1, "blocks": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}]}
        ],
        "tables": [{"page": 1, "cells": [{"id": "cell", "block_ids": ["a", "b"]}]}],
    }
    units = ContextPackBuilder().units(ir)
    assert len(units) == 1 and units[0].kind == "table"
    assert set(units[0].block_ids) == {"a", "b"}
