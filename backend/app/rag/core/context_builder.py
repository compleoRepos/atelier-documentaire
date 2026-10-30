"""Construction des canaux de contexte RAG au format du constructeur existant.

Canaux utilisés (et seulement eux) :
* ``document_memory.terminology``          : ``[{"source", "target"}]``
* ``document_memory.translation_decisions``: ``[{"source", "decision"}]`` (ACTIVE)
* ``country_context``                       : contexte pays validé (ACTIVE)

Jamais ``glossary`` (le glossaire client reste seul autoritaire), jamais les
clés ``domain``/``document_type``/``language``/``style`` de ``document_memory``
(elles changeraient le filtrage par domaine du constructeur).

Les textes de référentiel sont des données non fiables : ils sont nettoyés,
bornés en longueur, et toute entrée qui ressemble à une instruction est
écartée (REJECTED_UNSAFE). Ils ne sont transmis que comme valeurs JSON.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from .ranking import Exclusion
from .retrieval import NotionView, TermView

MAX_TERM_CHARS = 120
MAX_DECISION_CHARS = 300
_UNSAFE = re.compile(
    r"(<\||\|>|```|\{\{|\}\}|<\s*/?\s*(script|system|im_start|im_end)\b|"
    r"\b(system|assistant|developer)\s*:|"
    r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instruction|instructions|rules|previous|above)\b|"
    r"\b(ignore[rz]?|oublie[rz]?)\b.{0,40}\b(instructions?|consignes?|r[eè]gles?)\b|"
    r"\b(ignora|olvida)\b.{0,40}\b(instrucciones|reglas)\b|"
    r"\bignorier\w*\b.{0,40}\b(anweisung\w*|regeln)\b|"
    r"تجاهل.{0,40}(التعليمات|القواعد))",
    re.IGNORECASE | re.DOTALL,
)


def clean_text(value: object, limit: int) -> tuple[str | None, str | None]:
    """Texte nettoyé, ou (None, motif) s'il doit être écarté."""
    text = "".join(
        " " if unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"} else ch
        for ch in str(value or "")
    )
    text = " ".join(text.split())
    if not text:
        return None, "EMPTY"
    if len(text) > limit:
        return None, "TOO_LONG_FOR_CONTEXT"
    if _UNSAFE.search(text):
        return None, "REJECTED_UNSAFE"
    return text, None


def terminology_items(terms: Sequence[TermView]) -> tuple[list[dict], list[Exclusion]]:
    items, rejected = [], []
    for view in terms:
        source, why_source = clean_text(view.source_term, MAX_TERM_CHARS)
        target, why_target = clean_text(view.target_term, MAX_TERM_CHARS)
        if source is None or target is None:
            rejected.append(Exclusion(view.id, why_source or why_target or "EMPTY"))
            continue
        items.append({"source": source, "target": target})
    return items, rejected


def decision_items(notions: Sequence[NotionView]) -> tuple[list[dict], list[Exclusion]]:
    items, rejected = [], []
    for view in notions:
        source, why_source = clean_text(view.notion, MAX_TERM_CHARS)
        guidance = view.guidance or ""
        decision, why_decision = clean_text(
            f"[{view.equivalence_type}] {guidance}".strip(), MAX_DECISION_CHARS
        )
        if source is None or decision is None:
            rejected.append(Exclusion(view.id, why_source or why_decision or "EMPTY"))
            continue
        items.append({"source": source, "decision": decision})
    return items, rejected


def country_items(context: Mapping[str, Any] | None) -> dict | None:
    if not context:
        return None
    result = {}
    for name in ("source_country", "target_country", "jurisdiction"):
        value = context.get(name)
        if value:
            text, _ = clean_text(value, 80)
            if text:
                result[name] = text
    for name in ("document_date", "legal_reference_date"):
        value = context.get(name)
        if isinstance(value, date):
            result[name] = value.isoformat()
    return result or None


def channels(
    terminology: Sequence[dict],
    decisions: Sequence[dict] = (),
    country_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Options supplémentaires ; aucune clé n'est créée si elle serait vide."""
    added: dict[str, Any] = {}
    memory: dict[str, Any] = {}
    if terminology:
        memory["terminology"] = [dict(item) for item in terminology]
    if decisions:
        memory["translation_decisions"] = [dict(item) for item in decisions]
    if memory:
        added["document_memory"] = memory
    if country_context:
        added["country_context"] = dict(country_context)
    return added
