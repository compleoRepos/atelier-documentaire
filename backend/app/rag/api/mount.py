"""Montage des routeurs RAG dans l'application FastAPI existante.

Appelé par ``app.main.create_app`` seulement si ``rag_mode != DISABLED`` ou
``rag_admin_enabled`` : en DISABLED sans administration, rien n'est importé ni
monté et le schéma OpenAPI est strictement celui de l'existant.
"""

from __future__ import annotations

from typing import Any

from ..bootstrap import ensure_rag_schema
from .routes import create_rag_router


def mount_rag(app: Any, factory: Any, engine: Any, settings: Any) -> list[str]:
    ensure_rag_schema(engine, settings)
    mounted = ["/api/rag"]
    app.include_router(create_rag_router(factory, settings))
    if settings.rag_admin_enabled:
        from .admin_routes import create_rag_admin_router

        app.include_router(create_rag_admin_router(factory, settings))
        mounted.append("/api/rag-admin")
    app.state.rag_mounted = tuple(mounted)
    return mounted
