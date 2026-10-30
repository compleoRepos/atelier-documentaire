# ruff: noqa: B008
"""Routeur d'administration ``/api/rag-admin/*``.

Monté uniquement si ``TRANSLATOR_RAG_ADMIN_ENABLED=true``. Aucune publication
automatique : chaque transition est une action humaine (voir
``storage/versioning.py``). Un administrateur applicatif existant (rôle
``admin``) peut seulement attribuer les rôles RAG et fixer le mode maximal du
tenant (amorçage) ; il n'obtient aucun droit terminologique implicite.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from ...core.models import User
from ...core.security import current_user_factory
from ..models import RagImportBatch, RagLexicalIndex, RagReferential, RagValidationEvent
from ..schemas import (
    ActiveRequest,
    DraftRequest,
    EntriesRequest,
    ReferentialRequest,
    RoleRequest,
    TenantModeRequest,
    TransitionRequest,
)
from ..storage import repository, versioning
from .deps import ANY_RAG_ROLE, rag_errors, require_any


def _referential(row: RagReferential) -> dict[str, Any]:
    return {
        "id": row.id,
        "scope": "common" if row.tenant_id is None else "tenant",
        "read_only": row.tenant_id is None,
        "kind": row.kind,
        "name": row.name,
        "domain": row.domain,
        "country": row.country,
        "jurisdiction": row.jurisdiction,
        "languages": row.languages or [],
        "active": row.active,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _version(row: Any) -> dict[str, Any]:
    def iso(value):
        return value.isoformat() if value else None

    return {
        "id": row.id,
        "referential_id": row.referential_id,
        "number": row.number,
        "status": row.status,
        "entry_count": row.entry_count,
        "content_sha256": row.content_sha256,
        "created_by": row.created_by,
        "submitted_by": row.submitted_by,
        "validated_by": row.validated_by,
        "published_by": row.published_by,
        "created_at": iso(row.created_at),
        "submitted_at": iso(row.submitted_at),
        "validated_at": iso(row.validated_at),
        "published_at": iso(row.published_at),
        "retired_at": iso(row.retired_at),
    }


def _entry(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "status": row.status,
        "normalized_source": row.normalized_source,
        **{name: getattr(row, name) for name in versioning.ENTRY_FIELDS},
        "validated_by": row.validated_by,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
    }


def create_rag_admin_router(factory, settings) -> APIRouter:
    router = APIRouter(prefix="/api/rag-admin", tags=["rag-admin"])
    get_user = current_user_factory(factory)

    def roles_of(db, user: User) -> set[str]:
        return repository.user_roles(db, user.tenant_id, user.id)

    def require_role_manager(db, user: User) -> None:
        if user.role != "admin":
            require_any(roles_of(db, user), {"rag_admin"})

    # ------------------------------------------------------------ référentiels
    @router.get("/referentials")
    def referentials(user: User = Depends(get_user)):
        with factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            return [_referential(row) for row in repository.list_referentials(db, user.tenant_id)]

    @router.post("/referentials")
    def create_referential(body: ReferentialRequest, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            row = versioning.create_referential(
                db, user.tenant_id, body.model_dump(), user.id, roles_of(db, user)
            )
            db.commit()
            return _referential(row)

    @router.post("/referentials/{referential_id}/active")
    def activate(referential_id: str, body: ActiveRequest, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            row = repository.writable_referential(db, user.tenant_id, referential_id)
            versioning.set_referential_active(db, row, body.active, user.id, roles_of(db, user))
            db.commit()
            return _referential(row)

    @router.get("/referentials/{referential_id}/versions")
    def versions(referential_id: str, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            row = repository.visible_referential(db, user.tenant_id, referential_id)
            return [_version(v) for v in repository.versions_of(db, row)]

    @router.post("/referentials/{referential_id}/versions")
    def create_version(referential_id: str, body: DraftRequest, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            row = repository.writable_referential(db, user.tenant_id, referential_id)
            source = (
                repository.writable_version(db, user.tenant_id, body.copy_from)
                if body.copy_from
                else None
            )
            version = versioning.create_draft(db, row, user.id, roles_of(db, user), source)
            db.commit()
            return _version(version)

    # ----------------------------------------------------------------- versions
    @router.get("/versions/{version_id}/entries")
    def entries(version_id: str, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            version = repository.visible_version(db, user.tenant_id, version_id)
            return [_entry(e) for e in repository.version_entries(db, version)]

    @router.post("/versions/{version_id}/entries")
    def add_entries(version_id: str, body: EntriesRequest, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            version = repository.writable_version(db, user.tenant_id, version_id)
            referential = repository.writable_referential(
                db, user.tenant_id, version.referential_id
            )
            created = versioning.add_entries(
                db,
                referential,
                version,
                [entry.model_dump(by_alias=True) for entry in body.entries],
                user.id,
                roles_of(db, user),
            )
            db.commit()
            return {"created": len(created), "version": _version(version)}

    @router.post("/versions/{version_id}/transitions")
    def transition(version_id: str, body: TransitionRequest, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            version = repository.writable_version(db, user.tenant_id, version_id)
            referential = repository.writable_referential(
                db, user.tenant_id, version.referential_id
            )
            versioning.transition(
                db, referential, version, body.action, user.id, roles_of(db, user), body.comment
            )
            db.commit()
            return _version(version)

    @router.get("/versions/{version_id}/events")
    def events(version_id: str, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            version = repository.visible_version(db, user.tenant_id, version_id)
            rows = (
                db.query(RagValidationEvent)
                .filter(RagValidationEvent.object_id == version.id)
                .filter(
                    (RagValidationEvent.tenant_id == user.tenant_id)
                    | RagValidationEvent.tenant_id.is_(None)
                )
                .order_by(RagValidationEvent.created_at, RagValidationEvent.id)
                .all()
            )
            return [
                {
                    "action": row.action,
                    "actor_id": row.actor_id,
                    "actor_role": row.actor_role,
                    "comment": row.comment,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]

    # ------------------------------------------------- LOT 2 : import, historique
    @router.post("/versions/{version_id}/import")
    async def import_entries(
        version_id: str,
        request: Request,
        file_format: str = Query("auto", alias="format", pattern="^(auto|csv|xlsx)$"),
        dry_run: bool = Query(True),
        user: User = Depends(get_user),
    ):
        """Import CSV/XLSX tout-ou-rien dans un brouillon ; essai à blanc par défaut."""
        limit = settings.rag_import_max_bytes
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            raise HTTPException(413, "IMPORT_TOO_LARGE")
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise HTTPException(413, "IMPORT_TOO_LARGE")
            chunks.append(chunk)
        data = b"".join(chunks)

        def work():
            from ..terminology import importer

            with rag_errors(), factory() as db:
                version = repository.writable_version(db, user.tenant_id, version_id)
                referential = repository.writable_referential(
                    db, user.tenant_id, version.referential_id
                )
                batch = importer.import_file(
                    db,
                    settings=settings,
                    tenant_id=user.tenant_id,
                    referential=referential,
                    version=version,
                    data=data,
                    file_format=file_format,
                    actor_id=user.id,
                    roles=roles_of(db, user),
                    dry_run=dry_run,
                )
                db.commit()
                return {**importer.batch_view(batch), "version": _version(version)}

        return await run_in_threadpool(work)

    @router.get("/versions/{version_id}/imports")
    def imports(version_id: str, user: User = Depends(get_user)):
        from ..terminology.importer import batch_view

        with rag_errors(), factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            version = repository.writable_version(db, user.tenant_id, version_id)
            rows = (
                db.query(RagImportBatch)
                .filter(
                    RagImportBatch.tenant_id == user.tenant_id,
                    RagImportBatch.version_id == version.id,
                )
                .order_by(RagImportBatch.created_at, RagImportBatch.id)
                .all()
            )
            return [batch_view(row) for row in rows]

    @router.get("/referentials/{referential_id}/history")
    def referential_history(referential_id: str, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            row = repository.visible_referential(db, user.tenant_id, referential_id)
            return versioning.history(db, row)

    @router.get("/versions/{version_id}/diff")
    def version_diff(
        version_id: str,
        against: str = Query(..., min_length=1, max_length=36),
        user: User = Depends(get_user),
    ):
        """Différences ``against`` -> ``version_id`` (même référentiel)."""
        with rag_errors(), factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            other = repository.visible_version(db, user.tenant_id, version_id)
            base = repository.visible_version(db, user.tenant_id, against)
            return versioning.diff_versions(db, base, other)

    @router.get("/lexical/status")
    def lexical_status(user: User = Depends(get_user)):
        from ..core.lexical import NORMALIZER_VERSION

        with factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            scope = repository.published_scope(db, user.tenant_id)
            states = {
                row.version_id: row
                for row in db.query(RagLexicalIndex)
                .filter(RagLexicalIndex.version_id.in_([i["version_id"] for i in scope] or [""]))
                .all()
            }
            out = []
            for item in scope:
                state = states.get(item["version_id"])
                fresh = (
                    state is not None
                    and state.normalizer_version == NORMALIZER_VERSION
                    and state.content_sha256 == item["content_sha256"]
                )
                out.append(
                    {
                        "version_id": item["version_id"],
                        "referential_id": item["referential_id"],
                        "scope": item["scope"],
                        "indexed": fresh,
                        "entry_count": state.entry_count if state else 0,
                        "posting_count": state.posting_count if state else 0,
                        "normalizer_version": state.normalizer_version if state else None,
                    }
                )
            return {"normalizer_version": NORMALIZER_VERSION, "versions": out}

    @router.post("/lexical/rebuild")
    def lexical_rebuild(force: bool = Query(False), user: User = Depends(get_user)):
        """Reconstruit l'index des versions publiées du tenant (jamais la bibliothèque commune)."""
        from ..core import lexical

        with rag_errors(), factory() as db:
            require_any(roles_of(db, user), {"rag_admin"})
            result = lexical.rebuild_tenant_indexes(db, user.tenant_id, force=force)
            db.commit()
            return result

    # ---------------------------------------------------------- rôles et tenant
    @router.get("/roles")
    def roles(user: User = Depends(get_user)):
        with factory() as db:
            require_role_manager(db, user)
            return [
                {
                    "user_id": row.user_id,
                    "role": row.role,
                    "granted_by": row.granted_by,
                    "granted_at": row.granted_at.isoformat() if row.granted_at else None,
                }
                for row in repository.list_roles(db, user.tenant_id)
            ]

    @router.post("/roles")
    def change_role(body: RoleRequest, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            require_role_manager(db, user)
            if body.grant:
                repository.grant_role(db, user.tenant_id, body.user_id, body.role, user.id)
                changed = True
            else:
                changed = repository.revoke_role(db, user.tenant_id, body.user_id, body.role)
            db.commit()
            return {"changed": changed, "user_id": body.user_id, "role": body.role}

    @router.get("/tenant")
    def tenant_settings(user: User = Depends(get_user)):
        with factory() as db:
            require_role_manager(db, user)
            return {
                "global_mode": settings.rag_mode,
                "max_mode": repository.tenant_max_mode(db, user.tenant_id),
            }

    @router.post("/tenant")
    def set_tenant_mode(body: TenantModeRequest, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            require_role_manager(db, user)
            row = repository.set_tenant_max_mode(
                db, user.tenant_id, body.max_mode, user.id, settings.rag_mode
            )
            db.commit()
            return {"global_mode": settings.rag_mode, "max_mode": row.max_mode}

    @router.get("/search-log")
    def search_log(limit: int = Query(50, ge=1, le=200), user: User = Depends(get_user)):
        with factory() as db:
            require_any(roles_of(db, user), ANY_RAG_ROLE)
            return [
                {
                    "id": row.id,
                    "document_id": row.document_id,
                    "mode": row.mode,
                    "origin": row.origin,
                    "query_sha256": row.query_sha256,
                    "result_ids": row.result_ids or [],
                    "result_count": row.result_count,
                    "referential_versions": row.referential_versions or [],
                    "latency_ms": row.latency_ms,
                    "decision": (row.outcome or {}).get("decision"),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in repository.search_logs(db, user.tenant_id, limit=limit)
            ]

    return router
