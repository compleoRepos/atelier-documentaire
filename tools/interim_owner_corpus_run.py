"""Translate owner-authorised ORIGINAL documents with the temporary Interim provider.

Data leaves the private boundary: run only with an explicit owner authorisation
file (outside Git) listing the exact source SHA-256 values. Outputs (translated
documents, previews, JSON) are written to a private directory outside Git.
Console output contains only identifiers, counters and issue codes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import app.ai.translation.service as service_module  # noqa: E402
from app.ai.translation.interim_guard import OWNER_SCOPE, load_owner_authorization  # noqa: E402
from app.documents.pipeline import analyze_document, translate_document  # noqa: E402

MAX_CONTEXT = 32768
MAX_COMPLETION = 8000
_REAL_TRANSLATE_BLOCKS = service_module.translate_blocks
_SERVICE_CODES = {
    "CONTEXT_OVERFLOW", "INVALID_MODEL_OUTPUT", "OUTPUT_BUDGET_INVALID", "OUTPUT_LENGTH",
    "PROTECTED_ENTITY_COLLISION", "UNKNOWN_FINISH_REASON", "UNMAPPED_TABLE_CONTENT",
}


def _capturing_translate(work: Path):
    """Call the real service and keep its raw result for later re-rendering."""

    async def wrapper(ir, options):
        result = _REAL_TRANSLATE_BLOCKS(ir, options)
        if asyncio.iscoroutine(result):
            result = await result
        (work / "interim-service-result.json").write_text(json.dumps(result, ensure_ascii=False))
        return result

    return wrapper


def _saved_service_result(work: Path) -> dict:
    """Return the Interim service result already obtained (no new request)."""
    raw = work / "interim-service-result.json"
    if raw.is_file():
        return json.loads(raw.read_text())
    saved = json.loads((work / "translation.json").read_text())
    issues = [
        i for i in saved.get("issues") or []
        if str(i.get("code", "")).startswith("INTERIM_")
        or i.get("code") in _SERVICE_CODES
        or (i.get("code") == "PROTECTED_ENTITY_CHANGED" and "block_id" in i and "page" not in i)
    ]
    return {
        "translations": saved["translations"],
        "issues": issues,
        "untranslated_blocks": saved.get("untranslated_blocks") or [],
        "translation_telemetry": saved.get("translation_telemetry") or {},
        "versions": {k: v for k, v in (saved.get("versions") or {}).items() if k in {"model", "provider", "context_budgets", "prompt"}},
    }


def _reusing_translate(work: Path):
    result = _saved_service_result(work)
    if (result.get("translation_telemetry") or {}).get("provider") != "interim":
        raise RuntimeError("REUSE_SOURCE_NOT_INTERIM")

    async def wrapper(ir, options):
        return json.loads(json.dumps(result))

    return wrapper


def _catalog(input_dir: Path) -> list[dict]:
    catalog = json.loads((ROOT / "dataset" / "metadata" / "catalog.json").read_text())
    entries = catalog.get("documents", catalog) if isinstance(catalog, dict) else catalog
    if isinstance(entries, dict):
        entries = list(entries.values())
    for entry in entries:
        entry["source"] = input_dir / entry["filename"]
    return sorted(entries, key=lambda e: e["document_id"])


def _budget_check(telemetry: dict) -> dict:
    chunks = telemetry.get("chunks") or []
    reserved = [c.get("reserved_total_tokens") for c in chunks if c.get("reserved_total_tokens") is not None]
    totals = [((c.get("usage") or {}).get("total_tokens")) for c in chunks]
    completions = [((c.get("usage") or {}).get("completion_tokens")) for c in chunks]
    totals = [t for t in totals if isinstance(t, int)]
    completions = [t for t in completions if isinstance(t, int)]
    return {
        "chunks": len(chunks),
        "max_reserved_total_tokens": max(reserved) if reserved else None,
        "max_usage_total_tokens": max(totals) if totals else None,
        "max_completion_tokens": max(completions) if completions else None,
        "violations": sum(1 for t in reserved if t > MAX_CONTEXT)
        + sum(1 for t in totals if t > MAX_CONTEXT)
        + sum(1 for t in completions if t > MAX_COMPLETION),
    }


async def run_one(
    entry: dict, out_dir: Path, authorization: Path, timeout: float, reuse: bool = False, reuse_analysis: bool = False
) -> dict:
    doc_id = entry["document_id"]
    source = entry["source"]
    work = out_dir / doc_id
    work.mkdir(parents=True, exist_ok=True)
    sha_before = hashlib.sha256(source.read_bytes()).hexdigest()
    started = time.perf_counter()
    if reuse or reuse_analysis:
        ir = json.loads((work / "analysis.json").read_text())
        if ir.get("versions", {}).get("source_sha256") != sha_before:
            raise RuntimeError("REUSE_ANALYSIS_SHA_MISMATCH")
        # Re-derive PDF-object protections with the current detector; keep the
        # preprocessing/user candidates. Block flags are purely derived from
        # region intersection, so they are recomputed by protect_ir.
        from app.documents.protected_visuals import protect_ir

        pdf_provenances = {"pdf_embedded_image_original", "pdf_vector_original", "pdf_widget_original"}
        ir["protected_visual_regions"] = [
            r for r in ir.get("protected_visual_regions") or [] if r.get("provenance") not in pdf_provenances
        ]
        for page in ir.get("pages", []):
            for block in page.get("blocks", []):
                block.pop("protected", None)
        protect_ir(ir)
        for stale in [*(work / "previews").glob("translated-*.png"), *(work / "previews").glob("diff-*.png")]:
            stale.unlink()
        service_module.translate_blocks = _reusing_translate(work) if reuse else _capturing_translate(work)
    else:
        ir = analyze_document(str(source), str(work))
        service_module.translate_blocks = _capturing_translate(work)
    analysis_s = time.perf_counter() - started
    options = {
        "engine": "interim",
        "environment": "lab",
        "interim_data_scope": OWNER_SCOPE,
        "interim_owner_authorization_file": str(authorization),
        "source_sha256": sha_before,
        "target_language": "fr",
        "interim_api_base": os.environ["OPENAI_API_BASE"],
        "interim_api_key": os.environ["OPENAI_API_KEY"],
        "timeout": timeout,
    }
    started = time.perf_counter()
    try:
        result = await translate_document(ir, str(work), options)
    finally:
        service_module.translate_blocks = _REAL_TRANSLATE_BLOCKS
    translation_s = time.perf_counter() - started
    sha_after = hashlib.sha256(source.read_bytes()).hexdigest()
    telemetry = result.get("translation_telemetry") or {}
    blocks = [b for p in ir.get("pages", []) for b in p.get("blocks", [])]
    changed = sum(1 for b in blocks if result["translations"].get(str(b["id"]), b.get("text")) != b.get("text"))
    quality = result.get("quality") or {}
    candidate = work / ("candidate.docx" if ir.get("format") == "docx" else "candidate.pdf")
    summary = {
        "document_id": doc_id,
        "pages": len(ir.get("pages", [])),
        "blocks": len(blocks),
        "blocks_changed": changed,
        "untranslated_blocks": len(result.get("untranslated_blocks") or []),
        "requests_sent": telemetry.get("requests_sent"),
        "served_model": telemetry.get("served_version"),
        "data_scope": telemetry.get("data_scope"),
        "owner_authorization_id": (telemetry.get("owner_authorization") or {}).get("authorization_id"),
        "usage": telemetry.get("usage"),
        "budget": _budget_check(telemetry),
        "issue_codes": dict(Counter(i.get("code") for i in result.get("issues") or [])),
        "critical_issue_codes": sorted(
            {i.get("code") for i in result.get("issues") or [] if i.get("severity") == "critical"}
        ),
        "quality_status": quality.get("status"),
        "scores": {k: quality.get(k) for k in ("ocr_score", "translation_score", "semantic_score", "layout_score", "visual_score")},
        "candidate_file": candidate.name if candidate.is_file() else None,
        "previews": {
            "original": len(list((work / "previews").glob("original-*.png"))),
            "translated": len(list((work / "previews").glob("translated-*.png"))),
            "diff": len(list((work / "previews").glob("diff-*.png"))),
        },
        "original_sha256_unchanged": sha_before == sha_after,
        "analysis_s": round(analysis_s, 1),
        "translation_s": round(translation_s, 1),
        "translations_reused_without_new_request": reuse,
        "human_reference_validated": False,
    }
    (work / "interim-run-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="required: sends authorised originals to Interim")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "dataset" / "input")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--reuse-translations", action="store_true",
                        help="re-render/evaluate from the Interim translations already obtained; no new request")
    parser.add_argument("--reuse-analysis", action="store_true",
                        help="reuse the saved OCR/IR analysis (same SHA) but send new Interim requests")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live requis : les originaux autorisés seront envoyés à Interim")
    if ROOT == args.out_dir.resolve() or ROOT in args.out_dir.resolve().parents:
        parser.error("--out-dir doit être hors du dépôt (données confidentielles)")
    error, record = load_owner_authorization(args.authorization)
    if error:
        raise SystemExit(error)
    authorized = set(record["document_sha256"])
    entries = [e for e in _catalog(args.input_dir) if not args.only or e["document_id"] in args.only]
    for entry in entries:
        sha = hashlib.sha256(entry["source"].read_bytes()).hexdigest()
        if sha not in authorized:
            raise SystemExit(f"{entry['document_id']}: INTERIM_OWNER_DOCUMENT_NOT_AUTHORIZED")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        print(json.dumps({"start": entry["document_id"]}), flush=True)
        try:
            summary = asyncio.run(
                run_one(
                    entry, args.out_dir, args.authorization, args.timeout,
                    args.reuse_translations, args.reuse_analysis,
                )
            )
        except Exception as exc:  # report class only, never document content
            import re
            import traceback

            frame = traceback.extract_tb(exc.__traceback__)[-1]
            message = str(exc)
            summary = {
                "document_id": entry["document_id"],
                "error": type(exc).__name__,
                # Only technical codes are kept; free text could carry document content.
                "error_code": message if re.fullmatch(r"[A-Z0-9_:.\- ]{3,80}", message) else None,
                "error_at": f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}",
            }
            (args.out_dir / entry["document_id"]).mkdir(parents=True, exist_ok=True)
            (args.out_dir / entry["document_id"] / "interim-run-summary.json").write_text(json.dumps(summary))
        compact = {k: summary.get(k) for k in ("document_id", "error", "error_code", "error_at", "pages", "blocks", "blocks_changed",
                                                "untranslated_blocks", "requests_sent", "budget",
                                                "critical_issue_codes", "quality_status", "translation_s")}
        print(json.dumps(compact, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
