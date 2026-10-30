"""Dépendances communes des routes RAG.

L'authentification réutilise ``core.security.current_user_factory`` (jeton,
cookie + CSRF, tenant, révocation) : aucune règle d'accès existante n'est
dupliquée ni assouplie. Les droits RAG viennent de la table indépendante
``rag_role_assignments``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from ..storage.repository import RagAccessError

ANY_RAG_ROLE = frozenset({"rag_admin", "terminology_manager", "legal_manager", "reader"})
# Rôles applicatifs existants autorisés à déclarer/valider un contexte documentaire.
CONTEXT_APP_ROLES = frozenset({"reviewer", "admin"})


@contextmanager
def rag_errors() -> Iterator[None]:
    try:
        yield
    except RagAccessError as exc:
        raise HTTPException(exc.status, exc.code) from None
    except ValueError as exc:
        code = str(exc) if str(exc).startswith("RAG_") else "RAG_INVALID_REQUEST"
        raise HTTPException(422, code) from None


def require_any(roles: Iterable[str], allowed: Iterable[str], code: str = "RAG_ROLE_REQUIRED"):
    if not set(roles) & set(allowed):
        raise HTTPException(403, code)
