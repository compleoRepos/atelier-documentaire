"""Recherche lexicale BM25 sur PostgreSQL (LOT 2), sans extension ni base vectorielle.

Rôle strictement limité : **suggestions** pour l'API de recherche, l'import et la
détection de doublons. Un résultat BM25 n'est jamais injecté dans la traduction :
seules les correspondances exactes, synonymes, variantes ou formes pliées non
ambiguës du moteur (``retrieval``/``ranking``) peuvent l'être, et uniquement
depuis des versions publiées par un humain.

Index : une ligne ``rag_term_postings`` par (entrée validée, jeton normalisé) ;
les formes indexées sont le terme, ses synonymes et ses variantes régionales,
normalisés par ``linguistic.bm25_tokens``. L'index d'une version est construit
à sa publication ou à sa restauration, dans la même transaction (une erreur
annule la publication), et reconstruit si la version du normaliseur change.

Requête : la sélection des candidats et les statistiques (N, longueur moyenne,
fréquences documentaires) sont calculées par SQL indexé, filtré par versions
publiées visibles du tenant et par paire de langues ; l'arithmétique BM25
(k1 = 1,2 ; b = 0,75 ; idf ``ln(1 + (N - df + 0,5) / (df + 0,5))``) est
appliquée ensuite aux seuls candidats, de façon déterministe (tri score
décroissant puis identifiant).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, distinct, func, insert, select
from sqlalchemy.orm import Session

from ...core.models import now_utc, uid
from ..models import RagLexicalIndex, RagReferentialVersion, RagTermEntry, RagTermPosting
from ..storage.repository import _visible, published_scope, version_entries
from ..terminology import domains
from ..terminology.linguistic import VERSION as NORMALIZER_VERSION
from ..terminology.linguistic import alias_keys, bm25_tokens, search_key

K1 = 1.2
B = 0.75
AUTHORITY = "suggestion_non_injectable"
MAX_QUERY_TOKENS = 32
MAX_RESULTS = 50
_TOKEN_LIMIT = 200


def entry_forms(entry: Any) -> list[str]:
    """Terme, synonymes et variantes, dédoublonnés par clé de recherche."""
    forms: list[str] = []
    seen: set[str] = set()
    for form in [entry.source_term, *(entry.synonyms or []), *(entry.regional_variants or [])]:
        key = search_key(form)
        if key and key not in seen:
            seen.add(key)
            forms.append(str(form))
    return forms


def entry_token_counts(entry: Any) -> Counter:
    """Jetons de toutes les formes ; l'alias allemand (ü -> ue...) est indexé en plus."""
    counts: Counter = Counter()
    for form in entry_forms(entry):
        tokens = [token[:_TOKEN_LIMIT] for token in bm25_tokens(form) if token]
        counts.update(tokens)
        for alias in alias_keys(form, entry.source_language):
            counts.update(t[:_TOKEN_LIMIT] for t in alias.split(" ") if t and t not in tokens)
    return counts


def _fresh(state: RagLexicalIndex | None, version: RagReferentialVersion) -> bool:
    return (
        state is not None
        and state.normalizer_version == NORMALIZER_VERSION
        and (state.content_sha256 or None) == (version.content_sha256 or None)
    )


def _pair(source_language: str, target_language: str) -> str:
    return f"{source_language}>{target_language}"


def index_version(
    db: Session,
    version: RagReferentialVersion,
    entries: Iterable[RagTermEntry] | None = None,
    *,
    force: bool = False,
) -> RagLexicalIndex:
    """Construit (ou réutilise) l'index lexical d'une version ; idempotent."""
    state = db.get(RagLexicalIndex, version.id)
    if not force and _fresh(state, version):
        return state
    rows = [e for e in (entries if entries is not None else version_entries(db, version))]
    rows = sorted((e for e in rows if e.status == "validated"), key=lambda e: e.id)
    db.execute(delete(RagTermPosting).where(RagTermPosting.version_id == version.id))
    payload = []
    stats: dict[str, list[int]] = {}
    for entry in rows:
        counts = entry_token_counts(entry)
        length = sum(counts.values())
        pair = stats.setdefault(_pair(entry.source_language, entry.target_language), [0, 0])
        pair[0] += 1
        pair[1] += length
        for token, tf in sorted(counts.items()):
            payload.append(
                {
                    "id": uid(),
                    "version_id": version.id,
                    "entry_id": entry.id,
                    "tenant_id": entry.tenant_id,
                    "source_language": entry.source_language,
                    "target_language": entry.target_language,
                    "token": token,
                    "tf": tf,
                    "doc_len": length,
                }
            )
    if payload:
        db.execute(insert(RagTermPosting), payload)
    if state is None:
        state = RagLexicalIndex(version_id=version.id)
        db.add(state)
    state.tenant_id = version.tenant_id
    state.normalizer_version = NORMALIZER_VERSION
    state.content_sha256 = version.content_sha256
    state.entry_count = len(rows)
    state.posting_count = len(payload)
    state.pair_stats = {key: stats[key] for key in sorted(stats)}
    state.built_at = now_utc()
    db.flush()
    return state


def rebuild_tenant_indexes(db: Session, tenant_id: str, *, force: bool = False) -> dict[str, int]:
    """Reconstruit l'index des versions publiées appartenant au tenant (jamais la commune)."""
    built = reused = 0
    for item in published_scope(db, tenant_id):
        if item["tenant_id"] != tenant_id:
            continue
        version = db.get(RagReferentialVersion, item["version_id"])
        before = db.get(RagLexicalIndex, version.id)
        stale = force or not _fresh(before, version)
        index_version(db, version, force=force)
        built += int(stale)
        reused += int(not stale)
    return {"built": built, "reused": reused}


def _bm25(tf: int, df: int, doc_len: int, n_docs: int, avgdl: float) -> float:
    idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
    norm = tf + K1 * (1.0 - B + B * doc_len / (avgdl or 1.0))
    return idf * tf * (K1 + 1.0) / norm


def query_tokens(text: object) -> list[str]:
    out: list[str] = []
    for token in bm25_tokens(text):
        token = token[:_TOKEN_LIMIT]
        if token and token not in out:
            out.append(token)
    return out[:MAX_QUERY_TOKENS]


def search(
    db: Session,
    tenant_id: str,
    text: object,
    source_language: str,
    target_language: str,
    *,
    limit: int = 10,
    domain: str | None = None,
) -> dict[str, Any]:
    """Suggestions BM25 dans les versions publiées visibles du tenant."""
    limit = max(1, min(int(limit), MAX_RESULTS))
    tokens = query_tokens(text)
    scope = published_scope(db, tenant_id)
    owners = {item["version_id"]: item for item in scope}
    states = {
        row.version_id: row
        for row in db.scalars(
            select(RagLexicalIndex).where(RagLexicalIndex.version_id.in_(sorted(owners) or [""]))
        )
    }
    versions = sorted(
        vid
        for vid, item in owners.items()
        if states.get(vid) is not None
        and states[vid].normalizer_version == NORMALIZER_VERSION
        and (states[vid].content_sha256 or None) == (item["content_sha256"] or None)
    )
    meta = {
        "algorithm": {"name": "BM25", "k1": K1, "b": B, "normalizer": NORMALIZER_VERSION},
        "authority": AUTHORITY,
        "query_tokens": len(tokens),
        "indexed_versions": len(versions),
        "unindexed_versions": len(owners) - len(versions),
    }
    if not tokens or not versions:
        return {**meta, "documents": 0, "candidates": 0, "results": []}
    base = (
        RagTermPosting.version_id.in_(versions),
        RagTermPosting.source_language == source_language,
        RagTermPosting.target_language == target_language,
        _visible(RagTermPosting.tenant_id, tenant_id),
    )
    pair = _pair(source_language, target_language)
    if all(isinstance(states[v].pair_stats, dict) for v in versions):
        # Statistiques précalculées à l'indexation : coût constant quel que soit le volume.
        sums = [(states[v].pair_stats or {}).get(pair, [0, 0]) for v in versions]
        n_docs = sum(int(n) for n, _ in sums)
        avgdl = sum(int(total) for _, total in sums) / n_docs if n_docs else 0.0
    else:  # index construit sans statistiques : calcul SQL (plus coûteux)
        per_entry = (
            select(RagTermPosting.entry_id, func.max(RagTermPosting.doc_len).label("dl"))
            .where(*base)
            .group_by(RagTermPosting.entry_id)
            .subquery()
        )
        n_docs, avgdl = db.execute(select(func.count(), func.avg(per_entry.c.dl))).one()
        n_docs = int(n_docs or 0)
        avgdl = float(avgdl or 0.0)
    df = dict(
        db.execute(
            select(RagTermPosting.token, func.count(distinct(RagTermPosting.entry_id)))
            .where(*base, RagTermPosting.token.in_(tokens))
            .group_by(RagTermPosting.token)
        ).all()
    )
    rows = db.execute(
        select(
            RagTermPosting.entry_id,
            RagTermPosting.version_id,
            RagTermPosting.tenant_id,
            RagTermPosting.token,
            RagTermPosting.tf,
            RagTermPosting.doc_len,
        )
        .where(*base, RagTermPosting.token.in_(tokens))
        .order_by(RagTermPosting.entry_id, RagTermPosting.token)
    ).all()
    scores: dict[str, float] = defaultdict(float)
    matched: dict[str, list[str]] = defaultdict(list)
    for entry_id, version_id, owner, token, tf, doc_len in rows:
        if owner != owners[version_id]["tenant_id"]:
            continue  # même règle que published_entries : entrée et version du même tenant
        scores[entry_id] += _bm25(int(tf), int(df.get(token, 1)), int(doc_len), n_docs, avgdl)
        matched[entry_id].append(token)
    ranked = sorted(scores, key=lambda eid: (-round(scores[eid], 9), eid))
    entries = {
        row.id: row
        for row in db.scalars(
            select(RagTermEntry).where(
                RagTermEntry.id.in_(ranked[: MAX_RESULTS * 4] or [""]),
                RagTermEntry.status == "validated",
                _visible(RagTermEntry.tenant_id, tenant_id),
            )
        )
    }
    wanted = domains.canonical_domain(domain) if domain else None
    results = []
    for entry_id in ranked:
        entry = entries.get(entry_id)
        if entry is None:
            continue
        compatible = domains.compatible(entry.domain, wanted) if wanted else None
        if compatible is False:
            continue
        item = owners[entry.version_id]
        results.append(
            {
                "entry_id": entry.id,
                "version_id": entry.version_id,
                "referential_id": entry.referential_id,
                "scope": item["scope"],
                "source_language": entry.source_language,
                "source_term": entry.source_term,
                "target_language": entry.target_language,
                "target_term": entry.target_term,
                "domain": entry.domain,
                "country": entry.country,
                "score": round(scores[entry_id], 6),
                "matched_tokens": len(matched[entry_id]),
                "coverage": round(len(matched[entry_id]) / len(tokens), 4),
                "authority": AUTHORITY,
                "injectable": False,
            }
        )
        if len(results) >= limit:
            break
    return {**meta, "documents": n_docs, "candidates": len(scores), "results": results}
