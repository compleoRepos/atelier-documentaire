"""RUN29 F46/F47 — private engine (Qwen / gpt-oss via vLLM or llama.cpp) budget guard.

Found while wiring a real local gpt-oss-20b server: with transformers 5 the chat
template returns a ``BatchEncoding`` and the 32K preflight counted its 2 keys
instead of the tokens (fail-open), and jinja2 — required to render any chat
template — was not a declared dependency. These tests use a REAL transformers
tokenizer built in memory (no download, no network) so that the actual return
type of ``apply_chat_template`` is exercised; the HTTP transport refuses any
call, proving the guard decides before the network.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx
import pytest

from app.ai.translation.service import PrivateQwenEngine, _token_count

BACKEND = Path(__file__).resolve().parents[2]
CHAT_TEMPLATE = (
    "{% for m in messages %}<|{{ m['role'] }}|> {{ m['content'] }} <|end|> {% endfor %}"
    "{% if add_generation_prompt %}<|assistant|>{% endif %}"
)


def real_tokenizer():
    """A genuine PreTrainedTokenizerFast (word-level vocabulary, whitespace split)."""
    pytest.importorskip("jinja2")
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast

    vocab = {"[UNK]": 0, "<|system|>": 1, "<|user|>": 2, "<|end|>": 3, "<|assistant|>": 4}
    for index, word in enumerate(["word", "translate", "into", "french", "json"], start=5):
        vocab[word] = index
    core = Tokenizer(models.WordLevel(vocab=vocab, unk_token="[UNK]"))
    core.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=core, unk_token="[UNK]")
    tokenizer.chat_template = CHAT_TEMPLATE
    return tokenizer


def private_resolver(host, port, **kwargs):
    return [(2, 1, 6, "", ("192.0.2.10", port))]


class NetworkForbidden:
    def __init__(self) -> None:
        self.calls = 0

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.calls += 1
            raise AssertionError("the budget guard must decide before any network call")

        return httpx.MockTransport(handler)


def engine(tokenizer, network: NetworkForbidden, **kwargs) -> PrivateQwenEngine:
    return PrivateQwenEngine(
        base_url="http://private-gateway.internal/v1",
        allowed_hosts=["private-gateway.internal"],
        model="private-model",
        tokenizer_path=None,
        tokenizer=tokenizer,
        transport=network.transport(),
        resolver=private_resolver,
        **kwargs,
    )


def messages(words: int) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "translate into french json"},
        {"role": "user", "content": " ".join(["word"] * words)},
    ]


def test_real_chat_template_returns_a_mapping_and_the_preflight_counts_its_ids():
    tokenizer = real_tokenizer()
    rendered = tokenizer.apply_chat_template(
        messages(3000), tokenize=True, add_generation_prompt=True
    )
    ids = rendered["input_ids"] if hasattr(rendered, "keys") else rendered
    assert len(ids) > 3000
    network = NetworkForbidden()
    with_schema, prompt_tokens = engine(tokenizer, network)._preflight(messages(3000))
    # before F47 this was len(BatchEncoding) == 2
    assert prompt_tokens == len(ids)
    assert with_schema > prompt_tokens
    assert network.calls == 0


def test_an_over_budget_prompt_is_refused_before_the_network():
    network = NetworkForbidden()
    result = asyncio.run(
        engine(real_tokenizer(), network).translate_chunk(messages(40000), ["b1"], max_output=8000)
    )
    assert [issue["code"] for issue in result.issues] == ["CONTEXT_OVERFLOW"]
    assert result.issues[0]["prompt_tokens"] > 32768
    assert result.translations == {}
    assert network.calls == 0


def test_a_prompt_just_inside_the_budget_is_not_refused_by_a_miscount():
    tokenizer = real_tokenizer()
    network = NetworkForbidden()
    guarded = engine(tokenizer, network)
    with_schema, _ = guarded._preflight(messages(100))
    assert with_schema + 8000 + guarded.safety_margin <= guarded.max_context
    assert with_schema > 100


@pytest.mark.parametrize(
    "value",
    [{"attention_mask": [1, 1, 1]}, [[1, 2], [3, 4]], object(), 12.5],
    ids=["mapping-without-ids", "batch-of-two", "unknown-object", "float"],
)
def test_an_undeterminable_token_count_is_refused(value):
    with pytest.raises(ValueError):
        _token_count(value)


def test_supported_encodings_keep_their_exact_length():
    assert _token_count({"input_ids": [1, 2, 3, 4]}) == 4
    assert _token_count({"input_ids": [[1, 2, 3]]}) == 3
    assert _token_count([[7, 8]]) == 2
    assert _token_count(range(11)) == 11
    assert _token_count([0] * 5) == 5


def test_a_preflight_that_cannot_render_the_template_is_a_critical_issue_without_network():
    class TemplateUnavailable:
        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            raise ImportError("apply_chat_template requires jinja2")

        def encode(self, value, **kwargs):
            return [0]

    network = NetworkForbidden()
    result = asyncio.run(
        engine(TemplateUnavailable(), network).translate_chunk(messages(10), ["b1"], max_output=100)
    )
    assert [issue["code"] for issue in result.issues] == ["PRIVATE_PREFLIGHT_FAILED"]
    assert result.issues[0]["severity"] == "critical"
    assert network.calls == 0


def test_jinja2_is_a_declared_backend_dependency():
    requirements = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    pyproject = (BACKEND / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^jinja2==\d", requirements, re.MULTILINE)
    assert re.search(r'"jinja2==\d', pyproject)
