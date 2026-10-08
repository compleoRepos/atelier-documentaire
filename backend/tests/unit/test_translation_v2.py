from __future__ import annotations

import json

import httpx
import pytest

from app.ai.translation.service import (
    PrivateQwenEngine,
    _config,
    _strict_translation_json,
    translate_blocks,
)


class SyntheticChatTokenizer:
    name_or_path = "synthetic-local"

    def apply_chat_template(self, messages, *, tokenize: bool, add_generation_prompt: bool):
        rendered = "".join(f"<{item['role']}>{item['content']}" for item in messages)
        return rendered + ("<assistant>" if add_generation_prompt else "")


def resolver_private(host, port, **kwargs):
    return [(2, 1, 6, "", ("192.0.2.10", port))]


def resolver_public(host, port, **kwargs):
    return [(2, 1, 6, "", ("8.8.8.8", port))]


def test_duplicate_json_keys_are_rejected_before_id_validation():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        _strict_translation_json(
            '{"translations":[{"id":"a","text":"x"}],"translations":[]}', ["a"]
        )


def test_output_projection_is_hard_capped():
    with pytest.raises(ValueError, match="8000"):
        _config({"max_output": 8001})


@pytest.mark.asyncio
async def test_private_transport_returns_usage_and_served_version_without_public_fallback():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["max_tokens"] == 8000
        return httpx.Response(
            200,
            json={
                "model": "qwen-private-served-1",
                "usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11},
                "choices": [
                    {
                        "message": {"content": '{"translations":[{"id":"a","text":"Bonjour"}]}'},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    engine = PrivateQwenEngine(
        base_url="http://private.internal/api",
        allowed_hosts=["private.internal"],
        model="qwen-private",
        tokenizer_path=None,
        tokenizer=SyntheticChatTokenizer(),
        transport=httpx.MockTransport(handler),
        resolver=resolver_private,
    )
    result = await translate_blocks(
        {"language": "en", "pages": [{"number": 1, "blocks": [{"id": "a", "text": "Hello"}]}]},
        {"engine": "private", "translation_engine": engine},
    )

    assert result["translations"] == {"a": "Bonjour"}
    assert result["translation_telemetry"]["served_version"] == "qwen-private-served-1"
    assert result["translation_telemetry"]["usage"]["total_tokens"] == 11


def test_dns_revalidation_rejects_public_rebinding():
    engine = PrivateQwenEngine(
        base_url="http://private.internal/api",
        allowed_hosts=["private.internal"],
        model="qwen-private",
        tokenizer_path=None,
        tokenizer=SyntheticChatTokenizer(),
        resolver=resolver_private,
    )
    engine.resolver = resolver_public
    # The constructor accepted the private address, but a subsequent lookup is public.
    with pytest.raises(ValueError, match="public"):
        engine._revalidate_endpoint()
