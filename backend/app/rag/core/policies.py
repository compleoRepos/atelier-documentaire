"""Politiques par mode : canaux autorisés et ordre de réduction du contexte.

Ordre de réduction (consigne §9) quand une configuration dépasse le budget ou
évincerait un contexte existant :
1. réduire le nombre d'entrées terminologiques (moitié par moitié, jusqu'à 1) ;
2. réduire les décisions de traduction (passages secondaires), jusqu'à 0 ;
3. retirer le contexte pays ;
4. abandonner l'injection (la traduction se fait exactement comme sans RAG).
Le contexte existant (mémoire validée, entités protégées, contexte documentaire)
n'est jamais réduit : il est la référence à laquelle chaque essai est comparé.
"""

from __future__ import annotations

from dataclasses import dataclass

CHANNELS: dict[str, tuple[str, ...]] = {
    "DISABLED": (),
    "SHADOW": (),
    "ASSISTED": ("terminology",),
    "ACTIVE": ("terminology", "translation_decisions", "country_context"),
}
MAX_ATTEMPTS = 16


@dataclass(frozen=True)
class Attempt:
    terms: int
    decisions: int
    country: bool


def _halvings(count: int) -> list[int]:
    values, current = [], count
    while current >= 1:
        values.append(current)
        if current == 1:
            break
        current = (current + 1) // 2 if current > 2 else 1
    return values


def attempts(mode: str, terms: int, decisions: int, country: bool) -> list[Attempt]:
    allowed = CHANNELS.get(mode, ())
    decisions = decisions if "translation_decisions" in allowed else 0
    country = country and "country_context" in allowed
    terms = terms if "terminology" in allowed else 0
    sequence: list[Attempt] = []
    for count in _halvings(terms) or [0]:
        sequence.append(Attempt(count, decisions, country))
    floor_terms = 1 if terms else 0
    for count in _halvings(decisions)[1:] + ([0] if decisions else []):
        sequence.append(Attempt(floor_terms, count, country))
    if country:
        sequence.append(Attempt(floor_terms, 0, False))
    unique: list[Attempt] = []
    for attempt in sequence:
        empty = attempt.terms == 0 and attempt.decisions == 0 and not attempt.country
        if not empty and attempt not in unique:
            unique.append(attempt)
    return unique[:MAX_ATTEMPTS]
