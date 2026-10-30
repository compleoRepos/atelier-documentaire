"""Filtres de priorité et classement des correspondances.

Ordre des sources (consigne §7.7) :
1. glossaire client validé — toute entrée RAG qui recouvre un terme du
   glossaire, en clé exacte ou pliée, est écartée (GLOSSARY_PRIORITY) ;
2. mémoire de traduction validée — les blocs couverts par la mémoire ne sont
   pas examinés (``retrieval.text_units``) ;
3. référentiel validé correspondant au domaine — le référentiel du tenant
   prime sur la bibliothèque commune (TENANT_PRIORITY) ;
4. suggestions non autoritaires (BM25) — jamais injectées.

Une forme qui garde plusieurs traductions distinctes après filtrage n'est pas
injectée (AMBIGUOUS_REQUIRES_CONTEXT) ; une forme pliée qui désigne plusieurs
clés exactes non plus (FOLDED_AMBIGUOUS) : le choix revient au relecteur.

Classement des entrées retenues (pertinence, déterministe) : les formes les
plus longues d'abord (plus spécifiques), puis les plus fréquentes dans le
document, le tenant avant la bibliothèque commune, l'appariement exact avant
l'appariement plié, puis l'ordre lexical. Une entrée trouvée sous plusieurs
formes (terme et synonyme) n'est retenue qu'une fois, sous la forme la mieux
classée.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace

from ..terminology import domains, linguistic
from ..terminology.normalizer import normalize_term
from .retrieval import MatchResult, NotionView, TermIndex, TermView

GENERAL_DOMAINS = frozenset({"", "general", "général", "generic"})
UNKNOWN_DOCUMENT_DOMAINS = frozenset({"unknown", "inconnu"})


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
    keys = [g for g in glossary_keys if g]
    for candidate in {key, linguistic.fold_key(key)}:
        padded = f" {candidate} "
        if any(f" {g} " in padded or padded in f" {g} " for g in keys):
            return True
    return False


def glossary_keys(glossary: object) -> set[str]:
    """Clés du glossaire : LOT 1 (normalize_term), exacte v2 et pliée v2."""
    keys = set()
    for item in glossary or []:
        if isinstance(item, Mapping) and item.get("source"):
            source = item["source"]
            exact = linguistic.search_key(source)
            keys.update({normalize_term(source), exact, linguistic.fold_key(exact)})
    return {key for key in keys if key}


def _domain_ok(entry_domain: str | None, document_domain: str | None) -> str | None:
    entry = (entry_domain or "").strip().lower()
    if entry in GENERAL_DOMAINS:
        return None
    document = (document_domain or "").strip().lower()
    if not document or document in GENERAL_DOMAINS or document in UNKNOWN_DOCUMENT_DOMAINS:
        return "DOMAIN_UNKNOWN"
    if entry == document or domains.compatible(entry_domain, document_domain):
        return None
    return "DOMAIN_MISMATCH"


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


def _annotate(view: TermView, key: str, details: MatchResult | None) -> TermView:
    if details is None:
        return view
    return replace(
        view,
        matched_by=details.kinds.get(key, "exact"),
        surface=details.surfaces.get(key, ""),
    )


def rank(
    index: TermIndex,
    term_hits: Counter,
    notion_hits: Counter,
    *,
    glossary: set[str],
    filters: DocumentFilters,
    max_entries: int,
    details: MatchResult | None = None,
) -> Selection:
    exclusions: list[Exclusion] = []
    selected: list[tuple[TermView, int]] = []
    ambiguous = 0
    if details is not None:
        for key in sorted(details.folded_ambiguous - set(term_hits)):
            ambiguous += 1
            exclusions.extend(Exclusion(v.id, "FOLDED_AMBIGUOUS") for v in index.terms.get(key, ()))
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
        selected.append((_annotate(ordered[0], key, details), term_hits[key]))
        exclusions.extend(Exclusion(v.id, "DUPLICATE") for v in ordered[1:])
    selected.sort(
        key=lambda item: (
            -len(item[0].normalized_source.split(" ")),
            -item[1],
            item[0].scope != "tenant",
            item[0].matched_by != "exact",
            item[0].normalized_source,
            item[0].id,
        )
    )
    unique: list[tuple[TermView, int]] = []
    seen_ids: set[str] = set()
    for view, count in selected:
        if view.id not in seen_ids:
            seen_ids.add(view.id)
            unique.append((view, count))
    kept, dropped = unique[:max_entries], unique[max_entries:]
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
