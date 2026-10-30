"""Traçabilité des recherches RAG.

Le journal ``rag_search_log`` ne contient jamais de texte de document ni de
requête : seulement une empreinte HMAC-SHA256 (clé dérivée du secret de
l'application, ce qui empêche un lecteur de la base de retrouver un texte court
par dictionnaire), les identifiants d'entrées, le tenant, les versions de
référentiel, le mode, les compteurs, la latence et l'origine.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections.abc import Iterable
from typing import Any

from sqlalchemy.exc import OperationalError

from ..storage import repository

logger = logging.getLogger("app.rag")
PROVENANCE_VERSION = "rag-provenance-1"


def _key(settings: Any) -> bytes:
    secret = str(getattr(settings, "jwt_secret", "") or "")
    return hashlib.sha256(b"dice-query-fingerprint-v1|" + secret.encode("utf-8")).digest()


def query_fingerprint(settings: Any, tenant_id: str, mode: str, parts: Iterable[str]) -> str:
    digest = hmac.new(_key(settings), digestmod=hashlib.sha256)
    for part in (PROVENANCE_VERSION, str(tenant_id), str(mode), *parts):
        data = str(part).encode("utf-8")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def write_search_log(session_factory: Any, **fields: Any) -> str | None:
    """Écrit une ligne de journal dans une session dédiée ; ne lève jamais."""
    for attempt in range(3):
        try:
            with session_factory() as db:
                row = repository.add_search_log(db, **fields)
                db.commit()
                return row.id
        except OperationalError:
            time.sleep(0.05 * (attempt + 1))
        except Exception as exc:  # pragma: no cover - défense : jamais bloquant
            logger.warning("rag_search_log_failed", extra={"error": type(exc).__name__})
            return None
    logger.warning("rag_search_log_failed", extra={"error": "OperationalError"})
    return None
