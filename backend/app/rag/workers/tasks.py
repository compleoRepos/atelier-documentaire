"""Mode SHADOW : recherche RAG en arrière-plan, sans influence sur la traduction.

* ``execution_mode=celery`` : tâche sur la file Celery distincte ``rag``
  (application Celery « translator-rag », séparée de la file ``documents``).
  Le message ne contient que des identifiants ; le worker relit l'IR, le
  glossaire et la mémoire en base. Envoi sans réessai (``retry=False``) et avec
  expiration : un courtier indisponible ne bloque pas le traitement.
* autres modes : exécuteur à un seul thread dédié, dans le même processus ;
  la traduction n'attend jamais son résultat.

Une erreur de recherche est journalisée par code et n'interrompt rien.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from typing import Any

from ...core.models import Document, GlossaryEntry, MemoryEntry
from ..audit.provenance import write_search_log
from ..config import effective_mode
from ..core.engine import RagEngine
from ..storage import repository

logger = logging.getLogger("app.rag")
QUEUE = "rag"
TASK_NAME = "app.rag.workers.tasks.shadow_search"
_LOCK = threading.Lock()
_EXECUTOR: ThreadPoolExecutor | None = None
_PENDING: set[Future] = set()
_CELERY = None


def celery_app():
    """Application Celery RAG, créée au premier usage (aucun import Celery sinon)."""
    global _CELERY
    with _LOCK:
        if _CELERY is None:
            from celery import Celery

            from ...core.settings import get_settings

            settings = get_settings()
            app = Celery("translator-rag", broker=settings.celery_broker_url)
            app.conf.update(
                task_default_queue=QUEUE,
                task_routes={TASK_NAME: {"queue": QUEUE}},
                task_serializer="json",
                accept_content=["json"],
                task_ignore_result=True,
                worker_prefetch_multiplier=1,
                broker_connection_retry_on_startup=True,
            )
            app.task(name=TASK_NAME)(_celery_shadow_search)
            _CELERY = app
        return _CELERY


def _celery_shadow_search(**job: Any) -> str | None:
    from ...core.db import init_db, make_engine, make_session_factory
    from ...core.settings import get_settings
    from ..bootstrap import ensure_rag_schema

    settings = get_settings()
    engine = make_engine(settings)
    init_db(engine, settings)
    ensure_rag_schema(engine, settings)
    return run_shadow(settings, make_session_factory(engine), job)


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag-shadow")
        return _EXECUTOR


def dispatch_shadow(
    settings: Any, session_factory: Any, job: dict, options: dict | None = None
) -> str:
    """Planifie la recherche et rend la main immédiatement."""
    if getattr(settings, "execution_mode", "inline") == "celery":
        celery_app().send_task(
            TASK_NAME,
            kwargs=dict(job),
            queue=QUEUE,
            expires=int(getattr(settings, "rag_shadow_task_expires_seconds", 3600)),
            retry=False,
        )
        return "celery"
    future = _executor().submit(run_shadow, settings, session_factory, dict(job), options)
    with _LOCK:
        _PENDING.add(future)
    future.add_done_callback(_forget)
    return "thread"


def _forget(future: Future) -> None:
    with _LOCK:
        _PENDING.discard(future)


def wait_for_shadow(timeout: float = 30.0) -> bool:
    """Attend la fin des recherches en cours (tests et lanceur de recette)."""
    with _LOCK:
        pending = list(_PENDING)
    done, not_done = wait_futures(pending, timeout=timeout)
    return not not_done


def _options_from_database(db: Any, tenant_id: str) -> dict:
    glossary = [
        {"source": x.source, "target": x.target, "domain": x.domain}
        for x in db.query(GlossaryEntry)
        .filter_by(tenant_id=tenant_id)
        .order_by(GlossaryEntry.version, GlossaryEntry.id)
        .all()
    ]
    memory = {
        x.source: x.target
        for x in db.query(MemoryEntry)
        .filter_by(tenant_id=tenant_id, validated=True)
        .order_by(MemoryEntry.version, MemoryEntry.id)
        .all()
    }
    return {"glossary": glossary, "memory": memory}


def run_shadow(
    settings: Any,
    session_factory: Any,
    job: dict,
    options: dict | None = None,
    ir: dict | None = None,
) -> str | None:
    """Recherche observée ; écrit une ligne de journal ; ne lève jamais.

    ``ir`` n'est fourni que par le lanceur de recette (IR hors base) ; le worker
    relit toujours l'analyse du document de son tenant.
    """
    started = time.perf_counter()
    tenant_id = str(job.get("tenant_id") or "")
    document_id = job.get("document_id")
    try:
        with session_factory() as db:
            if ir is None:
                doc = db.get(Document, document_id) if document_id else None
                if doc is None or doc.tenant_id != tenant_id:
                    return None
                ir = dict(doc.analysis_json or {})
            elif not tenant_id:
                return None
            tenant_mode = repository.tenant_max_mode(db, tenant_id)
            context_options = dict(options) if options is not None else {}
            if options is None:
                context_options.update(_options_from_database(db, tenant_id))
        effective = effective_mode(
            str(job.get("requested_mode") or "SHADOW"), tenant_mode, str(job.get("engine"))
        )
        if effective.mode == "DISABLED":
            return None
        plan = RagEngine(settings, session_factory).plan(
            tenant_id=tenant_id,
            document_id=document_id,
            ir=ir,
            options=context_options,
            mode="SHADOW",
        )
        audit = plan.audit()
        return write_search_log(
            session_factory,
            tenant_id=tenant_id,
            document_id=document_id,
            mode="SHADOW",
            origin=str(job.get("origin") or "job")[:20],
            query_sha256=plan.query_sha256,
            filters={
                "domain": ir.get("domain"),
                "source_languages": plan.stats.get("source_languages"),
                "target_language": plan.stats.get("target_language"),
            },
            result_ids=audit["candidate_term_ids"],
            result_count=len(audit["candidate_term_ids"]),
            referential_versions=plan.versions,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            outcome={
                "decision": "SHADOW_ONLY",
                "effective_mode": effective.mode,
                "reasons": list(effective.reasons),
                "requested_mode": job.get("requested_mode"),
                "engine": job.get("engine"),
                **audit,
            },
        )
    except Exception as exc:
        logger.warning("rag_shadow_failed", extra={"error": type(exc).__name__})
        return None
