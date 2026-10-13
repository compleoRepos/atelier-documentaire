"""Documentary confidence score, version 2 (RUN27).

``doc-confidence-1`` (``confidence_score.py``) is kept byte-identical so that
the RUN26 results stay reproducible. Version 2 answers the RUN27 audit:

1. **Evidence is a gate, not points.** In v1 the "evidence" dimension (10
   points) measured the traceability of the run, not the document: four
   sub-components that did not exist before RUN26 moved every document by
   +5.71 points, including documents whose PDF was pixel-identical. In v2 the
   evidence requirements must all be proven, otherwise the document is
   ``BLOCKED`` (its numbers are shown but not opposable); they add no point.
   The seven quality dimensions keep their v1 weights (relative weights are
   unchanged; the score is normalised by the applicable weight).
2. **Derived ceiling.** Each document exposes ``unknown_points`` U (what only a
   measurement can settle) and its structural ceiling C = 100 - U: the best
   lower bound reachable if every measured sub-component were perfect while the
   unknown ones stay unknown, with the document's own applicability. Exact
   identities: ``score_max - score_min = U = 100 - C``; the upper bound is a
   hypothesis ("every unknown would be perfect"), never a result, and it is not
   limited by C. U is split between missing human references and missing
   measurements (a tool that did not produce its measure).
3. **Entities beyond digits and layout alerts.** ``entities`` adds the
   product's critical entity alerts and a human sub-component for names,
   clauses and units (no automatic check proves them); ``layout`` adds the
   critical layout alerts (overflow, oversized masks, text over ink, missing
   text, protected regions), which v1 ignored.
4. **Partially validated human references** are intervals: a sub-component
   ``{"lower": a, "upper": b}`` (e.g. accuracy 0.98 on 40 % validated content:
   lower 0.392, upper 0.992). The unvalidated part is never scored.
5. **Corpus**: equal weight per expected document, computed on unrounded
   values; an expected document that is absent or unreadable is counted
   (lower 0, upper 100, BLOCKED), never dropped.
6. **Conservative display**: lower bounds and ceilings are rounded DOWN and
   upper bounds UP to 0.1; the threshold is always tested on the exact value
   (an exact 93.96 is displayed 93.9, never 94.0).

``VALIDATED`` requires an authorised human validation, no unknown human
sub-component, no missing measurement, no critical defect and no blocking.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

VERSION = "doc-confidence-2"
THRESHOLD = 94.0
NOT_APPLICABLE = "NOT_APPLICABLE"
HUMAN_REFERENCE_MISSING = "HUMAN_REFERENCE_MISSING"
MEASUREMENT_MISSING = "MEASUREMENT_MISSING"

DIMENSIONS: dict[str, dict[str, Any]] = {
    "coverage": {
        "weight": 20,
        "label": "Couverture textuelle écrite",
        "components": {
            "written_share": "caractères attendus effectivement écrits dans le PDF / caractères attendus",
        },
    },
    "translation": {
        "weight": 15,
        "label": "Confiance de traduction",
        "components": {
            "target_language": "caractères traduits reconnus comme du français / caractères traduits évalués",
            "semantic_accuracy": "exactitude contre une traduction de référence validée par un humain autorisé",
        },
    },
    "source_fidelity": {
        "weight": 10,
        "label": "Fidélité au document source",
        "components": {
            "pages_preserved": "1 si le PDF reconstruit a le même nombre de pages que la source, sinon 0",
            "regions_unaltered": "régions graphiques/protégées non altérées / régions détectées",
        },
    },
    "entities": {
        "weight": 15,
        "label": "Préservation des entités et données sensibles",
        "components": {
            "digit_sequences": "blocs traduits dont la suite des nombres est identique à la source / blocs traduits contenant des nombres",
            "entity_alerts": "1 - blocs traduits porteurs d'une alerte critique d'entité / blocs traduits contenant une entité détectée",
            "names_clauses_verified": "noms, clauses, unités et montants vérifiés par un humain autorisé contre la source",
        },
    },
    "layout": {
        "weight": 10,
        "label": "Qualité visuelle et mise en page",
        "components": {
            "no_text_over_ink": "1 - blocs écrits sur encre source résiduelle / blocs mesurés",
            "no_collision": "1 - mots insérés en collision / mots insérés",
            "in_page": "1 - mots insérés hors page / mots insérés",
            "not_truncated": "1 - blocs tronqués (PARTIAL) / blocs mesurés",
            "no_critical_layout_alert": "1 - min(1, occurrences d'alertes critiques de rendu / blocs mesurés)",
        },
    },
    "ocr": {
        "weight": 10,
        "label": "Qualité OCR",
        "components": {
            "engine_confidence": "caractères attendus de confiance OCR moteur >= 0,80 / caractères attendus (indicateur, pas une exactitude)",
            "character_accuracy": "exactitude caractère contre une transcription humaine de référence",
        },
    },
    "hallucination": {
        "weight": 10,
        "label": "Absence d'hallucination",
        "components": {
            "no_unreliable_source_translated": "1 - caractères traduits depuis un OCR de confiance < 0,60 / caractères traduits",
            "no_length_anomaly": "1 - caractères traduits à rapport de longueur anormal / caractères traduits",
            "proven_by_reference": "absence d'ajout ou d'omission prouvée contre une référence humaine",
        },
    },
}

HUMAN_COMPONENTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("translation", "semantic_accuracy"),
        ("entities", "names_clauses_verified"),
        ("ocr", "character_accuracy"),
        ("hallucination", "proven_by_reference"),
    }
)

EVIDENCE_REQUIREMENTS: dict[str, str] = {
    "original_unchanged": "empreinte SHA-256 de l'original identique avant/après",
    "block_provenance": "origine déclarée pour chaque bloc (appel modèle, mémoire, non envoyé)",
    "request_reconciliation": "traces de requêtes = requêtes envoyées, identifiants de corrélation présents",
    "generation_mode": "mode de génération déclaré (nouvelle génération, mémoire, rejeu)",
    "execution_journal": "journal horodaté avec empreinte de code et HEAD Git",
    "candidate_produced": "PDF reconstruit présent et lisible",
    "budget_respected": "aucune réservation ni consommation au-delà de 32 768 tokens",
}


def floor1(value: float) -> float:
    """Display a LOWER bound: rounded down to 0.1 (a displayed 94.0 is never an exact 93.96)."""
    return math.floor(value * 10 + 1e-9) / 10


def ceil1(value: float) -> float:
    """Display an UPPER bound: rounded up to 0.1."""
    return math.ceil(value * 10 - 1e-9) / 10


TOTAL_WEIGHT = sum(d["weight"] for d in DIMENSIONS.values())
assert TOTAL_WEIGHT == 90  # the v1 quality weights, evidence removed from the points
assert all(c in DIMENSIONS[d]["components"] for d, c in HUMAN_COMPONENTS)


def _component(dim: str, key: str, value: Any) -> dict[str, Any]:
    """Normalise one sub-component to {kind, lower, upper, reason}."""
    if value == NOT_APPLICABLE:
        return {"kind": "not_applicable"}
    human = (dim, key) in HUMAN_COMPONENTS
    if value is None:
        return {
            "kind": "unknown",
            "lower": 0.0,
            "upper": 1.0,
            "reason": HUMAN_REFERENCE_MISSING if human else MEASUREMENT_MISSING,
            "human": human,
        }
    if isinstance(value, Mapping):
        if set(value) - {"lower", "upper", "validated_share"}:
            raise KeyError(f"{dim}.{key}: unexpected interval keys {sorted(value)}")
        low, up = float(value["lower"]), float(value["upper"])
        if not 0.0 <= low <= up <= 1.0:
            raise ValueError(f"{dim}.{key}: invalid interval [{low}, {up}]")
        kind = "measured" if low == up else "partial"
        return {"kind": kind, "lower": low, "upper": up, "human": human}
    if isinstance(value, bool):
        raise TypeError(f"{dim}.{key}: a ratio is expected, not a boolean")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{dim}.{key}: sub-component outside [0, 1]: {number}")
    return {"kind": "measured", "lower": number, "upper": number, "human": human}


def score_dimension(name: str, components: Mapping[str, Any]) -> dict[str, Any]:
    spec = DIMENSIONS[name]
    unexpected = set(components) - set(spec["components"])
    if unexpected:
        raise KeyError(f"{name}: unexpected sub-components {sorted(unexpected)}")
    parts = {key: _component(name, key, components.get(key)) for key in spec["components"]}
    used = {k: p for k, p in parts.items() if p["kind"] != "not_applicable"}
    base = {"label": spec["label"], "weight": spec["weight"], "components": parts}
    if not used:
        return {**base, "applicable": False, "min": None, "max": None}
    n = len(used)
    lower = sum(p["lower"] for p in used.values()) / n
    upper = sum(p["upper"] for p in used.values()) / n
    unknown_human = sum(p["upper"] - p["lower"] for p in used.values() if p["human"]) / n
    unknown_missing = sum(p["upper"] - p["lower"] for p in used.values() if not p["human"]) / n
    return {
        **base,
        "applicable": True,
        "min": lower,
        "max": upper,
        "unknown_human_share": unknown_human,
        "unknown_measurement_share": unknown_missing,
    }


def score_document(
    components: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Any],
    critical_defects: Iterable[Mapping[str, Any]] = (),
    *,
    human_validated: bool = False,
    blocking: Iterable[str] = (),
) -> dict[str, Any]:
    """Documentary confidence of one document (v2).

    ``components``: quality dimension -> sub-component -> ratio | None |
    NOT_APPLICABLE | {"lower", "upper"[, "validated_share"]}.
    ``evidence``: requirement -> True (proven) | False/None (not proven).
    """
    unexpected = set(components) - set(DIMENSIONS)
    if unexpected:
        raise KeyError(f"unexpected dimensions {sorted(unexpected)}")
    unexpected = set(evidence) - set(EVIDENCE_REQUIREMENTS)
    if unexpected:
        raise KeyError(f"unexpected evidence {sorted(unexpected)}")
    dims = {name: score_dimension(name, components.get(name, {})) for name in DIMENSIONS}
    applicable = {k: v for k, v in dims.items() if v["applicable"]}
    if not applicable:
        raise ValueError("no applicable quality dimension")
    weight = sum(v["weight"] for v in applicable.values())
    lower = 100.0 * sum(v["weight"] * v["min"] for v in applicable.values()) / weight
    upper = 100.0 * sum(v["weight"] * v["max"] for v in applicable.values()) / weight
    u_human = (
        100.0 * sum(v["weight"] * v["unknown_human_share"] for v in applicable.values()) / weight
    )
    u_missing = (
        100.0
        * sum(v["weight"] * v["unknown_measurement_share"] for v in applicable.values())
        / weight
    )
    for v in applicable.values():
        v["effective_weight"] = 100.0 * v["weight"] / weight
    unknowns = [
        {"dimension": d, "component": k, "reason": p["reason"]}
        for d, v in dims.items()
        if v["applicable"]
        for k, p in v["components"].items()
        if p["kind"] == "unknown"
    ]
    partial = [
        {"dimension": d, "component": k, "lower": p["lower"], "upper": p["upper"]}
        for d, v in dims.items()
        if v["applicable"]
        for k, p in v["components"].items()
        if p["kind"] == "partial"
    ]
    missing_evidence = sorted(k for k in EVIDENCE_REQUIREMENTS if evidence.get(k) is not True)
    blocking = sorted(set(blocking) | {f"EVIDENCE_MISSING:{k}" for k in missing_evidence})
    defects = [dict(d) for d in critical_defects]
    measurement_gaps = sorted(
        f"{u['dimension']}.{u['component']}" for u in unknowns if u["reason"] == MEASUREMENT_MISSING
    )
    if blocking:
        status = "BLOCKED"
    elif defects or not human_validated or u_human > 0 or measurement_gaps:
        status = "REVIEW_REQUIRED"
    else:
        status = "VALIDATED"
    return {
        "version": VERSION,
        "score": floor1(lower),
        "score_min": floor1(lower),
        "score_max": ceil1(upper),
        "ceiling": floor1(100.0 - (upper - lower)),
        "unknown_points": round(upper - lower, 3),
        "unknown_points_human": round(u_human, 3),
        "unknown_points_measurement": round(u_missing, 3),
        "exact": {"lower": lower, "upper": upper, "ceiling": 100.0 - (upper - lower)},
        "applicable_weight": weight,
        "threshold": THRESHOLD,
        "threshold_met": lower >= THRESHOLD and not defects and not blocking,
        "critical_defects": defects,
        "blocking": blocking,
        "evidence": {k: evidence.get(k) is True for k in EVIDENCE_REQUIREMENTS},
        "unknowns": unknowns,
        "partial_components": partial,
        "measurement_gaps": measurement_gaps,
        "human_validated": bool(human_validated),
        "status": status,
        "dimensions": dims,
    }


def missing_document() -> dict[str, Any]:
    """An expected document that is absent or unreadable: counted, never dropped."""
    return {
        "version": VERSION,
        "score": 0.0,
        "score_min": 0.0,
        "score_max": 100.0,
        "ceiling": 0.0,
        "unknown_points": 100.0,
        "exact": {"lower": 0.0, "upper": 100.0, "ceiling": 0.0},
        "threshold_met": False,
        "critical_defects": [],
        "blocking": ["DOCUMENT_MISSING_OR_UNREADABLE"],
        "human_validated": False,
        "status": "BLOCKED",
    }


def score_corpus(
    documents: Mapping[str, Mapping[str, Any] | None], expected: Iterable[str]
) -> dict[str, Any]:
    """Equal weight per EXPECTED document, on unrounded values."""
    expected = sorted(set(expected))
    if not expected:
        raise ValueError("no expected document")
    unexpected = sorted(set(documents) - set(expected))
    if unexpected:
        raise KeyError(f"documents not expected: {unexpected}")
    docs = {k: (documents.get(k) or missing_document()) for k in expected}
    n = len(docs)
    lower = sum(d["exact"]["lower"] for d in docs.values()) / n
    upper = sum(d["exact"]["upper"] for d in docs.values()) / n
    ceiling = sum(d["exact"]["ceiling"] for d in docs.values()) / n
    flagged = sorted(k for k, d in docs.items() if d["critical_defects"] or d["blocking"])
    return {
        "version": VERSION,
        "documents": n,
        "missing_documents": sorted(k for k in expected if not documents.get(k)),
        "score": floor1(lower),
        "score_min": floor1(lower),
        "score_max": ceil1(upper),
        "ceiling": floor1(ceiling),
        "unknown_points": round(upper - lower, 3),
        "exact": {"lower": lower, "upper": upper, "ceiling": ceiling},
        "threshold": THRESHOLD,
        "threshold_met": lower >= THRESHOLD and not flagged,
        "documents_with_critical_defects_or_blocking": flagged,
        "statuses": {k: d["status"] for k, d in docs.items()},
    }


def ceiling_without_human_references(components: Mapping[str, Mapping[str, Any]]) -> float:
    """Best lower bound of THIS document if every automatic measure were perfect
    and every human sub-component stayed unknown (derived, never hard-coded)."""
    best: dict[str, dict[str, Any]] = {}
    for dim, spec in DIMENSIONS.items():
        given = components.get(dim, {})
        best[dim] = {}
        for key in spec["components"]:
            value = given.get(key)
            if value == NOT_APPLICABLE:
                best[dim][key] = NOT_APPLICABLE
            elif (dim, key) in HUMAN_COMPONENTS:
                best[dim][key] = None
            else:
                best[dim][key] = 1.0
    evidence = {k: True for k in EVIDENCE_REQUIREMENTS}
    return score_document(best, evidence)["exact"]["lower"]
