"""DICE (RAG) LOT 1 — le mode SHADOW n'influence ni le résultat ni le chemin critique."""

from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache

import fitz

from .rag_support import headers, make_rag_client, publish_referential

SOURCE_TEXT = "Gross salary and notice period 1234. Pay slip reference 9876."
_VOLATILE = {"id", "created_at", "timings", "stages", "_tenant", "_data", "_pixels"}


@lru_cache(maxsize=4)
def make_pdf(text: str) -> bytes:
    """Octets générés une seule fois : les variantes A et B reçoivent le même fichier."""
    document = fitz.open()
    page = document.new_page(width=420, height=220)
    page.insert_text((20, 45), text, fontsize=11)
    data = document.tobytes()
    document.close()
    return data


def upload_pdf(client, username: str, text: str = SOURCE_TEXT) -> str:
    response = client.post(
        "/api/documents",
        headers=headers(client, username),
        files={"file": ("synthetique.pdf", make_pdf(text), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _without_latency(value):
    if isinstance(value, dict):
        return {k: _without_latency(v) for k, v in value.items() if k != "latency_ms"}
    if isinstance(value, list):
        return [_without_latency(v) for v in value]
    return value


def _normalized(detail: dict) -> str:
    """Tout sauf identifiants, horodatages, latences mesurées et dossier de données."""
    kept = {key: value for key, value in detail.items() if key not in _VOLATILE}
    text = json.dumps(_without_latency(kept), sort_keys=True, ensure_ascii=False)
    text = text.replace(detail["id"], "DOC").replace(detail["_data"], "DATA")
    # L'identifiant du tenant (clé de stockage) diffère entre deux bases.
    return text.replace(detail["_tenant"], "TENANT")


def _page_images(detail: dict) -> list[str]:
    """Empreintes des pixels de chaque page du PDF candidat produit (API)."""
    assert detail["_pixels"], "aucune page rendue"
    return detail["_pixels"]


def _candidate_pixels(client, doc_id: str, username: str) -> list[str]:
    response = client.get(
        f"/api/documents/{doc_id}/artifact/candidate", headers=headers(client, username)
    )
    assert response.status_code == 200, response.text
    document = fitz.open(stream=response.content, filetype="pdf")
    try:
        return [hashlib.sha256(page.get_pixmap(dpi=100).samples).hexdigest() for page in document]
    finally:
        document.close()


def _translate(monkeypatch, tmp_path, label: str, mode: str, *, seed: bool, engine=None):
    from app.rag.workers.tasks import wait_for_shadow

    monkeypatch.setenv("TRANSLATOR_DATABASE_URL", f"sqlite:///{tmp_path / (label + '.db')}")
    monkeypatch.setenv("TRANSLATOR_DATA_DIR", str(tmp_path / label))
    client, app, ids = make_rag_client(
        monkeypatch, mode=mode, admin=mode != "DISABLED", engine=engine
    )
    if seed:
        publish_referential(client, ids, max_mode="SHADOW" if mode == "SHADOW" else mode)
    doc_id = upload_pdf(client, "admin-a")
    response = client.post(f"/api/documents/{doc_id}/translate", headers=headers(client, "admin-a"))
    assert response.status_code == 200, response.text
    assert wait_for_shadow(30)
    detail = client.get(f"/api/documents/{doc_id}", headers=headers(client, "admin-a")).json()
    detail["_tenant"] = ids["tenant-a"]
    detail["_data"] = str(tmp_path / label)
    detail["_pixels"] = _candidate_pixels(client, doc_id, "admin-a")
    return client, app, ids, detail


def test_shadow_translation_is_identical_to_disabled(app_env, monkeypatch):
    _, _, _, disabled = _translate(monkeypatch, app_env, "a", "DISABLED", seed=False)
    client, _, _, shadow = _translate(monkeypatch, app_env, "b", "SHADOW", seed=True)
    assert disabled["translation"], "la traduction de référence doit exister"
    assert _normalized(shadow) == _normalized(disabled)
    assert _page_images(shadow) == _page_images(disabled)
    # La recherche a bien eu lieu en arrière-plan, et rien n'a été injecté.
    log = client.get("/api/rag-admin/search-log", headers=headers(client, "admin-a")).json()
    assert [row["decision"] for row in log] == ["SHADOW_ONLY"]
    assert log[0]["result_count"] == 3
    dumped = json.dumps(log, ensure_ascii=False).lower()
    for word in ("gross salary", "notice period", "pay slip", "salaire", "1234", "9876"):
        assert word not in dumped


def test_assisted_with_offline_engine_is_capped_to_shadow(app_env, monkeypatch):
    _, _, _, disabled = _translate(monkeypatch, app_env, "a", "DISABLED", seed=False)
    client, _, _, assisted = _translate(monkeypatch, app_env, "c", "ASSISTED", seed=True)
    assert _normalized(assisted) == _normalized(disabled)
    assert _page_images(assisted) == _page_images(disabled)
    log = client.get("/api/rag-admin/search-log", headers=headers(client, "admin-a")).json()
    assert [row["decision"] for row in log] == ["SHADOW_ONLY"]


def test_shadow_dispatch_returns_before_the_search_finishes(app_env, monkeypatch):
    from app.core.settings import Settings
    from app.rag.integration import augment_options as integration
    from app.rag.workers import tasks

    started = []

    def slow_search(*args, **kwargs):
        started.append(time.perf_counter())
        time.sleep(1.0)

    monkeypatch.setattr(tasks, "run_shadow", slow_search)
    options = {"glossary": [], "memory": {}, "target_language": "fr"}
    reports = []
    begin = time.perf_counter()
    result = integration.augment_options(
        settings=Settings(rag_mode="SHADOW"),
        session_factory=None,
        tenant_id="t",
        document_id="d",
        ir={"pages": []},
        options=options,
        on_report=reports.append,
    )
    elapsed = time.perf_counter() - begin
    assert result is options
    assert elapsed < 0.2, elapsed
    assert reports[0]["decision"] == "SHADOW_DISPATCHED"
    assert reports[0]["dispatch"] == "thread"
    assert tasks.wait_for_shadow(5)
    assert started


def test_rag_errors_never_interrupt_translation(app_env, monkeypatch):
    from app.core.settings import Settings
    from app.rag.core.engine import RagEngine
    from app.rag.integration import augment_options as integration
    from app.rag.workers import tasks

    def broken(*args, **kwargs):
        raise RuntimeError("panne simulée")

    options = {"glossary": [], "target_language": "fr"}
    reports = []
    result = integration.augment_options(
        settings=Settings(rag_mode="SHADOW"),
        session_factory=None,
        tenant_id="t",
        document_id="d",
        ir={},
        options=options,
        on_report=reports.append,
        shadow_dispatch=broken,
    )
    assert result is options
    assert reports[0]["decision"] == "ERROR_FAIL_SAFE"
    assert tasks.run_shadow(Settings(), broken, {"tenant_id": "t", "document_id": "d"}) is None
    # Bout en bout : une recherche qui plante ne change pas la traduction.
    _, _, _, reference = _translate(monkeypatch, app_env, "a", "DISABLED", seed=False)
    monkeypatch.setattr(RagEngine, "plan", broken)
    _, _, _, shadow = _translate(monkeypatch, app_env, "b", "SHADOW", seed=True)
    assert _normalized(shadow) == _normalized(reference)
    assert _page_images(shadow) == _page_images(reference)


def test_celery_dispatch_uses_rag_queue_and_carries_no_text(monkeypatch):
    from app.core.settings import Settings
    from app.rag.workers import tasks

    sent = []

    class FakeCelery:
        def send_task(self, name, **kwargs):
            sent.append((name, kwargs))

    monkeypatch.setattr(tasks, "celery_app", lambda: FakeCelery())
    job = {
        "tenant_id": "t",
        "document_id": "d",
        "origin": "job",
        "requested_mode": "SHADOW",
        "engine": "offline",
    }
    options = {"glossary": [{"source": "secret term", "target": "x"}], "memory": {"a": "b"}}
    tasks.reset_breaker()  # LOT 2 (F-L2-01) : publication asynchrone par le thread éditeur
    assert tasks.dispatch_shadow(Settings(execution_mode="celery"), None, job, options) == "celery"
    assert tasks.wait_for_shadow(5)
    name, kwargs = sent[0]
    assert name == tasks.TASK_NAME
    assert kwargs["queue"] == "rag"
    assert kwargs["retry"] is False
    assert kwargs["kwargs"] == job
    assert "secret term" not in json.dumps(kwargs)
