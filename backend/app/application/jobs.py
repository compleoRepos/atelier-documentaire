from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..core.models import (
    AuditEvent,
    Document,
    DocumentVersion,
    GlossaryEntry,
    GoldenReference,
    MemoryEntry,
    now_utc,
)
from ..infrastructure.storage import Storage

TERMINAL = {"APPROVED", "REJECTED", "FAILED"}


def audit(
    db: Session,
    tenant_id: str,
    action: str,
    user_id: str | None,
    document_id: str | None = None,
    details: dict | None = None,
) -> None:
    allowed = {
        "status",
        "issue_codes",
        "version",
        "kind",
        "page",
        "result",
        "model",
        "model_version",
        "ocr_version",
        "prompt_version",
        "glossary_version",
        "memory_version",
        "quality_scores",
        "duration_seconds",
        "source_sha256",
        "preprocessing_version",
        "preprocessing_profile",
        "preprocessing_operations",
        "preprocessing_sha256",
        "preprocessing_telemetry",
        "provider",
        "data_boundary",
        "data_scope",
        "reference_validated",
    }
    safe = {key: value for key, value in (details or {}).items() if key in allowed}
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            action=action,
            user_id=user_id,
            document_id=document_id,
            details=safe,
        )
    )


def _pipeline():
    from ..documents import pipeline

    return pipeline


def _call_analyze(source: Path, work: Path, options: dict) -> dict:
    pipeline = _pipeline()
    if not callable(getattr(pipeline, "analyze_document", None)):
        raise RuntimeError("PIPELINE_UNAVAILABLE")
    return pipeline.analyze_document(str(source), str(work), options)


def _call_translate(ir: dict, work: Path, options: dict) -> dict:
    pipeline = _pipeline()
    if not callable(getattr(pipeline, "translate_document", None)):
        raise RuntimeError("PIPELINE_UNAVAILABLE")
    result = pipeline.translate_document(ir, str(work), options)
    return asyncio.run(result) if inspect.isawaitable(result) else result


def _write_json(storage: Storage, key: str, value: Any) -> None:
    storage.put(key, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def _materialize(storage: Storage, key: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with storage.open(key) as source, path.open("wb") as target:
        shutil.copyfileobj(source, target)


def _ensure_enhanced_previews(work: Path) -> None:
    """Keep an explicit processing image even when the selected variant is original."""
    preview_dir = work / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    originals = sorted(preview_dir.glob("original-*.png"))
    for original in originals:
        suffix = original.stem.removeprefix("original-")
        enhanced = preview_dir / f"enhanced-{suffix}.png"
        if not enhanced.exists():
            shutil.copyfile(original, enhanced)


def _materialize_processing_images(storage: Storage, ir: dict, work: Path) -> None:
    """Make storage-backed processing images available to a worker without leaking paths."""
    preview_dir = work / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for page in ir.get("pages", []):
        value = page.get("processing_image_path")
        if not isinstance(value, str) or not value.startswith("storage://"):
            continue
        key = value.removeprefix("storage://")
        local = preview_dir / Path(key).name
        if storage.exists(key):
            _materialize(storage, key, local)
            page["processing_image_path"] = str(local)
            if isinstance(page.get("preprocessing"), dict):
                page["preprocessing"]["processing_image_path"] = str(local)


def _externalize_processing_images(
    storage: Storage, ir: dict, tenant_id: str, doc_id: str, prefix: str | None = None
) -> None:
    """Replace ephemeral processing paths with authenticated storage URIs."""
    root = prefix or f"{tenant_id}/{doc_id}/previews"
    for page in ir.get("pages", []):
        value = page.get("processing_image_path")
        if not isinstance(value, str):
            continue
        if value.startswith("storage://") and prefix is None:
            continue
        name = Path(value).name
        if not name:
            continue
        key = f"{root}/{name}"
        if storage.exists(key):
            page["processing_image_path"] = f"storage://{key}"
            if isinstance(page.get("preprocessing"), dict):
                page["preprocessing"]["processing_image_path"] = f"storage://{key}"


def _copy_enhanced_snapshot(
    storage: Storage, ir: dict, tenant_id: str, doc_id: str, version_prefix: str
) -> None:
    """Copy analysis processing images into an immutable translation-version prefix."""
    source_prefix = f"{tenant_id}/{doc_id}/previews"
    target_prefix = f"{version_prefix}/previews"
    for page in ir.get("pages", []):
        value = page.get("processing_image_path")
        name = Path(value.removeprefix("storage://")).name if isinstance(value, str) else ""
        if not name:
            name = f"enhanced-{int(page.get('number', 1)):03d}.png"
        source_key = f"{source_prefix}/{name}"
        target_key = f"{target_prefix}/{name}"
        if storage.exists(source_key) and not storage.exists(target_key):
            storage.put(target_key, storage.get(source_key))
        if storage.exists(target_key):
            page["processing_image_path"] = f"storage://{target_key}"
            if isinstance(page.get("preprocessing"), dict):
                page["preprocessing"]["processing_image_path"] = f"storage://{target_key}"


def _protected_regions(doc: Document) -> list[dict]:
    latest = None
    versions = getattr(doc, "versions", None) or []
    if versions:
        latest = max(versions, key=lambda item: item.version)
    regions = getattr(latest, "protected_regions", None) if latest else None
    return regions if isinstance(regions, list) else []


def _preprocessing_audit_details(ir: dict) -> dict:
    """Return telemetry-only preprocessing evidence (never text or local paths)."""
    pages = ir.get("pages", [])
    records = [page.get("preprocessing") for page in pages if isinstance(page.get("preprocessing"), dict)]
    if not records:
        return {}
    first = records[0]
    operations = []
    for operation in first.get("operations", []) or []:
        if isinstance(operation, str):
            operations.append(operation[:120])
        elif isinstance(operation, dict):
            safe = {
                key: value
                for key, value in operation.items()
                if key in {"name", "operation", "type", "version", "sha256", "duration_seconds"}
                and isinstance(value, (str, int, float, bool, type(None)))
            }
            if safe:
                operations.append(safe)
    result = {
        "preprocessing_version": first.get("version"),
        "preprocessing_profile": first.get("profile"),
        "preprocessing_operations": operations,
    }
    for key in ("processing_pixel_sha256", "sha256", "processing_sha256", "source_sha256"):
        if first.get(key):
            result["preprocessing_sha256"] = first[key]
            break
    telemetry = first.get("telemetry")
    if isinstance(telemetry, dict):
        result["preprocessing_telemetry"] = {
            key: value
            for key, value in telemetry.items()
            if key in {"duration_seconds", "variant", "version", "operation_count"}
            and isinstance(value, (str, int, float, bool, type(None)))
        }
    return {key: value for key, value in result.items() if value is not None}


def _next_version(db: Session, doc_id: str) -> int:
    current = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version.desc())
        .first()
    )
    return current.version + 1 if current else 1


def _persist_previews(
    storage: Storage, tenant_id: str, doc_id: str, work: Path, prefix: str | None = None
) -> None:
    preview_dir = work / "previews"
    if not preview_dir.exists():
        return
    for path in preview_dir.glob("*.png"):
        storage.put(f"{prefix or f'{tenant_id}/{doc_id}/previews'}/{path.name}", path.read_bytes())


def _failure(db: Session, tenant_id: str, doc_id: str, actor_id: str | None, code: str) -> None:
    doc = db.get(Document, doc_id)
    if doc and doc.tenant_id == tenant_id:
        doc.status = "FAILED"
        doc.issues_json = [{"code": code, "severity": "error", "message": "Traitement impossible"}]
        db.commit()
        audit(
            db,
            tenant_id,
            "DOCUMENT_FAILED",
            actor_id,
            doc_id,
            {"status": "FAILED", "issue_codes": [code]},
        )
        db.commit()


def run_analyze(
    doc_id: str, tenant_id: str, factory, storage: Storage, settings, actor_id: str | None = None
) -> None:
    with factory() as db:
        claimed = db.execute(
            update(Document)
            .where(
                Document.id == doc_id,
                Document.tenant_id == tenant_id,
                Document.status.in_(
                    ["UPLOADED", "ANALYZED", "REVIEW_REQUIRED", "APPROVED", "REJECTED", "FAILED"]
                ),
            )
            .values(
                status="ANALYZING",
                active_version_id=None,
                review_version=None,
                analysis_json=None,
                translation_json=None,
                quality_json=None,
                issues_json=None,
                updated_at=now_utc(),
            )
        ).rowcount
        db.commit()
        if not claimed:
            return
        doc = db.get(Document, doc_id)
        work = Path(settings.data_dir) / "work" / doc_id
        source = work / f"source.{doc.format}"
        started = time.perf_counter()
        try:
            _materialize(storage, doc.original_key, source)
            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            if doc.source_sha256 and doc.source_sha256 != source_sha:
                raise ValueError("ORIGINAL_INTEGRITY_MISMATCH")
            doc.source_sha256 = source_sha
            options = {
                "max_pages": settings.max_pages,
                "ocr_backend": settings.ocr_backend,
                "soffice_path": settings.soffice_path,
                "image_preprocessing_profile": getattr(
                    settings, "image_preprocessing_profile", "auto"
                ),
                "protected_regions": _protected_regions(doc),
            }
            if settings.paddle_model_dir:
                options["ocr_assets"] = {
                    "det_model_dir": str(settings.paddle_model_dir / "det"),
                    "rec_model_dir": str(settings.paddle_model_dir / "rec"),
                }
            ir = _call_analyze(source, work, options)
            ir["source_sha256"] = source_sha
            doc.analysis_revision = (doc.analysis_revision or 0) + 1
            ir["analysis_revision"] = doc.analysis_revision
            pages = ir.get("pages", [])
            if len(pages) > settings.max_pages:
                raise ValueError("PAGE_LIMIT")
            # The pipeline owns selection; the worker guarantees a stable copy and URI.
            _ensure_enhanced_previews(work)
            _persist_previews(storage, tenant_id, doc_id, work)
            _externalize_processing_images(storage, ir, tenant_id, doc_id)
            # A worker path is ephemeral. Review reconstructs from original_key.
            ir["source_path"] = f"storage://{doc.original_key}"
            analysis_key = f"{tenant_id}/{doc_id}/analysis.json"
            _write_json(storage, analysis_key, ir)
            _write_json(storage, f"{tenant_id}/{doc_id}/analyses/{doc.analysis_revision}.json", ir)
            doc.analysis_json = ir
            doc.language = ir.get("language")
            doc.document_type = ir.get("document_type")
            doc.domain = ir.get("domain")
            doc.page_count = len(pages)
            doc.status = "ANALYZED"
            doc.issues_json = ir.get("warnings", [])
            doc.timings_json = {
                **(doc.timings_json or {}),
                "analyze_seconds": time.perf_counter() - started,
                "ocr_seconds": (ir.get("timings") or {}).get("ocr_seconds"),
            }
            audit(
                db,
                tenant_id,
                "DOCUMENT_ANALYZED",
                actor_id,
                doc_id,
                {
                    "status": "ANALYZED",
                    "issue_codes": [x.get("code") for x in ir.get("warnings", [])],
                    **_preprocessing_audit_details(ir),
                },
            )
            db.commit()
        except Exception as exc:
            logging.getLogger("translator.jobs").error(
                "stage_failed stage=analysis exception_class=%s", type(exc).__name__
            )
            _failure(db, tenant_id, doc_id, actor_id, "ANALYSIS_FAILED")
        finally:
            shutil.rmtree(work, ignore_errors=True)


def run_translate(
    doc_id: str, tenant_id: str, factory, storage: Storage, settings, actor_id: str | None = None
) -> None:
    with factory() as db:
        claimed = db.execute(
            update(Document)
            .where(
                Document.id == doc_id,
                Document.tenant_id == tenant_id,
                Document.status.in_(["ANALYZED", "REVIEW_REQUIRED", "APPROVED", "REJECTED"]),
            )
            .values(status="TRANSLATING", active_version_id=None, updated_at=now_utc())
        ).rowcount
        db.commit()
        if not claimed:
            return
        doc = db.get(Document, doc_id)
        work = Path(settings.data_dir) / "work" / doc_id
        source = work / f"source.{doc.format}"
        started = time.perf_counter()
        try:
            _materialize(storage, doc.original_key, source)
            # Avoid mutating the JSON object attached to the SQLAlchemy document.
            ir = json.loads(json.dumps(doc.analysis_json or {}))
            ir["source_path"] = str(source)
            _materialize_processing_images(storage, ir, work)
            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            if doc.source_sha256 and doc.source_sha256 != source_sha:
                raise ValueError("ORIGINAL_INTEGRITY_MISMATCH")
            doc.source_sha256 = source_sha
            ir["source_sha256"] = source_sha
            ir["review_version"] = _next_version(db, doc_id)
            glossary_entries = (
                db.query(GlossaryEntry)
                .filter_by(tenant_id=tenant_id)
                .order_by(GlossaryEntry.version, GlossaryEntry.id)
                .all()
            )
            memory_entries = (
                db.query(MemoryEntry)
                .filter_by(tenant_id=tenant_id, validated=True)
                .order_by(MemoryEntry.version, MemoryEntry.id)
                .all()
            )
            glossary = [
                {"source": x.source, "target": x.target, "domain": x.domain}
                for x in glossary_entries
            ]
            memory = {x.source: x.target for x in memory_entries}
            options = {
                "engine": settings.engine,
                "private_ai_base_url": settings.private_ai_base_url,
                "private_ai_allowed_hosts": settings.private_hosts,
                "private_ai_model": settings.private_ai_model,
                "private_ai_api_key": settings.private_ai_api_key,
                "tokenizer_path": settings.tokenizer_path,
                "model_version": settings.private_ai_model_version,
                "quality_thresholds": settings.quality_thresholds,
                "source_sha256": source_sha,
                "review_version": ir["review_version"],
                **settings.translation_budgets,
                "glossary": glossary,
                "memory": memory,
                "glossary_version": max((x.version for x in glossary_entries), default=0),
                "memory_version": max((x.version for x in memory_entries), default=0),
                "image_preprocessing_profile": getattr(
                    settings, "image_preprocessing_profile", "auto"
                ),
                "protected_regions": _protected_regions(doc),
            }
            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            if settings.engine == "interim":
                options.update(
                    environment=settings.environment,
                    interim_model=settings.interim_model,
                    interim_api_base=settings.interim_api_base,
                    interim_api_key=settings.interim_api_key,
                    interim_data_scope=settings.interim_data_scope,
                    interim_synthetic_payload_sha256_allowlist=settings.interim_synthetic_payload_sha256_allowlist,
                    interim_total_generation_cap_verified=settings.interim_total_generation_cap_verified,
                    interim_capability_proof=settings.interim_capability_proof,
                )
            golden = (
                db.query(GoldenReference)
                .filter_by(tenant_id=tenant_id, sha256=source_sha, approved=True)
                .order_by(GoldenReference.version.desc())
                .first()
            )
            if golden and Path(golden.expected_key).is_file():
                reference = json.loads(Path(golden.expected_key).read_text(encoding="utf-8"))
                if (
                    reference.get("tenant_id") == tenant_id
                    and reference.get("source_sha256") == source_sha
                ):
                    # References are evaluation-only, never leaked into model context.
                    options["reference"] = reference
            from ..ai.quality.runtime import quality_options

            options.update(quality_options(settings, ir))
            result = _call_translate(ir, work, options)
            if not isinstance(result, dict):
                raise ValueError("TRANSLATION_RESULT_INVALID")
            # Le moteur conserve légitimement le français source en mode offline.
            # Une évaluation legacy le signalait à tort comme inconnu : ne retirer
            # que cette fausse alerte, jamais les blocs étrangers non traduits.
            blocks = [block for page in ir.get("pages", []) for block in page.get("blocks", [])]
            french_ids = {
                str(block.get("id"))
                for block in blocks
                if str(block.get("language", "")).lower() in {"fr", "fra", "fre", "french"}
            }
            result["untranslated_blocks"] = [
                block_id
                for block_id in result.get("untranslated_blocks", [])
                if str(block_id) not in french_ids
            ]

            def _false_french_unknown(issue: Any) -> bool:
                if not isinstance(issue, dict) or issue.get("code") != "UNTRANSLATED":
                    return False
                ids = issue.get("block_ids", []) or []
                return str(issue.get("block_id")) in french_ids or any(
                    str(item) in french_ids for item in ids
                )

            result["issues"] = [
                issue for issue in result.get("issues", []) if not _false_french_unknown(issue)
            ]
            quality = result.get("quality")
            if isinstance(quality, dict):
                quality["untranslated_blocks"] = [
                    block_id
                    for block_id in quality.get("untranslated_blocks", [])
                    if str(block_id) not in french_ids
                ]
                quality["issues"] = [
                    issue
                    for issue in quality.get("issues", [])
                    if not (
                        isinstance(issue, dict)
                        and issue.get("code") == "UNTRANSLATED"
                        and any(
                            str(block_id) in french_ids for block_id in issue.get("block_ids", [])
                        )
                    )
                ]
            vnum = _next_version(db, doc_id)
            key = f"{tenant_id}/{doc_id}/versions/{vnum}"
            telemetry = (
                result.get("translation_telemetry") or ir.get("_translation_telemetry") or {}
            )
            timings = {
                "translate_seconds": time.perf_counter() - started,
                "llm_seconds": telemetry.get("latency_ms", 0) / 1000
                if settings.engine == "private" and telemetry.get("latency_ms") is not None
                else None,
                "gpu_seconds": None,
                "ocr_seconds": (doc.timings_json or {}).get("ocr_seconds"),
            }
            translation_key = f"{key}/translation.json"
            _write_json(storage, translation_key, result)
            candidate_path = Path(result.get("versions", {}).get("candidate", ""))
            if not candidate_path.is_file():
                candidate_path = work / (
                    "candidate.docx" if doc.format == "docx" else "candidate.pdf"
                )
            if not candidate_path.is_file():
                raise ValueError("CANDIDATE_MISSING")
            candidate_ext = candidate_path.suffix.lower() or ".pdf"
            candidate_key = f"{key}/candidate{candidate_ext}"
            storage.put(candidate_key, candidate_path.read_bytes())
            _ensure_enhanced_previews(work)
            _persist_previews(storage, tenant_id, doc_id, work, prefix=f"{key}/previews")
            _copy_enhanced_snapshot(storage, ir, tenant_id, doc_id, key)
            analysis_snapshot = json.loads(json.dumps(ir))
            _externalize_processing_images(
                storage, analysis_snapshot, tenant_id, doc_id, prefix=f"{key}/previews"
            )
            analysis_snapshot["source_path"] = f"storage://{doc.original_key}"
            analysis_key = f"{key}/analysis.json"
            _write_json(storage, analysis_key, analysis_snapshot)
            version = DocumentVersion(
                document_id=doc_id,
                tenant_id=tenant_id,
                version=vnum,
                candidate_key=candidate_key,
                translation_key=translation_key,
                analysis_key=analysis_key,
                analysis_snapshot=analysis_snapshot,
                source_sha256=source_sha,
                provenance=result.get("versions"),
                timings_json=timings,
                previews_prefix=f"{key}/previews",
                translations=result.get("translations", {}),
                quality=result.get("quality"),
                issues=result.get("issues", []),
            )
            db.add(version)
            db.flush()
            doc.translation_json = result
            doc.quality_json = result.get("quality")
            doc.issues_json = result.get("issues", [])
            doc.review_version = vnum
            doc.timings_json = {**(doc.timings_json or {}), **timings}
            doc.status = "REVIEW_REQUIRED"
            audit(
                db,
                tenant_id,
                "DOCUMENT_TRANSLATED",
                actor_id,
                doc_id,
                {
                    "status": "REVIEW_REQUIRED",
                    "version": vnum,
                    "model": result.get("versions", {}).get("model"),
                    "model_version": telemetry.get("served_version") if settings.engine == "interim" else settings.private_ai_model_version,
                    "provider":telemetry.get("provider"),
                    "data_boundary":telemetry.get("data_boundary"),
                    "data_scope":telemetry.get("data_scope"),
                    "reference_validated":telemetry.get("reference_validated"),
                    "prompt_version": telemetry.get("prompt_version"),
                    "glossary_version": options["glossary_version"],
                    "memory_version": options["memory_version"],
                    "duration_seconds": timings["translate_seconds"],
                    "source_sha256": source_sha,
                    "quality_scores": {
                        key: (result.get("quality") or {}).get(key)
                        for key in settings.quality_thresholds
                    },
                    "issue_codes": [
                        x.get("code") for x in result.get("issues", []) if isinstance(x, dict)
                    ],
                    **_preprocessing_audit_details(analysis_snapshot),
                },
            )
            db.commit()
        except Exception as exc:
            logging.getLogger("translator.jobs").error(
                "stage_failed stage=translation exception_class=%s", type(exc).__name__
            )
            _failure(db, tenant_id, doc_id, actor_id, "TRANSLATION_FAILED")
        finally:
            shutil.rmtree(work, ignore_errors=True)
