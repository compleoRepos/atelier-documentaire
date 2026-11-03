from __future__ import annotations

import logging
import time

from celery import Celery
from celery.signals import worker_ready

from ..application.jobs import recover_lost_tasks, run_analyze, run_translate
from ..core.db import init_db, make_engine, make_session_factory
from ..core.settings import get_settings
from ..infrastructure.storage import make_storage

settings = get_settings()
celery_app = Celery(
    "translator", broker=settings.celery_broker_url, backend=settings.celery_broker_url
)
celery_app.conf.update(
    task_default_queue="documents",
    task_routes={"app.workers.tasks.execute": {"queue": "documents"}},
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_soft_time_limit=settings.job_soft_timeout_seconds,
    task_time_limit=settings.job_hard_timeout_seconds,
    broker_connection_retry_on_startup=True,
)


def enqueue(name: str, document_id: str, tenant_id: str, actor_id: str | None = None):
    return celery_app.send_task(
        "app.workers.tasks.execute",
        args=[name, document_id, tenant_id, actor_id],
        queue="documents",
    )


# LOT 2.3 D-OPS-01 : documents orphelins (tâche perdue) passés en FAILED / TASK_LOST,
# au démarrage du worker puis au plus une fois toutes les 5 minutes par processus.
LOST_TASK_SWEEP_INTERVAL_SECONDS = 300
_last_sweep = [float("-inf")]


def sweep_lost_tasks(factory) -> list[str]:
    if time.monotonic() - _last_sweep[0] < LOST_TASK_SWEEP_INTERVAL_SECONDS:
        return []
    _last_sweep[0] = time.monotonic()
    try:
        return recover_lost_tasks(factory, settings)
    except Exception as exc:  # never blocks the task itself
        logging.getLogger("translator.jobs").warning(
            "TASK_LOST_SWEEP_FAILED %s", type(exc).__name__
        )
        return []


@worker_ready.connect
def _sweep_on_worker_ready(**_kwargs):
    engine = make_engine(settings)
    init_db(engine, settings)
    sweep_lost_tasks(make_session_factory(engine))


@celery_app.task(name="app.workers.tasks.execute")
def execute(name: str, document_id: str, tenant_id: str, actor_id: str | None = None):
    engine = make_engine(settings)
    init_db(engine, settings)
    factory = make_session_factory(engine)
    storage = make_storage(settings)
    sweep_lost_tasks(factory)
    fn = {"run_analyze": run_analyze, "run_translate": run_translate}.get(name)
    if not fn:
        raise ValueError("job inconnu")
    return fn(document_id, tenant_id, factory, storage, settings, actor_id)
