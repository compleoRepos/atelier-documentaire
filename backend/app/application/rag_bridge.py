"""Pont entre l'application existante et le module RAG (hors ``app.rag``).

Ce module n'est importé que si ``rag_mode != DISABLED``. Il fournit à
``app.rag.integration.augment_options`` la *sonde* qui vérifie, avant toute
injection, ce que le service de traduction existant (gelé) enverrait réellement
au moteur privé :

* le service est exécuté **à blanc** avec un moteur de capture : chaque requête
  (messages, identifiants attendus) est enregistrée, aucune traduction n'est
  produite, aucun appel réseau n'est possible ;
* la capture est faite sur une copie profonde de l'IR, sans et avec le contexte
  RAG candidat ;
* l'injection n'est acceptée que si : même nombre de requêtes, mêmes blocs par
  requête, même message système, mêmes blocs protégés, même contexte documentaire
  (hors ``country_context`` ajouté), chaque élément de contexte existant toujours
  présent dans son canal, et surcoût RAG mesuré avec le tokenizer du moteur
  inférieur ou égal au budget du mode, pour chaque requête.

Toute anomalie de la sonde se traduit par un refus (``PROBE_FAILED``) : le
document est alors traduit exactement comme sans RAG.
"""

from __future__ import annotations

import asyncio
import copy
import json
import threading
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

from ..ai.context.builder import ContextPackBuilder
from ..ai.translation import service

DRY_RUN_CODE = "RAG_DRY_RUN"


class CaptureEngine(service.TranslationEngine):
    """Moteur factice explicite : enregistre les requêtes, ne traduit rien."""

    tokenizer_name = "rag-probe-capture"

    def __init__(self, tokenizer: Any = None) -> None:
        self.tokenizer = tokenizer
        self.requests: list[dict[str, Any]] = []

    async def translate_chunk(
        self,
        messages: list[dict[str, str]],
        expected_ids: Sequence[str],
        *,
        max_output: int,
    ) -> service.EngineResult:
        self.requests.append(
            {
                "messages": copy.deepcopy(list(messages)),
                "expected_ids": [str(x) for x in expected_ids],
            }
        )
        return service.EngineResult(
            translations={},
            issues=[{"code": DRY_RUN_CODE, "severity": "info", "message": "capture à blanc"}],
            finish_reason="stop",
        )


@lru_cache(maxsize=4)
def _local_tokenizer(path: str) -> Any:
    return service._load_local_tokenizer(path)


def probe_tokenizer(options: Mapping[str, Any]) -> Any:
    """Même tokenizer que celui qu'utilisera la vraie traduction."""
    if options.get("tokenizer") is not None:
        return options["tokenizer"]
    engine = options.get("translation_engine")
    if engine is not None:
        return getattr(engine, "tokenizer_adapter", None) or getattr(engine, "tokenizer", None)
    path = options.get("tokenizer_path")
    return _local_tokenizer(str(path)) if path else None


def _run(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:  # transmis à l'appelant
            box["error"] = exc

    thread = threading.Thread(target=target, name="rag-probe", daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


def capture_requests(
    ir: Mapping[str, Any], options: Mapping[str, Any], tokenizer: Any
) -> list[dict]:
    engine = CaptureEngine(tokenizer)
    dry = {key: value for key, value in options.items() if key != "transport"}
    dry["translation_engine"] = engine
    _run(service.translate_blocks(copy.deepcopy(dict(ir)), dry))
    return engine.requests


def _payload(request: Mapping[str, Any]) -> tuple[str, dict]:
    messages = request["messages"]
    if len(messages) != 2 or messages[0].get("role") != "system":
        raise ValueError("FORMAT")
    payload = json.loads(messages[1]["content"])
    if not isinstance(payload, dict) or not isinstance(payload.get("context"), dict):
        raise ValueError("FORMAT")
    return str(messages[0].get("content")), payload


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def compare_requests(
    base: list[dict], candidate: list[dict], counter: ContextPackBuilder, budget: int
) -> dict[str, Any]:
    """Verdict sans texte : motif stable, compteurs et surcoût en jetons."""
    if len(base) != len(candidate):
        return {"ok": False, "reason": "REQUEST_SPLIT_CHANGED", "requests": len(candidate)}
    overheads: list[int] = []
    # Éléments RAG réellement présents (le service peut les filtrer ou les retirer).
    sent: set[str] = set()
    country_sent = False
    for before, after in zip(base, candidate, strict=True):
        if before["expected_ids"] != after["expected_ids"]:
            return {"ok": False, "reason": "REQUEST_SPLIT_CHANGED", "requests": len(candidate)}
        try:
            system_a, payload_a = _payload(before)
            system_b, payload_b = _payload(after)
        except (KeyError, TypeError, ValueError):
            return {"ok": False, "reason": "PROBE_FAILED", "requests": len(candidate)}
        if system_a != system_b:
            return {"ok": False, "reason": "SYSTEM_CHANGED", "requests": len(candidate)}
        for key in ("target_language", "blocks"):
            if _canonical(payload_a.get(key)) != _canonical(payload_b.get(key)):
                return {"ok": False, "reason": "BLOCKS_CHANGED", "requests": len(candidate)}
        doc_a = dict(payload_a.get("document_context") or {})
        doc_b = dict(payload_b.get("document_context") or {})
        if "country_context" not in doc_a:
            country_sent = doc_b.pop("country_context", None) is not None or country_sent
        if _canonical(doc_a) != _canonical(doc_b):
            return {"ok": False, "reason": "DOCUMENT_CONTEXT_CHANGED", "requests": len(candidate)}
        context_a, context_b = payload_a["context"], payload_b["context"]
        for channel, items in context_a.items():
            if not isinstance(items, list):
                if _canonical(items) != _canonical(context_b.get(channel)):
                    return {"ok": False, "reason": "EXISTING_CONTEXT_EVICTED", "channel": channel}
                continue
            remaining = [_canonical(x) for x in context_b.get(channel) or []]
            for item in items:
                key = _canonical(item)
                if key not in remaining:
                    return {
                        "ok": False,
                        "reason": "EXISTING_CONTEXT_EVICTED",
                        "channel": channel,
                        "requests": len(candidate),
                    }
                remaining.remove(key)
            if channel == "document_memory":
                sent.update(remaining)
            if channel != "document_memory" and remaining:
                return {"ok": False, "reason": "UNEXPECTED_CHANNEL_CHANGE", "channel": channel}
        for channel in context_b:
            if channel not in context_a and channel != "document_memory":
                return {"ok": False, "reason": "UNEXPECTED_CHANNEL_CHANGE", "channel": channel}
            if channel not in context_a and isinstance(context_b[channel], list):
                sent.update(_canonical(x) for x in context_b[channel])
        overheads.append(
            counter.count_messages(after["messages"]) - counter.count_messages(before["messages"])
        )
    peak = max(overheads, default=0)
    verdict: dict[str, Any] = {
        "requests": len(candidate),
        "rag_tokens_max": peak,
        "rag_tokens_total": sum(max(0, x) for x in overheads),
        "rag_items_sent": len(sent),
        # Clés canoniques en mémoire seulement : jamais journalisées.
        "sent_keys": sorted(sent),
        "country_sent": country_sent,
    }
    if peak > budget:
        return {**verdict, "ok": False, "reason": "BUDGET_EXCEEDED"}
    return {**verdict, "ok": True, "reason": None}


def probe_context(ir: Mapping[str, Any], options: Mapping[str, Any]):
    """Sonde passée à ``augment_options`` ; la capture de base est faite une fois."""
    try:
        tokenizer = probe_tokenizer(options)
        counter = ContextPackBuilder(tokenizer=tokenizer, max_tokens=10**9)
        base = capture_requests(ir, options, tokenizer)
    except Exception:
        base = None

    def check(candidate: dict, budget: int) -> dict[str, Any]:
        if base is None:
            return {"ok": False, "reason": "PROBE_FAILED"}
        try:
            after = capture_requests(ir, candidate, tokenizer)
        except Exception:
            return {"ok": False, "reason": "PROBE_FAILED"}
        return compare_requests(base, after, counter, budget)

    return check


def augment_translation_options(
    settings: Any,
    session_factory: Any,
    tenant_id: str,
    document_id: str | None,
    ir: Mapping[str, Any],
    options: dict,
    *,
    origin: str = "job",
    on_report: Any = None,
    shadow_dispatch: Any = None,
) -> dict:
    """Appel unique partagé par ``run_translate`` et ``tools/rag_corpus_run.py``."""
    from ..rag.integration.augment_options import augment_options

    return augment_options(
        settings=settings,
        session_factory=session_factory,
        tenant_id=tenant_id,
        document_id=document_id,
        ir=ir,
        options=options,
        origin=origin,
        probe=probe_context,
        on_report=on_report,
        shadow_dispatch=shadow_dispatch,
    )
