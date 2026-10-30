"""Création des tables RAG hors Alembic (mode ``auto_create_schema`` uniquement).

En production (``auto_create_schema=false``), seule la migration ``0003_rag``
crée ces tables ; ``init_db`` vérifie déjà que la base est à la révision head.
"""

from __future__ import annotations

from typing import Any

from .models import rag_table_objects


def ensure_rag_schema(engine: Any, settings: Any) -> bool:
    if not getattr(settings, "auto_create_schema", False):
        return False
    from ..core.db import Base

    Base.metadata.create_all(engine, tables=rag_table_objects())
    return True
