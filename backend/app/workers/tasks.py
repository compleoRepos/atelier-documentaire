from __future__ import annotations

from celery import Celery

from ..application.jobs import run_analyze, run_translate
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


@celery_app.task(name="app.workers.tasks.execute")
def execute(name: str, document_id: str, tenant_id: str, actor_id: str | None = None):
    engine = make_engine(settings)
    init_db(engine, settings)
    factory = make_session_factory(engine)
    storage = make_storage(settings)
    fn = {"run_analyze": run_analyze, "run_translate": run_translate}.get(name)
    if not fn:
        raise ValueError("job inconnu")
    return fn(document_id, tenant_id, factory, storage, settings, actor_id)
