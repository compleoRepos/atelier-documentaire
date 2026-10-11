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
    "CONTEXT_OVERFLOW",
    "INVALID_MODEL_OUTPUT",
    "OUTPUT_BUDGET_INVALID",
    "OUTPUT_LENGTH",
    "PROTECTED_ENTITY_COLLISION",
    "UNKNOWN_FINISH_REASON",
    "UNMAPPED_TABLE_CONTENT",
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
        i
        for i in saved.get("issues") or []
        if str(i.get("code", "")).startswith("INTERIM_")
        or i.get("code") in _SERVICE_CODES
        or (i.get("code") == "PROTECTED_ENTITY_CHANGED" and "block_id" in i and "page" not in i)
    ]
    return {
        "translations": saved["translations"],
        "issues": issues,
        "untranslated_blocks": saved.get("untranslated_blocks") or [],
        "translation_telemetry": saved.get("translation_telemetry") or {},
        "versions": {
            k: v
            for k, v in (saved.get("versions") or {}).items()
            if k in {"model", "provider", "context_budgets", "prompt"}
        },
    }


def _reusing_translate(work: Path):
    result = _saved_service_result(work)
    if (result.get("translation_telemetry") or {}).get("provider") != "interim":
        raise RuntimeError("REUSE_SOURCE_NOT_INTERIM")

    async def wrapper(ir, options):
        return json.loads(json.dumps(result))

    return wrapper


# Rendering-only fields: they never change what is sent to the model nor how
# its answer is validated. Every other block field must be identical for a
# cached translation to be reused (fail-closed: any difference = new request).
_RENDER_ONLY_KEYS = frozenset(
    {
        "bbox",
        "coordinates_kind",
        "font_size",
        "line_count",
        "line_heights",
        "line_pitch",
        "reading_order",
        "segmentation",
        "source_lines",
        "style",
        "checkbox_glyphs",
        "near_protected_regions",
        "protected_by",
        "split_from",
    }
)


def _send_signature(block: dict) -> str:
    return json.dumps(
        {k: v for k, v in block.items() if k not in _RENDER_ONLY_KEYS},
        sort_keys=True,
        ensure_ascii=False,
    )


def _table_has_members(table: dict, pages: list[dict]) -> bool:
    """Same membership rule as ContextPackBuilder (ids first, else bbox centres)."""
    from app.ai.context.builder import ContextPackBuilder

    blocks = {str(b["id"]): b for page in pages for b in page.get("blocks", [])}
    if any(i in blocks for i in ContextPackBuilder._table_block_ids(table)):
        return True
    bbox = table.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    left, top, right, bottom = (float(v) for v in bbox)
    for page in pages:
        if int(page.get("number") or 0) != int(table.get("page") or 1):
            continue
        for block in page.get("blocks", []):
            b = block.get("bbox")
            if isinstance(b, (list, tuple)) and len(b) == 4:
                cx, cy = (float(b[0]) + float(b[2])) / 2, (float(b[1]) + float(b[3])) / 2
                if left <= cx <= right and top <= cy <= bottom:
                    return True
    return False


def _cached_issues_for(issues: list[dict], hits: set[str]) -> list[dict]:
    kept = []
    for issue in issues:
        if str(issue.get("block_id")) in hits:
            kept.append(issue)
        elif isinstance(issue.get("block_ids"), list):
            ids = [str(i) for i in issue["block_ids"] if str(i) in hits]
            if ids:
                kept.append(
                    {
                        **issue,
                        "block_ids": ids,
                        **({"blocks": len(ids)} if "blocks" in issue else {}),
                    }
                )
    return kept


def _caching_translate(work: Path, cache_dir: Path):
    """Translation memory: reuse the Interim target of a previous run for every
    block whose send signature is unchanged; send only the other blocks (real
    service, same 32K guard). Makes a re-run attributable to code changes
    instead of model sampling variance (run18 audit)."""
    cached = _saved_service_result(cache_dir)
    if (cached.get("translation_telemetry") or {}).get("provider") != "interim":
        raise RuntimeError("TRANSLATION_CACHE_NOT_INTERIM")
    analysis = json.loads((cache_dir / "analysis.json").read_text())
    signatures = {
        str(b["id"]): _send_signature(b)
        for page in analysis.get("pages", [])
        for b in page.get("blocks", [])
    }
    cached_untranslated = set(map(str, cached.get("untranslated_blocks") or []))

    async def wrapper(ir, options):
        import copy

        reduced = copy.deepcopy(ir)
        hits: set[str] = set()
        for page in reduced.get("pages", []):
            kept = []
            for block in page.get("blocks", []):
                bid = str(block["id"])
                if bid in cached["translations"] and signatures.get(bid) == _send_signature(block):
                    hits.add(bid)
                else:
                    kept.append(block)
            page["blocks"] = kept
        # A table fully served by the memory would otherwise become an empty
        # synthetic unit (false UNMAPPED_TABLE_CONTENT); genuinely unmapped
        # tables (no member in the full IR) are kept so their alert stays.
        reduced["tables"] = [
            table
            for table in ir.get("tables") or []
            if not isinstance(table, dict)
            or not _table_has_members(table, ir.get("pages", []))
            or _table_has_members(table, reduced.get("pages", []))
        ]
        fresh = _REAL_TRANSLATE_BLOCKS(reduced, options)
        if asyncio.iscoroutine(fresh):
            fresh = await fresh
        merged = json.loads(json.dumps(fresh))
        merged["translations"] = {
            **{bid: cached["translations"][bid] for bid in hits},
            **(fresh.get("translations") or {}),
        }
        merged["issues"] = _cached_issues_for(cached.get("issues") or [], hits) + list(
            fresh.get("issues") or []
        )
        merged["untranslated_blocks"] = sorted(
            set(map(str, fresh.get("untranslated_blocks") or [])) | (cached_untranslated & hits)
        )
        telemetry = merged.setdefault("translation_telemetry", {})
        telemetry["translation_memory"] = {
            "cache_run": cache_dir.parent.parent.name,
            "blocks_reused": len(hits),
            "blocks_processed_now": sum(len(p.get("blocks", [])) for p in reduced.get("pages", [])),
        }
        (work / "interim-service-result.json").write_text(json.dumps(merged, ensure_ascii=False))
        return merged

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
    reserved = [
        c.get("reserved_total_tokens") for c in chunks if c.get("reserved_total_tokens") is not None
    ]
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
    entry: dict,
    out_dir: Path,
    authorization: Path,
    timeout: float,
    reuse: bool = False,
    reuse_analysis: bool = False,
    translation_cache: Path | None = None,
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

        pdf_provenances = {
            "pdf_embedded_image_original",
            "pdf_vector_original",
            "pdf_widget_original",
        }
        ir["protected_visual_regions"] = [
            r
            for r in ir.get("protected_visual_regions") or []
            if r.get("provenance") not in pdf_provenances
        ]
        for page in ir.get("pages", []):
            for block in page.get("blocks", []):
                block.pop("protected", None)
        protect_ir(ir)
        # Line verification (highlight + critical-entity double reading) is
        # idempotent and measured on the original raster: re-applied so that a
        # reused analysis carries the current safety net.
        if any(p.get("scanned") for p in ir.get("pages", [])):
            from app.documents.pipeline import run_line_verification

            run_line_verification(ir, source)
            (work / "analysis.json").write_text(json.dumps(ir, ensure_ascii=False))
        for stale in [
            *(work / "previews").glob("translated-*.png"),
            *(work / "previews").glob("diff-*.png"),
        ]:
            stale.unlink()
        if reuse:
            service_module.translate_blocks = _reusing_translate(work)
        elif translation_cache is not None:
            service_module.translate_blocks = _caching_translate(work, translation_cache / doc_id)
        else:
            service_module.translate_blocks = _capturing_translate(work)
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
    changed = sum(
        1
        for b in blocks
        if result["translations"].get(str(b["id"]), b.get("text")) != b.get("text")
    )
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
        "owner_authorization_id": (telemetry.get("owner_authorization") or {}).get(
            "authorization_id"
        ),
        "usage": telemetry.get("usage"),
        "budget": _budget_check(telemetry),
        "issue_codes": dict(Counter(i.get("code") for i in result.get("issues") or [])),
        "critical_issue_codes": sorted(
            {i.get("code") for i in result.get("issues") or [] if i.get("severity") == "critical"}
        ),
        "block_status": (result.get("block_status") or {}).get("summary"),
        "quality_status": quality.get("status"),
        "scores": {
            k: quality.get(k)
            for k in (
                "ocr_score",
                "translation_score",
                "semantic_score",
                "layout_score",
                "visual_score",
            )
        },
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
        "translation_memory": telemetry.get("translation_memory"),
        "human_reference_validated": False,
    }
    (work / "interim-run-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="required: sends authorised originals to Interim"
    )
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "dataset" / "input")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument(
        "--reuse-translations",
        action="store_true",
        help="re-render/evaluate from the Interim translations already obtained; no new request",
    )
    parser.add_argument(
        "--reuse-analysis",
        action="store_true",
        help="reuse the saved OCR/IR analysis (same SHA) but send new Interim requests",
    )
    parser.add_argument(
        "--translation-cache",
        type=Path,
        default=None,
        help="out dir of a previous Interim run: reuse targets of unchanged blocks (with --reuse-analysis)",
    )
    args = parser.parse_args()
    if args.translation_cache is not None and not args.reuse_analysis:
        parser.error("--translation-cache requiert --reuse-analysis")
    if not args.live:
        parser.error("--live requis : les originaux autorisés seront envoyés à Interim")
    if ROOT == args.out_dir.resolve() or ROOT in args.out_dir.resolve().parents:
        parser.error("--out-dir doit être hors du dépôt (données confidentielles)")
    error, record = load_owner_authorization(args.authorization)
    if error:
        raise SystemExit(error)
    authorized = set(record["document_sha256"])
    entries = [
        e for e in _catalog(args.input_dir) if not args.only or e["document_id"] in args.only
    ]
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
                    entry,
                    args.out_dir,
                    args.authorization,
                    args.timeout,
                    args.reuse_translations,
                    args.reuse_analysis,
                    args.translation_cache,
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
            (args.out_dir / entry["document_id"] / "interim-run-summary.json").write_text(
                json.dumps(summary)
            )
        compact = {
            k: summary.get(k)
            for k in (
                "document_id",
                "error",
                "error_code",
                "error_at",
                "pages",
                "blocks",
                "blocks_changed",
                "untranslated_blocks",
                "requests_sent",
                "budget",
                "critical_issue_codes",
                "quality_status",
                "translation_s",
            )
        }
        print(json.dumps(compact, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
