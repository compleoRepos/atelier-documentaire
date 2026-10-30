"""Lanceur de recette DICE (RAG) : variantes A, B, C sur exactement les mêmes IR.

* A : traduction actuelle, RAG ``DISABLED`` ;
* B : ``SHADOW`` (recherche observée, aucune influence attendue) ;
* C : ``ASSISTED`` (injection vérifiée par la sonde ; le moteur ``offline`` ou
  ``interim`` est plafonné à SHADOW par configuration).

Les trois variantes passent par le point d'intégration de ``run_translate`` :
``app.application.rag_bridge.augment_translation_options``. Seul le mode RAG
change entre variantes ; documents, glossaire, mémoire et moteur sont identiques.

Entrées : un dossier de fichiers JSON, chacun étant soit une IR, soit
``{"ir": {...}, "options": {...}}`` (glossaire, mémoire, langue cible...).
Sortie : ``rag-corpus-report.json`` sans aucun texte de document — empreintes
SHA-256, compteurs, décisions, identifiants d'entrées de référentiel.

Par défaut aucune traduction n'est demandée : seules les requêtes sont
reconstruites à blanc (moteur de capture, sans réseau). ``--translate`` exécute
la traduction avec le moteur configuré ; pour ``private``, il faut en plus
``--allow-model-calls``. ``--dump-translations`` (dossier HORS dépôt, droits
0700) conserve les traductions pour une évaluation privée ; le rapport, lui,
reste sans texte. Ce lanceur ne mesure pas la qualité : aucun gain n'est
déduit de ses résultats sans corpus annoté et relecture humaine.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

VARIANTS = {"A": "DISABLED", "B": "SHADOW", "C": "ASSISTED"}
REPORT_NAME = "rag-corpus-report.json"
VOLATILE_KEYS = {"latency_ms", "elapsed_ms", "duration_ms", "started_at", "finished_at"}


def _sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items() if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def _visible(options: dict) -> dict:
    return {k: v for k, v in options.items() if k != "translation_engine"}


def load_inputs(folder: Path) -> list[tuple[str, dict, dict]]:
    items = []
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("ir"), dict):
            items.append((path.stem, data["ir"], dict(data.get("options") or {})))
        elif isinstance(data, dict) and isinstance(data.get("pages"), list):
            items.append((path.stem, data, {}))
        else:
            raise SystemExit(f"{path.name}: ni IR ni objet {{ir, options}}")
    if not items:
        raise SystemExit("aucun fichier JSON d'entrée")
    return items


def _request_digest(ir: dict, options: dict) -> dict:
    """Requêtes reconstruites à blanc (sans réseau) : empreinte et jetons."""
    from app.ai.context.builder import ContextPackBuilder
    from app.application import rag_bridge

    tokenizer = rag_bridge.probe_tokenizer(options)
    requests = rag_bridge.capture_requests(ir, options, tokenizer)
    counter = ContextPackBuilder(tokenizer=tokenizer, max_tokens=10**9)
    tokens = [rag_bridge.message_tokens(counter, request["messages"]) for request in requests]
    return {
        "requests": len(requests),
        "requests_sha256": _sha([request["messages"] for request in requests]),
        "prompt_tokens_total": sum(tokens),
        "prompt_tokens_max": max(tokens, default=0),
        "tokenizer": "exact" if tokenizer is not None else "approximate",
    }


def run_variant(
    settings: Any,
    session_factory: Any,
    tenant_id: str,
    ir: dict,
    base_options: dict,
    variant: str,
    *,
    translate: bool,
    on_result: Any = None,
) -> dict:
    from app.application import rag_bridge
    from app.rag.workers.tasks import run_shadow

    mode = VARIANTS[variant]
    variant_settings = settings.model_copy(update={"rag_mode": mode})
    options = copy.deepcopy(base_options)
    reports: list[dict] = []

    def inline_shadow(task_settings, factory, job, shadow_options):
        # Recherche SHADOW exécutée ici, sur l'IR fournie (aucune ligne Document).
        log_id = run_shadow(task_settings, factory, job, shadow_options, ir=copy.deepcopy(ir))
        return "inline-logged" if log_id else "inline-not-logged"

    started = time.perf_counter()
    augmented = rag_bridge.augment_translation_options(
        variant_settings,
        session_factory,
        tenant_id,
        None,
        copy.deepcopy(ir),
        options,
        origin="corpus",
        on_report=reports.append,
        shadow_dispatch=inline_shadow,
    )
    resolver_ms = round((time.perf_counter() - started) * 1000, 3)
    report = reports[0] if reports else {"decision": "UNCHANGED_DISABLED"}
    row: dict[str, Any] = {
        "variant": variant,
        "rag_mode": mode,
        "decision": report.get("decision"),
        "effective_mode": report.get("effective_mode"),
        "reasons": report.get("reasons", []),
        "dispatch": report.get("dispatch"),
        "injected_term_ids": report.get("injected_term_ids", []),
        "injected_notion_ids": report.get("injected_notion_ids", []),
        "rag_tokens_max": report.get("rag_tokens_max"),
        "attempts": [
            {k: v for k, v in attempt.items() if k != "sent_keys"}
            for attempt in report.get("attempts", [])
        ],
        "resolver_latency_ms": resolver_ms,
        "options_unchanged_object": augmented is options,
        "options_sha256": _sha(_visible(augmented)),
        **_request_digest(ir, augmented),
    }
    if translate:
        from app.ai.translation.service import translate_blocks

        t0 = time.perf_counter()
        result = asyncio.run(translate_blocks(copy.deepcopy(ir), augmented))
        telemetry = result.get("translation_telemetry") or {}
        usage = telemetry.get("usage") or {}
        chunks = telemetry.get("chunks") or []
        row.update(
            usage={
                k: int(usage.get(k) or 0)
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            },
            engine_chunks=len(chunks),
            engine_latency_ms=round(sum(float(c.get("latency_ms") or 0.0) for c in chunks), 3),
        )
        if on_result is not None:
            on_result(variant, result)
        row.update(
            translation_ms=round((time.perf_counter() - t0) * 1000, 3),
            translations_sha256=_sha(result.get("translations")),
            block_translation_sha256={
                str(k): _sha(v) for k, v in sorted((result.get("translations") or {}).items())
            },
            issues_sha256=_sha(_stable(result.get("issues"))),
            untranslated_blocks=len(result.get("untranslated_blocks") or []),
            quality_status=(result.get("quality") or {}).get("status"),
        )
    return row


def compare(rows: dict[str, dict]) -> dict:
    a, b, c = rows.get("A"), rows.get("B"), rows.get("C")
    out: dict[str, Any] = {}
    keys = ("options_sha256", "requests_sha256", "translations_sha256", "issues_sha256")
    if a and b:
        out["B_identical_to_A"] = all(a.get(k) == b.get(k) for k in keys if k in a or k in b)
    if a and c:
        out["C_requests_identical_to_A"] = a["requests_sha256"] == c["requests_sha256"]
        out["C_prompt_tokens_delta"] = c["prompt_tokens_total"] - a["prompt_tokens_total"]
        usage_a = (a.get("usage") or {}).get("prompt_tokens")
        usage_c = (c.get("usage") or {}).get("prompt_tokens")
        if usage_a is not None and usage_c is not None:
            # Jetons d'entrée réellement facturés par le moteur (et non reconstruits).
            out["C_engine_prompt_tokens_delta"] = usage_c - usage_a
        if "block_translation_sha256" in a and "block_translation_sha256" in c:
            blocks = set(a["block_translation_sha256"]) | set(c["block_translation_sha256"])
            out["C_blocks_changed"] = sum(
                a["block_translation_sha256"].get(x) != c["block_translation_sha256"].get(x)
                for x in blocks
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True, help="dossier de JSON (IR)")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--variants", default="A,B,C")
    parser.add_argument("--engine", choices=("offline", "private", "interim"))
    parser.add_argument("--target-language", default=None)
    parser.add_argument("--translate", action="store_true")
    parser.add_argument("--allow-model-calls", action="store_true")
    parser.add_argument(
        "--dump-translations",
        type=Path,
        default=None,
        help="dossier HORS dépôt où écrire traductions et anomalies (évaluation privée)",
    )
    args = parser.parse_args(argv)

    out_dir = args.out_dir.resolve()
    if out_dir == ROOT or ROOT in out_dir.parents:
        raise SystemExit("--out-dir doit être hors du dépôt (sorties de recette non versionnées)")
    dump_dir = args.dump_translations.resolve() if args.dump_translations else None
    if dump_dir is not None:
        if dump_dir == ROOT or ROOT in dump_dir.parents:
            raise SystemExit("--dump-translations doit être hors du dépôt (textes privés)")
        if not args.translate:
            raise SystemExit("--dump-translations exige --translate")
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.chmod(0o700)
    variants = [v.strip().upper() for v in args.variants.split(",") if v.strip()]
    if not variants or any(v not in VARIANTS for v in variants):
        raise SystemExit("--variants : sous-ensemble de A,B,C")

    from app.core.db import make_engine, make_session_factory
    from app.core.settings import get_settings

    settings = get_settings()
    engine_name = args.engine or settings.engine
    if args.translate and engine_name != "offline" and not args.allow_model_calls:
        raise SystemExit("--translate avec un moteur non offline exige --allow-model-calls")
    factory = make_session_factory(make_engine(settings))

    documents = []
    for label, ir, options in load_inputs(args.input):
        base = {"engine": engine_name, **options}
        if args.target_language:
            base["target_language"] = args.target_language

        def dump(variant: str, result: dict, label: str = label) -> None:
            if dump_dir is None:
                return
            payload = {
                "translations": result.get("translations"),
                "issues": _stable(result.get("issues")),
                "untranslated_blocks": result.get("untranslated_blocks"),
            }
            target = dump_dir / f"{label}.{variant}.json"
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            target.chmod(0o600)

        rows = {
            variant: run_variant(
                settings,
                factory,
                args.tenant_id,
                ir,
                base,
                variant,
                translate=args.translate,
                on_result=dump,
            )
            for variant in variants
        }
        documents.append(
            {
                "document": label,
                "ir_sha256": _sha(ir),
                "blocks": sum(len(page.get("blocks") or []) for page in ir.get("pages") or []),
                "variants": rows,
                "comparison": compare(rows),
            }
        )
    summary = {
        "documents": len(documents),
        "variants": variants,
        "engine": engine_name,
        "translated": bool(args.translate),
        "B_identical_to_A_all": all(
            d["comparison"].get("B_identical_to_A", True) for d in documents
        ),
        "C_decisions": sorted(
            {
                str(d["variants"].get("C", {}).get("decision"))
                for d in documents
                if "C" in d["variants"]
            }
        ),
        "note": "Aucune mesure de qualité : comparaison technique uniquement.",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"summary": summary, "documents": documents}
    (out_dir / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    # Une variante B qui diffère de A est une régression : code retour non nul.
    return 0 if summary["B_identical_to_A_all"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
