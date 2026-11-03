"""LOT 2.3 Phase B — D-ENG-01 (délai moteur réglable) et D-OPS-01 (tâches perdues).

D-ENG-01 : le délai d'un appel au moteur était fixé à 60 s dans le code ; il est désormais
réglable (``TRANSLATOR_PRIVATE_AI_TIMEOUT_SECONDS``), défaut inchangé, et atteint le
moteur par le vrai chemin ``run_translate``.

D-OPS-01 : un document resté ANALYZING/TRANSLATING au-delà du délai dur de tâche ne peut
plus avoir de tâche vivante ; il devient FAILED / TASK_LOST, audité et relançable.
"""

from __future__ import annotations

from datetime import timedelta

import fitz
import pytest
from sqlalchemy import select, update

from .conftest import login


def _pdf(text: str = "Bonjour chantier 1234") -> bytes:
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.insert_text((20, 40), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def _upload(client, headers) -> str:
    response = client.post(
        "/api/documents", headers=headers, files={"file": ("s.pdf", _pdf(), "application/pdf")}
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _capture_options(monkeypatch):
    from app.application import jobs

    seen: list[dict] = []
    original = jobs._call_translate

    def spy(ir, work, options):
        seen.append(dict(options))
        return original(ir, work, options)

    monkeypatch.setattr(jobs, "_call_translate", spy)
    return seen


def test_engine_timeout_default_is_the_historical_60_seconds(client, monkeypatch):
    seen = _capture_options(monkeypatch)
    headers = login(client, "admin-a", "Admin-A-password-12")
    doc_id = _upload(client, headers)
    assert client.post(f"/api/documents/{doc_id}/translate", headers=headers).status_code == 200
    assert seen and seen[-1]["timeout"] == 60.0


def test_engine_timeout_is_configurable_end_to_end(app_env, monkeypatch):
    monkeypatch.setenv("TRANSLATOR_PRIVATE_AI_TIMEOUT_SECONDS", "900")
    from app.core.settings import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.core.models import Tenant, User
    from app.core.security import hash_password
    from app.main import create_app

    app = create_app()
    with app.state.session_factory() as db:
        tenant = Tenant(name="tenant-t")
        db.add(tenant)
        db.flush()
        db.add(
            User(
                username="admin-t",
                password_hash=hash_password("Admin-T-password-12"),
                tenant_id=tenant.id,
                role="admin",
            )
        )
        db.commit()
    client = TestClient(app)
    seen = _capture_options(monkeypatch)
    headers = login(client, "admin-t", "Admin-T-password-12")
    doc_id = _upload(client, headers)
    assert client.post(f"/api/documents/{doc_id}/translate", headers=headers).status_code == 200
    assert seen and seen[-1]["timeout"] == 900.0


@pytest.mark.parametrize(
    "values",
    [
        {"private_ai_timeout_seconds": 0},
        {"private_ai_timeout_seconds": -5},
        {"private_ai_timeout_seconds": 3601},
        {"private_ai_timeout_seconds": 1800},  # = délai souple par défaut : refusé
    ],
)
def test_engine_timeout_out_of_contract_is_rejected(values):
    from app.core.settings import Settings

    with pytest.raises(ValueError):
        Settings(**values)


def _age(factory, doc_id: str, status: str, seconds: int) -> None:
    from app.core.models import Document, now_utc

    with factory() as db:
        db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status=status, updated_at=now_utc() - timedelta(seconds=seconds))
        )
        db.commit()


def test_lost_tasks_become_failed_task_lost_and_are_relaunchable(client):
    from app.application.jobs import TASK_LOST_CODE, recover_lost_tasks
    from app.core.models import AuditEvent
    from app.core.settings import get_settings

    settings = get_settings()
    factory = client.app.state.session_factory
    headers = login(client, "admin-a", "Admin-A-password-12")
    lost_analysis, lost_translation, live, finished = (_upload(client, headers) for _ in range(4))
    hard = settings.job_hard_timeout_seconds
    _age(factory, lost_analysis, "ANALYZING", hard + 600)
    _age(factory, lost_translation, "TRANSLATING", hard + 600)
    _age(factory, live, "TRANSLATING", hard - 60)  # tâche encore possiblement vivante
    _age(factory, finished, "REVIEW_REQUIRED", hard + 600)  # statut terminal : intact

    recovered = recover_lost_tasks(factory, settings)
    assert sorted(recovered) == sorted([lost_analysis, lost_translation])
    assert recover_lost_tasks(factory, settings) == []  # idempotent

    def detail(doc_id):
        return client.get(f"/api/documents/{doc_id}", headers=headers).json()

    for doc_id in (lost_analysis, lost_translation):
        body = detail(doc_id)
        assert body["status"] == "FAILED"
        assert [issue["code"] for issue in body["issues"]] == [TASK_LOST_CODE]
    assert detail(live)["status"] == "TRANSLATING"
    assert detail(finished)["status"] == "REVIEW_REQUIRED"
    with factory() as db:
        actions = db.scalars(
            select(AuditEvent.action).where(AuditEvent.document_id == lost_translation)
        ).all()
    assert "DOCUMENT_TASK_LOST" in actions

    # Relance par la route existante : l'analyse repart depuis FAILED.
    assert (
        client.post(f"/api/documents/{lost_analysis}/analyze", headers=headers).status_code == 200
    )
    assert detail(lost_analysis)["status"] == "ANALYZED"


def test_worker_sweep_is_rate_limited_and_never_raises(monkeypatch):
    from app.workers import tasks

    calls: list[int] = []
    monkeypatch.setattr(
        tasks, "recover_lost_tasks", lambda factory, settings: calls.append(1) or []
    )
    monkeypatch.setattr(tasks, "_last_sweep", [float("-inf")])
    tasks.sweep_lost_tasks(object())
    tasks.sweep_lost_tasks(object())
    assert calls == [1]

    def broken(factory, settings):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(tasks, "recover_lost_tasks", broken)
    monkeypatch.setattr(tasks, "_last_sweep", [float("-inf")])
    assert tasks.sweep_lost_tasks(object()) == []
