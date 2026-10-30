"""Point d'intégration unique entre le RAG et la traduction existante.

Appelé par ``app.application.jobs.run_translate`` (uniquement si le mode global
n'est pas DISABLED) et par ``tools/rag_corpus_run.py``.

Garanties :
* DISABLED : l'objet ``options`` reçu est renvoyé tel quel ;
* SHADOW : aucune lecture en base sur le chemin critique, la recherche est
  planifiée en arrière-plan, ``options`` est renvoyé tel quel ;
* ASSISTED / ACTIVE : un *nouveau* dictionnaire est renvoyé, ``options`` n'est
  jamais modifié ; seuls ``document_memory.terminology``,
  ``document_memory.translation_decisions`` et ``country_context`` sont ajoutés,
  jamais ``glossary`` ;
* avant toute injection, la sonde (fournie par l'appelant, hors ``app.rag``)
  reconstruit à blanc chaque requête avec et sans RAG ; l'injection n'a lieu
  que si aucun élément de contexte existant n'est évincé, si le découpage des
  requêtes est identique et si le surcoût RAG respecte le budget du mode ;
* toute erreur RAG renvoie ``options`` inchangé (le document est traité comme
  sans RAG) et n'interrompt jamais le traitement.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping
from typing import Any

from ..audit.provenance import write_search_log
from ..config import INJECTING_ENGINES, effective_mode, normalize_mode, token_budget
from ..core import context_builder, policies
from ..core.engine import RagEngine
from ..storage import repository

logger = logging.getLogger("app.rag")

# probe(ir, options) -> check(candidate_options, budget) -> verdict
ProbeCheck = Callable[[dict, int], Mapping[str, Any]]
Probe = Callable[[Mapping[str, Any], Mapping[str, Any]], ProbeCheck]
Dispatch = Callable[..., Any]


def _default_dispatch(settings: Any, session_factory: Any, job: dict, options: dict | None) -> Any:
    from ..workers.tasks import dispatch_shadow

    return dispatch_shadow(settings, session_factory, job, options)


def merge_channels(options: Mapping[str, Any], added: Mapping[str, Any]) -> dict | None:
    """Nouvelles options : éléments existants d'abord, ajouts RAG à la suite.

    Renvoie None si un canal existant n'a pas un format fusionnable (aucune
    injection plutôt qu'un remplacement).
    """
    result = dict(options)
    if "document_memory" in added:
        existing = options.get("document_memory")
        if existing is not None and not isinstance(existing, Mapping):
            return None
        memory = dict(existing or {})
        for channel in ("terminology", "translation_decisions"):
            items = added["document_memory"].get(channel)
            if items:
                current = memory.get(channel) or []
                if not isinstance(current, list):
                    return None
                memory[channel] = [*current, *items]
        result["document_memory"] = memory
    if "country_context" in added and not options.get("country_context"):
        result["country_context"] = dict(added["country_context"])
    return result


def augment_options(
    *,
    settings: Any,
    session_factory: Any,
    tenant_id: str,
    document_id: str | None,
    ir: Mapping[str, Any],
    options: dict,
    origin: str = "job",
    probe: Probe | None = None,
    on_report: Callable[[dict], None] | None = None,
    shadow_dispatch: Dispatch | None = None,
) -> dict:
    global_mode = normalize_mode(getattr(settings, "rag_mode", "DISABLED"))
    if global_mode == "DISABLED":
        return options
    started = time.perf_counter()
    engine_name = str(options.get("engine") or getattr(settings, "engine", "offline"))
    report: dict[str, Any] = {"origin": origin, "global_mode": global_mode, "engine": engine_name}
    dispatch = shadow_dispatch or _default_dispatch
    job = {
        "tenant_id": tenant_id,
        "document_id": document_id,
        "origin": origin,
        "requested_mode": global_mode,
        "engine": engine_name,
    }
    try:
        if global_mode == "SHADOW" or engine_name not in INJECTING_ENGINES:
            # Aucune lecture en base ici : le worker résout le mode du tenant.
            report["decision"] = "SHADOW_DISPATCHED"
            report["dispatch"] = dispatch(settings, session_factory, job, _shadow_options(options))
            return options
        with session_factory() as db:
            tenant_mode = repository.tenant_max_mode(db, tenant_id)
        effective = effective_mode(global_mode, tenant_mode, engine_name)
        report.update(effective_mode=effective.mode, reasons=list(effective.reasons))
        if effective.mode == "DISABLED":
            report["decision"] = "TENANT_DISABLED"
            return options
        if not effective.injects:
            report["decision"] = "SHADOW_DISPATCHED"
            report["dispatch"] = dispatch(settings, session_factory, job, _shadow_options(options))
            return options
        plan = RagEngine(settings, session_factory).plan(
            tenant_id=tenant_id,
            document_id=document_id,
            ir=ir,
            options=options,
            mode=effective.mode,
        )
        result, outcome = _inject(settings, plan, ir, options, probe)
        report.update(outcome)
        audit = plan.audit()
        write_search_log(
            session_factory,
            tenant_id=tenant_id,
            document_id=document_id,
            mode=effective.mode,
            origin=origin[:20],
            query_sha256=plan.query_sha256,
            filters={
                "domain": ir.get("domain"),
                "source_languages": plan.stats.get("source_languages"),
                "target_language": plan.stats.get("target_language"),
            },
            result_ids=outcome.get("injected_term_ids", [])
            + outcome.get("injected_notion_ids", []),
            result_count=len(outcome.get("injected_term_ids", []))
            + len(outcome.get("injected_notion_ids", [])),
            referential_versions=plan.versions,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            outcome={
                **outcome,
                "effective_mode": effective.mode,
                "reasons": list(effective.reasons),
                **audit,
            },
        )
        return result
    except Exception as exc:
        logger.warning("rag_augment_failed", extra={"error": type(exc).__name__})
        report["decision"] = "ERROR_FAIL_SAFE"
        report["error"] = type(exc).__name__
        return options
    finally:
        report["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        if on_report is not None:
            on_report(report)


def _shadow_options(options: Mapping[str, Any]) -> dict:
    # Copie limitée à ce que la recherche lit ; jamais transmise à un courtier.
    return {
        "glossary": list(options.get("glossary") or []),
        "memory": dict(options.get("memory") or {}),
        "target_language": options.get("target_language"),
    }


def _inject(
    settings: Any,
    plan: Any,
    ir: Mapping[str, Any],
    options: dict,
    probe: Probe | None,
) -> tuple[dict, dict]:
    budget = token_budget(plan.mode, settings)
    outcome: dict[str, Any] = {"budget_tokens": budget, "attempts": []}
    if plan.empty:
        outcome["decision"] = "NO_RESULT"
        return options, outcome
    if probe is None:
        outcome["decision"] = "PROBE_UNAVAILABLE"
        return options, outcome
    check = probe(ir, options)
    for attempt in policies.attempts(
        plan.mode, len(plan.terminology), len(plan.decisions), bool(plan.country_context)
    ):
        added = context_builder.channels(
            plan.terminology[: attempt.terms],
            plan.decisions[: attempt.decisions],
            plan.country_context if attempt.country else None,
        )
        candidate = merge_channels(options, added)
        if candidate is None:
            outcome["decision"] = "EXISTING_CHANNEL_NOT_MERGEABLE"
            return options, outcome
        verdict = dict(check(candidate, budget))
        outcome["attempts"].append(
            {
                "terms": attempt.terms,
                "decisions": attempt.decisions,
                "country_context": attempt.country,
                "ok": bool(verdict.get("ok")),
                "reason": verdict.get("reason"),
                "requests": verdict.get("requests"),
                "rag_tokens_max": verdict.get("rag_tokens_max"),
                "rag_tokens_total": verdict.get("rag_tokens_total"),
                "rag_items_added": _added_count(added),
                "rag_items_sent": verdict.get("rag_items_sent"),
            }
        )
        if verdict.get("ok"):
            sent = set(verdict.get("sent_keys") or [])
            memory = added.get("document_memory") or {}
            term_ids = [
                view.id
                for view, item in zip(
                    plan.terms[: attempt.terms], memory.get("terminology") or [], strict=False
                )
                if _canonical(item) in sent
            ]
            notion_ids = [
                view.id
                for view, item in zip(
                    plan.notions[: attempt.decisions],
                    memory.get("translation_decisions") or [],
                    strict=False,
                )
                if _canonical(item) in sent
            ]
            country = bool(attempt.country and verdict.get("country_sent"))
            if not term_ids and not notion_ids and not country:
                # Le service a filtré ou retiré tout l'apport : rien n'est injecté.
                outcome["decision"] = "NOT_SENT"
                return options, outcome
            outcome.update(
                decision="INJECTED",
                injected_term_ids=term_ids,
                injected_notion_ids=notion_ids,
                injected_country_context=country,
                rag_tokens_max=verdict.get("rag_tokens_max"),
                rag_tokens_total=verdict.get("rag_tokens_total"),
                requests=verdict.get("requests"),
            )
            return candidate, outcome
        if verdict.get("reason") == "PROBE_FAILED":
            break
    outcome["decision"] = "ABANDONED"
    return options, outcome


def _canonical(value: Any) -> str:
    # Même forme canonique que la sonde (comparaison d'éléments, jamais journalisée).
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _added_count(added: Mapping[str, Any]) -> int:
    memory = added.get("document_memory") or {}
    return sum(len(memory.get(key) or []) for key in ("terminology", "translation_decisions"))
