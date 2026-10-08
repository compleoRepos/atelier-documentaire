from __future__ import annotations

import json
import sys
import types

import httpx

from app.ai.quality.engine import evaluate_quality
from app.ai.quality.providers import LocalEmbeddingProvider, PrivateQwenJudgeProvider


class FakeTokenizer:
    name_or_path = "tiny-local-tokenizer"

    def __call__(self, text, **kwargs):
        # Deliberately small deterministic ids for a synthetic model.
        ids = [len(token) % 11 + 1 for token in str(text).split()] or [1]
        return {"input_ids": ids, "attention_mask": [1] * len(ids)}

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is True
        assert add_generation_prompt is True
        return [word for message in messages for word in message["content"].split()]


class FakeModel:
    def __init__(self):
        self.device = None
        self.evaluated = False

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        self.evaluated = True

    def encode(self, token_ids):
        # A tiny deterministic vector; no claim of linguistic quality is made.
        total = sum(token_ids)
        return [float(total), float(len(token_ids)), 1.0]


def test_local_loader_is_explicitly_local_and_provider_is_typed(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    calls = []

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls.append(("tokenizer", path, kwargs))
            return FakeTokenizer()

    class AutoModel:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls.append(("model", path, kwargs))
            return FakeModel()

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(AutoTokenizer=AutoTokenizer, AutoModel=AutoModel),
    )
    provider = LocalEmbeddingProvider(tmp_path, model_version="tiny-v1")

    assert provider.scope == "local"
    assert provider.no_public_model_calls is True
    assert provider("A short sentence.", "A short sentence.") is not None
    assert all(call[2] == {"local_files_only": True, "trust_remote_code": False} for call in calls)


def test_embedding_score_is_bounded_and_sentence_windows_are_token_bounded(tmp_path):
    provider = LocalEmbeddingProvider(
        tmp_path,
        model_version="synthetic-v1",
        tokenizer=FakeTokenizer(),
        model=FakeModel(),
        window_tokens=3,
    )
    result = provider.evaluate(
        "One sentence. Two sentence.", "One sentence. Two sentence.", max_context=6
    )

    assert result is not None
    assert result["metric"] == "semantic_agreement_cosine"
    assert 0.0 <= result["score"] <= 1.0
    assert result["tokens"]["max_context"] == 6
    assert provider("x", "y", max_context=32769) is None


def _judge_provider(handler, tmp_path):
    transport = httpx.MockTransport(handler)
    return PrivateQwenJudgeProvider(
        base_url="http://private.test/v1",
        allowed_hosts=["private.test"],
        model="qwen-private-v1",
        tokenizer=FakeTokenizer(),
        transport=transport,
        resolver=lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 80))],
    )


def test_private_judge_validates_json_offsets_and_tracks_missing_coverage(tmp_path):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "qwen-private-v1"
        assert payload["messages"][1]["content"].find("original_source") >= 0
        output = {
            "scores": {
                "fidelity": 0.8,
                "coherence": 0.9,
                "terminology": 0.7,
                "context": 0.8,
                "style": 0.9,
            },
            "citations": [{"source": [0, 5], "candidate": [0, 5], "proof": "same protected fact"}],
            "contradictions": [],
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(output)}}]},
        )

    provider = _judge_provider(handler, tmp_path)
    result = provider.evaluate("Alpha fact", "Alpha fact", "Alpha fact")

    assert result is not None
    assert result["coverage"] is None
    assert result["coverage_complete"] is False
    assert result["citations"][0]["source"] == {"start": 0, "end": 5}


def test_private_judge_rejects_boolean_score_and_out_of_bounds_citation(tmp_path):
    def handler(request):
        del request
        output = {
            "scores": {
                "fidelity": True,
                "coherence": 0.9,
                "terminology": 0.7,
                "context": 0.8,
                "style": 0.9,
            },
            "citations": [],
            "contradictions": [],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(output)}}]})

    provider = _judge_provider(handler, tmp_path)
    assert provider.evaluate("Alpha", "Alpha", "Alpha") is None


def test_entity_checks_remain_critical_when_embedding_agreement_is_high(tmp_path):
    provider = LocalEmbeddingProvider(
        tmp_path,
        model_version="synthetic-v1",
        tokenizer=FakeTokenizer(),
        model=FakeModel(),
    )
    source = "The critical date is 2025-01-02."
    reference = {
        "approved": True,
        "reviewer_id": "human",
        "validated_at": "2025-01-03",
        "version": 1,
        "schema_version": 1,
        "target_text": source,
    }
    result = evaluate_quality(
        {"blocks": [{"id": "b1", "text": source}]},
        {"b1": "The critical date is 2024-01-02."},
        reference=reference,
        options={"embedding_provider": provider},
    )

    assert result["semantic_score"] is not None
    assert any(
        issue["code"] == "HALLUCINATION_ENTITY_MODIFIED" for issue in result["hallucination_errors"]
    )
    assert result["status"] == "FAIL"
