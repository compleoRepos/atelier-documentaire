"""Recherche terminologique : correspondance exacte, synonymes, variantes, repli plié.

LOT 1 : correspondance exacte après normalisation.
LOT 2 :
* clés calculées par la normalisation linguistique v2 (``linguistic.search_key``) ;
* une entrée est indexée sous son terme source, ses synonymes et ses variantes
  régionales (formes de la langue source) ; ``match_kind`` dit laquelle a servi ;
* repli plié (sans diacritiques, variantes arabes) : accepté seulement si la clé
  pliée désigne une seule clé exacte de l'index, sinon FOLDED_AMBIGUOUS ;
* la forme de surface trouvée dans le document est conservée pour que le terme
  injecté soit celui que le modèle lit dans le bloc.

Le classement BM25 (``core.lexical``) ne sert qu'à la recherche libre et aux
suggestions ; il n'alimente jamais l'injection.

Cache : un index n'est réutilisé que pour la même clé
(tenant, mode, versions publiées et empreintes de contenu, langues source,
langue cible, domaine, contexte). Le mode fait partie de la clé : aucun index
n'est partagé entre SHADOW, ASSISTED et ACTIVE.
"""

from __future__ import annotations

import re
import threading
import time
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ..terminology import linguistic
from ..terminology.normalizer import _strip_edges, normalize_language

MAX_NGRAM_WORDS = 8
INDEX_VERSION = "rag-index-2"
_WORD = re.compile(r"\S+")


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
    key: str = ""
    match_kind: str = "term"  # term | synonym | variant
    matched_by: str = "exact"  # exact | folded (renseigné par le classement)
    surface: str = ""  # forme lue dans le document (renseignée par le classement)


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
    folded: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass
class MatchResult:
    term_hits: Counter = field(default_factory=Counter)
    notion_hits: Counter = field(default_factory=Counter)
    kinds: dict[str, str] = field(default_factory=dict)  # clé -> exact | folded
    surfaces: dict[str, str] = field(default_factory=dict)  # clé -> forme du document
    folded_ambiguous: set[str] = field(default_factory=set)  # clés exactes concurrentes


def term_view(entry: Any, scope: str, key: str = "", match_kind: str = "term") -> TermView:
    return TermView(
        id=str(entry.id),
        version_id=str(entry.version_id),
        referential_id=str(entry.referential_id),
        scope=scope,
        source_language=str(entry.source_language),
        source_term=str(entry.source_term),
        normalized_source=key or linguistic.search_key(entry.source_term),
        target_language=str(entry.target_language),
        target_term=str(entry.target_term),
        normalized_target=linguistic.search_key(entry.target_term),
        domain=entry.domain,
        country=entry.country,
        jurisdiction=entry.jurisdiction,
        register=entry.register,
        key=key,
        match_kind=match_kind,
    )


def notion_view(row: Any, scope: str) -> NotionView:
    return NotionView(
        id=str(row.id),
        version_id=str(row.version_id),
        referential_id=str(row.referential_id),
        scope=scope,
        notion=str(row.notion),
        normalized=linguistic.search_key(row.notion),
        source_language=normalize_language(row.source_language),
        target_language=normalize_language(row.target_language),
        source_country=row.source_country,
        target_country=row.target_country,
        equivalence_type=str(row.equivalence_type),
        guidance=row.guidance,
    )


def entry_forms(entry: Any) -> list[tuple[str, str]]:
    """Formes source d'une entrée : (texte, nature), terme principal en premier."""
    forms = [(str(entry.source_term), "term")]
    forms += [(str(x), "synonym") for x in entry.synonyms or [] if str(x).strip()]
    forms += [(str(x), "variant") for x in entry.regional_variants or [] if str(x).strip()]
    return forms


def build_index(scope: list[dict], entries: Iterable[Any], notions: Iterable[Any]) -> TermIndex:
    scopes = {item["version_id"]: item["scope"] for item in scope}
    terms: dict[str, list[TermView]] = {}
    folded: dict[str, set[str]] = {}
    for entry in entries:
        entry_scope = scopes.get(str(entry.version_id), "tenant")
        language = normalize_language(entry.source_language)
        seen: set[str] = set()
        for text, kind in entry_forms(entry):
            key = linguistic.search_key(text)
            if not key or key in seen or len(key.split(" ")) > MAX_NGRAM_WORDS:
                continue
            seen.add(key)
            terms.setdefault(key, []).append(term_view(entry, entry_scope, key, kind))
            for alias in {linguistic.fold_key(key), *linguistic.alias_keys(text, language)}:
                folded.setdefault(alias, set()).add(key)
    found: dict[str, list[NotionView]] = {}
    for row in notions:
        view = notion_view(row, scopes.get(str(row.version_id), "tenant"))
        if view.normalized and len(view.normalized.split(" ")) <= MAX_NGRAM_WORDS:
            found.setdefault(view.normalized, []).append(view)
    keys = [*terms, *found, *folded]
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
        folded={key: tuple(sorted(values)) for key, values in folded.items()},
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
        INDEX_VERSION,
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


def _spanned_tokens(text: str) -> list[tuple[str, int, int]]:
    """Mots de la clé exacte avec la position du mot d'origine dans le texte."""
    out = []
    for word in _WORD.finditer(text):
        for token in linguistic.search_tokens(word.group()):
            out.append((token, word.start(), word.end()))
    return out


def _surface(text: str, start: int, end: int) -> str:
    return _strip_edges(" ".join(text[start:end].split()))


def match_details(index: TermIndex, units: list[dict]) -> MatchResult:
    """Occurrences des clés (termes, notions) dans les blocs, avec nature et surface."""
    result = MatchResult()
    if index.max_words == 0:
        return result
    for unit in units:
        text = str(unit["text"])
        spanned = _spanned_tokens(text)
        words = [token for token, _, _ in spanned]
        folded = [linguistic.fold_key(token) for token in words]
        for size in range(1, min(index.max_words, len(words)) + 1):
            for start in range(len(words) - size + 1):
                key = " ".join(words[start : start + size])
                surface = _surface(text, spanned[start][1], spanned[start + size - 1][2])
                views = index.terms.get(key)
                if views and any(_language_ok(v.source_language, unit) for v in views):
                    result.term_hits[key] += 1
                    result.kinds[key] = "exact"
                    result.surfaces.setdefault(key, surface)
                elif index.folded:
                    candidates = index.folded.get(" ".join(folded[start : start + size]), ())
                    usable = [
                        c
                        for c in candidates
                        if any(_language_ok(v.source_language, unit) for v in index.terms[c])
                    ]
                    if len(usable) == 1:
                        exact = usable[0]
                        result.term_hits[exact] += 1
                        result.kinds.setdefault(exact, "folded")
                        result.surfaces.setdefault(exact, surface)
                    elif len(usable) > 1:
                        result.folded_ambiguous.update(usable)
                if key in index.notions:
                    result.notion_hits[key] += 1
    return result


def match(index: TermIndex, units: list[dict]) -> tuple[Counter, Counter]:
    """Interface LOT 1 : occurrences des clés de l'index (termes, notions)."""
    details = match_details(index, units)
    return details.term_hits, details.notion_hits


def _language_ok(entry_language: str, unit: dict) -> bool:
    # Bloc de langue inconnue : la langue du document a déjà filtré les entrées.
    return unit["language"] is None or unit["language"] == entry_language
