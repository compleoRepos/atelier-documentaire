"""DICE (RAG) LOT 1 — injection ASSISTED vérifiée par la sonde, moteur privé factice.

Le service de traduction gelé est exécuté réellement (``translate_blocks``) ;
seul le moteur est un double de test explicite, sans réseau. Termes synthétiques.
"""

from __future__ import annotations

import asyncio
import copy
import json

from app.ai.context.builder import ContextPackBuilder
from app.ai.translation.service import EngineResult, TranslationEngine, translate_blocks
from app.application import rag_bridge
from app.rag.models import RagSearchLog

from .rag_support import TERMS_EN_FR, make_rag_client, publish_referential

IR = {
    "language": "en",
    "domain": "HR",
    "pages": [
        {
            "number": 1,
            "blocks": [
                {"id": "b001", "text": "Gross salary and notice period apply.", "language": "en"},
                {"id": "b002", "text": "See the pay slip for details.", "language": "en"},
            ],
        }
    ],
}
GLOSSARY = [{"source": "gross salary", "target": "rémunération brute", "domain": "HR"}]


class RecordingPrivateEngine(TranslationEngine):
    """Double de test explicite : enregistre les requêtes, renvoie un texte fixe."""

    tokenizer_name = "test-double-words"

    def __init__(self) -> None:
        self.requests: list[list[dict]] = []

    async def translate_chunk(self, messages, expected_ids, *, max_output):
        self.requests.append(copy.deepcopy(messages))
        return EngineResult(translations={i: f"Traduction {i}" for i in expected_ids})


def _setup(monkeypatch, **settings_update):
    client, app, ids = make_rag_client(monkeypatch, mode="ASSISTED")
    publish_referential(client, ids, max_mode="ASSISTED")
    settings = app.state.settings.model_copy(update=settings_update)
    return client, app, ids, settings


def _options(**extra) -> dict:
    return {
        "engine": "private",
        "translation_engine": RecordingPrivateEngine(),
        "target_language": "fr",
        "glossary": copy.deepcopy(GLOSSARY),
        "memory": {},
        **extra,
    }


def _augment(app, ids, settings, options):
    reports: list[dict] = []
    result = rag_bridge.augment_translation_options(
        settings,
        app.state.session_factory,
        ids["tenant-a"],
        None,
        IR,
        options,
        on_report=reports.append,
    )
    return result, reports[0]


def _payloads(options) -> list[dict]:
    engine = RecordingPrivateEngine()
    asyncio.run(translate_blocks(copy.deepcopy(IR), {**options, "translation_engine": engine}))
    return [json.loads(messages[1]["content"]) for messages in engine.requests]


def _visible(options) -> str:
    return json.dumps(
        {k: v for k, v in options.items() if k != "translation_engine"}, sort_keys=True
    )


def test_assisted_adds_only_document_memory_and_keeps_glossary_first(app_env, monkeypatch):
    _, app, ids, settings = _setup(monkeypatch)
    options = _options()
    snapshot = _visible(options)
    result, report = _augment(app, ids, settings, options)

    assert report["decision"] == "INJECTED", report
    assert result is not options and _visible(options) == snapshot  # options intactes
    assert set(result) - set(options) == {"document_memory"}
    assert result["glossary"] == options["glossary"]
    assert {k: v for k, v in result.items() if k != "document_memory"} == options
    terminology = result["document_memory"]["terminology"]
    # Le glossaire client prime : « gross salary » n'est pas réinjecté par le RAG.
    assert terminology == [
        {"source": "notice period", "target": "préavis"},
        {"source": "pay slip", "target": "bulletin de paie"},
    ]
    assert len(report["injected_term_ids"]) == 2
    assert report["rag_tokens_max"] <= settings.rag_assisted_max_tokens

    before, after = _payloads(options), _payloads(result)
    assert len(before) == len(after) >= 1
    for a, b in zip(before, after, strict=True):
        assert a["blocks"] == b["blocks"]
        assert a["context"]["terms"] == b["context"]["terms"]  # glossaire inchangé
        assert "document_memory" not in a["context"]
    sent = [item for b in after for item in b["context"].get("document_memory", [])]
    assert {"source": "pay slip", "target": "bulletin de paie"} in sent

    with app.state.session_factory() as db:
        rows = db.query(RagSearchLog).all()
    assert [(row.mode, row.outcome["decision"]) for row in rows] == [("ASSISTED", "INJECTED")]
    dumped = json.dumps(
        [{"outcome": r.outcome, "filters": r.filters, "ids": r.result_ids} for r in rows],
        ensure_ascii=False,
    ).lower()
    for word in ("gross", "notice", "pay slip", "préavis", "bulletin", "rémunération"):
        assert word not in dumped


def test_existing_context_is_never_evicted(app_env, monkeypatch):
    _, app, ids, settings = _setup(monkeypatch)
    probe_options = _options(document_context=[{"text": "salary notice letter", "domain": "HR"}])
    base = rag_bridge.capture_requests(IR, probe_options, None)
    counter = ContextPackBuilder(tokenizer=None, max_tokens=10**9)
    fitted = max(counter.count_messages(request["messages"]) for request in base)
    # Budget d'entrée juste suffisant pour le contexte existant : tout ajout l'évincerait.
    options = _options(document_context=probe_options["document_context"], target_input=fitted)
    payloads = _payloads(options)
    assert any(p["context"].get("document") for p in payloads), "contexte existant requis"
    snapshot = _visible(options)
    result, report = _augment(app, ids, settings, options)
    assert result is options and _visible(options) == snapshot
    assert report["decision"] == "ABANDONED", report
    assert [a["terms"] for a in report["attempts"]] == [2, 1]
    assert {a["reason"] for a in report["attempts"]} == {"EXISTING_CONTEXT_EVICTED"}
    assert _payloads(result) == payloads


def test_budget_reduces_the_rag_contribution_before_giving_up(app_env, monkeypatch):
    _, app, ids, settings = _setup(monkeypatch, rag_max_entries=1)
    single, report_single = _augment(app, ids, settings, _options(glossary=[]))
    assert report_single["decision"] == "INJECTED"
    one_term_cost = report_single["rag_tokens_max"]
    assert one_term_cost > 0

    settings = settings.model_copy(
        update={"rag_max_entries": 16, "rag_assisted_max_tokens": one_term_cost}
    )
    result, report = _augment(app, ids, settings, _options(glossary=[]))
    assert report["decision"] == "INJECTED", report
    assert [a["terms"] for a in report["attempts"]] == [3, 2, 1]
    assert [a["reason"] for a in report["attempts"]][:2] == ["BUDGET_EXCEEDED"] * 2
    assert len(result["document_memory"]["terminology"]) == 1
    assert report["rag_tokens_max"] <= one_term_cost

    tight = settings.model_copy(update={"rag_assisted_max_tokens": 1})
    options = _options(glossary=[])
    unchanged, report_tight = _augment(app, ids, tight, options)
    assert unchanged is options
    assert report_tight["decision"] == "ABANDONED"
    assert {a["reason"] for a in report_tight["attempts"]} == {"BUDGET_EXCEEDED"}


def test_items_filtered_by_the_service_are_not_reported_as_injected(app_env, monkeypatch):
    # Un document dont aucun mot (> 2 lettres) n'apparaît dans les éléments RAG :
    # le constructeur gelé les filtre ; la sonde le voit et rien n'est déclaré injecté.
    _, app, ids, settings = _setup(monkeypatch)
    terms = [t["source_term"] for t in TERMS_EN_FR]
    assert terms  # les termes publiés existent

    def plan_with_unmatched(*args, **kwargs):
        plan = original(*args, **kwargs)
        plan.terminology = [{"source": "zz", "target": "qq"} for _ in plan.terminology]
        return plan

    from app.rag.core.engine import RagEngine

    original = RagEngine.plan
    monkeypatch.setattr(RagEngine, "plan", plan_with_unmatched)
    options = _options(glossary=[])
    result, report = _augment(app, ids, settings, options)
    assert result is options
    assert report["decision"] == "NOT_SENT", report
    assert report["attempts"][0]["rag_items_sent"] == 0


def test_probe_failure_means_no_injection(app_env, monkeypatch):
    _, app, ids, settings = _setup(monkeypatch)

    def broken_capture(*args, **kwargs):
        raise RuntimeError("capture impossible")

    monkeypatch.setattr(rag_bridge, "capture_requests", broken_capture)
    options = _options()
    result, report = _augment(app, ids, settings, options)
    assert result is options
    assert report["decision"] == "ABANDONED"
    assert [a["reason"] for a in report["attempts"]] == ["PROBE_FAILED"]
