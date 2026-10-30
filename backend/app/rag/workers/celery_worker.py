"""Point d'entrée du worker de la file ``rag``.

celery -A app.rag.workers.celery_worker:app worker -Q rag --concurrency 1
"""

from __future__ import annotations

from .tasks import celery_app

app = celery_app()
