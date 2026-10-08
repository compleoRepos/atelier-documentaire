"""Temporary Interim translation provider.

This module is intentionally separate from the offline and private/Qwen engines.
The service types are resolved lazily so a future service-side registration cannot
create an import cycle.  This adapter is fail-closed: it never guesses a public
endpoint, never follows redirects, and never sends non-authorized document data.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

import httpx

from .service import TranslationEngine

MAX_CONTEXT_CEILING = 32_768
DEFAULT_MAX_CONTEXT = 32_768
DEFAULT_TARGET_INPUT = 22_000
DEFAULT_MAX_TOKENS = 8_000
DEFAULT_SAFETY_MARGIN = 2_768
MODEL = "gpt-5-mini"
CATALOG_OWNER = "openai"
ENGINE_PROVIDER = "interim"
CONTRACT_URL = "https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create"
_BLOCKED_PROVIDERS: set[tuple[str,str]] = set()


# The schema is deliberately closed.  Do not loosen additionalProperties: the
# caller relies on exact IDs and exact cardinality after JSON parsing.
TRANSLATION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "translation_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["id", "text"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["translations"],
            "additionalProperties": False,
        },
    },
}


def _service_result(**kwargs: Any) -> Any:
    """Construct EngineResult without importing service at module import time."""
    from .service import EngineResult

    return EngineResult(**kwargs)


def _issue(code: str, message: str, **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "severity": "critical", "message": message}
    value.update(extra)
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _encoded_length(tokenizer: Any, value: str) -> int:
    """Count using an injected GPT tokenizer, without downloading anything."""
    encoder = getattr(tokenizer, "encode", None)
    if callable(encoder):
        try:
            result = encoder(value, add_special_tokens=False)
        except TypeError:
            result = encoder(value)
        try:
            return max(0, len(result))
        except TypeError:
            return max(0, int(result))
    return len(value)


def _load_gpt_tokenizer(model: str) -> Any:
    """Load the real GPT encoding locally; tiktoken never downloads model data here."""
    try:
        import tiktoken
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise RuntimeError("tiktoken is required for Interim GPT preflight") from exc
    try:
        return tiktoken.encoding_for_model(model)
    except (KeyError, ValueError):
        # Missing exact model encoding is a deployment failure, never a Qwen/GPT fallback.
        raise RuntimeError("Exact GPT encoding unavailable; no tokenizer fallback") from None


def _strict_json_translations(content: Any, expected_ids: Sequence[str]) -> dict[str, str]:
    if not isinstance(content, str):
        raise ValueError("model content must be JSON text")

    def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    parsed = json.loads(content, object_pairs_hook=no_duplicate_keys)
    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"translations"}
        or not isinstance(parsed["translations"], list)
    ):
        raise ValueError("output must be exactly {translations:[{id,text}]}")

    expected = [str(value) for value in expected_ids]
    actual: list[str] = []
    result: dict[str, str] = {}
    for item in parsed["translations"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "text"}
            or not isinstance(item["id"], str)
            or not isinstance(item["text"], str)
        ):
            raise ValueError("each translation must contain only string id and text")
        block_id = item["id"]
        if block_id in result:
            raise ValueError("duplicate translation id")
        actual.append(block_id)
        result[block_id] = item["text"]
    if actual != expected or set(actual) != set(expected):
        raise ValueError("translation IDs/cardinality do not exactly match request")
    return result


def _valid_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


class _TokenizerAdapter:
    """Optional ContextPackBuilder-compatible view over the engine tokenizer."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def encode(self, value: str, add_special_tokens: bool = False) -> list[int]:
        tokenizer = self._engine.tokenizer
        encoder = getattr(tokenizer, "encode", None)
        if callable(encoder):
            try:
                result = encoder(value, add_special_tokens=add_special_tokens)
            except TypeError:
                result = encoder(value)
            return list(result) if not isinstance(result, int) else [0] * result
        return list(range(len(value)))

    def apply_chat_template(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> Any:
        template = getattr(self._engine.tokenizer, "apply_chat_template", None)
        if callable(template):
            return template(
                list(messages), tokenize=tokenize, add_generation_prompt=add_generation_prompt
            )
        if tokenize:
            # Upper-bound accounting, not fabricated GPT chat-template token IDs.
            # Actual tiktoken counts are separately retained in preflight telemetry.
            return [0] * self._engine.count_messages(messages)
        rendered = self._engine._render_messages(messages, add_generation_prompt)
        return self.encode(rendered) if tokenize else rendered


class _InterimEngineImplementation:
    """Implementation mixed into a lazily-created TranslationEngine subclass."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        proxy_base_url: str | None = None,
        model: str = MODEL,
        tokenizer: Any = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
        max_context: int = DEFAULT_MAX_CONTEXT,
        target_input: int = DEFAULT_TARGET_INPUT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_output: int | None = None,
        safety_margin: int = DEFAULT_SAFETY_MARGIN,
        data_scope: str = "unknown",
        synthetic_fixture_authorized: bool = False,
        trusted_synthetic_fixture: bool | None = None,
        fixture_sha256: str | None = None,
        allowed_fixture_sha256: str | Sequence[str] | None = None,
        denied_document_sha256: str | Sequence[str] | None = None,
        total_generation_cap_verified: bool = True,
        capability_proof: Any = None,
        server_capability_proof: Any = None,
    ) -> None:
        configured_base = proxy_base_url if proxy_base_url is not None else base_url
        if configured_base is None:
            configured_base = os.environ.get("INTERIM_PROXY_BASE_URL") or os.environ.get("INTERIM_API_BASE")
        if not configured_base:
            raise ValueError("INTERIM proxy base URL must be explicitly configured")
        self.base_url = self._validate_base_url(str(configured_base))

        configured_key = api_key
        if configured_key is None:
            configured_key = os.environ.get("INTERIM_API_KEY")
        self.api_key = configured_key
        if not model or model != MODEL:
            raise ValueError("Interim temporary provider requires model gpt-5-mini")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout = timeout
        self.transport = transport
        self.requests_sent = 0

        if not self._positive_int(max_context) or max_context > MAX_CONTEXT_CEILING:
            raise ValueError("max_context must be a positive integer no greater than 32768")
        if not self._positive_int(target_input) or target_input > max_context:
            raise ValueError("target_input must be a positive integer within max_context")
        if not self._positive_int(max_tokens) or max_tokens > DEFAULT_MAX_TOKENS:
            raise ValueError("max_tokens must be a positive integer no greater than 8000")
        if max_output is not None:
            if not self._positive_int(max_output) or max_output > max_tokens:
                raise ValueError("max_output must be positive and no greater than max_tokens")
            max_tokens = max_output
        if not self._positive_int(safety_margin):
            raise ValueError("safety_margin must be a positive integer")
        if target_input + max_tokens + safety_margin > max_context:
            raise ValueError("target_input + max_tokens + safety_margin exceeds max_context")

        if not isinstance(data_scope, str):
            raise ValueError("data_scope must be explicit")
        if not isinstance(synthetic_fixture_authorized, bool):
            raise ValueError("synthetic_fixture_authorized must be a boolean")
        if trusted_synthetic_fixture is not None and not isinstance(
            trusted_synthetic_fixture, bool
        ):
            raise ValueError("trusted_synthetic_fixture must be a boolean")
        self.max_context = max_context
        self.target_input = target_input
        self.max_tokens = max_tokens
        self.safety_margin = safety_margin
        self.data_scope = data_scope
        self.synthetic_fixture_authorized = (
            synthetic_fixture_authorized
            if trusted_synthetic_fixture is None
            else trusted_synthetic_fixture
        )
        self.fixture_sha256 = fixture_sha256
        self.allowed_fixture_sha256 = self._hash_set(allowed_fixture_sha256)
        self.denied_document_sha256 = self._hash_set(denied_document_sha256)
        self.total_generation_cap_verified = bool(total_generation_cap_verified)
        self.capability_proof = capability_proof if capability_proof is not None else server_capability_proof
        self.model = model
        self.tokenizer_name = getattr(tokenizer,"name","injected-test-tokenizer") if tokenizer is not None else "o200k_base"
        self.token_counter_type = "GPT/injected counter + UTF8/framing conservative upper bound"
        self.tokenizer = tokenizer if tokenizer is not None else _load_gpt_tokenizer(model)
        self.tokenizer_adapter = _TokenizerAdapter(self)
        self.prompt_version = "interim-translation-v1"

    @staticmethod
    def _positive_int(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _hash_set(value: str | Sequence[str] | None) -> set[str]:
        if value is None:
            return set()
        if isinstance(value, str):
            return {value}
        if isinstance(value, set):
            return {str(item) for item in value}
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            return {str(item) for item in value}
        raise ValueError("SHA-256 hash configuration must be a string or sequence")

    @staticmethod
    def _validate_base_url(value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("INTERIM proxy base URL must be an explicit HTTPS URL")
        # Preserve the configured path exactly; only the API route is appended at call time.
        return value.rstrip("/")

    def _render_messages(
        self, messages: Sequence[Mapping[str, Any]], add_generation_prompt: bool = True
    ) -> str:
        rendered = "".join(
            f"<{item.get('role', '')}>{item.get('content', '')}" for item in messages
        )
        return rendered + ("<assistant>" if add_generation_prompt else "")

    def _preflight(self, messages: Sequence[Mapping[str, Any]], output_tokens: int) -> dict[str, int]:
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
            raise ValueError("messages must be a sequence")
        message_list = [dict(item) for item in messages]
        control = {
            "model": MODEL,
            "reasoning": {"effort": "minimal"},
            "max_completion_tokens": output_tokens,
        }
        payload_for_bound = {
            "model": MODEL,
            "messages": message_list,
            "response_format": TRANSLATION_RESPONSE_SCHEMA,
            **control,
        }
        serialized = _json_bytes(payload_for_bound)
        encoded_parts = (
            _encoded_length(self.tokenizer, _json_bytes(message_list).decode("utf-8"))
            + _encoded_length(self.tokenizer, _json_bytes(TRANSLATION_RESPONSE_SCHEMA).decode("utf-8"))
            + _encoded_length(self.tokenizer, _json_bytes(control).decode("utf-8"))
        )
        # Fixed JSON/chat framing is conservatively added, while the UTF-8 byte
        # bound protects against Unicode/tokenizer mismatches (notably Arabic).
        framing_overhead = 4096 + (len(message_list) * 16)
        encoded_upper = encoded_parts + framing_overhead
        byte_upper = len(serialized) + framing_overhead
        prompt_upper = max(encoded_upper, byte_upper)
        return {
            "prompt_upper_bound": prompt_upper,
            "encoded_upper_bound": encoded_upper,
            "utf8_payload_bytes": byte_upper,
            "output_tokens": output_tokens,
            "reserved_total": prompt_upper + output_tokens + self.safety_margin,
        }

    def count_messages(self, messages: Sequence[Mapping[str, Any]]) -> int:
        """Return a conservative complete-payload upper bound for ContextPackBuilder."""
        return self._preflight(messages, self.max_tokens)["prompt_upper_bound"]

    def _gate_issue(self) -> dict[str, Any] | None:
        if self.data_scope != "synthetic_fixture" or not self.synthetic_fixture_authorized:
            return _issue(
                "INTERIM_SYNTHETIC_FIXTURE_NOT_AUTHORIZED",
                "The temporary Interim provider currently accepts only an explicitly authorized synthetic_fixture.",
            )
        if self.fixture_sha256 and self.fixture_sha256 in self.denied_document_sha256:
            return _issue(
                "INTERIM_DATA_HASH_DENIED",
                "The supplied fixture hash is denylisted and no request was sent.",
            )
        if not self.fixture_sha256:
            return _issue("INTERIM_FIXTURE_HASH_REQUIRED","Server allowlisted fixture hash required; no request sent.")
        if not self.allowed_fixture_sha256 or self.fixture_sha256 not in self.allowed_fixture_sha256:
            return _issue(
                "INTERIM_FIXTURE_HASH_NOT_ALLOWLISTED",
                "The supplied fixture hash is not on the server fixture allowlist and no request was sent.",
            )
        if self.denied_document_sha256 and self.fixture_sha256 is None:
            return _issue(
                "INTERIM_FIXTURE_HASH_REQUIRED",
                "A fixture hash is required when a document denylist is configured.",
            )
        return None

    def _cap_issue(self) -> dict[str, Any] | None:
        if (self.base_url,self.model) in _BLOCKED_PROVIDERS or not self.total_generation_cap_verified:
            return _issue("INTERIM_TOTAL_GENERATION_CAP_NOT_VERIFIED","Provider circuit blocked after a budget contract violation; no request sent.")
        return None

    def _metadata(self, body: Mapping[str, Any], preflight: Mapping[str, int]) -> dict[str, Any]:
        # Do not copy arbitrary provider/diagnostic fields: credentials and Qwen
        # identifiers must never enter telemetry.  provider is intentionally Interim.
        return {
            "engine": "interim",
            "provider": ENGINE_PROVIDER,
            "catalog_owner": CATALOG_OWNER,
            "tokenizer_name": self.tokenizer_name,
            "token_counter_type": self.token_counter_type,
            "model": MODEL,
            "served_model": body.get("model"),
            "served_version": body.get("served_version") or body.get("model"),
            "usage": body.get("usage"),
            "reasoning_effort": "minimal",
            "completion_limit_parameter": "max_completion_tokens",
            "total_generation_contract": CONTRACT_URL,
            "contract_includes_hidden_reasoning": True,
            "reasoning_tokens": None,
            "prompt_upper_bound": preflight["prompt_upper_bound"],
            "encoded_upper_bound": preflight["encoded_upper_bound"],
            "utf8_payload_bytes": preflight["utf8_payload_bytes"],
            "reserved_output_tokens": preflight["output_tokens"],
            "safety_margin": self.safety_margin,
            "max_context": self.max_context,
            "reserved_total_tokens": preflight["reserved_total"],
        }

    @staticmethod
    def _validate_usage(
        usage: Any, *, prompt_upper_bound: int, max_tokens: int, reserved_total: int
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not isinstance(usage, Mapping):
            return None, "usage is missing or not an object"
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if not _valid_nonnegative_int(usage.get(key)):
                return None, f"usage.{key} must be a non-negative integer"
        prompt = int(usage["prompt_tokens"])
        completion = int(usage["completion_tokens"])
        total = int(usage["total_tokens"])
        if total != prompt + completion:
            return None, "usage.total_tokens is inconsistent with prompt and completion tokens"
        if prompt > prompt_upper_bound:
            return None, "usage.prompt_tokens exceeds the conservative preflight bound"
        if completion > max_tokens:
            return None, "usage.completion_tokens exceeds max_tokens"
        if total > MAX_CONTEXT_CEILING:
            return None, "usage.total_tokens exceeds 32768"
        if total > reserved_total:
            return None, "usage.total_tokens exceeds the reserved context"
        details = usage.get("completion_tokens_details", usage.get("completion_details"))
        reasoning_tokens: int | None = None
        if not isinstance(details, Mapping) or "reasoning_tokens" not in details:
            return None, "reasoning token telemetry unavailable"
        if details is not None:
            if not isinstance(details, Mapping):
                return None, "usage.completion_details must be an object"
            if "reasoning_tokens" in details:
                if not _valid_nonnegative_int(details["reasoning_tokens"]):
                    return None, "usage.completion_details.reasoning_tokens is malformed"
                reasoning_tokens = int(details["reasoning_tokens"])
                if reasoning_tokens > completion:
                    return None, "reasoning_tokens exceeds completion_tokens"
        normalized = dict(usage)
        return normalized, None

    async def translate_chunk(
        self,
        messages: list[dict[str, str]],
        expected_ids: Sequence[str],
        *,
        max_output: int,
    ) -> Any:
        gate = self._gate_issue()
        if gate is not None:
            return _service_result(issues=[gate])
        cap = self._cap_issue()
        if cap is not None:
            return _service_result(issues=[cap])
        if not self._positive_int(max_output) or max_output > self.max_tokens:
            return _service_result(
                issues=[
                    _issue(
                        "INTERIM_OUTPUT_BUDGET_INVALID",
                        "max_output must be a positive integer no greater than the configured max_tokens.",
                    )
                ]
            )
        try:
            preflight = self._preflight(messages, max_output)
        except (TypeError, ValueError, OverflowError) as exc:
            return _service_result(issues=[_issue("INTERIM_PREFLIGHT_INVALID", str(exc))])
        if (
            preflight["prompt_upper_bound"] > self.target_input
            or preflight["reserved_total"] > self.max_context
            or preflight["reserved_total"] > MAX_CONTEXT_CEILING
        ):
            return _service_result(
                issues=[
                    _issue(
                        "INTERIM_CONTEXT_OVERFLOW",
                        "Complete Interim prompt bound or reserved total exceeds the configured context budget.",
                        prompt_upper_bound=preflight["prompt_upper_bound"],
                        target_input=self.target_input,
                        reserved_total=preflight["reserved_total"],
                        max_context=self.max_context,
                    )
                ]
            )

        payload: dict[str, Any] = {
            "model": MODEL,
            "messages": messages,
            "response_format": TRANSLATION_RESPONSE_SCHEMA,
            "max_completion_tokens": max_output,
            "reasoning": {"effort": "minimal"},
        }
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        endpoint = self.base_url + "/chat/completions"
        try:
            async with httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                self.requests_sent += 1
                response = await client.post(endpoint, headers=headers, json=payload)
                if 300 <= response.status_code < 400:
                    return _service_result(
                        issues=[
                            _issue(
                                "INTERIM_REDIRECT",
                                "Redirects from the configured Interim proxy are forbidden.",
                            )
                        ]
                    )
                response.raise_for_status()
        except httpx.TimeoutException:
            return _service_result(issues=[_issue("INTERIM_TIMEOUT", "Interim proxy request timed out.")])
        except (httpx.HTTPError, OSError, RuntimeError):
            return _service_result(issues=[_issue("INTERIM_GATEWAY_FAILED", "Interim proxy request failed.")])

        try:
            body = response.json()
            if not isinstance(body, Mapping):
                raise ValueError("response body must be an object")
        except (ValueError, json.JSONDecodeError, TypeError):
            return _service_result(issues=[_issue("INTERIM_INVALID_MODEL_OUTPUT", "Response body is not valid JSON.")])
        metadata = self._metadata(body, preflight)
        checked_usage, checked_error = self._validate_usage(body.get("usage"),prompt_upper_bound=preflight["prompt_upper_bound"],max_tokens=max_output,reserved_total=preflight["reserved_total"])
        if checked_error:
            violation = any(word in checked_error for word in ("exceeds","inconsistent"))
            if violation:
                _BLOCKED_PROVIDERS.add((self.base_url,self.model))
            return _service_result(issues=[_issue("INTERIM_BUDGET_CONTRACT_VIOLATION" if violation else "INTERIM_USAGE_INVALID",checked_error)],metadata=metadata)
        metadata["prompt_counter_delta"] = preflight["encoded_upper_bound"] - checked_usage["prompt_tokens"]
        metadata["prompt_upper_bound_delta"] = preflight["prompt_upper_bound"] - checked_usage["prompt_tokens"]
        checked_details=checked_usage.get("completion_tokens_details",checked_usage.get("completion_details",{}))
        metadata["reasoning_tokens"]=checked_details.get("reasoning_tokens")

        if body.get("model") != MODEL:
            return _service_result(
                issues=[_issue("INTERIM_MODEL_MISMATCH", "Served model does not match gpt-5-mini.")],
                metadata=metadata,
            )
        try:
            choice = body["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason") if isinstance(choice, Mapping) else None
        except (KeyError, IndexError, TypeError):
            return _service_result(
                issues=[_issue("INTERIM_INVALID_MODEL_OUTPUT", "Response choices/message/finish_reason is malformed.")],
                metadata=metadata,
            )
        if not isinstance(message, Mapping):
            return _service_result(
                issues=[_issue("INTERIM_INVALID_MODEL_OUTPUT", "Response message is malformed.")],
                metadata=metadata,
            )
        if not isinstance(finish_reason, str) or not finish_reason:
            return _service_result(
                issues=[_issue("INTERIM_FINISH_REASON_MISSING", "The response has no valid finish_reason.")],
                metadata=metadata,
            )
        refusal = message.get("refusal")
        if refusal:
            return _service_result(
                issues=[_issue("INTERIM_REFUSAL", "The model refused the translation.")],
                finish_reason=finish_reason,
                metadata=metadata,
            )
        if finish_reason == "length":
            return _service_result(
                issues=[_issue("INTERIM_OUTPUT_LENGTH", "The response reached max_tokens.")],
                finish_reason=finish_reason,
                metadata=metadata,
            )
        if finish_reason != "stop":
            return _service_result(
                issues=[_issue("INTERIM_UNKNOWN_FINISH_REASON", "The response has an unsupported finish_reason.")],
                finish_reason=finish_reason,
                metadata=metadata,
            )

        usage, usage_error = self._validate_usage(
            body.get("usage"),
            prompt_upper_bound=preflight["prompt_upper_bound"],
            max_tokens=max_output,
            reserved_total=preflight["reserved_total"],
        )
        if usage_error:
            return _service_result(
                issues=[_issue("INTERIM_USAGE_INVALID", usage_error)],
                finish_reason=finish_reason,
                metadata=metadata,
            )
        metadata["usage"] = usage
        details = usage.get("completion_tokens_details", usage.get("completion_details")) if usage else None
        if isinstance(details, Mapping) and "reasoning_tokens" in details:
            metadata["reasoning_tokens"] = details["reasoning_tokens"]
        try:
            translations = _strict_json_translations(message.get("content"), expected_ids)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return _service_result(
                issues=[_issue("INTERIM_INVALID_MODEL_OUTPUT", str(exc))],
                finish_reason=finish_reason,
                metadata=metadata,
            )
        return _service_result(
            translations=translations,
            finish_reason=finish_reason,
            metadata=metadata,
        )


class InterimTranslationEngine(_InterimEngineImplementation, TranslationEngine):
    pass


__all__ = ["InterimTranslationEngine", "TRANSLATION_RESPONSE_SCHEMA"]
