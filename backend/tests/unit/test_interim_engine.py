from __future__ import annotations

import json

import httpx
import pytest

from app.ai.translation.interim import InterimTranslationEngine


@pytest.fixture(autouse=True)
def reset_circuit():
    from app.ai.translation.interim import _BLOCKED_PROVIDERS
    _BLOCKED_PROVIDERS.clear()
    yield
    _BLOCKED_PROVIDERS.clear()


class GPTDouble:
    def encode(self, value: str, add_special_tokens: bool = False) -> list[int]:
        # A deterministic stand-in for injected tiktoken; UTF-8 is intentionally
        # not token-counted so the engine's byte upper bound remains observable.
        return list(range(max(1, len(value) // 4)))


def messages(text: str = "Translate this") -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "You translate exactly."},
        {"role": "user", "content": json.dumps({"blocks": [{"id": "a", "text": text}]})},
    ]


def body(*, finish_reason: str = "stop", content: str | None = None, model: str = "gpt-5-mini", usage=None, refusal=None):
    message = {"role": "assistant", "content": content or json.dumps({"translations": [{"id": "a", "text": "Traduit"}]})}
    if refusal is not None:
        message["refusal"] = refusal
    return {
        "model": model,
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 24, "completion_tokens_details": {"reasoning_tokens": 0}},
    }


def engine(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    defaults = {
        "base_url": "https://interim.example/v1",
        "api_key": "secret",
        "tokenizer": GPTDouble(),
        "transport": transport,
        "data_scope": "synthetic_fixture",
        "synthetic_fixture_authorized": True,
        "total_generation_cap_verified": True,
        "fixture_sha256": "approved-fixture",
        "allowed_fixture_sha256": {"approved-fixture"},
        "capability_proof": {"host": "fixture", "total_generation": True},
    }
    defaults.update(kwargs)
    return InterimTranslationEngine(**defaults)


@pytest.mark.asyncio
async def test_default_unknown_scope_blocks_before_http():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=body())

    e = engine(handler, data_scope="unknown", synthetic_fixture_authorized=False)
    result = await e.translate_chunk(messages(), ["a"], max_output=8)
    assert calls == 0
    assert result.issues[0]["code"] == "INTERIM_SYNTHETIC_FIXTURE_NOT_AUTHORIZED"


@pytest.mark.asyncio
async def test_denylisted_or_non_allowlisted_fixture_blocks_before_http():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=body())

    denied = engine(handler, fixture_sha256="dead", denied_document_sha256={"dead"})
    result = await denied.translate_chunk(messages(), ["a"], max_output=8)
    assert calls == 0
    assert result.issues[0]["code"] == "INTERIM_DATA_HASH_DENIED"

    not_allowed = engine(handler, fixture_sha256="other", allowed_fixture_sha256={"good"})
    result = await not_allowed.translate_chunk(messages(), ["a"], max_output=8)
    assert calls == 0
    assert result.issues[0]["code"] == "INTERIM_FIXTURE_HASH_NOT_ALLOWLISTED"


@pytest.mark.asyncio
async def test_unverified_total_generation_cap_blocks_before_http():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=body())

    e = engine(handler, total_generation_cap_verified=False)
    result = await e.translate_chunk(messages(), ["a"], max_output=8)
    assert calls == 0
    assert result.issues[0]["code"] == "INTERIM_TOTAL_GENERATION_CAP_NOT_VERIFIED"


@pytest.mark.asyncio
async def test_payload_is_interim_gpt_json_schema_reasoning_and_max_tokens_only():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=body())

    e = engine(handler)
    result = await e.translate_chunk(messages(), ["a"], max_output=8)
    assert not result.issues
    payload = seen[0]
    assert payload["model"] == "gpt-5-mini"
    assert payload["max_completion_tokens"] == 8
    assert "max_tokens" not in payload
    assert payload["reasoning"] == {"effort": "minimal"}
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert result.metadata["provider"] == "interim"
    assert "qwen" not in json.dumps(result.metadata).lower()


@pytest.mark.asyncio
async def test_unicode_byte_upper_bound_is_recorded_and_overflow_is_pre_http():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=body())

    e = engine(handler, target_input=22_000, max_context=32_768)
    result = await e.translate_chunk(messages("العربية" * 3000), ["a"], max_output=8)
    assert calls == 0
    assert result.issues[0]["code"] == "INTERIM_CONTEXT_OVERFLOW"


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [10000, 20000, 22000, 25000, 30000, 31000, 32000, 32768, 32769])
async def test_context_thresholds_are_checked_before_http(target):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=body())

    # Keep construction valid even for a tiny target; the full JSON schema and
    # UTF-8 payload are still counted before any request is considered.
    configured_target = min(target, 32_766)
    e = engine(handler, target_input=configured_target, max_context=32_768, max_tokens=1, safety_margin=1)
    result = await e.translate_chunk(messages("x" * 40_000), ["a"], max_output=1)
    assert calls == 0
    assert result.issues[0]["code"] == "INTERIM_CONTEXT_OVERFLOW"


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", [None, "length", "tool_calls"])
async def test_missing_length_and_unknown_finish_are_fail_closed(finish):
    def handler(request):
        value = body(finish_reason=finish or "stop")
        if finish is None:
            value["choices"][0].pop("finish_reason")
        return httpx.Response(200, json=value)

    result = await engine(handler).translate_chunk(messages(), ["a"], max_output=8)
    expected = "INTERIM_FINISH_REASON_MISSING" if finish is None else ("INTERIM_OUTPUT_LENGTH" if finish == "length" else "INTERIM_UNKNOWN_FINISH_REASON")
    assert result.issues[0]["code"] == expected


@pytest.mark.asyncio
async def test_refusal_invalid_ids_and_model_mismatch():
    result = await engine(lambda r: httpx.Response(200, json=body(refusal="no"))).translate_chunk(messages(), ["a"], max_output=8)
    assert result.issues[0]["code"] == "INTERIM_REFUSAL"
    invalid = body(content=json.dumps({"translations": [{"id": "extra", "text": "x"}]}))
    result = await engine(lambda r: httpx.Response(200, json=invalid)).translate_chunk(messages(), ["a"], max_output=8)
    assert result.issues[0]["code"] == "INTERIM_INVALID_MODEL_OUTPUT"
    result = await engine(lambda r: httpx.Response(200, json=body(model="gpt-5"))).translate_chunk(messages(), ["a"], max_output=8)
    assert result.issues[0]["code"] == "INTERIM_MODEL_MISMATCH"


@pytest.mark.asyncio
async def test_usage_reasoning_is_recorded_once_and_malformed_usage_rejected():
    usage = {"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 24, "completion_details": {"reasoning_tokens": 2}}
    result = await engine(lambda r: httpx.Response(200, json=body(usage=usage))).translate_chunk(messages(), ["a"], max_output=8)
    assert result.metadata["reasoning_tokens"] == 2
    assert result.metadata["usage"]["total_tokens"] == 24
    assert result.metadata["usage"]["total_tokens"] != 24 + 2
    malformed = body(usage={"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 99})
    result = await engine(lambda r: httpx.Response(200, json=malformed)).translate_chunk(messages(), ["a"], max_output=8)
    assert result.issues[0]["code"] == "INTERIM_BUDGET_CONTRACT_VIOLATION"


@pytest.mark.asyncio
async def test_timeout_has_no_secret_in_error():
    async def handler(request):
        raise httpx.ReadTimeout("synthetic timeout")

    e = engine(handler, api_key="do-not-log")
    result = await e.translate_chunk(messages(), ["a"], max_output=8)
    assert result.issues[0]["code"] == "INTERIM_TIMEOUT"
    assert "do-not-log" not in json.dumps(result.issues)


def test_count_messages_and_adapter_are_available_for_context_builder():
    e = engine(lambda r: httpx.Response(200, json=body()))
    assert e.count_messages(messages()) >= e._preflight(messages(), 8)["prompt_upper_bound"]
    assert hasattr(e.tokenizer_adapter, "encode")
    assert hasattr(e.tokenizer_adapter, "apply_chat_template")


@pytest.mark.asyncio
@pytest.mark.parametrize('prompt_bound',[10000,20000,22000,25000,30000,31000,32000,32768,33000])
async def test_complete_boundary_with_8000_total_output_and_2768_margin(prompt_bound):
    seen=[]
    e=engine(lambda r:(seen.append(r) or httpx.Response(200,json=body())))
    base=e._preflight(messages(''),8000)['prompt_upper_bound']
    request=messages('x'*(prompt_bound-base))
    preflight=e._preflight(request,8000)
    assert preflight['prompt_upper_bound']==prompt_bound
    assert preflight['reserved_total']==prompt_bound+8000+2768
    result=await e.translate_chunk(request,['a'],max_output=8000)
    assert bool(seen)==(prompt_bound<=22000)
    if prompt_bound>22000:
        assert result.issues[0]['code']=='INTERIM_CONTEXT_OVERFLOW'
    else:
        assert not result.issues
        assert result.metadata['max_context']==32768


@pytest.mark.asyncio
async def test_missing_reasoning_detail_is_not_assumed_zero():
    value=body(usage={'prompt_tokens':20,'completion_tokens':4,'total_tokens':24})
    result=await engine(lambda r:httpx.Response(200,json=value)).translate_chunk(messages(),['a'],max_output=8)
    assert result.issues[0]['code']=='INTERIM_USAGE_INVALID'
    assert result.translations=={}


@pytest.mark.asyncio
async def test_budget_violation_opens_circuit_for_current_and_next_engine():
    calls=[]
    bad=body(usage={'prompt_tokens':20,'completion_tokens':9000,'total_tokens':9020,'completion_tokens_details':{'reasoning_tokens':100}})
    e=engine(lambda r:(calls.append(r) or httpx.Response(200,json=bad)))
    result=await e.translate_chunk(messages(),['a'],max_output=8000)
    assert result.issues[0]['code']=='INTERIM_BUDGET_CONTRACT_VIOLATION'
    assert result.translations=={}
    assert len(calls)==1
    next_engine=engine(lambda r:(calls.append(r) or httpx.Response(200,json=body())))
    result=await next_engine.translate_chunk(messages(),['a'],max_output=8000)
    assert result.issues[0]['code']=='INTERIM_TOTAL_GENERATION_CAP_NOT_VERIFIED'
    assert len(calls)==1


@pytest.mark.asyncio
async def test_length_cannot_hide_reasoning_budget_violation():
    bad=body(finish_reason='length',usage={'prompt_tokens':20,'completion_tokens':9,'total_tokens':29,'completion_tokens_details':{'reasoning_tokens':9}})
    result=await engine(lambda r:httpx.Response(200,json=bad)).translate_chunk(messages(),['a'],max_output=8)
    assert result.issues[0]['code']=='INTERIM_BUDGET_CONTRACT_VIOLATION'
    assert result.translations=={}


@pytest.mark.asyncio
async def test_local_server_counter_delta_and_total_contract_are_recorded():
    result=await engine(lambda r:httpx.Response(200,json=body())).translate_chunk(messages(),['a'],max_output=8000)
    assert result.metadata['completion_limit_parameter']=='max_completion_tokens'
    assert result.metadata['contract_includes_hidden_reasoning'] is True
    assert result.metadata['prompt_counter_delta']==result.metadata['encoded_upper_bound']-20
    assert result.metadata['prompt_upper_bound_delta']==result.metadata['prompt_upper_bound']-20
