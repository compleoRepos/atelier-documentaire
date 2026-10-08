"""Conservative, auditable protected-entity extraction and comparison.

The extractor deliberately reports its limits: regular expressions are useful
for invariants, but are not a complete named-entity recogniser.  Callers can
supply annotations from a human or document-understanding stage; those
annotations are always preferred and are compared occurrence-by-occurrence.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])"),
    "iban": re.compile(r"(?i)(?<![A-Z0-9])[A-Z]{2}\s?\d{2}(?:\s?[A-Z0-9]){11,30}(?![A-Z0-9])"),
    "phone": re.compile(r"(?<!\w)(?:\+\d[\d .()/\-]{6,}\d|\d[\d .()\-]{7,}\d)(?!\w)"),
    "date": re.compile(
        r"(?<!\w)(?:\d{1,4}[./-]){2}\d{1,4}(?!\w)|"
        r"(?<!\w)(?:\d{1,2}\s+)?(?:janvier|février|fevrier|mars|avril|mai|juin|"
        r"juillet|août|aout|septembre|octobre|novembre|décembre|decembre|"
        r"january|february|march|april|may|june|july|august|september|"
        r"october|november|december)\s+\d{4}(?!\w)",
    ),
    "amount": re.compile(
        r"(?i)(?<!\w)(?:[$€£]|USD|EUR|GBP|MAD|DHS|DH|AED|"
        r"dollars?\s+am(?:e|é)ricains?|euros?|dirhams?)\s*"
        r"[+-]?(?:\d[\d .,\u00a0]*)(?!\w)|"
        r"(?<!\w)[+-]?\d[\d .,\u00a0]*\s*"
        r"(?:[$€£]|USD|EUR|GBP|MAD|DHS|DH|AED|"
        r"dollars?\s+am(?:e|é)ricains?|euros?|dirhams?)(?!\w)",
    ),
    "code": re.compile(
        r"(?i)(?<![\w])(?:[A-Z]{2,}[\-_/]?\d{2,}[A-Z0-9\-_/.]*|"
        r"\d{3,}[A-Z][A-Z0-9\-_/.]*)(?![\w])"
    ),
    "number": re.compile(r"(?<![\w])[-+]?\d+(?:[.,:/-]\d+)*(?![\w])"),
}

# This stop list avoids treating ordinary English/French headings as people.
_NON_NAME_WORDS = {
    "employment",
    "certificate",
    "attestation",
    "travail",
    "account",
    "statement",
    "relevé",
    "releve",
    "invoice",
    "facture",
    "contract",
    "contrat",
    "date",
    "name",
    "nom",
    "address",
    "adresse",
    "company",
    "société",
    "societe",
    "salary",
    "salaire",
    "gross",
    "net",
    "total",
    "amount",
    "montant",
    "bank",
    "office",
    "department",
    "service",
    "document",
    "reference",
    "référence",
    "number",
    "numéro",
}
_COMPANY_SUFFIX = re.compile(
    r"(?i)\b(?:[\wÀ-ÿ'’-]+\s+){0,8}[\wÀ-ÿ'’-]+\s+"
    r"(?:S\.?A\.?|SAS|SARL|Ltd\.?|LLC|Inc\.?|Corp\.?|GmbH|PLC|S\.A\.R\.L\.?)\b"
)
_NAME_LABEL = re.compile(
    r"(?i)\b(?:name|full\s+name|nom|prénom|prenom|beneficiary|titulaire|applicant)\s*[:\-]\s*"
    r"([A-ZÀ-Ý][\wÀ-ÿ'’-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'’-]+){1,5})"
)
_ADDRESS_LABEL = re.compile(r"(?i)\b(?:address|adresse|domicile|siège|siege)\s*[:\-]\s*([^\n;]+)")


@dataclass(frozen=True)
class EntityOccurrence:
    type: str
    value: str
    start: int
    end: int
    source: str = "regex"
    confidence: float | None = None
    annotation_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "").strip())
    return value.casefold()


def _annotation_value(item: Any) -> tuple[str, str, int | None, int | None, str | None] | None:
    if isinstance(item, str):
        return "name", item, None, None, None
    if not isinstance(item, Mapping):
        return None
    value = item.get("value", item.get("text", item.get("entity")))
    kind = item.get("type", item.get("kind", item.get("label", "name")))
    if value is None:
        return None
    start = item.get("start", item.get("offset"))
    end = item.get("end")
    return (
        str(kind).lower(),
        str(value),
        _int_or_none(start),
        _int_or_none(end),
        (str(item["id"]) if item.get("id") is not None else None),
    )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _add_occurrence(
    output: list[EntityOccurrence],
    kind: str,
    value: str,
    start: int,
    end: int,
    source: str,
    confidence: float | None = None,
    annotation_id: str | None = None,
) -> None:
    if not value.strip():
        return
    kind = {"organisation": "company", "organization": "company", "phone_number": "phone"}.get(
        kind.lower(), kind.lower()
    )
    output.append(EntityOccurrence(kind, value, start, end, source, confidence, annotation_id))


def extract_entities(
    text: str,
    annotations: Sequence[Mapping[str, Any] | str] | Mapping[str, Any] | None = None,
    *,
    include_numbers: bool = True,
) -> list[dict[str, Any]]:
    """Extract protected occurrences with offsets and declared provenance.

    ``annotations`` may contain ``{type, value, start, end}`` records.  Regex
    extraction is intentionally limited to stable invariants; names and
    companies are only inferred with label/suffix/high-signal heuristics.
    """
    value = str(text or "")
    found: list[EntityOccurrence] = []
    annotation_values: Iterable[Any]
    if isinstance(annotations, Mapping):
        grouped = annotations.get("entities")
        if grouped is None:
            grouped = [
                item
                for key in (
                    "names",
                    "companies",
                    "dates",
                    "amounts",
                    "codes",
                    "ibans",
                    "phones",
                    "emails",
                    "addresses",
                )
                for item in (annotations.get(key) or [])
            ]
        annotation_values = (
            grouped
            if isinstance(grouped, Iterable) and not isinstance(grouped, (str, bytes))
            else []
        )
    else:
        annotation_values = annotations or ()
    for item in annotation_values:
        parsed = _annotation_value(item)
        if not parsed:
            continue
        kind, entity, start, end, annotation_id = parsed
        if start is None:
            start = value.find(entity)
        if end is None and start >= 0:
            end = start + len(entity)
        if start is not None and end is not None and start >= 0:
            _add_occurrence(found, kind, entity, start, end, "annotation", 1.0, annotation_id)

    for kind, pattern in _PATTERNS.items():
        if kind == "number" and not include_numbers:
            continue
        for match in pattern.finditer(value):
            _add_occurrence(found, kind, match.group(0), match.start(), match.end(), "regex", 0.98)
    for match in _COMPANY_SUFFIX.finditer(value):
        _add_occurrence(found, "company", match.group(0), match.start(), match.end(), "regex", 0.9)
    for match in _NAME_LABEL.finditer(value):
        start, end = match.span(1)
        _add_occurrence(found, "name", match.group(1), start, end, "regex", 0.88)
    for match in _ADDRESS_LABEL.finditer(value):
        start, end = match.span(1)
        _add_occurrence(found, "address", match.group(1).strip(), start, end, "regex", 0.82)

    # A two-token title-cased name is only inferred when at least one token is
    # a likely given name shape and neither token is a document heading word.
    for match in re.finditer(
        r"(?<![\wÀ-ÿ])([A-ZÀ-Ý][\wÀ-ÿ'’-]{2,})\s+([A-ZÀ-Ý][\wÀ-ÿ'’-]{2,})(?![\wÀ-ÿ])",
        value,
    ):
        words = [match.group(1), match.group(2)]
        if any(word.casefold() in _NON_NAME_WORDS for word in words):
            continue
        _add_occurrence(found, "name", match.group(0), match.start(), match.end(), "regex", 0.72)

    # Prefer annotations over regex duplicates, then remove nested/identical
    # occurrences.  Keeping all independent occurrences is essential for dates
    # or references repeated twice in a document.
    priority = {"annotation": 3, "regex": 1}
    found.sort(key=lambda item: (item.start, -(item.end - item.start), -priority[item.source]))
    selected: list[EntityOccurrence] = []
    for item in found:
        if any(
            item.start == old.start
            and item.end == old.end
            and _normalise(item.value) == _normalise(old.value)
            for old in selected
        ):
            continue
        # Drop number/code fragments contained in a stronger amount/date/etc.
        if item.type in {"number", "code"} and any(
            old.start <= item.start and item.end <= old.end and old.type not in {"number", "code"}
            for old in selected
        ):
            continue
        selected.append(item)
    return [item.as_dict() for item in selected]


def _coerce_annotations(annotations: Any, kind: str | None = None) -> list[Any]:
    if isinstance(annotations, Mapping):
        values = annotations.get(kind or "entities", annotations.get("entities", []))
    else:
        values = annotations
    return (
        list(values or [])
        if isinstance(values, Iterable) and not isinstance(values, (str, bytes))
        else []
    )


def _entity_key(kind: str, value: str) -> str:
    """Canonical invariant key, allowing language-level unit/currency aliases."""
    normalized = _normalise(value)
    if kind != "amount":
        return normalized
    number = re.search(r"[+-]?\d[\d .,\u00a0]*", normalized)
    numeric = re.sub(r"[ .\u00a0]", "", number.group(0)) if number else normalized
    currency = ""
    for alias, canonical in {
        "dollars américains": "usd",
        "dollar américain": "usd",
        "usd": "usd",
        "$": "usd",
        "euros": "eur",
        "euro": "eur",
        "eur": "eur",
        "€": "eur",
        "dirhams": "mad",
        "dirham": "mad",
        "dhs": "mad",
        "dh": "mad",
        "mad": "mad",
        "gbp": "gbp",
        "aed": "aed",
        "£": "gbp",
    }.items():
        if alias in normalized:
            currency = canonical
            break
    return f"{numeric}|{currency}"


def compare_entities(
    source: str,
    target: str,
    annotations: Sequence[Mapping[str, Any] | str] | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare invariant occurrences, preserving multiplicity and order."""
    annotation_values = _coerce_annotations(annotations)
    source_entities = extract_entities(source, annotation_values)
    # Source annotations define what must be protected; applying their source
    # values verbatim to the target would manufacture a match after a change.
    target_entities = extract_entities(target)
    by_type_source: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    by_type_target: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in source_entities:
        by_type_source[item["type"]].append(item)
    for item in target_entities:
        by_type_target[item["type"]].append(item)
    errors: list[dict[str, Any]] = []
    matched = 0
    for kind in sorted(set(by_type_source) | set(by_type_target)):
        expected = by_type_source[kind]
        actual = by_type_target[kind]
        used: set[int] = set()
        for occurrence, entity in enumerate(expected):
            wanted = _entity_key(kind, entity["value"])
            matches = [
                index
                for index, candidate in enumerate(actual)
                if index not in used and _entity_key(kind, candidate["value"]) == wanted
            ]
            if matches:
                used.add(matches[0])
                matched += 1
                continue
            # A same-type occurrence at the same ordinal is a modification,
            # otherwise it is an omission. Both remain critical invariants.
            if occurrence < len(actual) and occurrence not in used:
                candidate = actual[occurrence]
                used.add(occurrence)
                code = "CRITICAL_ENTITY_MODIFIED"
                detail = {"expected": entity["value"], "actual": candidate["value"]}
            else:
                code = "CRITICAL_ENTITY_MISSING"
                detail = {"expected": entity["value"], "actual": None}
            errors.append(
                {
                    "code": code,
                    "severity": "critical",
                    "entity_type": kind,
                    "occurrence": occurrence + 1,
                    **detail,
                }
            )
        source_order = [_entity_key(kind, entity["value"]) for entity in expected]
        target_order = [_entity_key(kind, entity["value"]) for entity in actual]
        if (
            len(source_order) > 1
            and Counter(source_order) == Counter(target_order)
            and source_order != target_order
        ):
            errors.append(
                {
                    "code": "CRITICAL_ENTITY_ORDER_CHANGED",
                    "severity": "critical",
                    "entity_type": kind,
                    "expected_order": [entity["value"] for entity in expected],
                    "actual_order": [entity["value"] for entity in actual],
                }
            )
        for index, entity in enumerate(actual):
            if index not in used:
                errors.append(
                    {
                        "code": "CRITICAL_ENTITY_EXTRA",
                        "severity": "critical",
                        "entity_type": kind,
                        "occurrence": index + 1,
                        "expected": None,
                        "actual": entity["value"],
                    }
                )
    source_count = len(source_entities)
    return {
        "source": source_entities,
        "target": target_entities,
        "errors": errors,
        "matched": matched,
        "source_count": source_count,
        "target_count": len(target_entities),
        "coverage": {
            "source_entities_detected": source_count,
            "target_entities_detected": len(target_entities),
            "automatic_regex_is_not_complete_ner": True,
            "annotation_count": len(annotation_values),
        },
    }


def protected_entity_issues(
    source: str,
    target: str,
    annotations: Sequence[Mapping[str, Any] | str] | Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Compatibility helper returning only issue records."""
    return compare_entities(source, target, annotations)["errors"]


__all__ = ["EntityOccurrence", "compare_entities", "extract_entities", "protected_entity_issues"]
