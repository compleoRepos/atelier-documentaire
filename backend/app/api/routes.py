# ruff: noqa: B008
from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import shutil
import unicodedata
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..application.jobs import audit, run_analyze, run_translate
from ..core.models import (
    AuditEvent,
    Document,
    DocumentVersion,
    GlossaryEntry,
    GoldenReference,
    MemoryEntry,
    RevokedSession,
    Tenant,
    User,
)
from ..core.security import (
    create_access_token,
    current_user_factory,
    session_id,
    user_payload,
    verify_password,
)
from ..infrastructure.antivirus import scan_upload
from ..infrastructure.validation import validate_upload


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=190)
    password: str = Field(min_length=1, max_length=1024)


class ReviewIn(BaseModel):
    action: str
    corrections: dict[str, str] = Field(default_factory=dict)
    protected_entities: list[str] = Field(default_factory=list)
    protected_regions: list[dict[str, Any]] = Field(default_factory=list)
    comment: str | None = Field(default=None, max_length=2000)
    attest_review: bool = False
    promote_golden: bool = False
    expected_version: int | None = Field(default=None, ge=1)
    ocr_text: str | None = Field(default=None, max_length=500000)
    attest_ocr: bool = False
    quality_rubric: dict[str, float] | None = None

    @field_validator("quality_rubric", mode="before")
    @classmethod
    def valid_rubric(cls, value):
        if value is None:
            return value
        dimensions = {"fidelity", "coherence", "terminology", "context", "style"}
        if not isinstance(value, dict) or set(value) != dimensions:
            raise ValueError("Les cinq dimensions de la rubrique sont requises")
        for score in value.values():
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not 0 <= score <= 1
            ):
                raise ValueError("Score humain invalide : nombre entre 0 et 1")
        return value


class GlossaryIn(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    target: str = Field(min_length=1, max_length=500)
    domain: str | None = Field(default=None, max_length=100)


class MemoryIn(GlossaryIn):
    pass


TERMINAL = {"APPROVED", "REJECTED", "FAILED"}
_NUMBER_RE = re.compile(r"(?<![\w])\d+(?:[.,/]\d+)*(?![\w])")


def _safe_filename(value: str) -> str:
    value = unicodedata.normalize("NFKC", Path(value or "document").name)
    value = value.replace("\r", "").replace("\n", "")
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)
    value = re.sub(r"[^\w. -]+", "_", value, flags=re.UNICODE).strip(" .")
    return (value or "document")[:180]


def _content_disposition(filename: str) -> str:
    safe = _safe_filename(filename).replace('"', "_")
    fallback = unicodedata.normalize("NFKD", safe).encode("ascii", "ignore").decode() or "document"
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", fallback)
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(safe, safe='')}"


def _all_blocks(ir: dict | None) -> list[dict]:
    return [block for page in (ir or {}).get("pages", []) for block in page.get("blocks", [])]


def _validate_regions(regions: list[dict], ir: dict | None) -> None:
    pages = {int(page.get("number")): page for page in (ir or {}).get("pages", [])}
    for region in regions:
        try:
            page = pages[int(region["page"])]
            bbox = [float(x) for x in region["bbox"]]
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "Zone protégée invalide") from None
        if len(bbox) != 4 or not all(math.isfinite(x) for x in bbox):
            raise HTTPException(422, "Zone protégée non finie")
        if bbox[0] < 0 or bbox[1] < 0 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise HTTPException(422, "Zone protégée invalide")
        if bbox[2] > float(page.get("width", 0)) or bbox[3] > float(page.get("height", 0)):
            raise HTTPException(422, "Zone protégée hors page")


def _entity_ok(source: str, target: str, entities: list[str]) -> bool:
    if Counter(_NUMBER_RE.findall(source)) != Counter(_NUMBER_RE.findall(target)):
        return False
    return all(not entity or source.count(entity) == target.count(entity) for entity in entities)


def _render_review_previews(source: Path, candidate: Path, fmt: str, preview_dir: Path) -> None:
    """Render translated and diff previews while the review source is materialized."""
    if fmt == "docx":
        from ..documents.pipeline import _convert_docx_with_libreoffice

        source_pdf = _convert_docx_with_libreoffice(source, preview_dir / "source-lo")
        candidate_pdf = _convert_docx_with_libreoffice(candidate, preview_dir / "candidate-lo")
        _render_review_previews(source_pdf, candidate_pdf, "pdf", preview_dir)
        return
    import fitz
    from PIL import Image, ImageChops, ImageEnhance

    preview_dir.mkdir(parents=True, exist_ok=True)
    if fmt in {"png", "jpg", "jpeg"}:
        source_doc = fitz.open()
        page = source_doc.new_page(width=1, height=1)
        image = Image.open(source).convert("RGB")
        page.set_mediabox(fitz.Rect(0, 0, image.width, image.height))
        page.insert_image(page.rect, filename=str(source))
    else:
        source_doc = fitz.open(str(source))
    candidate_doc = fitz.open(str(candidate))
    try:
        for number, page in enumerate(candidate_doc, 1):
            translated = preview_dir / f"translated-{number:03d}.png"
            pix = page.get_pixmap(matrix=fitz.Matrix(120 / 72, 120 / 72), alpha=False)
            pix.save(str(translated))
            if number <= len(source_doc):
                source_page = source_doc[number - 1]
                original = preview_dir / f"original-{number:03d}.png"
                source_pix = source_page.get_pixmap(
                    matrix=fitz.Matrix(120 / 72, 120 / 72), alpha=False
                )
                source_pix.save(str(original))
                left = Image.open(original).convert("RGB")
                right = Image.open(translated).convert("RGB")
                if left.size != right.size:
                    right = right.resize(left.size)
                diff = ImageEnhance.Contrast(ImageChops.difference(left, right)).enhance(4)
                diff.save(preview_dir / f"diff-{number:03d}.png")
    finally:
        candidate_doc.close()
        source_doc.close()


def create_router(factory, storage, settings):
    router = APIRouter(prefix="/api")
    get_user = current_user_factory(factory)
    login_attempts: dict[str, list[datetime]] = {}

    def require(user: User, *roles: str) -> None:
        if user.role not in roles:
            raise HTTPException(403, "Rôle insuffisant")

    def doc_or_404(db: Session, doc_id: str, user: User, locking: bool = False) -> Document:
        try:
            uuid.UUID(doc_id)
        except ValueError:
            raise HTTPException(404, "Document introuvable") from None
        query = select(Document).where(Document.id == doc_id, Document.tenant_id == user.tenant_id)
        if locking:
            query = query.with_for_update()
        doc = db.scalar(query)
        if not doc:
            raise HTTPException(404, "Document introuvable")
        if user.role == "uploader" and doc.uploaded_by != user.id:
            raise HTTPException(404, "Document introuvable")
        tenant = db.get(Tenant, user.tenant_id)
        if not tenant or not tenant.enabled:
            raise HTTPException(401, "Tenant désactivé")
        return doc

    def public_doc(doc: Document) -> dict:
        return {
            "id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
            "language": doc.language,
            "document_type": doc.document_type,
            "domain": doc.domain,
            "page_count": doc.page_count,
            "quality": doc.quality_json,
            "issues": doc.issues_json or [],
            "review_version": doc.review_version,
            "timings": doc.timings_json,
            "source_sha256": doc.source_sha256,
            "analysis_revision": doc.analysis_revision,
        }

    def run_or_queue(fn, doc, user, background: BackgroundTasks):
        if settings.execution_mode == "inline":
            fn(doc.id, user.tenant_id, factory, storage, settings, user.id)
        elif settings.execution_mode == "background":
            background.add_task(fn, doc.id, user.tenant_id, factory, storage, settings, user.id)
        else:
            try:
                from ..workers.tasks import enqueue

                enqueue(fn.__name__, doc.id, user.tenant_id, user.id)
            except Exception as exc:
                raise HTTPException(503, "File de jobs indisponible") from exc

    @router.post("/auth/login")
    def login(request: Request, payload: LoginIn, response: Response):
        now = datetime.now(UTC)
        address = request.client.host if request.client else "unknown"
        key = f"{address}:{payload.username.lower()}"
        recent = [item for item in login_attempts.get(key, []) if (now - item).total_seconds() < 60]
        if len(recent) >= 10:
            raise HTTPException(429, "Trop de tentatives; réessayez plus tard")
        recent.append(now)
        login_attempts[key] = recent
        with factory() as db:
            user = db.scalar(select(User).where(User.username == payload.username))
            tenant = db.get(Tenant, user.tenant_id) if user else None
            if (
                not user
                or not user.enabled
                or not tenant
                or not tenant.enabled
                or not verify_password(payload.password, user.password_hash)
            ):
                raise HTTPException(401, "Identifiants invalides")
            token = create_access_token(user)
            if settings.auth_mode != "bearer":
                response.set_cookie(
                    settings.session_cookie,
                    token,
                    httponly=True,
                    secure=settings.cookie_secure,
                    samesite="strict",
                    path="/api",
                    max_age=settings.jwt_expire_minutes * 60,
                )
                response.set_cookie(
                    settings.csrf_cookie,
                    secrets.token_urlsafe(32),
                    httponly=False,
                    secure=settings.cookie_secure,
                    samesite="strict",
                    path="/",
                    max_age=settings.jwt_expire_minutes * 60,
                )
            result = {
                "token_type": "cookie" if settings.auth_mode != "bearer" else "bearer",
                "user": user_payload(user),
            }
            if settings.auth_mode != "cookie":
                result["access_token"] = token
            return result

    @router.post("/auth/logout")
    def logout(request: Request, response: Response, user: User = Depends(get_user)):
        claims = request.state.auth_claims
        with factory() as db:
            db.merge(
                RevokedSession(
                    id=session_id(claims),
                    user_id=user.id,
                    expires_at=datetime.fromtimestamp(claims["exp"], UTC),
                )
            )
            audit(db, user.tenant_id, "SESSION_REVOKED", user.id)
            db.commit()
        response.delete_cookie(
            settings.session_cookie,
            path="/api",
            secure=settings.cookie_secure,
            httponly=True,
            samesite="strict",
        )
        response.delete_cookie(
            settings.csrf_cookie, path="/", secure=settings.cookie_secure, samesite="strict"
        )
        return {"status": "logged_out"}

    @router.get("/auth/me")
    def me(user: User = Depends(get_user)):
        return user_payload(user)

    @router.get("/health")
    def health():
        checks = {}
        try:
            with factory() as db:
                db.execute(text("SELECT 1"))
            checks["database"] = True
        except Exception:
            checks["database"] = False
        try:
            if settings.storage_backend == "s3":
                storage.client.head_bucket(Bucket=storage.bucket)
            else:
                settings.ensure_directories()
                checks["storage_writable"] = storage.root.is_dir()
            checks["storage"] = True
        except Exception:
            checks["storage"] = False
        if settings.execution_mode == "celery":
            try:
                import redis

                broker = redis.Redis.from_url(
                    settings.celery_broker_url, socket_timeout=2, socket_connect_timeout=2
                )
                checks["queue"] = bool(broker.ping())
                broker.close()
            except Exception:
                checks["queue"] = False
        status_ok = all(checks.values())
        return Response(
            json.dumps(
                {
                    "status": "ok" if status_ok else "degraded",
                    "service": "translator",
                    "checks": checks,
                }
            ),
            media_type="application/json",
            status_code=200 if status_ok else 503,
        )

    @router.get("/dashboard")
    def dashboard(user: User = Depends(get_user)):
        with factory() as db:
            query = select(Document).where(Document.tenant_id == user.tenant_id)
            if user.role == "uploader":
                query = query.where(Document.uploaded_by == user.id)
            docs = db.scalars(query).all()
            return {
                "documents": len(docs),
                "review_required": sum(x.status == "REVIEW_REQUIRED" for x in docs),
                "approved": sum(x.status == "APPROVED" for x in docs),
                "failed": sum(x.status == "FAILED" for x in docs),
                "engine": settings.engine,
                "metrics": {
                    key: (sum(values) / len(values) if values else None)
                    for key in settings.quality_thresholds
                    for values in [
                        [
                            float(doc.quality_json[key])
                            for doc in docs
                            if isinstance(doc.quality_json, dict)
                            and isinstance(doc.quality_json.get(key), (int, float))
                            and not isinstance(doc.quality_json.get(key), bool)
                        ]
                    ]
                },
            }

    @router.post("/documents")
    async def upload(
        background: BackgroundTasks, file: UploadFile = File(...), user: User = Depends(get_user)
    ):
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > settings.max_upload_bytes:
                raise HTTPException(
                    413, detail={"code": "SIZE_LIMIT", "message": "Fichier trop volumineux"}
                )
        ext, media = validate_upload(
            bytes(data), file.filename or "", file.content_type, settings.max_pages
        )
        scan_upload(bytes(data), settings)
        with factory() as db:
            doc = Document(
                tenant_id=user.tenant_id,
                filename=_safe_filename(file.filename or "document"),
                media_type=media,
                format=ext,
                original_key="",
                source_sha256=hashlib.sha256(data).hexdigest(),
                uploaded_by=user.id,
            )
            db.add(doc)
            db.flush()
            doc.original_key = f"{user.tenant_id}/{doc.id}/original.{ext}"
            storage.put(doc.original_key, bytes(data))
            audit(db, user.tenant_id, "DOCUMENT_UPLOADED", user.id, doc.id, {"status": "UPLOADED"})
            db.commit()
            run_or_queue(run_analyze, doc, user, background)
            db.refresh(doc)
            return public_doc(doc)

    @router.get("/documents")
    def list_documents(user: User = Depends(get_user)):
        with factory() as db:
            query = select(Document).where(Document.tenant_id == user.tenant_id)
            if user.role == "uploader":
                query = query.where(Document.uploaded_by == user.id)
            return [
                public_doc(x) for x in db.scalars(query.order_by(Document.created_at.desc())).all()
            ]

    @router.get("/documents/{doc_id}")
    def get_document(doc_id: str, user: User = Depends(get_user)):
        with factory() as db:
            doc = doc_or_404(db, doc_id, user)
            result = public_doc(doc)
            result.update({"analysis": doc.analysis_json, "translation": doc.translation_json})
            version = db.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == doc.id,
                    DocumentVersion.version == doc.review_version,
                )
            )
            result["protected_entities"] = (version.protected_entities or []) if version else []
            result["protected_regions"] = (version.protected_regions or []) if version else []
            return result

    def process(endpoint_fn, doc_id, background, user):
        with factory() as db:
            doc = doc_or_404(db, doc_id, user)
            if doc.status in {"ANALYZING", "TRANSLATING"}:
                raise HTTPException(409, "Un job est déjà en cours")
            run_or_queue(endpoint_fn, doc, user, background)
            db.refresh(doc)
            return public_doc(doc)

    @router.post("/documents/{doc_id}/analyze")
    def analyze(doc_id: str, background: BackgroundTasks, user: User = Depends(get_user)):
        return process(run_analyze, doc_id, background, user)

    @router.post("/documents/{doc_id}/translate")
    def translate(doc_id: str, background: BackgroundTasks, user: User = Depends(get_user)):
        return process(run_translate, doc_id, background, user)

    @router.get("/documents/{doc_id}/artifact/{kind}")
    def artifact(doc_id: str, kind: str, user: User = Depends(get_user)):
        if kind not in {"original", "candidate", "final", "analysis", "translation"}:
            raise HTTPException(404, "Artifact inconnu")
        with factory() as db:
            doc = doc_or_404(db, doc_id, user)
            if kind == "final" and doc.status != "APPROVED":
                raise HTTPException(403, "Artifact final non disponible")
            version = (
                db.scalar(
                    select(DocumentVersion).where(DocumentVersion.id == doc.active_version_id)
                )
                if doc.active_version_id
                else db.scalar(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == doc.id)
                    .order_by(DocumentVersion.version.desc())
                )
            )
            key = doc.original_key if kind == "original" else None
            if kind == "candidate" and version:
                key = version.candidate_key
            elif kind == "final" and version:
                key = version.final_key
            elif kind == "analysis":
                key = f"{user.tenant_id}/{doc.id}/analysis.json"
            elif kind == "translation" and version:
                key = version.translation_key
            if not key or not storage.exists(key):
                raise HTTPException(404, "Artifact indisponible")
            content = storage.get(key)
            suffix = Path(key).suffix or Path(doc.filename).suffix
            media = (
                "application/json"
                if kind in {"analysis", "translation"}
                else ("application/pdf" if suffix == ".pdf" else doc.media_type)
            )
            name = f"{Path(doc.filename).stem}-{kind}{suffix}"
            audit(db, user.tenant_id, "ARTIFACT_ACCESSED", user.id, doc.id, {"kind": kind})
            db.commit()
            return Response(
                content=content,
                media_type=media,
                headers={"Content-Disposition": _content_disposition(name)},
            )

    @router.get("/documents/{doc_id}/preview/{kind}/{page}")
    def preview(
        doc_id: str,
        kind: str,
        page: int,
        version: int | None = None,
        user: User = Depends(get_user),
    ):
        if (
            kind not in {"original", "translated", "diff"}
            or page < 1
            or (version is not None and version < 1)
        ):
            raise HTTPException(404, "Aperçu indisponible")
        with factory() as db:
            doc = doc_or_404(db, doc_id, user)
            selected = db.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == doc.id,
                    DocumentVersion.version
                    == (version if version is not None else doc.review_version),
                )
            )
            if version is not None and not selected:
                raise HTTPException(404, "Version d'aperçu introuvable")
            prefix = selected.previews_prefix if selected else f"{user.tenant_id}/{doc_id}/previews"
            key = f"{prefix}/{kind}-{page:03d}.png"
            if kind == "original" and not storage.exists(key):
                key = f"{user.tenant_id}/{doc_id}/previews/original-{page:03d}.png"
            if not storage.exists(key):
                raise HTTPException(404, "Aperçu indisponible")
            audit(
                db,
                user.tenant_id,
                "PREVIEW_ACCESSED",
                user.id,
                doc.id,
                {"kind": kind, "page": page, "version": selected.version if selected else 0},
            )
            db.commit()
            return Response(storage.get(key), media_type="image/png")

    @router.post("/documents/{doc_id}/review")
    def review(doc_id: str, payload: ReviewIn, user: User = Depends(get_user)):
        require(user, "reviewer", "admin")
        if payload.action not in {"approve", "reject", "correct"}:
            raise HTTPException(422, "Action de revue invalide")
        with factory() as db:
            doc = doc_or_404(db, doc_id, user, locking=True)
            if (
                payload.expected_version is not None
                and payload.expected_version != doc.review_version
            ):
                raise HTTPException(409, "Version de revue obsolète")
            if doc.status in {"ANALYZING", "TRANSLATING"}:
                raise HTTPException(409, "Job en cours")
            version = db.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == doc.id,
                    DocumentVersion.version == doc.review_version,
                )
            )
            if not version:
                raise HTTPException(409, "Aucune version à revoir")
            if payload.action == "reject":
                doc.status = "REJECTED"
                doc.active_version_id = None
                audit(
                    db,
                    user.tenant_id,
                    "DOCUMENT_REJECTED",
                    user.id,
                    doc.id,
                    {"status": "REJECTED", "version": version.version},
                )
                db.commit()
                return public_doc(doc)
            ir = version.analysis_snapshot or doc.analysis_json or {}
            _validate_regions(payload.protected_regions or [], ir)
            if payload.action == "correct":
                _apply_corrections(db, doc, version, payload, user, storage, settings)
                db.commit()
                return public_doc(doc)
            if not payload.attest_review:
                raise HTTPException(422, "attest_review est requis")
            if payload.ocr_text is not None and (
                not payload.attest_ocr or not payload.ocr_text.strip()
            ):
                raise HTTPException(422, "Une transcription OCR doit être validée explicitement")
            if doc.status != "REVIEW_REQUIRED" or version.quality is None:
                raise HTTPException(422, "Une analyse qualité et un candidat en revue sont requis")
            translations = version.translations or {}
            if any(translations.get(key) != value for key, value in payload.corrections.items()):
                raise HTTPException(409, "Enregistrez et relisez les corrections avant d'approuver")
            if payload.protected_regions and payload.protected_regions != (
                version.protected_regions or []
            ):
                raise HTTPException(
                    409, "Enregistrez les zones protégées et relisez le nouveau candidat"
                )
            blocks = _all_blocks(ir)
            block_ids = {str(block.get("id")) for block in blocks}
            if set(translations) != block_ids:
                raise HTTPException(422, "La traduction ne couvre pas tous les blocs source")
            stored_regions = version.protected_regions or []
            _validate_regions(payload.protected_regions or stored_regions, ir)
            entities = payload.protected_entities or version.protected_entities or []
            for block in blocks:
                if not _entity_ok(
                    str(block.get("text", "")),
                    str(translations.get(str(block["id"]), "")),
                    entities,
                ):
                    raise HTTPException(422, "Entité ou référence modifiée")
            quality = version.quality
            unknown = quality.get("untranslated_blocks", []) or []
            errors = [
                issue
                for issue in (version.issues or quality.get("issues", []) or [])
                if isinstance(issue, dict) and issue.get("severity") in {"error", "critical"}
            ]
            if quality.get("critical_entity_errors") or unknown or errors:
                raise HTTPException(
                    422, "Validation bloquée: qualité critique, erreur ou segment inconnu"
                )
            if not version.candidate_key or not storage.exists(version.candidate_key):
                raise HTTPException(409, "Candidat absent")
            final_key = f"{user.tenant_id}/{doc.id}/versions/{version.version}/final{Path(version.candidate_key).suffix}"
            storage.put(final_key, storage.get(version.candidate_key))
            version.final_key = final_key
            version.is_final = True
            version.protected_entities = entities
            version.protected_regions = payload.protected_regions or stored_regions
            doc.active_version_id = version.id
            doc.status = "APPROVED"
            audit(
                db,
                user.tenant_id,
                "DOCUMENT_APPROVED",
                user.id,
                doc.id,
                {"status": "APPROVED", "version": version.version},
            )
            if payload.promote_golden:
                _promote_golden(db, doc, version, user, storage, settings, payload)
            db.commit()
            return public_doc(doc)

    def _apply_corrections(db, doc, version, payload, user, storage, settings):
        ir = dict(version.analysis_snapshot or doc.analysis_json or {})
        blocks = _all_blocks(ir)
        ids = {str(block.get("id")) for block in blocks}
        unknown = set(payload.corrections) - ids
        if unknown:
            raise HTTPException(422, "Bloc de correction inconnu")
        source_by_id = {str(block["id"]): str(block.get("text", "")) for block in blocks}
        if any(not isinstance(value, str) for value in payload.corrections.values()):
            raise HTTPException(422, "Correction textuelle invalide")
        entities = payload.protected_entities or version.protected_entities or []
        for block_id, target in payload.corrections.items():
            if not _entity_ok(source_by_id[block_id], target, entities):
                raise HTTPException(422, "Correction d’une entité ou référence interdite")
        translations = dict(version.translations or {})
        translations.update(payload.corrections)
        review_dir = Path(settings.data_dir) / "review" / doc.id
        review_dir.mkdir(parents=True, exist_ok=True)
        source_path = review_dir / f"source.{doc.format}"
        with storage.open(doc.original_key) as source, source_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        ir["source_path"] = str(source_path)
        try:
            from ..documents import pipeline

            output = review_dir / ("candidate.docx" if doc.format == "docx" else "candidate.pdf")
            render = pipeline.reconstruct_document(
                ir, translations, str(output), payload.protected_regions
            )
            ir["protected_entities"] = entities
            quality = pipeline.evaluate_document(
                ir,
                translations,
                render,
                None,
                {
                    "quality_thresholds": settings.quality_thresholds,
                    "source_sha256": doc.source_sha256,
                },
            )
            if not output.exists():
                raise ValueError("CANDIDATE_MISSING")
            _render_review_previews(source_path, output, doc.format, review_dir / "previews")
            vnum = max((item.version for item in doc.versions), default=0) + 1
            prefix = f"{user.tenant_id}/{doc.id}/versions/{vnum}"
            candidate_key = f"{prefix}/candidate{output.suffix.lower()}"
            translation_key = f"{prefix}/translation.json"
            storage.put(candidate_key, output.read_bytes())
            storage.put(
                translation_key,
                json.dumps(
                    {
                        "translations": translations,
                        "quality": quality,
                        "issues": quality.get("issues", []),
                    },
                    ensure_ascii=False,
                    indent=2,
                ).encode(),
            )
            for path in (
                (review_dir / "previews").glob("*.png")
                if (review_dir / "previews").exists()
                else []
            ):
                storage.put(f"{prefix}/previews/{path.name}", path.read_bytes())
            new_version = DocumentVersion(
                document_id=doc.id,
                tenant_id=user.tenant_id,
                version=vnum,
                candidate_key=candidate_key,
                translation_key=translation_key,
                previews_prefix=f"{prefix}/previews",
                translations=translations,
                quality=quality,
                issues=quality.get("issues", []),
                protected_entities=entities,
                protected_regions=payload.protected_regions,
                analysis_snapshot={**ir, "source_path": f"storage://{doc.original_key}"},
                source_sha256=doc.source_sha256,
                provenance={"reviewer_id": user.id, "review_version": vnum},
            )
            db.add(new_version)
            db.flush()
            doc.review_version = vnum
            doc.active_version_id = None
            doc.translation_json = {
                "translations": translations,
                "quality": quality,
                "issues": quality.get("issues", []),
                "untranslated_blocks": quality.get("untranslated_blocks", []),
            }
            doc.quality_json = quality
            doc.issues_json = quality.get("issues", [])
            doc.status = "REVIEW_REQUIRED"
            audit(
                db,
                user.tenant_id,
                "DOCUMENT_CORRECTED",
                user.id,
                doc.id,
                {"status": "REVIEW_REQUIRED", "version": vnum},
            )
            return quality
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, "Correction non validée par le moteur documentaire") from exc
        finally:
            shutil.rmtree(review_dir, ignore_errors=True)

    def _promote_golden(db, doc, version, user, storage, settings, human_review):
        source = storage.get(doc.original_key)
        source_sha = hashlib.sha256(source).hexdigest()
        db.scalar(select(Tenant).where(Tenant.id == user.tenant_id).with_for_update())
        latest = db.scalar(
            select(GoldenReference)
            .where(
                GoldenReference.tenant_id == user.tenant_id, GoldenReference.sha256 == source_sha
            )
            .order_by(GoldenReference.version.desc())
        )
        golden_version = (latest.version + 1) if latest else 1
        payload = {
            "schema_version": "1.0",
            "source_sha256": source_sha,
            "document_id": doc.id,
            "version": golden_version,
            "approved": True,
            "reviewer_id": user.id,
            "tenant_id": user.tenant_id,
            "validated_at": datetime.now(UTC).isoformat(),
            "translations": version.translations or {},
            "target_text": "\n".join(
                str((version.translations or {}).get(str(block["id"]), ""))
                for block in _all_blocks(doc.analysis_json or {})
            ),
            "ocr_validated": False,
        }
        translation_sha = hashlib.sha256(
            json.dumps(
                version.translations or {},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        payload["translation_sha256"] = translation_sha
        payload["review_version"] = version.version
        payload["entities"] = version.protected_entities or []
        if human_review.ocr_text is not None and human_review.attest_ocr:
            payload["ocr_text"] = human_review.ocr_text
            payload["ocr_validated"] = True
            payload["ocr_annotated_by"] = user.id
            payload["ocr_scope_sha256"] = source_sha
            payload["ocr_review"] = {
                "reviewer_id": user.id,
                "validated_at": payload["validated_at"],
            }
        if human_review.quality_rubric is not None:
            payload["quality_rubric"] = {
                "scores": human_review.quality_rubric,
                "reviewer_id": user.id,
                "validated_at": payload["validated_at"],
                "translation_sha256": translation_sha,
                "source_sha256": source_sha,
                "review_version": version.version,
            }
        expected_root = Path(settings.expected_dir) / user.tenant_id / source_sha
        expected_root.mkdir(parents=True, exist_ok=True)
        expected_file = expected_root / f"v{golden_version}.json"
        expected_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (expected_root / "latest.json").write_text(
            expected_file.read_text(encoding="utf-8"), encoding="utf-8"
        )
        key = f"{user.tenant_id}/{doc.id}/golden/v{golden_version}{Path(version.final_key).suffix}"
        storage.put(key, storage.get(version.final_key))
        db.add(
            GoldenReference(
                tenant_id=user.tenant_id,
                document_id=doc.id,
                version=golden_version,
                expected_key=str(expected_file),
                sha256=source_sha,
                reviewer_id=user.id,
            )
        )
        for block in _all_blocks(doc.analysis_json or {}):
            source_text = str(block.get("text", ""))
            target_text = (version.translations or {}).get(str(block.get("id")))
            if not source_text or not target_text or source_text == target_text:
                continue
            entry = db.scalar(
                select(MemoryEntry)
                .where(MemoryEntry.tenant_id == user.tenant_id, MemoryEntry.source == source_text)
                .order_by(MemoryEntry.version.desc())
            )
            if entry:
                entry.target = target_text
                entry.validated = True
                entry.version += 1
            else:
                db.add(
                    MemoryEntry(
                        tenant_id=user.tenant_id,
                        source=source_text,
                        target=target_text,
                        validated=True,
                    )
                )
        audit(
            db,
            user.tenant_id,
            "GOLDEN_PROMOTED",
            user.id,
            doc.id,
            {"version": golden_version, "result": "explicit"},
        )

    @router.get("/glossary")
    def glossary(user: User = Depends(get_user)):
        with factory() as db:
            return [
                {
                    "id": x.id,
                    "source": x.source,
                    "target": x.target,
                    "domain": x.domain,
                    "version": x.version,
                }
                for x in db.scalars(
                    select(GlossaryEntry)
                    .where(GlossaryEntry.tenant_id == user.tenant_id)
                    .order_by(GlossaryEntry.version, GlossaryEntry.id)
                ).all()
            ]

    @router.post("/glossary")
    def add_glossary(payload: GlossaryIn, user: User = Depends(get_user)):
        require(user, "reviewer", "admin")
        with factory() as db:
            entry = db.scalar(
                select(GlossaryEntry).where(
                    GlossaryEntry.tenant_id == user.tenant_id,
                    GlossaryEntry.source == payload.source,
                    GlossaryEntry.domain == payload.domain,
                )
            )
            version = (entry.version + 1) if entry else 1
            if entry:
                entry.target = payload.target
                entry.version = version
            else:
                entry = GlossaryEntry(
                    tenant_id=user.tenant_id, **payload.model_dump(), version=version
                )
                db.add(entry)
            audit(db, user.tenant_id, "GLOSSARY_UPDATED", user.id, details={"version": version})
            db.commit()
            return {
                "id": entry.id,
                "source": entry.source,
                "target": entry.target,
                "domain": entry.domain,
                "version": entry.version,
            }

    @router.get("/memory")
    def memory(user: User = Depends(get_user)):
        with factory() as db:
            return [
                {
                    "id": x.id,
                    "source": x.source,
                    "target": x.target,
                    "validated": x.validated,
                    "version": x.version,
                }
                for x in db.scalars(
                    select(MemoryEntry)
                    .where(MemoryEntry.tenant_id == user.tenant_id)
                    .order_by(MemoryEntry.version, MemoryEntry.id)
                ).all()
            ]

    @router.post("/memory")
    def add_memory(payload: MemoryIn, user: User = Depends(get_user)):
        require(user, "reviewer", "admin")
        with factory() as db:
            entry = db.scalar(
                select(MemoryEntry).where(
                    MemoryEntry.tenant_id == user.tenant_id, MemoryEntry.source == payload.source
                )
            )
            version = (entry.version + 1) if entry else 1
            if entry:
                entry.target = payload.target
                entry.version = version
                entry.validated = True
            else:
                entry = MemoryEntry(
                    tenant_id=user.tenant_id,
                    source=payload.source,
                    target=payload.target,
                    validated=True,
                    version=version,
                )
                db.add(entry)
            audit(db, user.tenant_id, "MEMORY_UPDATED", user.id, details={"version": version})
            db.commit()
            return {
                "id": entry.id,
                "source": entry.source,
                "target": entry.target,
                "validated": entry.validated,
                "version": entry.version,
            }

    @router.get("/audit")
    def audit_list(user: User = Depends(get_user)):
        with factory() as db:
            return [
                {
                    "id": x.id,
                    "action": x.action,
                    "document_id": x.document_id,
                    "user_id": x.user_id,
                    "timestamp": x.timestamp.isoformat(),
                    "details": x.details or {},
                }
                for x in db.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.tenant_id == user.tenant_id)
                    .order_by(AuditEvent.timestamp.desc())
                ).all()
            ]

    @router.get("/testing")
    def testing(user: User = Depends(get_user)):
        report = (
            Path(settings.report_dir) / user.tenant_id / "summary.json"
            if settings.report_dir
            else None
        )
        summary = None
        if report and report.is_file():
            try:
                summary = json.loads(report.read_text(encoding="utf-8"))
                if summary.get("tenant_id") != user.tenant_id:
                    summary = None
            except (OSError, json.JSONDecodeError):
                summary = None
        expected = Path(settings.expected_dir) / user.tenant_id
        dataset_available = bool(summary and summary.get("documents")) or (
            expected.is_dir() and any(expected.rglob("v*.json"))
        )
        return {
            "dataset_available": dataset_available,
            "documents": summary.get("documents") if summary else None,
            "tests_passed": summary.get("tests_passed") if summary else None,
            "tests_failed": summary.get("tests_failed") if summary else None,
            "metrics": summary.get("metrics") if summary else None,
            "reference_status": summary.get("reference_status") if summary else None,
        }

    @router.get("/admin")
    def admin(user: User = Depends(get_user)):
        require(user, "admin")
        return {
            "environment": settings.environment,
            "storage_backend": settings.storage_backend,
            "execution_mode": settings.execution_mode,
            "engine": settings.engine,
            "max_upload_bytes": settings.max_upload_bytes,
            "max_pages": settings.max_pages,
            "translation_budgets": settings.translation_budgets,
            "private_ai_configured": bool(
                settings.private_ai_base_url
                and settings.private_ai_model
                and settings.tokenizer_path
            ),
            "database_configured": bool(settings.database_url),
        }

    return router
