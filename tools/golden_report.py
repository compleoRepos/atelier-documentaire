#!/usr/bin/env python3
"""Rapport reproductible local : ingestion, OCR, structure, candidat et preuves QA."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--engine", choices=["offline", "private"], default="offline")
    parser.add_argument("--tenant-id", default=os.getenv("TRANSLATOR_GOLDEN_TENANT_ID"))
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Conservé pour compatibilité : ne traduit pas, mais analyse les scans.",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = (args.out or root / "test-report").resolve()
    output.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((root / "dataset/metadata/catalog.json").read_text(encoding="utf-8"))
    documents = catalog.get("documents", [])
    sys.path.insert(0, str(root / "backend"))
    from app.core.settings import Settings
    from app.documents.pipeline import analyze_document, translate_document
    from golden_references import load_reference

    settings = Settings()
    options = {
        "engine": args.engine,
        "private_ai_base_url": settings.private_ai_base_url,
        "private_ai_allowed_hosts": settings.private_hosts,
        "private_ai_model": settings.private_ai_model,
        "private_ai_api_key": settings.private_ai_api_key,
        "tokenizer_path": settings.tokenizer_path,
        **settings.translation_budgets,
    }
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(documents, 1):
        identity = item["document_id"]
        print(f"[{index}/{len(documents)}] {identity} — OCR et contrôles locaux", flush=True)
        source = root / "dataset/input" / item["filename"]
        destination = output / "documents" / identity
        destination.mkdir(parents=True, exist_ok=True)
        row: dict[str, Any] = {
            "document_id": identity,
            "source_sha256": item.get("sha256"),
            "tenant_id": args.tenant_id,
            "technical": "FAIL",
            "acceptance": "NOT_EVALUATED",
            "reference_status": "awaiting_human_reference",
            "pages": 0,
            "blocks": 0,
            "issues": [],
            "metrics": {
                "ocr_score": None,
                "translation_score": None,
                "semantic_score": None,
                "layout_score": None,
                "visual_score": None,
            },
        }
        if not source.is_file():
            row["issues"] = [{"code": "GOLDEN_INPUT_MISSING", "severity": "critical"}]
            rows.append(row)
            write_json(destination / "result.json", row)
            continue
        try:
            ir = analyze_document(str(source), str(destination), {})
            row.update(
                {
                    "pages": len(ir.get("pages", [])),
                    "blocks": sum(len(page.get("blocks", [])) for page in ir.get("pages", [])),
                    "detected_language": ir.get("language"),
                    "detected_languages": ir.get("languages", []),
                    "initial_visual_languages": item.get("source_language_codes", []),
                    "document_type": ir.get("document_type"),
                    "domain": ir.get("domain"),
                    "warnings": ir.get("warnings", []),
                }
            )
            reference = load_reference(
                root / "dataset/expected", str(item.get("sha256", "")), args.tenant_id
            )
            document_options = {**options, "reference": reference}
            if reference:
                row["reference_status"] = "human_reference_loaded"
            translated = (
                {}
                if args.no_ocr
                else asyncio.run(translate_document(ir, str(destination), document_options))
            )
            quality = translated.get("quality", {})
            row["issues"] = translated.get("issues", [])
            row["versions"] = translated.get("versions", {})
            row["untranslated_blocks"] = translated.get("untranslated_blocks", [])
            for metric in row["metrics"]:
                row["metrics"][metric] = quality.get(metric)
            row["critical_entity_errors"] = quality.get("critical_entity_errors", [])
            row["qa_status"] = quality.get("status", "REVIEW_REQUIRED")
            row["technical"] = "PASS" if row["pages"] == item.get("pages") else "FAIL"
            if row["technical"] == "FAIL":
                row["issues"].append({"code": "PAGE_COUNT_MISMATCH", "severity": "critical"})
            if not args.no_ocr and not any(destination.glob("candidate.*")):
                row["technical"] = "FAIL"
                row["issues"].append({"code": "CANDIDATE_MISSING", "severity": "critical"})
            write_json(destination / "metrics.json", quality)
            for kind in ("original", "translated", "diff"):
                preview = destination / "previews" / f"{kind}-001.png"
                if preview.is_file():
                    shutil.copyfile(preview, destination / f"{kind}.png")
        except Exception as exc:  # One failed item must not hide successful items.
            row["issues"] = [
                {
                    "code": "GOLDEN_PROCESSING_FAILED",
                    "severity": "critical",
                    "exception_type": type(exc).__name__,
                }
            ]
        write_json(destination / "result.json", row)
        rows.append(row)
    passed = sum(row["technical"] == "PASS" for row in rows)
    failed = sum(row["technical"] != "PASS" for row in rows)
    summary = {
        "schema_version": "1.0",
        "engine": args.engine,
        "tenant_id": args.tenant_id,
        "documents": len(rows),
        "tests_passed": passed,
        "tests_failed": failed,
        "total_pages": sum(row["pages"] for row in rows),
        "technical_status": "PASS" if rows and not failed else "FAIL",
        "reference_status": "awaiting_human_reference",
        "acceptance": {
            "status": "NOT_EVALUATED",
            "reason": "La réussite technique n'établit pas la fidélité linguistique ; aucune référence humaine validée n'est automatiquement présumée.",
        },
        "metrics": {
            "ocr_score": None,
            "translation_score": None,
            "semantic_score": None,
            "layout_score": None,
            "visual_score": None,
        },
        "technical": rows,
        "privacy": "Données locales : ce rapport et ses images ne doivent pas être publiés sur un runner public.",
    }
    write_json(output / "summary.json", summary)
    body = [
        "<!doctype html><html lang='fr'><meta charset='utf-8'><title>Rapport Golden</title>",
        "<style>body{font:15px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#172d3e}table{border-collapse:collapse;width:100%}td,th{padding:12px;border:1px solid #d8e0e4;text-align:left}.notice{background:#fff4dc;padding:18px}</style>",
        "<h1>Golden Dataset — preuves techniques</h1>",
        f"<p>{len(rows)} documents · {summary['total_pages']} pages · {passed} traitements techniques réussis · {failed} échecs</p>",
        "<p class='notice'><b>Acceptation linguistique : NON ÉVALUÉE.</b> Les textes inconnus ne sont pas simulés comme traduits. La confiance OCR n'est pas un taux d'exactitude. Les cachets et signatures exigent une revue humaine.</p>",
        "<table><thead><tr><th>Document</th><th>Technique</th><th>Pages</th><th>Blocs</th><th>Revue</th><th>Preuves</th></tr></thead><tbody>",
    ]
    for row in rows:
        identity = html.escape(row["document_id"], quote=True)
        body.append(
            f"<tr><td>{identity}</td><td>{row['technical']}</td><td>{row['pages']}</td><td>{row['blocks']}</td><td>Requise</td><td><a href='documents/{identity}/result.json'>Résultat</a> · <a href='documents/{identity}/metrics.json'>Métriques</a></td></tr>"
        )
    body.extend(
        [
            "</tbody></table><p>CER/WER, fidélité de traduction, sémantique et similarité de mise en page validée : non mesurés sans vérité terrain.</p></html>"
        ]
    )
    (output / "summary.html").write_text("\n".join(body) + "\n", encoding="utf-8")
    print(f"Rapport complet : {output / 'summary.json'}", flush=True)
    return 0 if summary["technical_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
