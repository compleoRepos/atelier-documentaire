"""Mode SHADOW : recherche RAG en arrière-plan, sans influence sur la traduction.

* ``execution_mode=celery`` : tâche sur la file Celery distincte ``rag``
  (application Celery « translator-rag », séparée de la file ``documents``).
  Le message ne contient que des identifiants ; le worker relit l'IR, le
  glossaire et la mémoire en base. Le chemin critique ne contacte JAMAIS le
  courtier : il dépose la publication dans une file bornée lue par un thread
  éditeur démon. L'éditeur publie sans réessai, avec des délais de connexion
  courts ; un échec ouvre un disjoncteur (aucun contact pendant
  ``rag_shadow_breaker_seconds``) et applique la stratégie
  ``rag_shadow_on_broker_failure`` : ``drop`` (observation perdue, comptée) ou
  ``local`` (recherche dans le thread local borné).
* autres modes : un seul thread local démon et une file bornée, dans le même
  processus ; la traduction n'attend jamais son résultat.

Limites assumées du thread local (documentées) : il partage le processus et le
GIL avec le traitement ; une file pleine fait perdre l'observation (comptée) ;
les observations en attente sont perdues à l'arrêt du processus (thread démon,
aucune attente à la sortie) ; il n'y a ni persistance ni reprise.

Une erreur de recherche est journalisée par code et n'interrompt rien.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import Counter
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
_CELERY = None
_STATS: Counter = Counter()
_BREAKER_UNTIL = 0.0


class _BoundedWorker:
    """Un thread démon et une file bornée ; ``submit`` ne bloque jamais."""

    def __init__(self, name: str, maxsize: int) -> None:
        self.name = name
        self.queue: queue.Queue = queue.Queue(maxsize=max(1, int(maxsize)))
        self._idle = threading.Condition()
        self._busy = 0
        self._thread = threading.Thread(target=self._loop, name=name, daemon=True)
        self._thread.start()

    def submit(self, fn, *args) -> bool:
        with self._idle:
            try:
                self.queue.put_nowait((fn, args))
            except queue.Full:
                return False
            self._busy += 1
        return True

    def _loop(self) -> None:
        while True:
            fn, args = self.queue.get()
            try:
                fn(*args)
            except Exception as exc:  # jamais propagé : observation seulement
                logger.warning("rag_worker_failed", extra={"error": type(exc).__name__})
            finally:
                with self._idle:
                    self._busy -= 1
                    self._idle.notify_all()

    def wait(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._idle:
            while self._busy:
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                self._idle.wait(left)
        return True


_WORKERS: dict[str, _BoundedWorker] = {}


def _worker(kind: str, settings: Any) -> _BoundedWorker:
    with _LOCK:
        worker = _WORKERS.get(kind)
        if worker is None:
            size = int(getattr(settings, "rag_shadow_queue_max", 64))
            worker = _WORKERS[kind] = _BoundedWorker(f"rag-shadow-{kind}", size)
        return worker


def shadow_stats() -> dict[str, int]:
    """Compteurs de répartition (aucun texte, aucun identifiant)."""
    with _LOCK:
        return dict(_STATS)


def _count(key: str) -> None:
    with _LOCK:
        _STATS[key] += 1


def _broker_options(timeout: float) -> dict[str, Any]:
    """Délais courts et aucun réessai pour l'éditeur (jamais le chemin critique)."""
    return {
        "broker_connection_timeout": timeout,
        "broker_connection_retry": False,
        "broker_connection_max_retries": 0,
        "broker_transport_options": {
            "max_retries": 0,
            "socket_timeout": timeout,
            "socket_connect_timeout": timeout,
        },
    }


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


def _publisher_app(settings: Any):
    """Application d'envoi : même routage, délais courts (le worker garde les siens)."""
    app = celery_app()
    if not getattr(app, "_rag_publisher_configured", False):
        timeout = float(getattr(settings, "rag_shadow_broker_timeout_seconds", 2.0))
        try:
            app.conf.update(_broker_options(timeout))
        except Exception:  # application de test sans configuration
            pass
        app._rag_publisher_configured = True
    return app


def _celery_shadow_search(**job: Any) -> str | None:
    from ...core.db import init_db, make_engine, make_session_factory
    from ...core.settings import get_settings
    from ..bootstrap import ensure_rag_schema

    settings = get_settings()
    engine = make_engine(settings)
    init_db(engine, settings)
    ensure_rag_schema(engine, settings)
    return run_shadow(settings, make_session_factory(engine), job)


def dispatch_shadow(
    settings: Any, session_factory: Any, job: dict, options: dict | None = None
) -> str:
    """Planifie la recherche et rend la main immédiatement (jamais d'E/S réseau)."""
    if getattr(settings, "execution_mode", "inline") == "celery":
        if time.monotonic() < _BREAKER_UNTIL:
            _count("breaker_open")
            return _degrade(settings, session_factory, job, options)
        publish = (settings, session_factory, dict(job), options)
        if _worker("publisher", settings).submit(_publish, *publish):
            _count("celery_queued")
            return "celery"
        _count("publisher_queue_full")
        return _degrade(settings, session_factory, job, options)
    return _local(settings, session_factory, job, options)


def _local(settings: Any, session_factory: Any, job: dict, options: dict | None) -> str:
    if _worker("local", settings).submit(run_shadow, settings, session_factory, dict(job), options):
        _count("thread_queued")
        return "thread"
    _count("thread_queue_full")
    return "dropped"


def _degrade(settings: Any, session_factory: Any, job: dict, options: dict | None) -> str:
    if getattr(settings, "rag_shadow_on_broker_failure", "drop") == "local":
        return _local(settings, session_factory, job, options)
    _count("dropped")
    return "dropped"


def _publish(settings: Any, session_factory: Any, job: dict, options: dict | None) -> None:
    """Exécuté par le thread éditeur : seul endroit qui contacte le courtier."""
    global _BREAKER_UNTIL
    started = time.perf_counter()
    try:
        _publisher_app(settings).send_task(
            TASK_NAME,
            kwargs=dict(job),
            queue=QUEUE,
            expires=int(getattr(settings, "rag_shadow_task_expires_seconds", 3600)),
            retry=False,
        )
        _count("celery_published")
    except Exception as exc:
        with _LOCK:
            _BREAKER_UNTIL = time.monotonic() + int(
                getattr(settings, "rag_shadow_breaker_seconds", 60)
            )
            _STATS["broker_failed"] += 1
        logger.warning(
            "rag_shadow_broker_unavailable",
            extra={
                "error": type(exc).__name__,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "strategy": getattr(settings, "rag_shadow_on_broker_failure", "drop"),
            },
        )
        _degrade(settings, session_factory, job, options)


def reset_breaker() -> None:
    """Referme le disjoncteur (tests et exploitation)."""
    global _BREAKER_UNTIL
    with _LOCK:
        _BREAKER_UNTIL = 0.0


def wait_for_shadow(timeout: float = 30.0) -> bool:
    """Attend la fin des publications et recherches en cours (tests, recette)."""
    deadline = time.monotonic() + timeout
    with _LOCK:
        workers = [_WORKERS[k] for k in ("publisher", "local") if k in _WORKERS]
    return all(w.wait(max(0.0, deadline - time.monotonic())) for w in workers)


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
