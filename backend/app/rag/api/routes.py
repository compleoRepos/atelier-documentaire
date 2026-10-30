# ruff: noqa: B008
"""Routes ``/api/rag/*`` (GET/POST uniquement, comme la politique CORS existante)."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...core.models import GlossaryEntry, User
from ...core.security import current_user_factory
from ..audit.explanation import explain_document
from ..audit.provenance import write_search_log
from ..config import effective_mode, token_budget
from ..core.engine import RagEngine
from ..schemas import DocumentContextRequest, SearchRequest
from ..storage import repository
from .deps import ANY_RAG_ROLE, CONTEXT_APP_ROLES, rag_errors, require_any


def _context_view(row: Any) -> dict[str, Any]:
    if row is None:
        return {"status": "none"}
    return {
        "status": row.status,
        "source_language": row.source_language,
        "target_language": row.target_language,
        "source_country": row.source_country,
        "target_country": row.target_country,
        "jurisdiction": row.jurisdiction,
        "document_date": row.document_date.isoformat() if row.document_date else None,
        "legal_reference_date": (
            row.legal_reference_date.isoformat() if row.legal_reference_date else None
        ),
        "origins": row.origins or {},
        "declared_by": row.declared_by,
        "declared_at": row.declared_at.isoformat() if row.declared_at else None,
        "validated_by": row.validated_by,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
    }


def create_rag_router(factory, settings) -> APIRouter:
    router = APIRouter(prefix="/api/rag", tags=["rag"])
    get_user = current_user_factory(factory)

    @router.get("/status")
    def status(user: User = Depends(get_user)):
        with factory() as db:
            tenant_mode = repository.tenant_max_mode(db, user.tenant_id)
            roles = repository.user_roles(db, user.tenant_id, user.id)
        effective = effective_mode(settings.rag_mode, tenant_mode, settings.engine)
        return {
            "global_mode": settings.rag_mode,
            "tenant_max_mode": tenant_mode,
            "engine": settings.engine,
            "effective_mode": effective.mode,
            "reasons": list(effective.reasons),
            "admin_enabled": settings.rag_admin_enabled,
            "budgets": {
                "ASSISTED": token_budget("ASSISTED", settings),
                "ACTIVE": token_budget("ACTIVE", settings),
            },
            "max_entries": settings.rag_max_entries,
            "roles": sorted(roles),
            "human_review_required": True,
        }

    @router.get("/documents/{doc_id}/context")
    def get_context(doc_id: str, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            repository.tenant_document(db, user.tenant_id, doc_id)
            return _context_view(repository.document_context(db, user.tenant_id, doc_id))

    @router.post("/documents/{doc_id}/context")
    def declare_context(doc_id: str, body: DocumentContextRequest, user: User = Depends(get_user)):
        require_any({user.role}, CONTEXT_APP_ROLES)
        with rag_errors(), factory() as db:
            values = body.model_dump()
            for name in ("source_country", "target_country"):
                if values.get(name):
                    values[name] = str(values[name]).upper()
            row = repository.declare_document_context(db, user.tenant_id, doc_id, values, user.id)
            db.commit()
            return _context_view(row)

    @router.post("/documents/{doc_id}/context/validate")
    def validate_context(doc_id: str, user: User = Depends(get_user)):
        require_any({user.role}, CONTEXT_APP_ROLES)
        with rag_errors(), factory() as db:
            repository.tenant_document(db, user.tenant_id, doc_id)
            row = repository.validate_document_context(db, user.tenant_id, doc_id, user.id)
            db.commit()
            return _context_view(row)

    @router.get("/documents/{doc_id}/explanation")
    def explanation(doc_id: str, user: User = Depends(get_user)):
        with rag_errors(), factory() as db:
            return explain_document(db, user.tenant_id, doc_id)

    @router.post("/search")
    def search(body: SearchRequest, user: User = Depends(get_user)):
        started = time.perf_counter()
        with factory() as db:
            roles = repository.user_roles(db, user.tenant_id, user.id)
            glossary = [
                {"source": x.source, "target": x.target}
                for x in db.query(GlossaryEntry).filter_by(tenant_id=user.tenant_id).all()
            ]
        if not roles & ANY_RAG_ROLE and user.role not in CONTEXT_APP_ROLES:
            raise HTTPException(403, "RAG_ROLE_REQUIRED")
        with rag_errors():
            result = RagEngine(settings, factory).search(
                tenant_id=user.tenant_id,
                text=body.text,
                source_language=body.source_language,
                target_language=body.target_language,
                domain=body.domain,
                glossary=glossary,
                limit=body.limit,
            )
        write_search_log(
            factory,
            tenant_id=user.tenant_id,
            document_id=None,
            mode="SEARCH",
            origin="api",
            query_sha256=result["query_sha256"],
            filters={
                "domain": body.domain,
                "source_languages": [body.source_language],
                "target_language": body.target_language,
            },
            result_ids=[item["id"] for item in result["results"]],
            result_count=len(result["results"]),
            referential_versions=result["versions"],
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            outcome={"decision": "SEARCH", "exclusion_reasons": result["exclusion_reasons"]},
        )
        return result

    return router
