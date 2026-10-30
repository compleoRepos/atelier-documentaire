"""Contexte documentaire : langues, pays, juridiction, dates.

LOT 1 : seul le contexte *déclaré* par un utilisateur (API) est utilisé.
* filtrage terminologique (pays/juridiction) : contexte déclaré ou validé —
  il ne fait que restreindre les entrées retenues ;
* ``country_context`` (mode ACTIVE) : uniquement un contexte validé par un
  second utilisateur habilité.

LOT 3 (non commencé) : la détection automatique du pays, de la juridiction
et des dates implémentera ``ContextResolver`` ; elle restera une proposition
soumise à validation humaine, jamais une déclaration.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..core.ranking import DocumentFilters


class ContextResolver(Protocol):  # interface LOT 3
    def propose(self, ir: dict[str, Any]) -> dict[str, Any]:
        """Retourne des propositions (valeur, confiance, preuve) — jamais validées."""
        ...


def filters_for(row: Any, document_domain: str | None) -> DocumentFilters:
    if row is None:
        return DocumentFilters(domain=document_domain)
    return DocumentFilters(
        domain=document_domain,
        source_country=row.source_country,
        target_country=row.target_country,
        jurisdiction=row.jurisdiction,
    )


def validated_country_context(row: Any, mode: str) -> dict[str, Any] | None:
    if row is None or row.status != "validated" or mode != "ACTIVE":
        return None
    return {
        "source_country": row.source_country,
        "target_country": row.target_country,
        "jurisdiction": row.jurisdiction,
        "document_date": row.document_date,
        "legal_reference_date": row.legal_reference_date,
    }


def fingerprint(row: Any) -> str:
    if row is None:
        return "none"
    parts = [
        row.status,
        row.source_country or "",
        row.target_country or "",
        row.jurisdiction or "",
        row.document_date.isoformat() if row.document_date else "",
        row.legal_reference_date.isoformat() if row.legal_reference_date else "",
    ]
    return "|".join(parts)


__all__ = ["ContextResolver", "filters_for", "fingerprint", "validated_country_context"]
