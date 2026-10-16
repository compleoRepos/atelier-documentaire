"""Gate de recette : une preuve absente ou non mesurée ne vaut jamais PASS."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

THRESHOLDS = {
    "ocr_score": 0.95,
    "translation_score": 0.90,
    "semantic_score": 0.95,
    "layout_score": 0.90,
    "visual_score": 0.90,
}


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def reference_valid(reference: dict[str, Any], sha256: str) -> bool:
    return bool(
        reference.get("approved") is True
        and reference.get("reviewer_id")
        and reference.get("tenant_id")
        and reference.get("validated_at")
        and reference.get("source_sha256") == sha256
        and isinstance(reference.get("translations"), dict)
        and reference.get("translations")
        and isinstance(reference.get("version"), int)
    )


def latest_reference(directory: Path, sha256: str, tenant: str | None) -> dict[str, Any] | None:
    roots = [directory / sha256]
    if tenant:
        roots.insert(0, directory / tenant / sha256)
    candidates = []
    for root in roots:
        for path in root.glob("v*.json"):
            reference = read_json(path)
            if reference and reference_valid(reference, sha256):
                if tenant and reference.get("tenant_id") != tenant:
                    continue
                candidates.append(reference)
    return max(candidates, key=lambda item: item["version"], default=None)


def collect_failures(
    catalog: dict[str, Any] | None,
    report: dict[str, Any] | None,
    reference_dir: Path,
    tenant: str | None,
    thresholds: dict[str, float],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    validated: list[str] = []
    documents = (catalog or {}).get("documents", [])
    if not documents:
        failures.append("inventaire Golden vide ou absent")
    if not report or report.get("technical_status") != "PASS":
        failures.append("rapport technique complet absent ou en échec")
    rows = {row.get("document_id"): row for row in (report or {}).get("technical", [])}
    for document in documents:
        identity = document.get("document_id", "unknown")
        sha256 = document.get("sha256", "")
        reference = latest_reference(reference_dir, sha256, tenant) if sha256 else None
        if reference is None:
            failures.append(
                f"{identity}: référence humaine approuvée, versionnée et liée au SHA256 absente"
            )
        else:
            validated.append(identity)
        row = rows.get(identity)
        if not row or row.get("technical") != "PASS":
            failures.append(f"{identity}: traitement technique réussi non démontré")
            continue
        if row.get("source_sha256") != sha256:
            failures.append(f"{identity}: empreinte du rapport différente de l'inventaire")
        if row.get("acceptance") != "PASS":
            failures.append(f"{identity}: acceptation de qualité non démontrée")
        metrics = row.get("metrics") or {}
        for name, threshold in thresholds.items():
            value = metrics.get(name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                failures.append(f"{identity}: {name} non mesuré")
            elif not 0 <= value <= 1 or value < threshold:
                failures.append(f"{identity}: {name} sous seuil ou hors échelle normalisée [0,1]")
        for field in ("critical_entity_errors", "hallucination_errors", "context_overflow"):
            value = row.get(field)
            if value not in (0, []):
                failures.append(f"{identity}: {field} absent ou non nul")
        if row.get("untranslated_blocks"):
            failures.append(f"{identity}: segments non traduits")
    return failures, validated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--input-report", type=Path)
    parser.add_argument("--tenant", default=os.getenv("GOLDEN_TENANT_ID"))
    parser.add_argument("--thresholds", type=Path)
    parser.add_argument(
        "--strict", action="store_true", help="Compatibilité : le contrôle est toujours strict."
    )
    parser.add_argument(
        "--report", type=Path, help="Écrit le résultat de la gate, pas le rapport Golden d'entrée."
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    references = args.reference_dir or root / "dataset/expected"
    report_path = args.input_report or root / "test-report/summary.json"
    thresholds = dict(THRESHOLDS)
    if args.thresholds:
        configured = read_json(args.thresholds)
        if not configured or any(key not in THRESHOLDS for key in configured):
            parser.error("configuration de seuils invalide")
        for key, value in configured.items():
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                parser.error(f"seuil invalide : {key}")
            thresholds[key] = float(value)
    failures, validated = collect_failures(
        read_json(root / "dataset/metadata/catalog.json"),
        read_json(report_path),
        references,
        args.tenant,
        thresholds,
    )
    if os.getenv("TRANSLATOR_ENGINE", "offline") != "private":
        failures.append(
            "moteur privé non sélectionné ; le mode hors ligne ne prouve pas une traduction IA"
        )
    if not os.getenv("TRANSLATOR_PRIVATE_AI_BASE_URL") or not os.getenv(
        "TRANSLATOR_PRIVATE_AI_ALLOWED_HOSTS"
    ):
        failures.append("endpoint IA privé et allowlist non configurés")
    tokenizer = os.getenv("TRANSLATOR_TOKENIZER_PATH", "")
    if not tokenizer or not Path(tokenizer).is_dir():
        failures.append("tokenizer local absent ; aucun téléchargement implicite autorisé")
    result = {
        "strict": True,
        "status": "FAIL" if failures else "PASS",
        "validated_documents": validated,
        "thresholds": thresholds,
        "failures": failures,
        "note": "Un PASS de pytest ne remplace ni les métriques de qualité ni la validation bancaire.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
