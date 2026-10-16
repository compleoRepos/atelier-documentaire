from __future__ import annotations

from unittest.mock import Mock


def test_publisher_and_worker_share_the_documents_queue():
    from app.workers.tasks import celery_app

    assert celery_app.conf.task_default_queue == "documents"
    assert celery_app.conf.task_routes["app.workers.tasks.execute"]["queue"] == "documents"
    assert celery_app.conf.accept_content == ["json"]


def test_actor_is_published_with_the_document_and_tenant(monkeypatch):
    from app.workers import tasks

    sender = Mock()
    monkeypatch.setattr(tasks.celery_app, "send_task", sender)
    tasks.enqueue("run_analyze", "synthetic-document", "synthetic-tenant", "synthetic-user")
    sender.assert_called_once_with(
        "app.workers.tasks.execute",
        args=["run_analyze", "synthetic-document", "synthetic-tenant", "synthetic-user"],
        queue="documents",
    )
