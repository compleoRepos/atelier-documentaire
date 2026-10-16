#!/usr/bin/env python3
"""Fail-closed release gate; no boolean-only approval can promote production."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "release-attestation/v1"
DEFAULT_THRESHOLDS = {
    "ocr_score": 0.95,
    "translation_score": 0.90,
    "semantic_score": 0.95,
    "layout_score": 0.90,
    "visual_score": 0.90,
}


def _number(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def evaluate_attestation(
    proof: dict[str, Any] | None,
    *,
    environment: str,
    repository_root: Path | None = None,
    proof_path: Path | None = None,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Return an auditable decision. Missing evidence always yields blocked."""
    errors: list[str] = []
    threshold_map = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if not isinstance(proof, dict):
        errors.append("private attestation JSON is required")
        proof = {}
    if proof.get("schema") != SCHEMA:
        errors.append("unsupported or missing attestation schema")
    if proof.get("environment") != environment:
        errors.append("attestation environment does not match requested environment")
    if environment == "production":
        if proof.get("evidence_class") != "private-golden":
            errors.append("production requires private-golden evidence")
        if proof.get("synthetic_only") is True:
            errors.append("synthetic-only evidence cannot promote production")
        if proof_path and repository_root:
            try:
                proof_path.resolve().relative_to(repository_root.resolve())
            except ValueError:
                pass
            else:
                errors.append("production proof must be outside the Git working tree")
    approval = proof.get("approval")
    if not isinstance(approval, dict) or approval.get("decision") != "approved":
        errors.append("structured approval with decision=approved is required")
    for field in ("reviewer", "approved_at", "ticket"):
        if not isinstance(approval, dict) or not str(approval.get(field, "")).strip():
            errors.append(f"approval.{field} is required")
    quality = proof.get("quality")
    if not isinstance(quality, dict):
        errors.append("quality object is required")
        quality = {}
    for metric, minimum in threshold_map.items():
        value = _number(quality.get(metric))
        if value is None:
            errors.append(f"quality.{metric} must be a measured number")
        elif value < minimum:
            errors.append(f"quality.{metric}={value} is below threshold {minimum}")
    if quality.get("critical_entity_errors") != 0:
        errors.append("critical_entity_errors must be measured and equal to zero")
    if quality.get("hallucination_errors") != 0:
        errors.append("hallucination_errors must be measured and equal to zero")
    provenance = proof.get("provenance")
    if (
        not isinstance(provenance, dict)
        or not isinstance(provenance.get("sources"), list)
        or not provenance["sources"]
    ):
        errors.append("provenance.sources is required")
    coverage = _number(proof.get("coverage"))
    if coverage is None or not 0 <= coverage <= 1:
        errors.append("coverage must be a measured number between 0 and 1")
    if proof.get("public_fixture") is True and environment == "production":
        errors.append("public fixtures cannot promote production")
    status = "blocked" if errors else "approved"
    return {
        "schema": "release-gate/v1",
        "status": status,
        "environment": environment,
        "errors": errors,
        "quality_score": proof.get("quality_score"),
        "provenance": provenance if isinstance(provenance, dict) else None,
        "coverage": coverage,
        "reviewer": approval.get("reviewer") if isinstance(approval, dict) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("dev", "test", "production"), required=True)
    parser.add_argument(
        "--proof", type=Path, required=True, help="private JSON attestation; never commit it"
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--thresholds", type=Path)
    args = parser.parse_args()
    try:
        proof = json.loads(args.proof.read_text())
        thresholds = json.loads(args.thresholds.read_text()) if args.thresholds else None
        result = evaluate_attestation(
            proof,
            environment=args.environment,
            repository_root=args.repository_root,
            proof_path=args.proof,
            thresholds=thresholds,
        )
    except Exception as exc:
        result = {"schema": "release-gate/v1", "status": "blocked", "errors": [str(exc)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "approved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
