"""Recherche terminologique du LOT 1 : correspondance exacte après normalisation.

Le LOT 2 ajoutera synonymes, normalisation arabe et classement lexical BM25 ;
l'interface (index -> occurrences -> classement) reste la même.

Cache : un index n'est réutilisé que pour la même clé
(tenant, mode, versions publiées et empreintes de contenu, langues source,
langue cible, domaine, contexte). Le mode fait partie de la clé : aucun index
n'est partagé entre SHADOW, ASSISTED et ACTIVE.
"""

from __future__ import annotations

import threading
import time
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ..terminology.normalizer import normalize_language, normalize_term, tokens

MAX_NGRAM_WORDS = 8


@dataclass(frozen=True)
class TermView:
    """Copie détachée d'une entrée validée (aucun objet de session en cache)."""

    id: str
    version_id: str
    referential_id: str
    scope: str  # tenant | common
    source_language: str
    source_term: str
    normalized_source: str
    target_language: str
    target_term: str
    normalized_target: str
    domain: str | None
    country: str | None
    jurisdiction: str | None
    register: str | None


@dataclass(frozen=True)
class NotionView:
    id: str
    version_id: str
    referential_id: str
    scope: str
    notion: str
    normalized: str
    source_language: str | None
    target_language: str | None
    source_country: str | None
    target_country: str | None
    equivalence_type: str
    guidance: str | None


@dataclass(frozen=True)
class TermIndex:
    terms: Mapping[str, tuple[TermView, ...]]
    notions: Mapping[str, tuple[NotionView, ...]]
    max_words: int
    versions: tuple[tuple[str, str, int, str], ...]  # (version, sha256, numéro, scope)


def term_view(entry: Any, scope: str) -> TermView:
    return TermView(
        id=str(entry.id),
        version_id=str(entry.version_id),
        referential_id=str(entry.referential_id),
        scope=scope,
        source_language=str(entry.source_language),
        source_term=str(entry.source_term),
        normalized_source=normalize_term(entry.source_term),
        target_language=str(entry.target_language),
        target_term=str(entry.target_term),
        normalized_target=normalize_term(entry.target_term),
        domain=entry.domain,
        country=entry.country,
        jurisdiction=entry.jurisdiction,
        register=entry.register,
    )


def notion_view(row: Any, scope: str) -> NotionView:
    return NotionView(
        id=str(row.id),
        version_id=str(row.version_id),
        referential_id=str(row.referential_id),
        scope=scope,
        notion=str(row.notion),
        normalized=normalize_term(row.notion),
        source_language=normalize_language(row.source_language),
        target_language=normalize_language(row.target_language),
        source_country=row.source_country,
        target_country=row.target_country,
        equivalence_type=str(row.equivalence_type),
        guidance=row.guidance,
    )


def build_index(scope: list[dict], entries: Iterable[Any], notions: Iterable[Any]) -> TermIndex:
    scopes = {item["version_id"]: item["scope"] for item in scope}
    terms: dict[str, list[TermView]] = {}
    for entry in entries:
        view = term_view(entry, scopes.get(str(entry.version_id), "tenant"))
        if view.normalized_source and len(view.normalized_source.split(" ")) <= MAX_NGRAM_WORDS:
            terms.setdefault(view.normalized_source, []).append(view)
    found: dict[str, list[NotionView]] = {}
    for row in notions:
        view = notion_view(row, scopes.get(str(row.version_id), "tenant"))
        if view.normalized and len(view.normalized.split(" ")) <= MAX_NGRAM_WORDS:
            found.setdefault(view.normalized, []).append(view)
    keys = [*terms, *found]
    return TermIndex(
        terms={key: tuple(sorted(values, key=lambda v: v.id)) for key, values in terms.items()},
        notions={key: tuple(sorted(values, key=lambda v: v.id)) for key, values in found.items()},
        max_words=max((len(key.split(" ")) for key in keys), default=0),
        versions=tuple(
            sorted(
                (
                    str(item["version_id"]),
                    str(item["content_sha256"] or ""),
                    int(item["number"]),
                    str(item["scope"]),
                )
                for item in scope
            )
        ),
    )


class IndexCache:
    """Cache LRU borné à durée de vie ; la clé porte toute l'isolation."""

    def __init__(self, max_items: int = 64, ttl_seconds: float = 300.0) -> None:
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[tuple, tuple[float, TermIndex]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get_or_build(self, key: tuple, builder: Callable[[], TermIndex]) -> tuple[TermIndex, bool]:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is not None and now - item[0] <= self.ttl_seconds:
                self._items.move_to_end(key)
                self.hits += 1
                return item[1], True
        index = builder()
        with self._lock:
            self.misses += 1
            self._items[key] = (now, index)
            self._items.move_to_end(key)
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)
        return index, False

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.hits = 0
            self.misses = 0


INDEX_CACHE = IndexCache()


def cache_key(
    *,
    tenant_id: str,
    mode: str,
    scope: list[dict],
    source_languages: Iterable[str],
    target_language: str,
    domain: str | None,
    context_fingerprint: str,
) -> tuple:
    versions = tuple(
        sorted((str(item["version_id"]), str(item["content_sha256"] or "")) for item in scope)
    )
    return (
        "rag-index-1",
        str(tenant_id),
        str(mode),
        versions,
        tuple(sorted(set(source_languages))),
        str(target_language),
        str(domain or ""),
        context_fingerprint,
    )


def text_units(ir: Mapping[str, Any], memory: Mapping[str, str] | None) -> tuple[list[dict], int]:
    """Blocs à examiner et nombre de blocs écartés car couverts par la mémoire.

    Un bloc dont le texte exact est dans la mémoire de traduction validée n'est
    pas examiné : la mémoire est prioritaire sur toute suggestion RAG.
    """
    document_language = ir.get("language")
    blocks = [
        block
        for page in ir.get("pages", []) or []
        for block in page.get("blocks", []) or []
        if block.get("id") is not None
    ] or [block for block in ir.get("blocks", []) or [] if block.get("id") is not None]
    memory_keys = set(memory or {})
    units, skipped = [], 0
    for block in blocks:
        text = str(block.get("text") or "")
        if not text.strip():
            continue
        if text in memory_keys:
            skipped += 1
            continue
        language = normalize_language(block.get("language") or document_language)
        units.append({"language": language, "text": text})
    return units, skipped


def source_languages(ir: Mapping[str, Any], units: list[dict]) -> list[str]:
    found = {unit["language"] for unit in units if unit["language"]}
    document = normalize_language(ir.get("language"))
    if document:
        found.add(document)
    return sorted(found)


def match(index: TermIndex, units: list[dict]) -> tuple[Counter, Counter]:
    """Occurrences des clés de l'index (termes, notions) dans les blocs."""
    term_hits: Counter = Counter()
    notion_hits: Counter = Counter()
    if index.max_words == 0:
        return term_hits, notion_hits
    for unit in units:
        words = tokens(unit["text"])
        for size in range(1, min(index.max_words, len(words)) + 1):
            for start in range(len(words) - size + 1):
                key = " ".join(words[start : start + size])
                views = index.terms.get(key)
                if views and any(_language_ok(v.source_language, unit) for v in views):
                    term_hits[key] += 1
                if key in index.notions:
                    notion_hits[key] += 1
    return term_hits, notion_hits


def _language_ok(entry_language: str, unit: dict) -> bool:
    # Bloc de langue inconnue : la langue du document a déjà filtré les entrées.
    return unit["language"] is None or unit["language"] == entry_language
