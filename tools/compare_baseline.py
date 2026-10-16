"""Comparer des métriques réelles ; l'absence de baseline ou de mesure bloque la promotion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

METRICS = ("ocr_score", "translation_score", "semantic_score", "layout_score", "visual_score")


def compare(current: dict, baseline: dict, tolerance: float = 0.0) -> dict:
    current_rows = {row["document_id"]: row for row in current.get("technical", [])}
    baseline_rows = {row["document_id"]: row for row in baseline.get("technical", [])}
    missing = []
    regressions = []
    if not current_rows or not baseline_rows:
        missing.append("rapport courant ou baseline vide")
    for identity in sorted(set(current_rows) | set(baseline_rows)):
        row, reference = current_rows.get(identity), baseline_rows.get(identity)
        if not row or not reference:
            missing.append(f"{identity}: document ajouté/retiré sans baseline approuvée")
            continue
        if not row.get("source_sha256") or row.get("source_sha256") != reference.get(
            "source_sha256"
        ):
            missing.append(f"{identity}: version de l'original différente ou non identifiée")
            continue
        for metric in METRICS:
            actual = (row.get("metrics") or {}).get(metric)
            previous = (reference.get("metrics") or {}).get(metric)
            if not isinstance(actual, (int, float)) or not isinstance(previous, (int, float)):
                missing.append(f"{identity}: {metric} non mesuré dans l'une des versions")
                continue
            if not 0 <= actual <= 1 or not 0 <= previous <= 1:
                missing.append(f"{identity}: {metric} hors échelle normalisée [0,1]")
                continue
            if actual + tolerance < previous:
                regressions.append(
                    {
                        "document_id": identity,
                        "metric": metric,
                        "previous": previous,
                        "current": actual,
                    }
                )
    status = "REGRESSION_DETECTED" if regressions else "NOT_EVALUATED" if missing else "PASS"
    return {
        "status": status,
        "regressions": regressions,
        "missing_evidence": missing,
        "tolerance": tolerance,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, default=Path("test-report/summary.json"))
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.tolerance < 0:
        parser.error("La tolérance ne peut pas être négative")
    try:
        current = json.loads(args.current.read_text(encoding="utf-8"))
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        result = compare(current, baseline, args.tolerance)
    except (OSError, json.JSONDecodeError):
        result = {
            "status": "NOT_EVALUATED",
            "missing_evidence": ["baseline ou rapport introuvable/invalide"],
            "regressions": [],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return (
        0 if result["status"] == "PASS" else 1 if result["status"] == "REGRESSION_DETECTED" else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
