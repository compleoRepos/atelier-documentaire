"""Independent verification of the documentary confidence score (RUN27).

This tool does NOT import the product score module: it re-implements the
documented formula with exact rational arithmetic (``fractions.Fraction``) and
its own declaration of the weights and sub-components, then compares the result
with what a scorecard JSON stored. It derives, per document and for the corpus:

* the lower bound (score of record): unknown sub-component = 0;
* the upper bound: unknown sub-component = 1 (hypothetical, never a result);
* the unknown weight share U (points that only a measurement can settle);
* the structural ceiling C = 100 - U: the best lower bound reachable if every
  MEASURED sub-component were perfect while the unknown ones stay unknown, with
  the same applicability (and therefore the same renormalisation).

Exact identities checked for every document (Fraction arithmetic, no tolerance):
    upper - lower = U = 100 - C,   lower <= C,   upper <= 100.
Consequence: the upper bound is NOT limited by the ceiling; upper = lower + U.

Usage (output must be outside the repository; it holds counts and ratios only):
  python tools/recette/score_verify.py --scorecard SC.json --out OUT.json [--runs run25 run26]
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERSION = "score-verify-1"
NA = "NOT_APPLICABLE"

# Independent declaration (RUN26-SCORE-METHODOLOGY.md, doc-confidence-1).
SPEC_V1: dict[str, tuple[int, tuple[str, ...]]] = {
    "coverage": (20, ("written_share",)),
    "translation": (15, ("target_language", "semantic_accuracy")),
    "source_fidelity": (10, ("pages_preserved", "regions_unaltered")),
    "entities": (15, ("digit_sequences",)),
    "layout": (10, ("no_text_over_ink", "no_collision", "in_page", "not_truncated")),
    "ocr": (10, ("engine_confidence", "character_accuracy")),
    "hallucination": (
        10,
        ("no_unreliable_source_translated", "no_length_anomaly", "proven_by_reference"),
    ),
    "evidence": (
        10,
        (
            "original_unchanged",
            "block_provenance",
            "request_reconciliation",
            "generation_mode",
            "execution_journal",
            "candidate_produced",
            "budget_respected",
        ),
    ),
}
assert sum(w for w, _ in SPEC_V1.values()) == 100

# Independent declaration of doc-confidence-2 (evidence is a gate, not points).
SPEC_V2: dict[str, tuple[int, tuple[str, ...]]] = {
    "coverage": (20, ("written_share",)),
    "translation": (15, ("target_language", "semantic_accuracy")),
    "source_fidelity": (10, ("pages_preserved", "regions_unaltered")),
    "entities": (15, ("digit_sequences", "entity_alerts", "names_clauses_verified")),
    "layout": (
        10,
        (
            "no_text_over_ink",
            "no_collision",
            "in_page",
            "not_truncated",
            "no_critical_layout_alert",
        ),
    ),
    "ocr": (10, ("engine_confidence", "character_accuracy")),
    "hallucination": (
        10,
        ("no_unreliable_source_translated", "no_length_anomaly", "proven_by_reference"),
    ),
}
HUMAN_V2 = {
    ("translation", "semantic_accuracy"),
    ("entities", "names_clauses_verified"),
    ("ocr", "character_accuracy"),
    ("hallucination", "proven_by_reference"),
}
EVIDENCE_V2 = (
    "original_unchanged",
    "block_provenance",
    "request_reconciliation",
    "generation_mode",
    "execution_journal",
    "candidate_produced",
    "budget_respected",
)
assert sum(w for w, _ in SPEC_V2.values()) == 90


def _frac(value) -> Fraction:
    return (
        Fraction(value).limit_denominator(10**12) if isinstance(value, float) else Fraction(value)
    )


def verify_document(dimensions: dict, spec=SPEC_V1) -> dict:
    """Exact bounds of one document from its stored sub-components."""
    if set(dimensions) != set(spec):
        raise ValueError(f"dimensions {sorted(dimensions)} != spec {sorted(spec)}")
    rows = {}
    total_w = Fraction(0)
    s_low = s_up = s_unk = Fraction(0)
    for name, (weight, comps) in spec.items():
        stored = dimensions[name]
        if int(stored["weight"]) != weight:
            raise ValueError(f"{name}: stored weight {stored['weight']} != declared {weight}")
        values = stored["components"]
        if set(values) != set(comps):
            raise ValueError(f"{name}: components {sorted(values)} != {sorted(comps)}")
        measured = {k: _frac(v) for k, v in values.items() if v is not None and v != NA}
        unknown = sorted(k for k, v in values.items() if v is None)
        na = sorted(k for k, v in values.items() if v == NA)
        n = len(measured) + len(unknown)
        if n == 0:
            rows[name] = {
                "weight": weight,
                "applicable": False,
                "measured": {},
                "unknown": [],
                "not_applicable": na,
            }
            continue
        low = sum(measured.values(), Fraction(0)) / n
        up = (sum(measured.values(), Fraction(0)) + len(unknown)) / n
        unk = Fraction(len(unknown), n)
        total_w += weight
        s_low += weight * low
        s_up += weight * up
        s_unk += weight * unk
        rows[name] = {
            "weight": weight,
            "applicable": True,
            "measured": {k: float(v) for k, v in sorted(measured.items())},
            "unknown": unknown,
            "not_applicable": na,
            "n_used": n,
            "dim_lower": float(low),
            "dim_upper": float(up),
            "dim_unknown_share": float(unk),
            "_low": low,
            "_up": up,
            "_unk": unk,
        }
    if total_w == 0:
        raise ValueError("no applicable dimension")
    lower = 100 * s_low / total_w
    upper = 100 * s_up / total_w
    unknown_pts = 100 * s_unk / total_w
    ceiling = 100 - unknown_pts
    # exact identities (Fractions): any failure is a formula error, not rounding
    assert upper - lower == unknown_pts, "upper - lower != U"
    assert lower <= ceiling, "lower > ceiling"
    assert upper <= 100, "upper > 100"
    for r in rows.values():
        if r["applicable"]:
            r["effective_weight"] = float(Fraction(100 * r["weight"]) / total_w)
            r["contribution_lower"] = float(100 * r["weight"] * r.pop("_low") / total_w)
            r["contribution_upper"] = float(100 * r["weight"] * r.pop("_up") / total_w)
            r["lost_to_unknown"] = float(100 * r["weight"] * r.pop("_unk") / total_w)
    return {
        "applicable_weight": int(total_w),
        "lower": lower,
        "upper": upper,
        "unknown_points": unknown_pts,
        "ceiling": ceiling,
        "dimensions": rows,
    }


def verify_run(run: dict, spec=SPEC_V1) -> dict:
    docs = {}
    max_dev = 0.0
    for doc, stored in sorted(run["documents"].items()):
        v = verify_document(stored["dimensions"], spec)
        dev_low = abs(float(v["lower"]) - stored["score_min"])
        dev_up = abs(float(v["upper"]) - stored["score_max"])
        max_dev = max(max_dev, dev_low, dev_up)
        docs[doc] = {
            **{k: (float(x) if isinstance(x, Fraction) else x) for k, x in v.items()},
            "stored_lower": stored["score_min"],
            "stored_upper": stored["score_max"],
            "deviation_lower": round(dev_low, 6),
            "deviation_upper": round(dev_up, 6),
            "critical_defects": sum(
                int(d.get("count") or 0) for d in stored.get("critical_defects") or []
            ),
            "status": stored.get("status"),
        }
    n = len(docs)
    exact_lower = sum(Fraction(d["lower"]) for d in docs.values()) / n
    exact_upper = sum(Fraction(d["upper"]) for d in docs.values()) / n
    ceiling = sum(Fraction(d["ceiling"]) for d in docs.values()) / n
    stored_c = run["corpus"]
    v1_style = (
        sum(Fraction(str(d["stored_lower"])) for d in docs.values()) / n
    )  # mean of rounded scores
    return {
        "documents": docs,
        "corpus": {
            "documents": n,
            "lower_exact_mean": float(exact_lower),
            "upper_exact_mean": float(exact_upper),
            "ceiling_mean": float(ceiling),
            "unknown_points_mean": float(exact_upper - exact_lower),
            "lower_mean_of_rounded_scores": float(v1_style),
            "stored_lower": stored_c["score_min"],
            "stored_upper": stored_c["score_max"],
            "rounding_effect": round(float(v1_style - exact_lower), 6),
            "max_document_deviation": round(max_dev, 6),
            "upper_minus_ceiling": float(exact_upper - ceiling),
        },
    }


def verify_document_v2(stored: dict) -> dict:
    """Exact bounds of a doc-confidence-2 document from its stored parts."""
    dims = stored["dimensions"]
    if set(dims) != set(SPEC_V2):
        raise ValueError(f"dimensions {sorted(dims)} != spec v2")
    total_w = Fraction(0)
    s_low = s_up = s_hum = s_mis = Fraction(0)
    rows = {}
    for name, (weight, comps) in SPEC_V2.items():
        d = dims[name]
        if int(d["weight"]) != weight or set(d["components"]) != set(comps):
            raise ValueError(f"{name}: weight/components differ from the v2 declaration")
        used = {k: p for k, p in d["components"].items() if p["kind"] != "not_applicable"}
        if not used:
            rows[name] = {"weight": weight, "applicable": False}
            continue
        n = len(used)
        lo = sum((_frac(p["lower"]) for p in used.values()), Fraction(0)) / n
        up = sum((_frac(p["upper"]) for p in used.values()), Fraction(0)) / n
        hum = (
            sum(
                (
                    _frac(p["upper"]) - _frac(p["lower"])
                    for k, p in used.items()
                    if (name, k) in HUMAN_V2
                ),
                Fraction(0),
            )
            / n
        )
        mis = (
            sum(
                (
                    _frac(p["upper"]) - _frac(p["lower"])
                    for k, p in used.items()
                    if (name, k) not in HUMAN_V2
                ),
                Fraction(0),
            )
            / n
        )
        for k, p in used.items():
            if p["kind"] == "unknown" and (p["lower"], p["upper"]) != (0.0, 1.0):
                raise ValueError(f"{name}.{k}: an unknown must be [0, 1]")
        total_w += weight
        s_low += weight * lo
        s_up += weight * up
        s_hum += weight * hum
        s_mis += weight * mis
        rows[name] = {
            "weight": weight,
            "applicable": True,
            "unknown": sorted(k for k, p in used.items() if p["kind"] == "unknown"),
            "partial": sorted(k for k, p in used.items() if p["kind"] == "partial"),
            "not_applicable": sorted(
                k for k, p in d["components"].items() if p["kind"] == "not_applicable"
            ),
            "measured": {
                k: float(p["lower"]) for k, p in sorted(used.items()) if p["kind"] == "measured"
            },
            "dim_lower": float(lo),
            "dim_upper": float(up),
            "effective_weight": None,
            "contribution_lower": None,
            "_lo": lo,
            "_up": up,
        }
    lower = 100 * s_low / total_w
    upper = 100 * s_up / total_w
    u = 100 * (s_hum + s_mis) / total_w
    ceiling = 100 - u
    assert upper - lower == u and lower <= ceiling and upper <= 100
    for r in rows.values():
        if r["applicable"]:
            r["effective_weight"] = float(Fraction(100 * r["weight"]) / total_w)
            r["contribution_lower"] = float(100 * r["weight"] * r.pop("_lo") / total_w)
            r["contribution_upper"] = float(100 * r["weight"] * r.pop("_up") / total_w)
    evidence_ok = all(stored["evidence"].get(k) is True for k in EVIDENCE_V2)
    expected_status_blocked = (not evidence_ok) or bool(stored.get("blocking"))
    if expected_status_blocked != (stored["status"] == "BLOCKED"):
        raise ValueError("evidence gate and status disagree")
    if stored["status"] == "VALIDATED" and (
        s_hum > 0 or s_mis > 0 or stored.get("critical_defects")
    ):
        raise ValueError("VALIDATED with unknowns or critical defects")
    return {
        "applicable_weight": int(total_w),
        "lower": float(lower),
        "upper": float(upper),
        "unknown_points": float(u),
        "unknown_points_human": float(100 * s_hum / total_w),
        "unknown_points_measurement": float(100 * s_mis / total_w),
        "ceiling": float(ceiling),
        "deviation_lower": abs(float(lower) - stored["exact"]["lower"]),
        "deviation_upper": abs(float(upper) - stored["exact"]["upper"]),
        "deviation_ceiling": abs(float(ceiling) - stored["exact"]["ceiling"]),
        "evidence_complete": evidence_ok,
        "status": stored["status"],
        "critical_defects": sum(
            int(d.get("count") or 0) for d in stored.get("critical_defects") or []
        ),
        "dimensions": rows,
    }


def verify_run_v2(run: dict) -> dict:
    docs = {
        d: verify_document_v2(x) for d, x in sorted(run["documents"].items()) if x.get("dimensions")
    }
    missing = sorted(d for d, x in run["documents"].items() if not x.get("dimensions"))
    n = len(run["documents"])
    lower = (sum(Fraction(x["lower"]) for x in docs.values())) / n  # missing documents count 0
    upper = (sum(Fraction(x["upper"]) for x in docs.values()) + 100 * len(missing)) / n
    ceiling = sum(Fraction(x["ceiling"]) for x in docs.values()) / n
    c = run["corpus"]
    max_dev = max(
        [
            max(x["deviation_lower"], x["deviation_upper"], x["deviation_ceiling"])
            for x in docs.values()
        ]
        or [0]
    )
    return {
        "documents": docs,
        "missing_documents": missing,
        "corpus": {
            "documents": n,
            "lower_exact_mean": float(lower),
            "upper_exact_mean": float(upper),
            "ceiling_mean": float(ceiling),
            "deviation_lower": abs(float(lower) - c["exact"]["lower"]),
            "deviation_upper": abs(float(upper) - c["exact"]["upper"]),
            "deviation_ceiling": abs(float(ceiling) - c["exact"]["ceiling"]),
            "max_document_deviation": max_dev,
            "stored_lower": c["score_min"],
            "stored_upper": c["score_max"],
            "stored_ceiling": c["ceiling"],
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scorecard", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--runs", nargs="*")
    args = ap.parse_args()
    out = args.out.resolve()
    if REPO == out or REPO in out.parents:
        raise SystemExit("--out doit être hors du dépôt")
    sc = json.loads(args.scorecard.read_text())
    if sc.get("score_version") not in ("doc-confidence-1", "doc-confidence-2"):
        raise SystemExit(f"version de score non prise en charge : {sc.get('score_version')}")
    v2 = sc["score_version"] == "doc-confidence-2"
    labels = args.runs or sorted(sc["runs"])
    result = {"version": VERSION, "score_version": sc["score_version"], "runs": {}}
    for label in labels:
        result["runs"][label] = (
            verify_run_v2(sc["runs"][label]) if v2 else verify_run(sc["runs"][label])
        )
        c = result["runs"][label]["corpus"]
        print(
            f"{label}: basse {c['lower_exact_mean']:.4f} (stockée {c['stored_lower']}), haute {c['upper_exact_mean']:.4f} "
            f"(stockée {c['stored_upper']}), plafond moyen {c['ceiling_mean']:.4f}, écart max doc {c['max_document_deviation']:.2e}"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
