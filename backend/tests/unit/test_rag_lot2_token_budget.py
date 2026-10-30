"""F-L2-02 : le surcoût RAG doit être mesuré en jetons réels avec transformers 5."""

from __future__ import annotations

import json

from transformers import BatchEncoding

from app.ai.context.builder import ContextPackBuilder
from app.application import rag_bridge


class BatchEncodingTokenizer:
    """Comme les tokenizers transformers 5 : ``apply_chat_template`` renvoie un BatchEncoding."""

    def apply_chat_template(self, messages, *, tokenize=True, add_generation_prompt=True):
        size = 8 + sum(len(str(m.get("content", ""))) // 4 for m in messages)
        return BatchEncoding({"input_ids": list(range(size)), "attention_mask": [1] * size})

    def encode(self, text, add_special_tokens=False):
        return list(range(max(1, len(text) // 4)))


class OpaqueTokenizer(BatchEncodingTokenizer):
    def apply_chat_template(self, messages, **kwargs):
        return object()


def _request(memory: list[dict]) -> dict:
    payload = {
        "target_language": "fr",
        "blocks": [{"id": "b001", "text": "gross salary"}],
        "document_context": {},
        "context": {"terms": [], "document_memory": memory},
    }
    return {
        "messages": [
            {"role": "system", "content": "Traduire."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "expected_ids": ["b001"],
    }


BASE = [_request([])]
WITH_RAG = [_request([{"source": "gross salary", "target": "salaire brut " * 60}])]


def test_frozen_counter_returns_key_count_with_batch_encoding():
    # Caractérisation du défaut du fichier gelé (non modifié au LOT 2).
    counter = ContextPackBuilder(tokenizer=BatchEncodingTokenizer(), max_tokens=10**9)
    assert counter.count_messages(BASE[0]["messages"]) == 2
    assert counter.count_messages(WITH_RAG[0]["messages"]) == 2


def test_rag_overhead_is_measured_in_real_tokens():
    counter = ContextPackBuilder(tokenizer=BatchEncodingTokenizer(), max_tokens=10**9)
    before = rag_bridge.message_tokens(counter, BASE[0]["messages"])
    after = rag_bridge.message_tokens(counter, WITH_RAG[0]["messages"])
    assert after - before > 150
    verdict = rag_bridge.compare_requests(BASE, WITH_RAG, counter, budget=800)
    assert verdict["ok"] and verdict["rag_tokens_max"] == after - before
    assert verdict["rag_items_sent"] == 1


def test_budget_guard_refuses_when_real_overhead_exceeds_budget():
    counter = ContextPackBuilder(tokenizer=BatchEncodingTokenizer(), max_tokens=10**9)
    verdict = rag_bridge.compare_requests(BASE, WITH_RAG, counter, budget=50)
    assert verdict["ok"] is False and verdict["reason"] == "BUDGET_EXCEEDED"
    assert verdict["rag_tokens_max"] > 50


def test_unknown_encoding_is_refused_fail_closed():
    counter = ContextPackBuilder(tokenizer=OpaqueTokenizer(), max_tokens=10**9)
    verdict = rag_bridge.compare_requests(BASE, WITH_RAG, counter, budget=800)
    assert verdict == {"ok": False, "reason": "PROBE_FAILED", "requests": 1}


def test_counter_without_chat_template_keeps_previous_behaviour():
    counter = ContextPackBuilder(tokenizer=None, max_tokens=10**9)
    messages = WITH_RAG[0]["messages"]
    assert rag_bridge.message_tokens(counter, messages) == counter.count_messages(messages)
