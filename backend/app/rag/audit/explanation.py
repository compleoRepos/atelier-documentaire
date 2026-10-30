"""Explication des décisions RAG d'un document.

Construite uniquement à partir du journal (identifiants, compteurs, motifs) et
des entrées de référentiel citées (données de référentiel, pas de document).
Aucun texte du document n'est stocké, donc aucun n'est restitué.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..storage import repository

REASON_LABELS = {
    "GLOSSARY_PRIORITY": "Écartée : le glossaire client couvre ce terme et reste prioritaire.",
    "TENANT_PRIORITY": "Écartée : le référentiel du tenant prime sur la bibliothèque commune.",
    "AMBIGUOUS_REQUIRES_CONTEXT": "Écartée : plusieurs traductions validées, choix humain requis.",
    "DOMAIN_MISMATCH": "Écartée : domaine de l'entrée différent de celui du document.",
    "DOMAIN_UNKNOWN": "Écartée : domaine du document inconnu, entrée spécifique à un domaine.",
    "COUNTRY_MISMATCH": "Écartée : pays de l'entrée différent du contexte déclaré.",
    "COUNTRY_UNKNOWN": "Écartée : entrée propre à un pays, pays du document non déclaré.",
    "JURISDICTION_MISMATCH": "Écartée : juridiction différente du contexte déclaré.",
    "JURISDICTION_UNKNOWN": "Écartée : entrée propre à une juridiction non déclarée.",
    "DUPLICATE": "Écartée : doublon d'une entrée retenue.",
    "ENTRY_LIMIT": "Écartée : nombre maximal d'entrées par document atteint.",
    "TOO_LONG_FOR_CONTEXT": "Écartée : texte trop long pour être injecté.",
    "REJECTED_UNSAFE": "Écartée : texte ressemblant à une instruction (sécurité).",
    "EMPTY": "Écartée : texte vide après nettoyage.",
}
DECISION_LABELS = {
    "INJECTED": "Contexte terminologique transmis au moteur privé.",
    "NO_RESULT": "Aucune entrée validée applicable.",
    "ABANDONED": "Injection abandonnée : budget dépassé ou contexte existant menacé.",
    "PROBE_UNAVAILABLE": "Injection impossible : vérification préalable indisponible.",
    "EXISTING_CHANNEL_NOT_MERGEABLE": "Injection refusée : canal existant non fusionnable.",
    "SHADOW_ONLY": "Mode observation : rien n'a été transmis au moteur.",
}


def _entry_view(entry: Any) -> dict[str, Any]:
    return {
        "id": entry.id,
        "referential_id": entry.referential_id,
        "version_id": entry.version_id,
        "scope": "common" if entry.tenant_id is None else "tenant",
        "source_language": entry.source_language,
        "source_term": entry.source_term,
        "target_language": entry.target_language,
        "target_term": entry.target_term,
        "domain": entry.domain,
        "country": entry.country,
        "status": entry.status,
    }


def explain_document(db: Session, tenant_id: str, document_id: str, limit: int = 20) -> dict:
    repository.tenant_document(db, tenant_id, document_id)
    logs = repository.search_logs(db, tenant_id, document_id, limit=limit)
    ids: set[str] = set()
    for log in logs:
        outcome = log.outcome or {}
        ids.update(str(x) for x in log.result_ids or [])
        ids.update(str(x) for x in outcome.get("candidate_term_ids") or [])
    entries = repository.entries_by_ids(db, tenant_id, ids)
    runs = []
    for log in logs:
        outcome = dict(log.outcome or {})
        decision = outcome.get("decision")
        reasons = outcome.get("exclusion_reasons") or {}
        runs.append(
            {
                "id": log.id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "mode": log.mode,
                "origin": log.origin,
                "query_sha256": log.query_sha256,
                "decision": decision,
                "decision_label": DECISION_LABELS.get(str(decision), decision),
                "effective_mode": outcome.get("effective_mode"),
                "mode_reasons": outcome.get("reasons") or [],
                "result_count": log.result_count,
                "latency_ms": log.latency_ms,
                "budget_tokens": outcome.get("budget_tokens"),
                "rag_tokens_max": outcome.get("rag_tokens_max"),
                "requests": outcome.get("requests"),
                "attempts": outcome.get("attempts") or [],
                "referential_versions": log.referential_versions or [],
                "injected_or_observed": [
                    _entry_view(entries[x]) for x in (log.result_ids or []) if x in entries
                ],
                "exclusions": [
                    {"reason": key, "count": count, "label": REASON_LABELS.get(key, key)}
                    for key, count in sorted(reasons.items())
                ],
                "blocks_examined": outcome.get("blocks_examined"),
                "blocks_memory_priority": outcome.get("blocks_memory_priority"),
            }
        )
    return {
        "document_id": document_id,
        "human_review_required": True,
        "runs": runs,
    }
