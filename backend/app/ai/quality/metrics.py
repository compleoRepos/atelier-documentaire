from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .entities import protected_entity_issues as _protected_entity_issues

_NUM = re.compile(r"(?<![\w])[+-]?(?:\d+[\d\s.,:/-]*|[٠-٩]+[\d٠-٩\s.,:/-]*)(?![\w])")
_TOKEN = re.compile(r"\w+", re.UNICODE)


def numeric_entities(text: str) -> list[str]:
    return [re.sub(r"\s+", "", value) for value in _NUM.findall(text or "")]


def protected_entity_issues(source: str, target: str) -> list[dict[str, Any]]:
    return _protected_entity_issues(source, target)


def token_delta(source: str, target: str) -> dict[str, Any]:
    source_tokens, target_tokens = (
        Counter(_TOKEN.findall(source or "")),
        Counter(_TOKEN.findall(target or "")),
    )
    return {
        "missing": dict(source_tokens - target_tokens),
        "extra": dict(target_tokens - source_tokens),
        "source_tokens": sum(source_tokens.values()),
        "target_tokens": sum(target_tokens.values()),
    }


def reference_is_valid(reference: dict[str, Any] | None) -> bool:
    if not reference:
        return False
    legacy = (
        reference.get("validated") is True
        and reference.get("reviewer")
        and reference.get("version")
    )
    golden = (
        reference.get("approved") is True
        and reference.get("reviewer_id")
        and reference.get("validated_at")
        and reference.get("version")
        and reference.get("schema_version")
    )
    return bool(legacy or golden)


def _levenshtein(expected: list[str], actual: list[str]) -> int:
    row = list(range(len(actual) + 1))
    for index, expected_value in enumerate(expected, 1):
        previous = row[0]
        row[0] = index
        for actual_index, actual_value in enumerate(actual, 1):
            current = row[actual_index]
            row[actual_index] = min(
                row[actual_index] + 1,
                row[actual_index - 1] + 1,
                previous + (expected_value != actual_value),
            )
            previous = current
    return row[-1]


def _distances(expected: str, actual: str) -> tuple[float, float]:
    characters = _levenshtein(list(expected), list(actual or "")) / max(1, len(expected))
    words = _levenshtein(_TOKEN.findall(expected), _TOKEN.findall(actual or "")) / max(
        1, len(_TOKEN.findall(expected))
    )
    return characters, words


def reference_metrics(
    source: str, target: str, reference: dict[str, Any] | None
) -> dict[str, float | None]:
    metrics = {"cer": None, "wer": None, "translation_cer": None, "translation_wer": None}
    if not reference_is_valid(reference):
        return metrics
    # Translation approval does NOT attest to the correctness of the OCR transcript.
    # OCR truth additionally requires a human annotation and a source scope
    # digest; ``ocr_validated`` alone is legacy/untrusted metadata.
    ocr_expected = reference.get("ocr_text")
    human = (
        reference.get("ocr_human_annotated") is True
        or reference.get("ocr_annotated") is True
        or reference.get("ocr_validation") in {"human", "signed"}
        or bool(reference.get("ocr_reviewer_id") or reference.get("ocr_annotated_by"))
        or (
            isinstance(reference.get("ocr_annotation"), Mapping)
            and bool(
                reference["ocr_annotation"].get("reviewer_id")
                or reference["ocr_annotation"].get("annotated_by")
                or reference["ocr_annotation"].get("human") is True
            )
        )
    )
    scope = reference.get("ocr_scope_sha256") or reference.get("ocr_source_sha256")
    canonical = json.dumps(source, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    scope_candidates = {
        hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        hashlib.sha256(source.encode("utf-8")).hexdigest(),
    }
    if (
        human
        and isinstance(ocr_expected, str)
        and isinstance(scope, str)
        and scope.casefold() in scope_candidates
    ):
        metrics["cer"], metrics["wer"] = _distances(ocr_expected, source)
    translation_expected = (
        reference.get("target_text") or reference.get("target") or reference.get("text")
    )
    if isinstance(translation_expected, str):
        metrics["translation_cer"], metrics["translation_wer"] = _distances(
            translation_expected, target
        )
    # These are lexical distances, never a semantic/translation-quality certification.
    return metrics
