"""LOT 2 — F-L2-01 : SHADOW en mode Celery avec courtier indisponible.

Défaut LOT 1 mesuré : ``send_task`` était appelé sur le chemin critique de la
traduction (6,5 s pour un port refusé, 133,9 s pour un hôte muet). Ces tests
utilisent une vraie application Celery/kombu et de vrais sockets ; seul le
courtier est volontairement inaccessible.
"""

from __future__ import annotations

import threading
import time

import pytest

JOB = {
    "tenant_id": "t",
    "document_id": "d",
    "origin": "job",
    "requested_mode": "SHADOW",
    "engine": "offline",
}


@pytest.fixture
def fresh(monkeypatch):
    """Application Celery neuve, compteurs et disjoncteur remis à zéro."""
    from app.core import settings as settings_module
    from app.rag.workers import tasks

    def install(**values):
        from app.core.settings import Settings

        conf = Settings(execution_mode="celery", **values)
        monkeypatch.setattr(settings_module, "get_settings", lambda: conf)
        monkeypatch.setattr(tasks, "_CELERY", None)
        monkeypatch.setattr(tasks, "_WORKERS", {})
        tasks._STATS.clear()
        tasks.reset_breaker()
        return conf

    yield install
    tasks.reset_breaker()


def test_refused_broker_never_blocks_critical_path(fresh):
    from app.rag.workers import tasks

    conf = fresh(celery_broker_url="redis://127.0.0.1:1/0", rag_shadow_broker_timeout_seconds=1.0)
    begin = time.perf_counter()
    assert tasks.dispatch_shadow(conf, None, dict(JOB), None) == "celery"
    assert time.perf_counter() - begin < 0.05
    assert tasks.wait_for_shadow(15)
    stats = tasks.shadow_stats()
    assert stats["broker_failed"] == 1 and stats["dropped"] == 1
    # Disjoncteur ouvert : aucun contact courtier, réponse immédiate.
    begin = time.perf_counter()
    assert tasks.dispatch_shadow(conf, None, dict(JOB), None) == "dropped"
    assert time.perf_counter() - begin < 0.01
    assert tasks.shadow_stats()["breaker_open"] == 1


def test_silent_host_is_bounded_by_short_timeout(fresh):
    from app.rag.workers import tasks

    conf = fresh(
        celery_broker_url="redis://10.255.255.1:6379/0", rag_shadow_broker_timeout_seconds=0.5
    )
    begin = time.perf_counter()
    assert tasks.dispatch_shadow(conf, None, dict(JOB), None) == "celery"
    assert time.perf_counter() - begin < 0.05
    begin = time.perf_counter()
    assert tasks.wait_for_shadow(20)
    assert time.perf_counter() - begin < 5.0  # délai court respecté (avant : 133,9 s)
    assert tasks.shadow_stats()["broker_failed"] == 1


def test_local_strategy_runs_search_in_bounded_thread(fresh, monkeypatch):
    from app.rag.workers import tasks

    conf = fresh(celery_broker_url="redis://127.0.0.1:1/0", rag_shadow_on_broker_failure="local")
    ran = []
    monkeypatch.setattr(
        tasks, "run_shadow", lambda *a, **k: ran.append(threading.current_thread().name)
    )
    assert tasks.dispatch_shadow(conf, None, dict(JOB), None) == "celery"
    assert tasks.wait_for_shadow(15)
    assert tasks.dispatch_shadow(conf, None, dict(JOB), None) == "thread"  # disjoncteur ouvert
    assert tasks.wait_for_shadow(5)
    assert ran == ["rag-shadow-local", "rag-shadow-local"]


def test_full_publisher_queue_drops_without_blocking(fresh, monkeypatch):
    from app.rag.workers import tasks

    conf = fresh(celery_broker_url="redis://127.0.0.1:1/0", rag_shadow_queue_max=2)
    gate = threading.Event()
    monkeypatch.setattr(tasks, "_publish", lambda *a: gate.wait(10))
    results = []
    for _ in range(6):
        begin = time.perf_counter()
        results.append(tasks.dispatch_shadow(conf, None, dict(JOB), None))
        assert time.perf_counter() - begin < 0.05
    gate.set()
    assert tasks.wait_for_shadow(10)
    # Une publication en cours + deux en file ; les suivantes sont perdues et comptées.
    assert results.count("celery") in (2, 3) and "dropped" in results
    assert tasks.shadow_stats()["publisher_queue_full"] == results.count("dropped")


def test_integration_point_unchanged_options_with_dead_broker(fresh):
    from app.core.settings import Settings
    from app.rag.integration import augment_options as integration
    from app.rag.workers import tasks

    fresh(celery_broker_url="redis://10.255.255.1:6379/0", rag_shadow_broker_timeout_seconds=0.5)
    settings = Settings(
        rag_mode="SHADOW", execution_mode="celery", celery_broker_url="redis://10.255.255.1:6379/0"
    )
    options = {"glossary": [], "target_language": "fr"}
    reports = []
    begin = time.perf_counter()
    result = integration.augment_options(
        settings=settings,
        session_factory=None,
        tenant_id="t",
        document_id="d",
        ir={"pages": []},
        options=options,
        on_report=reports.append,
    )
    assert time.perf_counter() - begin < 0.2
    assert result is options
    assert reports[0]["decision"] == "SHADOW_DISPATCHED" and reports[0]["dispatch"] == "celery"
    assert tasks.wait_for_shadow(20)


def test_publisher_logs_carry_no_document_data(fresh, caplog):
    import logging

    from app.rag.workers import tasks

    # Les tests de migration exécutent fileConfig d'Alembic, qui désactive les
    # journaux déjà créés : sans cette remise en état, rien ne serait capturé.
    for name, item in list(logging.root.manager.loggerDict.items()):
        if name.startswith("app.rag") and isinstance(item, logging.Logger):
            item.disabled = False
    conf = fresh(celery_broker_url="redis://127.0.0.1:1/0")
    job = dict(JOB, tenant_id="tenant-secret-xyz", document_id="doc-secret-xyz")
    with caplog.at_level("DEBUG", logger="app.rag"):
        tasks.dispatch_shadow(
            conf, None, job, {"glossary": [{"source": "terme secret", "target": "x"}]}
        )
        assert tasks.wait_for_shadow(15)
    dumped = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert "rag_shadow_broker_unavailable" in dumped
    for secret in ("secret", "127.0.0.1"):
        assert secret not in dumped
