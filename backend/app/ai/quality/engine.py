"""Fail-closed, evidence-bound quality evaluation for document translation.

This module deliberately distinguishes measurements from claims.  A lexical
comparison is not semantic quality, an approved translation is not OCR truth,
and a clean list of locally detected issues is not a proof of zero
hallucinations.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.ai.quality.entities import compare_entities
from app.ai.quality.metrics import reference_is_valid, reference_metrics
from app.ai.vision.scorer import score_visual

_TOKEN = re.compile(r"\w+", re.UNICODE)
_UNIT_WORDS = (
    r"kg|kgs|kilogram(?:me|mes)?|g|gram(?:me|mes)?|mg|milligram(?:me|mes)?|"
    r"lb|lbs|livre(?:s)?|m|met(?:re|res|er|ers)?|cm|centim(?:e|è)tre(?:s)?|"
    r"mm|millim(?:e|è)tre(?:s)?|km|kilom(?:e|è)tre(?:s)?|l|litre(?:s)?|ml|millilitre(?:s)?|"
    r"m²|m2|%|pourcent(?:s)?|euros?|€|dollars?(?:\s+am(?:e|é)ricains?)?|\$|"
    r"dirhams?|dh|dhs|usd|eur|gbp|mad|aed"
)
_CURRENCY_PREFIX = r"€|\$|euros?|eur|usd|gbp|mad|aed|dh|dhs|dirhams?"
# A unit is only meaningful when attached to a quantity: right after a digit
# ("12.345.00euro", "5 kg", "12 %") or, for currencies, right before one
# ("€ 123.456.789", "EUR 100"). Bare letters such as the French elision
# "l'"/"m'" or the article "l" are therefore not counted as litres/metres.
_UNIT = re.compile(
    rf"(?i)(?:(?<=\d)|(?<=\d[ \u00a0\u202f]))(?:{_UNIT_WORDS})(?![\w'’])"
    rf"|(?<!\w)(?:{_CURRENCY_PREFIX})(?=[ \u00a0\u202f]?\d)"
)
_UNIT_ALIASES = {
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "kilogramme": "kg",
    "kilogrammes": "kg",
    "g": "g",
    "gramme": "g",
    "grammes": "g",
    "mg": "mg",
    "milligramme": "mg",
    "milligrammes": "mg",
    "lb": "lb",
    "lbs": "lb",
    "livre": "lb",
    "livres": "lb",
    "m": "m",
    "metre": "m",
    "metres": "m",
    "meter": "m",
    "meters": "m",
    "cm": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "centimètre": "cm",
    "centimètres": "cm",
    "mm": "mm",
    "millimetre": "mm",
    "millimetres": "mm",
    "millimètre": "mm",
    "millimètres": "mm",
    "km": "km",
    "kilometre": "km",
    "kilometres": "km",
    "kilomètre": "km",
    "kilomètres": "km",
    "l": "l",
    "litre": "l",
    "litres": "l",
    "ml": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "m²": "m2",
    "m2": "m2",
    "%": "%",
    "pourcent": "%",
    "pourcents": "%",
    "€": "eur",
    "euro": "eur",
    "euros": "eur",
    "$": "usd",
    "dollar": "usd",
    "dollars": "usd",
    "dollar américain": "usd",
    "dollars américains": "usd",
    "dirham": "mad",
    "dirhams": "mad",
    "dh": "mad",
    "dhs": "mad",
    "usd": "usd",
    "eur": "eur",
    "gbp": "gbp",
    "mad": "mad",
    "aed": "aed",
}
_REQUIRED_RUBRIC = ("fidelity", "coherence", "terminology", "context", "style")


@dataclass(frozen=True)
class QualityProvider:
    """Explicitly typed local/private measurement provider.

    Plain user supplied callables are intentionally not accepted.  The
    declaration is not itself proof of privacy; it is an auditable capability
    boundary and the result provenance remains ``unknown`` when a plugin runs.
    """

    measure: Callable[..., Any]
    scope: Literal["local", "private"]
    name: str = "typed-quality-provider"
    no_public_model_calls: bool = True


SemanticProvider = QualityProvider


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


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _finite_score(value: Any) -> float | None:
    # bool is an int subclass, but a boolean is never a measured score.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and 0.0 <= value <= 1.0 else None


def _similarity(expected: str, actual: str, *, words: bool = False) -> float:
    left = _TOKEN.findall(expected) if words else list(expected)
    right = _TOKEN.findall(actual) if words else list(actual)
    return max(0.0, 1.0 - _levenshtein(left, right) / max(1, len(left)))


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha_candidates(value: str) -> set[str]:
    # Source hashes in existing callers have historically been either the
    # canonical JSON string hash or a direct UTF-8 text hash.  Candidate
    # translation bindings remain strictly canonical mapping hashes.
    return {_canonical_sha256(value), hashlib.sha256(value.encode("utf-8")).hexdigest()}


def _blocks(ir: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct = ir.get("blocks")
    if isinstance(direct, list):
        return [
            block for block in direct if isinstance(block, dict) and block.get("id") is not None
        ]
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in ir.get("pages", []) or []:
        if not isinstance(page, Mapping):
            continue
        for block in page.get("blocks", []) or []:
            if (
                isinstance(block, dict)
                and block.get("id") is not None
                and str(block["id"]) not in seen
            ):
                seen.add(str(block["id"]))
                output.append(block)
    return output


def _source_text(ir: Mapping[str, Any], blocks: list[dict[str, Any]]) -> str:
    for key in ("source_text", "ocr_text"):
        value = ir.get(key)
        if isinstance(value, str):
            return value
    return "\n".join(_text(block.get("text")) for block in blocks)


def _target_text(translations: Mapping[str, Any], blocks: list[dict[str, Any]]) -> str:
    if not blocks:
        return "\n".join(_text(value) for value in translations.values())
    return "\n".join(
        _text(translations.get(str(block["id"])))
        for block in blocks
        if str(block["id"]) in translations
    )


def _reference_target(reference: Mapping[str, Any] | None) -> str | None:
    if not reference:
        return None
    for key in ("target_text", "target", "text"):
        value = reference.get(key)
        if isinstance(value, str):
            return value
    return None


def _source_sha256(
    ir: Mapping[str, Any],
    reference: Mapping[str, Any] | None,
    source: str,
    options: Mapping[str, Any],
) -> str:
    supplied = options.get("source_sha256") or ir.get("source_sha256")
    if isinstance(supplied, str) and supplied:
        return supplied.casefold()
    return _canonical_sha256(source)


def _ocr_scope_is_trusted(reference: Mapping[str, Any], source: str, source_sha256: str) -> bool:
    if not reference_is_valid(reference):
        return False
    text = reference.get("ocr_text")
    if not isinstance(text, str):
        return False
    # ocr_validated on the IR is deliberately ignored.  A reference must have
    # a human annotation/reviewer and a scope digest tied to this source.
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
    if not human or not isinstance(scope, str):
        return False
    return scope.casefold() in _sha_candidates(source) | {source_sha256.casefold()}


def _ocr_evidence(
    ir: Mapping[str, Any], reference: Mapping[str, Any] | None, source: str, source_sha256: str
) -> tuple[float | None, dict[str, Any], str | None]:
    # Only human-annotated, scope-bound reference OCR is evidence.  In
    # particular, ir["ocr_validated"] must never elevate an unreviewed OCR.
    if reference and _ocr_scope_is_trusted(reference, source, source_sha256):
        text = reference["ocr_text"]
        cer = 1.0 - _similarity(text, source)
        wer = 1.0 - _similarity(text, source, words=True)
        return (
            max(0.0, min(1.0, 1.0 - cer)),
            {
                "cer": cer,
                "wer": wer,
                "reference_length": len(text),
                "observed_length": len(source),
                "scope_sha256": reference.get(
                    "ocr_scope_sha256", reference.get("ocr_source_sha256")
                ),
            },
            "human_annotated_scope_bound_ocr",
        )
    return None, {"cer": None, "wer": None}, None


def _rubric_container(reference: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for candidate in (
        reference.get("rubric"),
        reference.get("quality_rubric"),
        reference.get("human_review"),
    ):
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _rubric_binding(
    rubric: Mapping[str, Any],
    reference: Mapping[str, Any],
    translations: Mapping[str, Any],
    source_sha256: str,
    expected_review_version: Any,
    source_text: str | None = None,
) -> tuple[bool, str]:
    # Metadata may be stored beside scores or in the reference envelope.
    def field(name: str) -> Any:
        return rubric.get(name, reference.get(name))

    translation_sha = field("translation_sha256")
    if not isinstance(translation_sha, str) or translation_sha.casefold() != _canonical_sha256(
        dict(translations)
    ):
        return False, "translation_sha256 does not bind rubric to candidate mapping"
    bound_source = field("source_sha256")
    if not isinstance(bound_source, str) or bound_source.casefold() != source_sha256.casefold():
        return False, "source_sha256 does not bind rubric to source"
    review_version = field("review_version")
    if review_version is None or (
        expected_review_version is not None and review_version != expected_review_version
    ):
        return False, "review_version does not bind rubric to this candidate version"
    return True, "bound_candidate_source_and_review_version"


def _signed_rubric(
    reference: Mapping[str, Any] | None,
    translations: Mapping[str, Any] | None = None,
    source_sha256: str | None = None,
    expected_review_version: Any = None,
    source_text: str | None = None,
) -> tuple[dict[str, float] | None, str | None]:
    """Return a complete, signed, candidate-bound human rubric only."""
    if not reference or not translations or source_sha256 is None:
        return None, None
    candidate = _rubric_container(reference)
    if candidate is None or not (
        candidate.get("signed") is True or reference.get("rubric_signed") is True
    ):
        return None, None
    raw = candidate.get("scores", candidate.get("rubric", candidate.get("dimensions")))
    if not isinstance(raw, Mapping):
        return None, None
    # Partial rubrics cannot be averaged into a quality claim.  ``coverage``
    # is accepted only when it explicitly names all required dimensions.
    keys = {str(key) for key in raw}
    coverage = candidate.get("coverage", reference.get("rubric_coverage"))
    if not set(_REQUIRED_RUBRIC).issubset(keys):
        covered = (
            set(coverage)
            if isinstance(coverage, (list, tuple, set))
            else set(coverage or {})
            if isinstance(coverage, Mapping)
            else set()
        )
        if not set(_REQUIRED_RUBRIC).issubset(covered):
            return None, None
    result: dict[str, float] = {}
    for key in _REQUIRED_RUBRIC:
        value = raw.get(key)
        if value is None and isinstance(coverage, Mapping):
            covered_value = coverage.get(key)
            value = (
                covered_value.get("score") if isinstance(covered_value, Mapping) else covered_value
            )
        score = _finite_score(value)
        if score is None:
            return None, None
        result[key] = score
    bound, _ = _rubric_binding(
        candidate, reference, translations, source_sha256, expected_review_version, source_text
    )
    if not bound:
        return None, None
    return result, "signed_human_rubric_bound_candidate"


def _typed_provider(value: Any) -> QualityProvider | None:
    return (
        value
        if isinstance(value, QualityProvider) and value.scope in {"local", "private"}
        else None
    )


def _provider_score(
    provider: Any, left: str, right: str, max_context: int
) -> tuple[float | None, bool]:
    typed = _typed_provider(provider)
    if typed is None or typed.no_public_model_calls is not True or not 0 < max_context <= 32768:
        return None, False
    try:
        result = typed.measure(left, right, max_context=max_context)
    except (TypeError, ValueError, RuntimeError):
        return None, True
    return _finite_score(result), True


def _reference_semantic_score(
    candidate: str, expected: str, options: Mapping[str, Any]
) -> tuple[float | None, str | None]:
    # Exact agreement with an already validated human reference is the sole
    # automatic semantic claim.  A non-identical paraphrase is unknown.
    if _normalise(candidate) == _normalise(expected):
        return 1.0, "exact_normalized_validated_reference_match"
    max_context = options.get("max_context", 32768)
    if isinstance(max_context, bool) or not isinstance(max_context, int):
        max_context = 32768
    score, used = _provider_score(
        options.get("embedding_provider"), candidate, expected, max_context
    )
    if score is not None:
        return score, "typed_local_or_private_semantic_provider"
    judge_score, judge_used = _provider_score(
        options.get("private_judge"), candidate, expected, max_context
    )
    if judge_score is not None:
        return judge_score, "typed_private_semantic_judge"
    if used or judge_used:
        return None, "typed_provider_unavailable_or_invalid"
    return None, "semantic_measurement_unavailable"


def _annotations(ir: Mapping[str, Any], reference: Mapping[str, Any] | None) -> list[Any]:
    values: list[Any] = []
    for candidate in (
        ir.get("entities"),
        ir.get("protected_entities"),
        (reference or {}).get("entities"),
    ):
        if isinstance(candidate, list):
            values.extend(candidate)
    return values


def _unit_key(value: str) -> str:
    normalized = _normalise(value)
    return _UNIT_ALIASES.get(normalized, normalized)


def _unit_occurrences(text: str) -> list[str]:
    return [_unit_key(match.group(0)) for match in _UNIT.finditer(text)]


def _entity_and_hallucination_checks(
    source: str, target: str, ir: Mapping[str, Any], reference: Mapping[str, Any] | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    comparison = compare_entities(source, target, _annotations(ir, reference))
    entity_errors = list(comparison["errors"])
    hallucinations: list[dict[str, Any]] = []
    for issue in entity_errors:
        if issue["code"] in {"CRITICAL_ENTITY_EXTRA", "CRITICAL_ENTITY_MODIFIED"}:
            hallucinations.append(
                {
                    **issue,
                    "code": "HALLUCINATION_ENTITY_ADDED"
                    if issue["code"] == "CRITICAL_ENTITY_EXTRA"
                    else "HALLUCINATION_ENTITY_MODIFIED",
                }
            )
        elif issue["code"] == "CRITICAL_ENTITY_MISSING":
            hallucinations.append({**issue, "code": "HALLUCINATION_SOURCE_ASSERTION_REMOVED"})
        elif issue["code"] == "CRITICAL_ENTITY_ORDER_CHANGED":
            hallucinations.append({**issue, "code": "HALLUCINATION_ENTITY_ORDER_CHANGED"})
    source_units = _unit_occurrences(source)
    target_units = _unit_occurrences(target)
    if source_units != target_units:
        hallucinations.append(
            {
                "code": "HALLUCINATION_UNIT_CHANGED",
                "severity": "critical",
                "expected": source_units,
                "actual": target_units,
            }
        )
    assertions = (reference or {}).get("assertions", ir.get("assertions", []))
    assertion_checked = 0
    assertion_coverage_explicit = 0
    if isinstance(assertions, list):
        for assertion in assertions:
            if not isinstance(assertion, Mapping):
                continue
            required = assertion.get("target_text", assertion.get("target", assertion.get("text")))
            if not isinstance(required, str) or not required.strip():
                continue
            assertion_checked += 1
            if assertion.get("coverage") in {True, "explicit", "verified"}:
                assertion_coverage_explicit += 1
            if _normalise(required) not in _normalise(target):
                hallucinations.append(
                    {
                        "code": "HALLUCINATION_ASSERTION_MISSING",
                        "severity": "critical",
                        "assertion_id": assertion.get("id"),
                        "expected": required,
                    }
                )
    if assertion_checked and assertion_coverage_explicit < assertion_checked:
        hallucinations.append(
            {
                "code": "ASSERTION_SEMANTIC_COVERAGE_UNPROVEN",
                "severity": "warning",
                "message": "Normalized substring presence is not a semantic assertion checker.",
            }
        )
    coverage = {
        "entities": comparison["coverage"],
        "units_source": len(source_units),
        "units_target": len(target_units),
        "assertions_checked": assertion_checked,
        "assertions_declared": len(assertions) if isinstance(assertions, list) else 0,
        "assertions_semantic_coverage_explicit": assertion_coverage_explicit == assertion_checked
        if assertion_checked
        else False,
        "unit_normalization": "language_aliases_and_occurrence_order",
    }
    return entity_errors, hallucinations, coverage


def _layout_score(
    render: Mapping[str, Any] | None, visual: Mapping[str, Any]
) -> tuple[float | None, str | None]:
    if not render:
        return None, None
    geometry = visual.get("components", {}).get("geometry")
    if isinstance(geometry, (float, int)) and not isinstance(geometry, bool):
        return max(0.0, min(1.0, float(geometry))), "visual.geometry_metrics"
    value = render.get("layout_score")
    if (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ):
        return max(0.0, min(1.0, float(value))), "render_result.layout_score"
    return None, None


def _threshold_issues(scores: Mapping[str, float | None], thresholds: Any) -> list[dict[str, Any]]:
    if not isinstance(thresholds, Mapping):
        return []
    issues: list[dict[str, Any]] = []
    for key, threshold in thresholds.items():
        if key not in scores:
            continue
        value = _finite_score(threshold)
        if value is None:
            issues.append(
                {
                    "code": "INVALID_QUALITY_THRESHOLD",
                    "severity": "error",
                    "score": key,
                    "threshold": threshold,
                }
            )
        elif scores[key] is not None and scores[key] < value:
            issues.append(
                {
                    "code": "QUALITY_THRESHOLD_NOT_MET",
                    "severity": "error",
                    "score": key,
                    "value": scores[key],
                    "threshold": value,
                    "message": f"{key} is below configured quality threshold",
                }
            )
    return issues


def evaluate_quality(
    ir: dict,
    translations: dict[str, str],
    render_result: dict | None = None,
    reference: dict | None = None,
    options: dict | None = None,
) -> dict:
    """Evaluate quality using only evidence available for this candidate.

    The signature is intentionally stable for document-agent integrations.
    Missing proof is represented by ``None`` and results in review rather than
    being converted to a zero or an unqualified pass.
    """
    options = options or {}
    ir = ir if isinstance(ir, Mapping) else {}
    translations = translations if isinstance(translations, Mapping) else {}
    blocks = _blocks(ir)
    source = _source_text(ir, blocks)
    target = _target_text(translations, blocks)
    source_sha = _source_sha256(ir, reference, source, options)
    candidate_sha = _canonical_sha256(dict(translations))
    issues: list[dict[str, Any]] = []
    missing_ids = [str(block["id"]) for block in blocks if str(block["id"]) not in translations]
    known_ids = {str(block["id"]) for block in blocks}
    unknown_ids = sorted(set(str(key) for key in translations) - known_ids)
    issues.extend(
        {"code": "MISSING_TRANSLATION_BLOCK", "severity": "error", "block_id": item}
        for item in missing_ids
    )
    issues.extend(
        {"code": "UNKNOWN_TRANSLATION_BLOCK", "severity": "error", "block_id": item}
        for item in unknown_ids
    )
    if not blocks and not isinstance(ir.get("source_text"), str):
        issues.append({"code": "SOURCE_COVERAGE_MISSING", "severity": "warning"})
    ref_valid = reference_is_valid(reference)
    reference_status = (
        "validated" if ref_valid else ("not_available" if not reference else "unvalidated")
    )
    if not ref_valid:
        issues.append(
            {
                "code": "REFERENCE_NOT_VALIDATED",
                "severity": "warning",
                "message": "Aucune référence humaine/signée fiable.",
            }
        )
    ocr_score, ocr_details, ocr_method = _ocr_evidence(ir, reference, source, source_sha)
    if ocr_score is None:
        issues.append({"code": "OCR_EVIDENCE_MISSING", "severity": "warning"})
    expected = _reference_target(reference) if ref_valid else None
    candidate_complete = bool(target.strip()) and not missing_ids and not unknown_ids
    if not candidate_complete:
        issues.append({"code": "TRANSLATION_CANDIDATE_MISSING", "severity": "error"})
    expected_review = options.get("review_version", ir.get("review_version"))
    rubric, rubric_method = _signed_rubric(
        reference if ref_valid and candidate_complete else None,
        translations,
        source_sha,
        expected_review,
        source,
    )
    translation_details: dict[str, Any] = {
        "dimensions": rubric or {},
        "reference_agreement": None,
        "candidate_sha256": candidate_sha,
    }
    translation_method: str | None = None
    if rubric is not None:
        translation_score = round(sum(rubric.values()) / len(_REQUIRED_RUBRIC), 10)
        translation_method = rubric_method
    elif expected is not None and candidate_complete:
        agreement = _similarity(expected, target)
        translation_details["reference_agreement"] = agreement
        translation_method = "validated_reference_lexical_agreement_only"
        # A lexical reference distance is deliberately not the multidimensional
        # translation score. Exact validated agreement is a permitted perfect
        # score; a paraphrase remains unmeasured absent a rubric/provider.
        translation_score = 1.0 if _normalise(expected) == _normalise(target) else None
        if translation_score is None:
            issues.append(
                {
                    "code": "TRANSLATION_SEMANTIC_EVIDENCE_MISSING",
                    "severity": "warning",
                    "message": "Lexical reference agreement is reported separately, not as translation quality.",
                }
            )
    else:
        translation_score = None
        translation_method = None
        issues.append({"code": "TRANSLATION_EVIDENCE_MISSING", "severity": "warning"})
    semantic_score: float | None = None
    semantic_method: str | None = None
    provider_used = False
    if expected is not None and candidate_complete:
        semantic_score, semantic_method = _reference_semantic_score(target, expected, options)
        provider_used = semantic_method in {
            "typed_local_or_private_semantic_provider",
            "typed_private_semantic_judge",
            "typed_provider_unavailable_or_invalid",
        }
    else:
        issues.append({"code": "SEMANTIC_REFERENCE_MISSING", "severity": "warning"})
    entity_errors, hallucination_errors, hallucination_coverage = _entity_and_hallucination_checks(
        source, target, ir, reference
    )
    issues.extend(entity_errors)
    issues.extend(hallucination_errors)
    if not _annotations(ir, reference):
        issues.append(
            {
                "code": "ENTITY_EXTRACTION_LIMITED",
                "severity": "warning",
                "message": "Regex invariants are not a complete NER; provide signed entity annotations for exhaustive coverage.",
            }
        )
    # No local issue list can prove zero hallucinations without an explicit
    # trusted judge/coverage annotation.
    judge = _typed_provider(options.get("hallucination_judge"))
    hallucination_proven = bool(judge and options.get("hallucination_judge_verified") is True)
    if not hallucination_proven:
        issues.append(
            {
                "code": "HALLUCINATION_ZERO_NOT_PROVEN",
                "severity": "warning",
                "message": "No trusted judge or exhaustive human coverage proves zero hallucinations.",
            }
        )
    visual = score_visual(ir, render_result, options)
    issues.extend(visual["issues"])
    layout_score, layout_method = _layout_score(render_result, visual)
    if layout_score is None:
        issues.append({"code": "LAYOUT_EVIDENCE_MISSING", "severity": "warning"})
    visual_score = visual["score"]
    if visual_score is None:
        issues.append({"code": "VISUAL_EVIDENCE_MISSING", "severity": "warning"})
    metrics = (
        reference_metrics(source, target, reference)
        if ref_valid
        else {"cer": None, "wer": None, "translation_cer": None, "translation_wer": None}
    )
    scores: dict[str, float | None] = {
        "ocr_score": ocr_score,
        "translation_score": translation_score,
        "semantic_score": semantic_score,
        "layout_score": layout_score,
        "visual_score": visual_score,
    }
    issues.extend(_threshold_issues(scores, options.get("quality_thresholds")))
    missing_proof = any(value is None for value in scores.values())
    critical = bool(
        entity_errors
        or any(issue.get("severity") == "critical" for issue in hallucination_errors)
        or any(issue.get("severity") == "critical" for issue in visual["issues"])
    )
    status = (
        "FAIL"
        if critical
        else (
            "REVIEW_REQUIRED"
            if missing_proof
            or any(issue.get("severity") in {"error", "warning"} for issue in issues)
            else "PASS"
        )
    )
    plugin_configured = any(
        options.get(key) is not None
        for key in (
            "embedding_provider",
            "private_judge",
            "translation_provider",
            "hallucination_judge",
        )
    )
    model_verification = {
        "status": "unknown"
        if (provider_used or plugin_configured)
        else "verified_no_quality_provider_invoked",
        "provider": semantic_method if provider_used else None,
    }
    provenance = {
        "ocr": ocr_method,
        "translation": translation_method,
        "semantic": semantic_method,
        "layout": layout_method,
        "visual": visual.get("provenance"),
        "reference": {
            "status": reference_status,
            "validated": ref_valid,
            "version": (reference or {}).get("version"),
            "reviewer": (reference or {}).get("reviewer_id", (reference or {}).get("reviewer")),
        },
        "translation_sha256": candidate_sha,
        "source_sha256": source_sha,
        "no_public_model_calls": model_verification,
        "hallucination_zero_proven": hallucination_proven,
    }
    coverage = {
        "source_blocks": len(blocks),
        "translated_blocks": len(translations),
        "translated_block_coverage": max(0.0, (len(blocks) - len(missing_ids)) / len(blocks))
        if blocks
        else 0.0,
        "reference": ref_valid,
        "ocr": ocr_method is not None,
        "translation_rubric": rubric is not None,
        "semantic_reference": expected is not None,
        "visual": visual.get("coverage"),
        "hallucinations": hallucination_coverage,
        "hallucination_zero_proven": hallucination_proven,
    }
    return {
        **scores,
        "status": status,
        "issues": issues,
        "critical_entity_errors": entity_errors,
        "hallucination_errors": hallucination_errors,
        "untranslated_blocks": missing_ids,
        "reference_status": reference_status,
        "provenance": provenance,
        "coverage": coverage,
        "metrics": metrics,
        "quality": {
            "ocr": ocr_details,
            "translation": translation_details,
            "semantic": {"score": semantic_score, "method": semantic_method},
            "geometry_only_layout": layout_score,
            "visual": visual,
            "reference_status": reference_status,
        },
    }


__all__ = ["QualityProvider", "SemanticProvider", "evaluate_quality"]
