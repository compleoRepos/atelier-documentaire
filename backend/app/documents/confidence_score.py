"""Documentary confidence score (RUN26).

The engine's historical scores are kept for compatibility (``fidelity_report``
GLOBAL/STRUCTURE/TABLE are always ``None``; the quality engine's OCR,
translation and semantic scores are ``None`` without a reference). They cannot
support a confidence statement, so this module adds an explicit, reproducible
documentary confidence score with a breakdown per dimension.

Rules (frozen before the RUN26 corpus run, see RUN26-SCORE-METHODOLOGY.md):

* eight dimensions with fixed weights (sum 100);
* each dimension is the mean of its sub-components, each a ratio in [0, 1]
  computed from produced artefacts, or ``None`` when it is NOT MEASURED
  (no human reference, no ground truth...). An unknown sub-component is never
  scored: it counts 0 in the lower bound and 1 in the upper bound;
* ``NOT_APPLICABLE`` sub-components (e.g. nothing to check) are left out of the
  mean of their dimension; a dimension whose sub-components are all
  not applicable is left out and its weight is redistributed - this is the
  only renormalisation, and it never applies to an unknown value;
* the score of record is the LOWER bound; the upper bound shows what remains
  unproven. The 94 threshold is met only if the lower bound is >= 94 AND no
  critical defect is known: a critical defect (amount, name, date, identifier,
  evidence integrity...) blocks whatever the average;
* without a validation by an authorised human the status can never be
  ``VALIDATED``: ``REVIEW_REQUIRED`` at best.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

VERSION = "doc-confidence-1"
THRESHOLD = 94.0
NOT_APPLICABLE = "NOT_APPLICABLE"

# weight, label, ordered sub-components (name -> definition shown in reports)
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
            "target_language": "caractères traduits dont la cible est reconnue comme du français / caractères traduits évalués",
            "semantic_accuracy": "exactitude contre une référence validée par un humain autorisé",
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
        },
    },
    "ocr": {
        "weight": 10,
        "label": "Qualité OCR",
        "components": {
            "engine_confidence": "caractères attendus dont la confiance OCR du moteur >= 0,80 / caractères attendus (indicateur, non une exactitude)",
            "character_accuracy": "exactitude caractère contre une transcription humaine",
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
    "evidence": {
        "weight": 10,
        "label": "Complétude et fiabilité des preuves",
        "components": {
            "original_unchanged": "empreinte SHA-256 de l'original identique avant/après",
            "block_provenance": "origine déclarée pour chaque bloc (appel modèle, mémoire, non envoyé)",
            "request_reconciliation": "traces de requêtes = requêtes envoyées, identifiants de corrélation présents",
            "generation_mode": "mode de génération déclaré (nouvelle génération, mémoire, rejeu)",
            "execution_journal": "journal horodaté avec empreinte de code et HEAD Git",
            "candidate_produced": "PDF reconstruit présent et lisible",
            "budget_respected": "aucune réservation ni consommation au-delà de 32 768 tokens",
        },
    },
}

assert sum(d["weight"] for d in DIMENSIONS.values()) == 100


def _ratio(value: Any) -> float | None | str:
    if value is None or value == NOT_APPLICABLE:
        return value
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"sub-component outside [0, 1]: {number}")
    return number


def score_dimension(name: str, components: Mapping[str, Any]) -> dict[str, Any]:
    """Bounds of one dimension from its sub-components (None = unknown)."""
    spec = DIMENSIONS[name]
    unknown_names = set(components) - set(spec["components"])
    if unknown_names:
        raise KeyError(f"{name}: unexpected sub-components {sorted(unknown_names)}")
    values = {key: _ratio(components.get(key)) for key in spec["components"]}
    used = {k: v for k, v in values.items() if v != NOT_APPLICABLE}
    if not used:
        return {
            "label": spec["label"],
            "weight": spec["weight"],
            "applicable": False,
            "components": values,
            "min": None,
            "max": None,
            "measured_share": None,
        }
    lower = sum(0.0 if v is None else v for v in used.values()) / len(used)
    upper = sum(1.0 if v is None else v for v in used.values()) / len(used)
    measured = sum(v is not None for v in used.values()) / len(used)
    return {
        "label": spec["label"],
        "weight": spec["weight"],
        "applicable": True,
        "components": values,
        "min": round(lower, 6),
        "max": round(upper, 6),
        "measured_share": round(measured, 6),
    }


def score_document(
    components: Mapping[str, Mapping[str, Any]],
    critical_defects: Iterable[Mapping[str, Any]] = (),
    *,
    human_validated: bool = False,
    blocking: Iterable[str] = (),
) -> dict[str, Any]:
    """Documentary confidence of one document.

    ``components``: dimension -> sub-component -> ratio | None | NOT_APPLICABLE.
    ``critical_defects``: known blocking defects (code, count...).
    ``blocking``: evidence failures that make the result unusable (BLOCKED).
    """
    dimensions = {name: score_dimension(name, components.get(name, {})) for name in DIMENSIONS}
    applicable = {k: v for k, v in dimensions.items() if v["applicable"]}
    total_weight = sum(v["weight"] for v in applicable.values())
    lower = 100.0 * sum(v["weight"] * v["min"] for v in applicable.values()) / total_weight
    upper = 100.0 * sum(v["weight"] * v["max"] for v in applicable.values()) / total_weight
    measured_weight = sum(v["weight"] * v["measured_share"] for v in applicable.values())
    defects = [dict(d) for d in critical_defects]
    blocking = sorted(set(blocking))
    if blocking:
        status = "BLOCKED"
    elif defects or not human_validated:
        status = "REVIEW_REQUIRED"
    else:
        status = "VALIDATED"
    return {
        "version": VERSION,
        "score": round(lower, 1),
        "score_min": round(lower, 1),
        "score_max": round(upper, 1),
        "measured_weight_share": round(measured_weight / total_weight, 4),
        "threshold": THRESHOLD,
        "threshold_met": lower >= THRESHOLD and not defects and not blocking,
        "critical_defects": defects,
        "blocking": blocking,
        "human_validated": bool(human_validated),
        "status": status,
        "dimensions": dimensions,
    }


def score_corpus(documents: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Equal weight per document: a difficult small document is not diluted."""
    if not documents:
        raise ValueError("no document")
    lower = sum(d["score_min"] for d in documents.values()) / len(documents)
    upper = sum(d["score_max"] for d in documents.values()) / len(documents)
    with_defects = sorted(k for k, d in documents.items() if d["critical_defects"] or d["blocking"])
    return {
        "version": VERSION,
        "documents": len(documents),
        "score": round(lower, 1),
        "score_min": round(lower, 1),
        "score_max": round(upper, 1),
        "threshold": THRESHOLD,
        "threshold_met": lower >= THRESHOLD and not with_defects,
        "documents_with_critical_defects": with_defects,
        "statuses": {k: d["status"] for k, d in sorted(documents.items())},
    }


def structural_ceiling(unknown: Mapping[str, Iterable[str]]) -> float:
    """Highest reachable lower bound when the given sub-components stay unknown."""
    lost = 0.0
    for name, keys in unknown.items():
        spec = DIMENSIONS[name]
        lost += spec["weight"] * len(list(keys)) / len(spec["components"])
    return round(100.0 - lost, 1)
