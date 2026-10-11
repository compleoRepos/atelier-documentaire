"""Explicit per-block translation status (run18 §10).

Every block of the document receives exactly one status and one reason, so a
block kept in the source language is never confused with a translated one:

* ``TRANSLATED`` - a real translation was produced and its replacement was
  planned without a rendering failure (the independent PDF measure in
  ``tools/recette/render_outcome.py`` still verifies what was written);
* ``PRESERVED_INTENTIONALLY`` - already French, identifier/number, proper
  name or reference, protected visual element;
* ``NOT_TRANSLATABLE`` - no word at all (symbol, number, OCR fragment);
* ``UNCERTAIN`` - kept for human review because the OCR reading or the form
  structure is not reliable enough to send or rewrite it;
* ``FAILED`` - a translation was expected but is missing from the output
  (model returned the source, entity guard rejection, engine error) or was
  produced but could not be written (overflow, residual ink, RTL shaping);
* ``NOT_PROCESSED`` - the block is absent from the translation result.

The function is pure (IR + translations + issues) so the same code computes
the statuses in production, in the corpus launcher and in offline audits.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

VERSION = "block-status-1"
STATUSES = (
    "TRANSLATED",
    "PRESERVED_INTENTIONALLY",
    "NOT_TRANSLATABLE",
    "UNCERTAIN",
    "FAILED",
    "NOT_PROCESSED",
)
_RENDER_FAILURES = {
    "LAYOUT_OVERFLOW": "render_overflow",
    "SCAN_TEXT_OVER_SOURCE_INK": "render_residual_source_ink",
    "RTL_SHAPING_UNSUPPORTED": "render_rtl_shaping_unsupported",
    "PROTECTED_OVERLAP_REVIEW": "render_protected_overlap",
    "PROTECTED_TRANSLATION_NOT_APPLIED": "render_protected_region",
    "NATIVE_REDACTION_OVERLAP": "render_mask_unsafe",
    "PDF_TABLE_CELL_TARGET_MISSING": "render_table_cell_missing",
    "PDF_NATIVE_ROTATION_REQUIRES_REVIEW": "render_rotation_unsupported",
}
_GUARD_FAILURES = {
    "PROTECTED_ENTITY_CHANGED": "entity_guard_rejected",
    "PROTECTED_ENTITY_COLLISION": "entity_guard_rejected",
    "INVALID_MODEL_OUTPUT": "invalid_model_output",
    "OUTPUT_LENGTH": "engine_output_length",
    "CONTEXT_OVERFLOW": "context_budget_exceeded",
    "UNKNOWN_FINISH_REASON": "engine_error",
    "PRIVATE_GATEWAY_FAILED": "engine_error",
    "PRIVATE_TRANSLATION_UNAVAILABLE": "engine_unavailable",
}
_UNCERTAIN_FLAGS = (
    ("ocr_unreliable", "ocr_unreliable"),
    ("minority_script_low_confidence", "ocr_script_inconsistent"),
    ("entity_read_disagreement", "critical_entity_double_read_disagreement"),
    ("form_structure_risk", "form_structure_ambiguous"),
)
_NUMERIC = re.compile(r"[\d\s.,:/+()\-–—€$%#°]+", re.UNICODE)


def _is_french(language: Any) -> bool:
    value = str(language or "").strip().lower().replace("_", "-")
    return value in {"fr", "fra", "fre", "french", "français"} or value.startswith("fr-")


def _issue_ids(issue: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("block_id", "block_ids", "blocks"):
        value = issue.get(key)
        if isinstance(value, str):
            ids.append(value)
        elif isinstance(value, (list, tuple)):
            ids.extend(str(v) for v in value if isinstance(v, (str, int)))
    return ids


def _proper_name_or_reference(text: str, languages: list[Any]) -> bool:
    """Every word is rare in French and in the document languages (names,
    places, brands, references); needs the offline lexicon, else False."""
    from app.documents.language_evidence import _ISO, _latin_words, _zipf, available

    if not available():
        return False
    words = _latin_words(text)
    if not words:
        return False
    isos = ["fr", *[_ISO[c] for c in (str(x).lower() for x in languages) if c in _ISO]]
    return all(max(_zipf(w, iso) for iso in isos) < 2.0 for w in words)


def classify_blocks(
    ir: dict[str, Any],
    translations: dict[str, str] | None,
    issues: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    from app.ai.translation.typography import typography_equivalent
    from app.documents.pipeline import _requires_translation

    translations = translations or {}
    by_block: dict[str, set[str]] = {}
    for issue in issues or []:
        if isinstance(issue, dict) and issue.get("code"):
            for block_id in _issue_ids(issue):
                by_block.setdefault(block_id, set()).add(str(issue["code"]))
    languages = [
        item.get("code") if isinstance(item, dict) else item for item in ir.get("languages") or []
    ]
    document_language = ir.get("language")
    blocks: dict[str, dict[str, Any]] = {}
    for page in ir.get("pages", []):
        for block in page.get("blocks", []):
            block_id = str(block.get("id"))
            source = str(block.get("text") or "")
            codes = by_block.get(block_id, set())
            language = block.get("language") or document_language
            status, reason = _classify(
                block,
                block_id,
                source,
                translations,
                codes,
                language,
                languages,
                typography_equivalent,
                _requires_translation,
            )
            blocks[block_id] = {
                "page": page.get("number"),
                "status": status,
                "reason": reason,
                "chars": len(source.strip()),
            }
    counts = Counter(v["status"] for v in blocks.values())
    chars = Counter()
    reasons = Counter()
    for value in blocks.values():
        chars[value["status"]] += value["chars"]
        reasons[f"{value['status']}:{value['reason']}"] += 1
    return {
        "version": VERSION,
        "blocks": blocks,
        "summary": {
            "blocks": {s: counts.get(s, 0) for s in STATUSES},
            "chars": {s: chars.get(s, 0) for s in STATUSES},
            "reasons": dict(sorted(reasons.items())),
        },
    }


def _classify(
    block, block_id, source, translations, codes, language, languages, typo_eq, requires
) -> tuple[str, str]:
    if block_id not in translations:
        return "NOT_PROCESSED", "absent_from_translation_result"
    target = str(translations.get(block_id) or "")
    if block.get("no_linguistic_content") or not re.search(r"[^\W\d_]{2,}", source):
        return "NOT_TRANSLATABLE", "no_linguistic_content"
    if block.get("protected"):
        return "PRESERVED_INTENTIONALLY", "protected_visual_element"
    changed = target.strip() != source.strip() and not typo_eq(source, target)
    if _is_french(language):
        return (
            ("TRANSLATED", "french_source_rewritten")
            if changed
            else (
                "PRESERVED_INTENTIONALLY",
                "already_french",
            )
        )
    if block.get("identifier_only") or not requires(source) or _NUMERIC.fullmatch(source.strip()):
        return "PRESERVED_INTENTIONALLY", "identifier_or_number"
    for flag, reason in _UNCERTAIN_FLAGS:
        if block.get(flag):
            return "UNCERTAIN", reason
    if changed:
        for code, reason in _RENDER_FAILURES.items():
            if code in codes:
                return "FAILED", reason
        return "TRANSLATED", "translated_and_placed"
    for code, reason in _GUARD_FAILURES.items():
        if code in codes:
            return "FAILED", reason
    from app.documents.language_evidence import identical_in_french

    if identical_in_french(source, [language, *languages]):
        return "PRESERVED_INTENTIONALLY", "identical_in_french"
    if _proper_name_or_reference(source, [language, *languages]):
        return "PRESERVED_INTENTIONALLY", "proper_name_or_reference"
    return "FAILED", "model_returned_source"
