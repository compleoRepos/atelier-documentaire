"""Prompt 1 regressions; all tokenizer doubles are local and non-Qwen."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.ai.context.builder import ContextPackBuilder
from app.ai.translation.service import (
    PrivateQwenEngine,
    _config,
    _tokenizer_hash,
)


class DoubleTokenizer:
    name_or_path = "double-not-qwen"

    def encode(self, value: str, *, add_special_tokens: bool = False) -> list[int]:
        return list(range(len(value.split())))

    def apply_chat_template(self, messages, *, tokenize: bool, add_generation_prompt: bool):
        rendered = "".join(f"<{m['role']}>{m['content']}" for m in messages)
        return list(range(len(rendered.split())))


class SchemaCountingTokenizer(DoubleTokenizer):
    def encode(self, value: str, *, add_special_tokens: bool = False) -> list[int]:
        return [1, 2, 3] if value == "translations:id,text" else super().encode(value)

    def apply_chat_template(self, messages, *, tokenize: bool, add_generation_prompt: bool):
        return [0] * 11


def private_engine(tokenizer=None, *, max_context=32768):
    return PrivateQwenEngine(
        base_url="http://private.internal/api",
        allowed_hosts=["private.internal"],
        model="qwen-private-double",
        tokenizer_path=None,
        tokenizer=tokenizer or DoubleTokenizer(),
        resolver=lambda host, port, **kwargs: [(2, 1, 6, "", ("192.0.2.10", port))],
        max_context=max_context,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": '{"translations":[]}'},
                            "finish_reason": "stop",
                        }
                    ]
                },
            )
        ),
    )


@pytest.mark.parametrize("budget", [10_000, 20_000, 22_000, 25_000, 30_000, 31_000, 32_000])
def test_supported_context_budgets_use_local_double_only(budget: int) -> None:
    assert _config(
        {"max_context": budget, "target_input": budget - 2, "max_output": 1, "safety_margin": 1}
    )["max_context"] == budget
    assert private_engine(max_context=budget).max_context == budget


def test_context_above_hard_ceiling_is_rejected_even_via_direct_constructor() -> None:
    with pytest.raises(ValueError, match="32768"):
        private_engine(max_context=32_769)
    with pytest.raises(ValueError, match="32768"):
        _config({"max_context": 32_769})


def test_schema_preflight_uses_tokenizer_tokens_not_string_characters() -> None:
    engine = private_engine(SchemaCountingTokenizer())
    total, prompt = engine._preflight([{"role": "user", "content": "tiny"}])
    assert prompt == 11
    assert total == 14


def test_tokenizer_hash_changes_when_local_asset_changes(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "tokenizer.json").write_text('{"vocab":{"a":1}}', encoding="utf-8")
    (second / "tokenizer.json").write_text('{"vocab":{"a":1}}', encoding="utf-8")
    assert _tokenizer_hash(DoubleTokenizer(), str(first)) == _tokenizer_hash(DoubleTokenizer(), str(second))
    (second / "tokenizer.json").write_text('{"vocab":{"a":2}}', encoding="utf-8")
    assert _tokenizer_hash(DoubleTokenizer(), str(first)) != _tokenizer_hash(DoubleTokenizer(), str(second))


def test_relevant_memory_list_requires_validated_true_and_glossary_domain_is_filtered() -> None:
    builder = ContextPackBuilder()
    context = builder.relevant_context(
        {"domain": "legal"},
        {"blocks": [{"id": "b", "text": "Term"}]},
        {
            "memory": [
                {"source": "Term", "target": "bad", "validated": False},
                {"source": "Term", "target": "good", "validated": True},
            ],
            "glossary": [
                {"source": "Term", "target": "legal", "domain": "legal"},
                {"source": "Term", "target": "hr", "domain": "hr"},
            ],
        },
    )
    assert context["memory"] == [{"source": "Term", "target": "good", "validated": True}]
    assert context["terms"] == [{"source": "Term", "target": "legal", "domain": "legal"}]


def test_dynamic_previous_decisions_can_be_injected_and_fitted_to_budget() -> None:
    builder = ContextPackBuilder(tokenizer=DoubleTokenizer(), max_tokens=100)
    chunk = {"blocks": [{"id": "b", "text": "term"}]}
    context = builder.relevant_context(
        {}, chunk, {"previous_decisions": [{"decision": "term", "text": "use approved"}]}
    )
    assert context["previous"] == [{"decision": "term", "text": "use approved"}]


def test_unknown_finish_reason_is_refused_without_accepting_json() -> None:
    engine = private_engine()
    engine.transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"translations":[]}'},
                        "finish_reason": "mystery",
                    }
                ]
            },
        )
    )

    import asyncio

    result = asyncio.run(engine.translate_chunk([], [], max_output=1))
    assert result.translations == {}
    assert result.issues[0]["code"] == "UNKNOWN_FINISH_REASON"


@pytest.mark.parametrize("total", [10000,20000,22000,25000,30000,31000,32000,32768,32769,33000])
def test_complete_request_boundary_including_output_and_margin(total):
    """Measured synthetic token counts; NOT proof of the absent Qwen tokenizer."""
    import asyncio
    output_budget = 4000 if total < 10769 else 8000
    margin = 1000 if total < 10769 else 2768
    class BoundaryTokenizer(DoubleTokenizer):
        def apply_chat_template(self,messages,**kwargs):
            return [0]*(total-output_budget-margin-1)
        def encode(self,value,**kwargs):
            return [0]
    requests = []
    engine = private_engine(BoundaryTokenizer())
    engine.safety_margin = margin
    def response(request):
        requests.append(request)
        return httpx.Response(200,json={"choices":[{"message":{"content":'{"translations":[]}'},"finish_reason":"stop"}]})
    engine.transport = httpx.MockTransport(response)
    result = asyncio.run(engine.translate_chunk([],[],max_output=output_budget))
    assert bool(requests) == (total <= 32768)
    if total>32768:
        assert result.issues[0]["code"] == "CONTEXT_OVERFLOW"
    else:
        assert result.metadata["reserved_total_tokens"] == total


def test_five_business_terminologies_have_client_priority_without_memory_promotion():
    from app.ai.context.terminology import DOMAINS, context_terms
    assert set(DOMAINS) == {"HR","BANKING","LEGAL","FINANCE","ADMINISTRATION"}
    terms = context_terms("RH",[{"source":"Employment Certificate","target":"Attestation client","domain":"HR"}])
    assert next(x for x in terms if x["source"]=="Employment Certificate")["target"] == "Attestation client"
    assert all(x.get("validated") is not True for x in terms)
    assert context_terms("unknown") == []


@pytest.mark.parametrize("address", ["169.254.169.254","fe80::1","0.0.0.0","224.0.0.1","8.8.8.8"])
def test_metadata_multicast_and_public_ssrf_destinations_blocked(address):
    from app.ai.translation.service import _validate_private_url
    with pytest.raises(ValueError):
        _validate_private_url("http://private.internal/v1",["private.internal"],resolver=lambda *args,**kwargs:[(2,1,6,"",(address,80))])
