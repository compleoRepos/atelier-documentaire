"""Filtres de priorité et classement des correspondances.

Ordre des sources (consigne §7.7) :
1. glossaire client validé — toute entrée RAG qui recouvre un terme du
   glossaire est écartée (GLOSSARY_PRIORITY) ;
2. mémoire de traduction validée — les blocs couverts par la mémoire ne sont
   pas examinés (``retrieval.text_units``) ;
3. référentiel validé correspondant au domaine — le référentiel du tenant
   prime sur la bibliothèque commune (TENANT_PRIORITY) ;
4. suggestions non autoritaires — jamais injectées.

Une forme qui garde plusieurs traductions distinctes après filtrage n'est pas
injectée (AMBIGUOUS_REQUIRES_CONTEXT) : le choix revient au relecteur.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ..terminology.normalizer import normalize_term
from .retrieval import NotionView, TermIndex, TermView

GENERAL_DOMAINS = frozenset({"", "general", "général", "generic"})


@dataclass(frozen=True)
class Exclusion:
    entry_id: str
    reason: str


@dataclass(frozen=True)
class DocumentFilters:
    domain: str | None = None
    source_country: str | None = None
    target_country: str | None = None
    jurisdiction: str | None = None


@dataclass(frozen=True)
class Selection:
    terms: tuple[tuple[TermView, int], ...] = ()
    notions: tuple[tuple[NotionView, int], ...] = ()
    exclusions: tuple[Exclusion, ...] = ()
    ambiguous_keys: int = 0
    reasons: Mapping[str, int] = field(default_factory=dict)


def _overlaps(key: str, glossary_keys: Iterable[str]) -> bool:
    padded = f" {key} "
    return any(f" {g} " in padded or padded in f" {g} " for g in glossary_keys if g)


def glossary_keys(glossary: object) -> set[str]:
    keys = set()
    for item in glossary or []:
        if isinstance(item, Mapping) and item.get("source"):
            keys.add(normalize_term(item["source"]))
    return {key for key in keys if key}


def _domain_ok(entry_domain: str | None, document_domain: str | None) -> str | None:
    entry = (entry_domain or "").strip().lower()
    if entry in GENERAL_DOMAINS:
        return None
    document = (document_domain or "").strip().lower()
    if not document or document in GENERAL_DOMAINS:
        return "DOMAIN_UNKNOWN"
    return None if entry == document else "DOMAIN_MISMATCH"


def _country_ok(view: TermView, filters: DocumentFilters) -> str | None:
    if view.country:
        if not filters.source_country:
            return "COUNTRY_UNKNOWN"
        if view.country != filters.source_country:
            return "COUNTRY_MISMATCH"
    if view.jurisdiction:
        if not filters.jurisdiction:
            return "JURISDICTION_UNKNOWN"
        if view.jurisdiction.strip().lower() != filters.jurisdiction.strip().lower():
            return "JURISDICTION_MISMATCH"
    return None


def rank(
    index: TermIndex,
    term_hits: Counter,
    notion_hits: Counter,
    *,
    glossary: set[str],
    filters: DocumentFilters,
    max_entries: int,
) -> Selection:
    exclusions: list[Exclusion] = []
    selected: list[tuple[TermView, int]] = []
    ambiguous = 0
    for key in sorted(term_hits):
        views = index.terms.get(key, ())
        if _overlaps(key, glossary):
            exclusions.extend(Exclusion(v.id, "GLOSSARY_PRIORITY") for v in views)
            continue
        survivors = []
        for view in views:
            reason = _domain_ok(view.domain, filters.domain) or _country_ok(view, filters)
            if reason:
                exclusions.append(Exclusion(view.id, reason))
            else:
                survivors.append(view)
        if any(v.scope == "tenant" for v in survivors):
            exclusions.extend(
                Exclusion(v.id, "TENANT_PRIORITY") for v in survivors if v.scope != "tenant"
            )
            survivors = [v for v in survivors if v.scope == "tenant"]
        if not survivors:
            continue
        if len({v.normalized_target for v in survivors}) > 1:
            ambiguous += 1
            exclusions.extend(Exclusion(v.id, "AMBIGUOUS_REQUIRES_CONTEXT") for v in survivors)
            continue
        ordered = sorted(
            survivors,
            key=lambda v: ((v.domain or "").strip().lower() in GENERAL_DOMAINS, v.id),
        )
        selected.append((ordered[0], term_hits[key]))
        exclusions.extend(Exclusion(v.id, "DUPLICATE") for v in ordered[1:])
    selected.sort(
        key=lambda item: (
            -len(item[0].normalized_source.split(" ")),
            -item[1],
            item[0].scope != "tenant",
            item[0].normalized_source,
            item[0].id,
        )
    )
    kept, dropped = selected[:max_entries], selected[max_entries:]
    exclusions.extend(Exclusion(v.id, "ENTRY_LIMIT") for v, _ in dropped)

    notions: list[tuple[NotionView, int]] = []
    for key in sorted(notion_hits):
        views = index.notions.get(key, ())
        if _overlaps(key, glossary):
            exclusions.extend(Exclusion(v.id, "GLOSSARY_PRIORITY") for v in views)
            continue
        if any(v.scope == "tenant" for v in views):
            exclusions.extend(
                Exclusion(v.id, "TENANT_PRIORITY") for v in views if v.scope != "tenant"
            )
            views = tuple(v for v in views if v.scope == "tenant")
        if len(views) > 1:
            exclusions.extend(Exclusion(v.id, "AMBIGUOUS_REQUIRES_CONTEXT") for v in views)
            ambiguous += 1
            continue
        notions.extend((view, notion_hits[key]) for view in views)
    notions.sort(key=lambda item: (-item[1], item[0].normalized, item[0].id))
    reasons = Counter(item.reason for item in exclusions)
    return Selection(
        terms=tuple(kept),
        notions=tuple(notions),
        exclusions=tuple(exclusions),
        ambiguous_keys=ambiguous,
        reasons=dict(sorted(reasons.items())),
    )
