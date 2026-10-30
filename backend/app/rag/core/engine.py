"""Orchestration d'une recherche RAG pour un document (sans effet de bord).

``RagEngine.plan`` lit les référentiels publiés du tenant et de la bibliothèque
commune, examine les blocs de l'IR, applique les priorités et produit un
``RagPlan``. Il n'écrit rien et ne modifie ni l'IR ni les options.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..audit.provenance import query_fingerprint
from ..resolver import document_context as resolver
from ..storage import repository
from ..terminology.linguistic import VERSION as NORMALIZER_VERSION
from ..terminology.normalizer import normalize_language, normalize_term
from . import context_builder, ranking, retrieval
from .ranking import Exclusion
from .retrieval import INDEX_CACHE, IndexCache, NotionView, TermView

ENGINE_VERSION = "dice-engine-2"


@dataclass
class RagPlan:
    mode: str
    terms: list[TermView] = field(default_factory=list)
    terminology: list[dict] = field(default_factory=list)
    notions: list[NotionView] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    country_context: dict | None = None
    exclusions: list[Exclusion] = field(default_factory=list)
    versions: list[dict] = field(default_factory=list)
    query_sha256: str = ""
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not self.terminology and not self.decisions and not self.country_context

    def audit(self) -> dict[str, Any]:
        """Résumé journalisable : identifiants et compteurs, jamais de texte."""
        reasons: dict[str, int] = {}
        for item in self.exclusions:
            reasons[item.reason] = reasons.get(item.reason, 0) + 1
        return {
            "engine_version": ENGINE_VERSION,
            "normalizer_version": NORMALIZER_VERSION,
            "candidate_term_ids": [view.id for view in self.terms],
            "candidate_notion_ids": [view.id for view in self.notions],
            "country_context": bool(self.country_context),
            "exclusion_reasons": dict(sorted(reasons.items())),
            "excluded_ids": sorted({item.entry_id for item in self.exclusions})[:200],
            **self.stats,
        }


def _match_kinds(terms: list[TermView]) -> dict[str, int]:
    """Nature des correspondances retenues (terme, synonyme, variante ; exacte ou pliée)."""
    counts: dict[str, int] = {}
    for view in terms:
        name = f"{view.match_kind}_{view.matched_by}"
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


class RagEngine:
    def __init__(self, settings: Any, session_factory: Any, cache: IndexCache | None = None):
        self.settings = settings
        self.session_factory = session_factory
        self.cache = cache or INDEX_CACHE

    def plan(
        self,
        *,
        tenant_id: str,
        document_id: str | None,
        ir: Mapping[str, Any],
        options: Mapping[str, Any],
        mode: str,
    ) -> RagPlan:
        started = time.perf_counter()
        target_language = normalize_language(options.get("target_language") or "fr") or "fr"
        units, memory_skipped = retrieval.text_units(ir, options.get("memory"))
        languages = retrieval.source_languages(ir, units)
        domain = ir.get("domain")
        with self.session_factory() as db:
            context_row = (
                repository.document_context(db, tenant_id, document_id) if document_id else None
            )
            scope = repository.published_scope(db, tenant_id)
            key = retrieval.cache_key(
                tenant_id=tenant_id,
                mode=mode,
                scope=scope,
                source_languages=languages,
                target_language=target_language,
                domain=domain,
                context_fingerprint=resolver.fingerprint(context_row),
            )

            def build() -> retrieval.TermIndex:
                entries = repository.published_entries(
                    db, tenant_id, scope, languages, target_language
                )
                notions = (
                    repository.published_notions(db, tenant_id, scope, target_language)
                    if mode == "ACTIVE"
                    else []
                )
                return retrieval.build_index(scope, entries, notions)

            index, cache_hit = self.cache.get_or_build(key, build)
            filters = resolver.filters_for(context_row, domain)
            country = resolver.validated_country_context(context_row, mode)
        details = retrieval.match_details(index, units)
        term_hits, notion_hits = details.term_hits, details.notion_hits
        selection = ranking.rank(
            index,
            term_hits,
            notion_hits,
            glossary=ranking.glossary_keys(options.get("glossary")),
            filters=filters,
            max_entries=int(getattr(self.settings, "rag_max_entries", 16)),
            details=details,
        )
        terms = [view for view, _ in selection.terms]
        notions = [view for view, _ in selection.notions] if mode == "ACTIVE" else []
        terminology, rejected_terms = context_builder.terminology_items(terms)
        decisions, rejected_notions = context_builder.decision_items(notions)
        rejected_ids = {item.entry_id for item in [*rejected_terms, *rejected_notions]}
        plan = RagPlan(
            mode=mode,
            terms=[view for view in terms if view.id not in rejected_ids],
            terminology=terminology,
            notions=[view for view in notions if view.id not in rejected_ids],
            decisions=decisions,
            country_context=context_builder.country_items(country),
            exclusions=[*selection.exclusions, *rejected_terms, *rejected_notions],
            versions=[
                {"version_id": v, "content_sha256": sha, "number": n, "scope": s}
                for v, sha, n, s in index.versions
            ],
        )
        plan.query_sha256 = query_fingerprint(
            self.settings,
            tenant_id,
            mode,
            [
                target_language,
                ",".join(languages),
                str(domain or ""),
                resolver.fingerprint(context_row),
                *sorted(normalize_term(unit["text"]) for unit in units),
            ],
        )
        plan.stats = {
            "blocks_examined": len(units),
            "blocks_memory_priority": memory_skipped,
            "source_languages": languages,
            "target_language": target_language,
            "matched_keys": len(term_hits) + len(notion_hits),
            "ambiguous_keys": selection.ambiguous_keys,
            "match_kinds": _match_kinds(plan.terms),
            "index_entries": sum(len(v) for v in index.terms.values()),
            "cache_hit": cache_hit,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        return plan

    def search(
        self,
        *,
        tenant_id: str,
        text: str,
        source_language: str,
        target_language: str,
        domain: str | None,
        glossary: object,
        limit: int,
    ) -> dict[str, Any]:
        """Recherche terminologique d'un texte libre (aucun texte journalisé ici)."""
        started = time.perf_counter()
        source = normalize_language(source_language)
        target = normalize_language(target_language) or "fr"
        if not source:
            raise ValueError("RAG_LANGUAGE_INVALID")
        units = [{"language": source, "text": text}]
        with self.session_factory() as db:
            scope = repository.published_scope(db, tenant_id)
            key = retrieval.cache_key(
                tenant_id=tenant_id,
                mode="SEARCH",
                scope=scope,
                source_languages=[source],
                target_language=target,
                domain=domain,
                context_fingerprint="search",
            )

            def build() -> retrieval.TermIndex:
                entries = repository.published_entries(db, tenant_id, scope, [source], target)
                return retrieval.build_index(scope, entries, [])

            index, cache_hit = self.cache.get_or_build(key, build)
        details = retrieval.match_details(index, units)
        selection = ranking.rank(
            index,
            details.term_hits,
            Counter(),
            glossary=ranking.glossary_keys(glossary),
            filters=ranking.DocumentFilters(domain=domain),
            max_entries=limit,
            details=details,
        )
        reasons: dict[str, int] = dict(selection.reasons)
        return {
            "results": [
                {
                    "id": view.id,
                    "referential_id": view.referential_id,
                    "version_id": view.version_id,
                    "scope": view.scope,
                    "source_language": view.source_language,
                    "source_term": view.source_term,
                    "target_language": view.target_language,
                    "target_term": view.target_term,
                    "domain": view.domain,
                    "country": view.country,
                    "occurrences": count,
                    "match_kind": view.match_kind,
                    "matched_by": view.matched_by,
                }
                for view, count in selection.terms
            ],
            "exclusion_reasons": reasons,
            "ambiguous_keys": selection.ambiguous_keys,
            "versions": [
                {"version_id": v, "content_sha256": sha, "number": n, "scope": s}
                for v, sha, n, s in index.versions
            ],
            "query_sha256": query_fingerprint(
                self.settings,
                tenant_id,
                "SEARCH",
                [source, target, str(domain or ""), normalize_term(text)],
            ),
            "cache_hit": cache_hit,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
