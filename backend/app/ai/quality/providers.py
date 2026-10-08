"""Concrete local/private providers for the quality engine.

The providers in this module are deliberately typed subclasses of
:class:`app.ai.quality.engine.QualityProvider`; callers cannot accidentally
register an unscoped callback.  The embedding provider is a semantic
*agreement* measurement, not a probability of correctness.  The Qwen provider
is a private, allow-listed judge and returns an auditable rubric only when its
JSON output is complete and bounded.

No constructor loads from the network.  Hugging Face loading is explicitly
``local_files_only=True`` and ``trust_remote_code=False``.  The private HTTP
client disables proxy environment variables and redirects, and revalidates
DNS immediately before every request.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from app.ai.quality.engine import QualityProvider
from app.ai.translation.service import _token_count, _validate_private_url

MAX_CONTEXT = 32768
DEFAULT_SAFETY_MARGIN = 512
DEFAULT_MAX_OUTPUT = 1024
RUBRIC_DIMENSIONS = ("fidelity", "coherence", "terminology", "context", "style")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])(?:\s+|$)")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _validate_budget(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= MAX_CONTEXT:
        return None
    return value


def _finite_unit(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        return None
    return result


def _hash_assets(path: Path) -> str:
    """Hash local asset names and metadata, never asset contents or user text."""
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            stat = item.stat()
            digest.update(str(item.relative_to(path)).encode("utf-8"))
            digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii"))
    return digest.hexdigest()


def _load_local_hf(path: Path) -> tuple[Any, Any]:
    """Load both tokenizer and model without a possible remote resolution."""
    try:
        transformers = importlib.import_module("transformers")
    except ImportError as exc:  # deferred optional dependency
        raise ImportError("transformers is required for a local embedding provider") from exc
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        str(path), local_files_only=True, trust_remote_code=False
    )
    model = transformers.AutoModel.from_pretrained(
        str(path), local_files_only=True, trust_remote_code=False
    )
    return tokenizer, model


def _torch_optional() -> Any:
    """Import torch only when a real transformer forward pass is needed."""
    try:
        return importlib.import_module("torch")
    except ImportError as exc:  # callers convert this to an unavailable result
        raise ImportError("torch is required for transformer embedding inference") from exc


def _as_array(value: Any) -> Any:
    """Convert tensor-like values to a NumPy array without importing torch."""
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - numpy is a project dependency
        raise ImportError("numpy is required for embedding comparison") from exc
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value, dtype="float64")


def _model_hidden(output: Any) -> Any:
    if isinstance(output, Mapping):
        for key in ("last_hidden_state", "pooler_output", "embeddings"):
            if key in output:
                return output[key]
    for key in ("last_hidden_state", "pooler_output", "embeddings"):
        value = getattr(output, key, None)
        if value is not None:
            return value
    if isinstance(output, (tuple, list)) and output:
        return output[0]
    return output


def _attention_mask(batch: Any, length: int) -> list[int]:
    if batch is None:
        return [1] * length
    if isinstance(batch, Mapping):
        value = batch.get("attention_mask")
    else:
        value = getattr(batch, "attention_mask", None)
    if value is None:
        return [1] * length
    array = _as_array(value).reshape(-1)
    return [int(item) for item in array[:length]]


class LocalEmbeddingProvider(QualityProvider):
    """Local Hugging Face encoder producing bounded cosine agreement scores.

    Sentence boundaries are retained while contiguous sentences are grouped
    into windows.  Every window is at most ``max_context`` tokens (a single
    sentence larger than that budget is unavailable rather than silently
    sliced).  Mean pooling, optional projection, and cosine similarity are
    applied per window and averaged by token count.  The score is a relative
    semantic agreement measurement; it is **not** a probability and makes no
    claim about factual faithfulness or protected-entity preservation.

    ``tokenizer`` and ``model`` are injectable for deterministic tests and
    local adapters.  If omitted, both are loaded from ``assets_dir`` with
    remote resolution disabled.
    """

    scope: Literal["local"] = "local"

    def __init__(
        self,
        assets_dir: str | Path,
        *,
        model_version: str,
        device: str = "cpu",
        tokenizer: Any = None,
        model: Any = None,
        projection: Any = None,
        window_tokens: int = 2048,
        name: str = "local-hf-embedding",
    ) -> None:
        path = Path(assets_dir).expanduser()
        if not path.is_dir():
            raise FileNotFoundError(f"local embedding assets_dir does not exist: {path}")
        if not isinstance(model_version, str) or not model_version.strip():
            raise ValueError("model_version is required for local embedding provenance")
        if not isinstance(device, str) or not device.strip():
            raise ValueError("device must be a declared non-empty string")
        if (
            isinstance(window_tokens, bool)
            or not isinstance(window_tokens, int)
            or window_tokens <= 0
        ):
            raise ValueError("window_tokens must be a positive integer")
        if window_tokens > MAX_CONTEXT:
            raise ValueError("window_tokens cannot exceed 32768")
        if tokenizer is None or model is None:
            loaded_tokenizer, loaded_model = _load_local_hf(path)
            tokenizer = tokenizer or loaded_tokenizer
            model = model or loaded_model
        if hasattr(model, "to"):
            model = model.to(device)
        if hasattr(model, "eval"):
            model.eval()
        asset_sha = _hash_assets(path)
        object.__setattr__(self, "assets_dir", str(path))
        object.__setattr__(self, "asset_sha", asset_sha)
        object.__setattr__(self, "asset_sha256", asset_sha)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "device", device)
        object.__setattr__(self, "tokenizer", tokenizer)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "projection", projection)
        object.__setattr__(self, "window_tokens", window_tokens)
        object.__setattr__(
            self,
            "asset_provenance",
            {
                "assets_dir": str(path),
                "asset_sha256": asset_sha,
                "model_version": model_version,
                "device": device,
                "scope": "local",
                "no_public_model_calls": True,
            },
        )
        # The engine recognizes the typed object, not a naked callback.
        QualityProvider.__init__(
            self,
            measure=self._measure,
            scope="local",
            name=name,
            no_public_model_calls=True,
        )

    def health_check(self) -> dict[str, Any] | None:
        """Return local asset status, or ``None`` when optional dependencies are absent."""
        try:
            _torch_optional()
        except ImportError:
            return None
        return {
            "status": "healthy",
            "scope": "local",
            "model_version": self.model_version,
            "device": self.device,
            "asset_sha256": self.asset_provenance["asset_sha256"],
        }

    @property
    def health(self) -> dict[str, Any] | None:
        return self.health_check()

    def _token_ids(self, sentence: str) -> tuple[list[int], list[int]] | None:
        try:
            encoded = self.tokenizer(
                sentence,
                add_special_tokens=True,
                truncation=False,
                return_attention_mask=True,
            )
        except TypeError:
            encoded = self.tokenizer(sentence)
        if isinstance(encoded, Mapping):
            ids = encoded.get("input_ids")
            mask = encoded.get("attention_mask")
        else:
            ids = getattr(encoded, "input_ids", encoded)
            mask = getattr(encoded, "attention_mask", None)
        values = _as_array(ids).reshape(-1).tolist() if ids is not None else []
        if not values:
            return None
        token_ids = [int(item) for item in values]
        if mask is None:
            attention = [1] * len(token_ids)
        else:
            attention = [int(item) for item in _as_array(mask).reshape(-1).tolist()]
            attention = (attention + [1] * len(token_ids))[: len(token_ids)]
        return token_ids, attention

    def _sentence_windows(
        self, text: str, max_context: int
    ) -> list[tuple[list[int], list[int]]] | None:
        sentences = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
        if not sentences:
            sentences = [text.strip()]
        encoded = [self._token_ids(sentence) for sentence in sentences]
        if any(item is None for item in encoded):
            return None
        units = [item for item in encoded if item is not None]
        budget = min(self.window_tokens, max_context)
        windows: list[tuple[list[int], list[int]]] = []
        current_ids: list[int] = []
        current_mask: list[int] = []
        for token_ids, mask in units:
            if len(token_ids) > budget:
                return None
            if current_ids and len(current_ids) + len(token_ids) > budget:
                windows.append((current_ids, current_mask))
                current_ids, current_mask = [], []
            current_ids.extend(token_ids)
            current_mask.extend(mask)
        if current_ids:
            windows.append((current_ids, current_mask))
        return windows

    def _vector(self, token_ids: list[int], mask: list[int]) -> Any | None:
        # A test/local adapter may expose a pure-Python encode method.
        try:
            if hasattr(self.model, "encode"):
                output = self.model.encode(token_ids)
            else:
                torch = _torch_optional()
                inputs = {
                    "input_ids": torch.tensor([token_ids], device=self.device),
                    "attention_mask": torch.tensor([mask], device=self.device),
                }
                with torch.no_grad():
                    output = self.model(**inputs)
            values = _as_array(_model_hidden(output))
            if values.ndim <= 1:
                vector = values
            elif values.ndim == 2:
                vector = values.mean(axis=0)
            else:
                sequence = values[0]
                weights = _as_array(mask).reshape(-1)[: sequence.shape[0]]
                if sequence.ndim == 1:
                    vector = sequence
                else:
                    vector = (sequence * weights[:, None]).sum(axis=0) / max(1.0, weights.sum())
            if self.projection is not None:
                projection = _as_array(self.projection)
                vector = vector @ projection if projection.ndim == 2 else vector
            return vector
        except (ImportError, TypeError, ValueError, RuntimeError, IndexError):
            return None

    @staticmethod
    def _cosine(left: Any, right: Any) -> float | None:
        try:
            import numpy as np

            left = np.asarray(left, dtype="float64").reshape(-1)
            right = np.asarray(right, dtype="float64").reshape(-1)
            if left.size == 0 or right.size == 0 or left.size != right.size:
                return None
            denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
            if denominator == 0 or not math.isfinite(denominator):
                return None
            cosine = float(np.dot(left, right) / denominator)
            if not math.isfinite(cosine):
                return None
            return max(0.0, min(1.0, (cosine + 1.0) / 2.0))
        except (ImportError, TypeError, ValueError):
            return None

    def score_agreement(
        self, text: str, expected: str, max_context: int = MAX_CONTEXT
    ) -> dict[str, Any] | None:
        budget = _validate_budget(max_context)
        if budget is None or not isinstance(text, str) or not isinstance(expected, str):
            return None
        if not text.strip() or not expected.strip():
            return None
        left_windows = self._sentence_windows(text, budget)
        right_windows = self._sentence_windows(expected, budget)
        if not left_windows or not right_windows:
            return None
        left_vectors = [self._vector(*window) for window in left_windows]
        right_vectors = [self._vector(*window) for window in right_windows]
        if any(vector is None for vector in left_vectors + right_vectors):
            return None
        left = sum(len(window[0]) for window in left_windows)
        right = sum(len(window[0]) for window in right_windows)
        pairs = min(len(left_vectors), len(right_vectors))
        scores = [self._cosine(left_vectors[index], right_vectors[index]) for index in range(pairs)]
        if any(score is None for score in scores):
            return None
        score = sum(float(item) for item in scores if item is not None) / max(1, len(scores))
        return {
            "score": score,
            "metric": "semantic_agreement_cosine",
            "scope": "local",
            "windows": {"text": len(left_windows), "expected": len(right_windows)},
            "tokens": {"text": left, "expected": right, "max_context": budget},
            "provenance": dict(self.asset_provenance),
        }

    def _measure(self, text: str, expected: str, max_context: int = MAX_CONTEXT) -> float | None:
        result = self.score_agreement(text, expected, max_context=max_context)
        return None if result is None else result["score"]

    def __call__(self, text: str, expected: str, max_context: int = MAX_CONTEXT) -> float | None:
        return self._measure(text, expected, max_context=max_context)

    def evaluate(
        self, text: str, expected: str, max_context: int = MAX_CONTEXT
    ) -> dict[str, Any] | None:
        return self.score_agreement(text, expected, max_context=max_context)


class PrivateQwenJudgeProvider(QualityProvider):
    """Synchronous private Qwen judge with strict, evidence-bound JSON output.

    ``evaluate`` requires the original source, candidate translation, and a
    human/reference translation.  Without the original source, faithfulness
    cannot be claimed; ``measure`` therefore only exposes the judge's bounded
    reference-agreement average for the engine's two-text contract.
    """

    scope: Literal["private"] = "private"

    def __init__(
        self,
        *,
        base_url: str,
        allowed_hosts: Sequence[str],
        model: str,
        tokenizer_path: str | Path | None = None,
        tokenizer: Any = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        resolver: Any = None,
        max_context: int = MAX_CONTEXT,
        safety_margin: int = DEFAULT_SAFETY_MARGIN,
        max_output: int = DEFAULT_MAX_OUTPUT,
        name: str = "private-qwen-quality-judge",
    ) -> None:
        budget = _validate_budget(max_context)
        if budget is None:
            raise ValueError("max_context must be an integer between 1 and 32768")
        if (
            isinstance(safety_margin, bool)
            or not isinstance(safety_margin, int)
            or safety_margin < 0
        ):
            raise ValueError("safety_margin must be a non-negative integer")
        if (
            isinstance(max_output, bool)
            or not isinstance(max_output, int)
            or not 0 < max_output <= 8000
        ):
            raise ValueError("max_output must be a positive integer no greater than 8000")
        if not model:
            raise ValueError("model is required")
        self_url = _validate_private_url(base_url, allowed_hosts, resolver=resolver)
        if tokenizer is None:
            if not tokenizer_path:
                raise ValueError("tokenizer_path is required for private judging")
            tokenizer = self._load_tokenizer(Path(tokenizer_path))
        object.__setattr__(self, "base_url", self_url)
        object.__setattr__(self, "allowed_hosts", tuple(allowed_hosts))
        object.__setattr__(self, "model_name", model)
        object.__setattr__(self, "tokenizer", tokenizer)
        object.__setattr__(
            self, "api_key", api_key
        )  # explicit argument only; no environment lookup
        object.__setattr__(self, "timeout", timeout)
        object.__setattr__(self, "transport", transport)
        object.__setattr__(self, "resolver", resolver)
        object.__setattr__(self, "max_context", budget)
        object.__setattr__(self, "safety_margin", safety_margin)
        object.__setattr__(self, "max_output", max_output)
        object.__setattr__(self, "last_error", None)
        object.__setattr__(
            self,
            "asset_provenance",
            {
                "tokenizer_path": str(tokenizer_path)
                if tokenizer_path
                else type(tokenizer).__name__,
                "model_version": model,
                "scope": "private",
                "no_public_model_calls": True,
            },
        )
        QualityProvider.__init__(
            self,
            measure=self._measure,
            scope="private",
            name=name,
            no_public_model_calls=True,
        )

    @staticmethod
    def _load_tokenizer(path: Path) -> Any:
        try:
            transformers = importlib.import_module("transformers")
        except ImportError as exc:
            raise ImportError("transformers is required for private judging") from exc
        return transformers.AutoTokenizer.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False
        )

    def health_check(self) -> dict[str, Any] | None:
        try:
            rendered = self.tokenizer.apply_chat_template(
                [{"role": "user", "content": "health"}], tokenize=True, add_generation_prompt=True
            )
            count = _token_count(rendered)
        except (AttributeError, TypeError, ValueError, RuntimeError):
            return None
        return {
            "status": "healthy",
            "scope": "private",
            "model_version": self.model_name,
            "chat_template_tokens": count,
            "max_context": self.max_context,
        }

    @property
    def health(self) -> dict[str, Any] | None:
        return self.health_check()

    def _messages(
        self, original_source: str, candidate: str, reference: str
    ) -> list[dict[str, str]]:
        schema = {
            "scores": {key: "number 0..1" for key in RUBRIC_DIMENSIONS},
            "citations": "list of bounded source/candidate offsets with proof",
            "contradictions": "list of bounded source/candidate offsets with reason",
            "coverage": "object or null; report null when not exhaustively covered",
        }
        system = (
            "You are a private translation quality judge. Return only JSON matching the schema. "
            "Score the candidate against the human reference; use the original source for evidence. "
            "Do not invent proof, citations, or coverage."
        )
        payload = {
            "original_source": original_source,
            "candidate_translation": candidate,
            "human_reference_translation": reference,
            "expected_output": schema,
        }
        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            },
        ]

    def _count_messages(self, messages: Sequence[Mapping[str, str]]) -> int:
        rendered = self.tokenizer.apply_chat_template(
            list(messages), tokenize=True, add_generation_prompt=True
        )
        return _token_count(rendered)

    def _revalidate(self) -> None:
        parsed = urlparse(self.base_url)
        _validate_private_url(self.base_url, [parsed.hostname or ""], resolver=self.resolver)

    @staticmethod
    def _offset(value: Any, limit: int, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= limit:
            raise ValueError(f"{field} offset is outside the supplied text")
        return value

    @classmethod
    def _span(cls, item: Mapping[str, Any], prefix: str, limit: int) -> tuple[int, int]:
        start = item.get(f"{prefix}_start")
        end = item.get(f"{prefix}_end")
        pair = item.get(prefix)
        if (start is None or end is None) and isinstance(pair, (list, tuple)) and len(pair) == 2:
            start, end = pair
        start = cls._offset(start, limit, f"{prefix}_start")
        end = cls._offset(end, limit, f"{prefix}_end")
        if start >= end:
            raise ValueError(f"{prefix} span must be non-empty")
        return start, end

    @classmethod
    def _strict_result(
        cls, value: Any, *, original_source: str, candidate: str, reference: str
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError("judge result must be an object")
        allowed = {"scores", "citations", "contradictions", "coverage"}
        if set(value) - allowed:
            raise ValueError("judge result contains unknown fields")
        raw_scores = value.get("scores")
        if not isinstance(raw_scores, Mapping) or set(raw_scores) != set(RUBRIC_DIMENSIONS):
            raise ValueError("scores must contain exactly the five rubric dimensions")
        scores: dict[str, float] = {}
        for key in RUBRIC_DIMENSIONS:
            score = _finite_unit(raw_scores.get(key))
            if score is None:
                raise ValueError(f"invalid score for {key}")
            scores[key] = score

        def records(key: str, proof_key: str) -> list[dict[str, Any]]:
            raw = value.get(key, [])
            if not isinstance(raw, list):
                raise ValueError(f"{key} must be a list")
            result: list[dict[str, Any]] = []
            for item in raw:
                if not isinstance(item, Mapping):
                    raise ValueError(f"{key} entries must be objects")
                source_span = cls._span(item, "source", len(original_source))
                candidate_span = cls._span(item, "candidate", len(candidate))
                proof = item.get(proof_key, item.get("proof"))
                if not isinstance(proof, str) or not proof.strip():
                    raise ValueError(f"{key} entries require a textual proof")
                result.append(
                    {
                        "source": {"start": source_span[0], "end": source_span[1]},
                        "candidate": {"start": candidate_span[0], "end": candidate_span[1]},
                        proof_key: proof,
                    }
                )
            return result

        citations = records("citations", "proof")
        contradictions = records("contradictions", "reason")
        coverage_value = value.get("coverage")
        coverage: dict[str, Any] | None
        if coverage_value is None:
            coverage = None
        elif not isinstance(coverage_value, Mapping):
            raise ValueError("coverage must be an object or null")
        else:
            coverage = dict(coverage_value)
            for key, limit in (
                ("source", len(original_source)),
                ("candidate", len(candidate)),
                ("source_spans", len(original_source)),
                ("candidate_spans", len(candidate)),
            ):
                if key not in coverage:
                    continue
                raw_spans = coverage[key]
                if not isinstance(raw_spans, list):
                    raise ValueError(f"coverage.{key} must be a list")
                normalized: list[dict[str, int]] = []
                for item in raw_spans:
                    if isinstance(item, Mapping) and "start" in item and "end" in item:
                        start = cls._offset(item["start"], limit, f"coverage.{key}.start")
                        end = cls._offset(item["end"], limit, f"coverage.{key}.end")
                    elif isinstance(item, (list, tuple)) and len(item) == 2:
                        start = cls._offset(item[0], limit, f"coverage.{key}.start")
                        end = cls._offset(item[1], limit, f"coverage.{key}.end")
                    else:
                        raise ValueError(f"coverage.{key} entries must be bounded spans")
                    if start >= end:
                        raise ValueError(f"coverage.{key} span must be non-empty")
                    normalized.append({"start": start, "end": end})
                coverage[key] = normalized
        return {
            "scores": scores,
            "citations": citations,
            "contradictions": contradictions,
            "coverage": coverage,
            "coverage_complete": coverage is not None,
            "source_length": len(original_source),
            "candidate_length": len(candidate),
            "reference_length": len(reference),
            "provenance": {
                "scope": "private",
                "no_public_model_calls": True,
            },
        }

    def _decode_response(
        self, body: Any, *, original_source: str, candidate: str, reference: str
    ) -> Any:
        content = body
        if isinstance(body, Mapping) and "choices" in body:
            content = body["choices"][0]["message"]["content"]
        if isinstance(content, str):
            content = json.loads(content, object_pairs_hook=_reject_duplicate_keys)
        return self._strict_result(
            content, original_source=original_source, candidate=candidate, reference=reference
        )

    def evaluate(
        self,
        original_source: str,
        candidate: str,
        expected_reference: str,
        max_context: int = MAX_CONTEXT,
    ) -> dict[str, Any] | None:
        budget = _validate_budget(max_context)
        if budget is None or not all(
            isinstance(item, str) for item in (original_source, candidate, expected_reference)
        ):
            self.last_error = "invalid quality judge arguments"
            return None
        messages = self._messages(original_source, candidate, expected_reference)
        try:
            self._revalidate()
            prompt_tokens = self._count_messages(messages)
            schema_tokens = _token_count("scores citations contradictions coverage")
            if prompt_tokens + schema_tokens + self.max_output + self.safety_margin > min(
                budget, MAX_CONTEXT
            ):
                self.last_error = "quality judge context budget exceeded"
                return None
            headers = {"content-type": "application/json"}
            if self.api_key:
                headers["authorization"] = f"Bearer {self.api_key}"
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0,
                "max_tokens": self.max_output,
                "response_format": {"type": "json_object"},
            }
            endpoint = self.base_url.rstrip("/") + "/chat/completions"
            with httpx.Client(
                trust_env=False,
                follow_redirects=False,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.post(endpoint, headers=headers, json=payload)
            if 300 <= response.status_code < 400:
                raise ValueError("private judge redirects are forbidden")
            response.raise_for_status()
            body = response.json()
            result = self._decode_response(
                body,
                original_source=original_source,
                candidate=candidate,
                reference=expected_reference,
            )
            result["provenance"] = {
                **self.asset_provenance,
                "model": self.model_name,
                "endpoint_host": urlparse(self.base_url).hostname,
                "prompt_tokens": prompt_tokens,
                "max_context": budget,
            }
            self.last_error = None
            return result
        except (
            httpx.HTTPError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ) as exc:
            self.last_error = str(exc)
            return None

    def _measure(self, text: str, expected: str, max_context: int = MAX_CONTEXT) -> float | None:
        # The engine's synchronous two-text contract has no original source.
        # A reference-agreement score is safe; faithfulness remains unavailable.
        result = self.evaluate(expected, text, expected, max_context=max_context)
        if not result:
            return None
        values = list(result["scores"].values())
        return sum(values) / len(values)

    def __call__(self, text: str, expected: str, max_context: int = MAX_CONTEXT) -> float | None:
        return self._measure(text, expected, max_context=max_context)


__all__ = [
    "LocalEmbeddingProvider",
    "PrivateQwenJudgeProvider",
    "MAX_CONTEXT",
    "RUBRIC_DIMENSIONS",
]
