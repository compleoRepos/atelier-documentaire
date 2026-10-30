"""Évaluation objective du corpus synthétique DICE (RAG) LOT 2.

Entrées (toutes hors dépôt) : dossier ``expected/`` du générateur
``tools/rag_lot2_corpus.py``, dossier de traductions écrit par
``tools/rag_corpus_run.py --dump-translations``, rapports du lanceur et, pour
relier les identifiants d'entrées injectées aux termes, la base du référentiel.

Mesures *objectives par construction* : présence du terme cible attendu dans le
bloc traduit, montants/dates/identifiants/nombres conservés, glossaire client
respecté, ambiguïtés et domaine frère jamais injectés, rappel de la sélection
RAG, conformité du modèle aux termes injectés, jetons et latences.

Indicateur de *substitution* : chrF (n-grammes de caractères 1..6, bêta 2)
contre une **référence candidate synthétique non validée par un humain**. Ce
n'est pas une mesure de fidélité : la fidélité sémantique reste NON MESURÉE
tant qu'aucune annotation humaine n'est disponible.

Le rapport produit ne contient aucun texte de document : compteurs et ratios.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'"})
SPACES = re.compile(r"[\s\u00a0\u202f\u2009]+")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})(?!\d)")
ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
NUMBER = re.compile(r"\d(?:[\d\u00a0\u202f\u2009 .,'٬٫]*\d)?")
MONTHS = {
    "fr": [
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ],
    "en": [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ],
}


def _generator():
    spec = importlib.util.spec_from_file_location(
        "rag_lot2_corpus", ROOT / "tools/rag_lot2_corpus.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def norm(text: Any) -> str:
    value = unicodedata.normalize("NFC", str(text or "")).translate(APOSTROPHES).casefold()
    return SPACES.sub(" ", value).strip()


def fold(text: str) -> str:
    base = unicodedata.normalize("NFD", text)
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def numeric_tokens(text: str) -> set[str]:
    value = str(text or "").translate(ARABIC_DIGITS)
    return {re.sub(r"\D", "", m.group(0)) for m in NUMBER.finditer(value)}


def number_parts(text: str) -> set[str]:
    """Nombres d'un texte et leurs composantes (séparateurs . / - , espace), sans zéros de tête."""
    value = str(text or "").translate(ARABIC_DIGITS)
    parts: set[str] = set()
    for match in NUMBER.finditer(value):
        raw = match.group(0)
        parts.add(re.sub(r"\D", "", raw).lstrip("0") or "0")
        parts.update(p.lstrip("0") or "0" for p in re.split(r"[^\d]+", raw) if p)
    for match in re.finditer(r"\d+", value):
        parts.add(match.group(0).lstrip("0") or "0")
    return parts


def added_numbers(source: str, translation: str) -> int:
    """Nombres de la traduction absents de la source (signal d'ajout ou d'hallucination).

    Un nombre est accepté si sa suite de chiffres existe dans la source, ou si chacune de ses
    composantes y existe (reformatage « 3.250,00 » -> « 3 250,00 », « 17.03.2026 » -> « 17/03 »)."""
    allowed = number_parts(source)
    added = set()
    for match in NUMBER.finditer(str(translation or "").translate(ARABIC_DIGITS)):
        raw = match.group(0)
        full = re.sub(r"\D", "", raw).lstrip("0") or "0"
        if full in allowed:
            continue
        parts = [p.lstrip("0") or "0" for p in re.split(r"[^\d]+", raw) if p]
        if parts and all(p in allowed for p in parts):
            continue
        added.add(full)
    return len(added)


def chrf(hypothesis: str, reference: str, n_max: int = 6, beta: float = 2.0) -> float:
    hyp, ref = norm(hypothesis).replace(" ", ""), norm(reference).replace(" ", "")
    precisions, recalls = [], []
    for n in range(1, n_max + 1):
        h = Counter(hyp[i : i + n] for i in range(max(0, len(hyp) - n + 1)))
        r = Counter(ref[i : i + n] for i in range(max(0, len(ref) - n + 1)))
        if not h or not r:
            continue
        overlap = sum((h & r).values())
        precisions.append(overlap / sum(h.values()))
        recalls.append(overlap / sum(r.values()))
    if not precisions:
        return 0.0
    p, r = sum(precisions) / len(precisions), sum(recalls) / len(recalls)
    if p + r == 0:
        return 0.0
    return round(100 * (1 + beta**2) * p * r / (beta**2 * p + r), 2)


def check_number(item: dict, values: dict, output: str, target: str) -> bool:
    tokens = numeric_tokens(output)
    slot, kind = item["slot"], item["kind"]
    if kind == "amount":
        return f"{values['amounts'][slot]:.2f}".replace(".", "") in tokens
    if kind == "id":
        return re.sub(r"\s", "", values["ids"][slot]) in re.sub(r"\s", "", output)
    if kind == "number":
        return values["nums"][slot] in tokens
    day, month, year = values["dates"][slot]
    ascii_text = str(output or "").translate(ARABIC_DIGITS)
    for d, m, y in NUMERIC_DATE.findall(ascii_text):
        if (int(d), int(m), int(y)) == (day, month, year):
            return True
    for y, m, d in ISO_DATE.findall(ascii_text):
        if (int(d), int(m), int(y)) == (day, month, year):
            return True
    names = MONTHS.get(target, [])
    has_month = bool(names) and names[month - 1] in norm(output)
    return has_month and str(year) in tokens and (str(day) in tokens or f"{day:02d}" in tokens)


def load_entries(db_url: str | None) -> dict[str, dict]:
    if not db_url:
        return {}
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select id, source_language, source_term, target_language, target_term, domain, "
                "provenance from rag_term_entries"
            )
        ).mappings()
        return {row["id"]: dict(row) for row in rows}


def evaluate(expected_dir: Path, dump_dir: Path, reports: list[Path], db_url: str | None) -> dict:
    gen = _generator()
    entries = load_entries(db_url)
    by_term = defaultdict(set)
    for entry_id, entry in entries.items():
        key = (entry["source_language"], entry["target_language"], norm(entry["source_term"]))
        by_term[key].add(entry_id)
    docs_dir = expected_dir.parent / "docs"
    runs: dict[str, dict] = {}
    for report in reports:
        data = json.loads(report.read_text(encoding="utf-8"))
        for doc in data["documents"]:
            runs[doc["document"]] = doc
    documents = []
    for path in sorted(expected_dir.glob("*.json")):
        exp = json.loads(path.read_text(encoding="utf-8"))
        name, target = exp["document"], exp["target_language"]
        run = runs.get(name)
        if run is None:
            continue
        source_path = docs_dir / f"{name}.json"
        sources: dict[str, str] = {}
        if source_path.exists():
            ir = json.loads(source_path.read_text(encoding="utf-8"))["ir"]
            sources = {b["id"]: b["text"] for page in ir["pages"] for b in page["blocks"]}
        variants = {}
        for variant, row in sorted(run["variants"].items()):
            dump = dump_dir / f"{name}.{variant}.json"
            translated = dump.exists()
            out = json.loads(dump.read_text(encoding="utf-8")) if translated else {}
            translations = out.get("translations") or {}
            injected = set(row.get("injected_term_ids") or [])
            terms = {"total": 0, "strict": 0, "folded": 0}
            glossary = {"total": 0, "respected": 0, "rag_injected": 0}
            selection = {"expected": 0, "injected": 0, "complied": 0}
            occurrences: dict[str, list[bool]] = defaultdict(list)
            for item in exp["terms"]:
                block_out = norm(translations.get(item["block"], ""))
                want = norm(item["expected_target"])
                hit = want in block_out
                folded_hit = fold(want) in fold(block_out)
                main = gen.TERMS[item["key"]][exp["source_language"]][0]
                candidates = by_term.get((exp["source_language"], target, norm(main)), set())
                if item["authority"] == "client_glossary":
                    glossary["total"] += 1
                    glossary["respected"] += int(hit)
                    glossary["rag_injected"] += int(bool(candidates & injected))
                    continue
                occurrences[item["key"]].append(hit)
                terms["total"] += 1
                terms["strict"] += int(hit)
                terms["folded"] += int(folded_hit)
                selection["expected"] += 1
                if candidates & injected:
                    selection["injected"] += 1
                    selection["complied"] += int(hit)
            numbers = Counter()
            for item in exp["numbers"]:
                ok = check_number(item, exp["values"], translations.get(item["block"], ""), target)
                numbers[f"{item['kind']}_total"] += 1
                numbers[f"{item['kind']}_ok"] += int(ok)
            withheld = {"ambiguous_injected": 0, "sibling_injected": 0, "unknown_ids": 0}
            for entry_id in injected:
                entry = entries.get(entry_id)
                if entry is None:
                    withheld["unknown_ids"] += int(bool(entries))
                    continue
                provenance = entry.get("provenance") or ""
                withheld["ambiguous_injected"] += int(provenance.endswith("-ambigu"))
                withheld["sibling_injected"] += int(provenance.endswith("-domaine-frere"))
            repeated = [hits for hits in occurrences.values() if len(hits) >= 2]
            consistency = {
                "repeated_terms": len(repeated),
                "all_correct": sum(all(h) for h in repeated),
            }
            added = 0
            abnormal_length = 0
            if translated:
                for block_id, text in translations.items():
                    added += added_numbers(sources.get(block_id, ""), text)
                    reference_text = exp["reference_candidate"].get(block_id, "")
                    if reference_text:
                        ratio = len(str(text)) / max(1, len(reference_text))
                        abnormal_length += int(ratio < 0.5 or ratio > 2.0)
            ordered = sorted(exp["reference_candidate"])
            hyp = "\n".join(str(translations.get(b, "")) for b in ordered)
            ref = "\n".join(exp["reference_candidate"][b] for b in ordered)
            variants[variant] = {
                "translated": translated,
                "decision": row.get("decision"),
                "injected_terms": len(injected),
                "terms": terms,
                "glossary": glossary,
                "selection": selection,
                "numbers": dict(numbers),
                "withheld": withheld,
                "consistency": consistency,
                "added_numbers": added if translated else None,
                "abnormal_length_blocks": abnormal_length if translated else None,
                "chrf_proxy": chrf(hyp, ref) if translated else None,
                "untranslated_blocks": row.get("untranslated_blocks"),
                "issues": len(out.get("issues") or []) if translated else None,
                "issue_codes": sorted({str(i.get("code")) for i in out.get("issues") or []}),
                "usage": row.get("usage"),
                "translation_ms": row.get("translation_ms"),
                "resolver_latency_ms": row.get("resolver_latency_ms"),
                "prompt_tokens_total": row.get("prompt_tokens_total"),
            }
        documents.append(
            {
                "document": name,
                "category": exp["category"],
                "domain": exp["domain"],
                "pair": f"{exp['source_language']}>{target}",
                "simulated_ocr_noise": exp["simulated_ocr_noise"],
                "B_identical_to_A": run["comparison"].get("B_identical_to_A"),
                "C_blocks_changed": run["comparison"].get("C_blocks_changed"),
                "variants": variants,
            }
        )
    return {"documents": documents, "aggregates": aggregate(documents)}


def _sum(rows: list[dict], path: tuple[str, ...]) -> int:
    total = 0
    for row in rows:
        value: Any = row
        for key in path:
            value = (value or {}).get(key) if isinstance(value, dict) else None
        total += int(value or 0)
    return total


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def summarize(rows: list[dict]) -> dict:
    """Plan RAG (sélection, retenues) sur tous les documents ; qualité de sortie sur les
    seuls documents traduits (un document non traduit n'est ni un succès ni un échec)."""
    translated = [r for r in rows if r.get("translated")]
    t = translated
    chrfs = [r["chrf_proxy"] for r in t if r.get("chrf_proxy") is not None]
    num_ok = sum(_sum(t, ("numbers", f"{k}_ok")) for k in ("amount", "date", "id", "number"))
    num_total = sum(_sum(t, ("numbers", f"{k}_total")) for k in ("amount", "date", "id", "number"))
    return {
        "documents": len(rows),
        "translated": len(t),
        "plan_selection_recall": _ratio(
            _sum(rows, ("selection", "injected")), _sum(rows, ("selection", "expected"))
        ),
        "plan_ambiguous_injected": _sum(rows, ("withheld", "ambiguous_injected")),
        "plan_sibling_injected": _sum(rows, ("withheld", "sibling_injected")),
        "plan_glossary_rag_injected": _sum(rows, ("glossary", "rag_injected")),
        "resolver_ms_max": max(
            (float(r.get("resolver_latency_ms") or 0) for r in rows), default=0.0
        ),
        "terms_total": _sum(t, ("terms", "total")),
        "terms_strict_ok": _sum(t, ("terms", "strict")),
        "terms_strict_rate": _ratio(_sum(t, ("terms", "strict")), _sum(t, ("terms", "total"))),
        "terms_folded_rate": _ratio(_sum(t, ("terms", "folded")), _sum(t, ("terms", "total"))),
        "glossary_respected": f"{_sum(t, ('glossary', 'respected'))}/{_sum(t, ('glossary', 'total'))}",
        "model_compliance": _ratio(
            _sum(t, ("selection", "complied")), _sum(t, ("selection", "injected"))
        ),
        "numbers_ok": f"{num_ok}/{num_total}",
        "numbers_rate": _ratio(num_ok, num_total),
        "repeated_terms_consistent": (
            f"{_sum(t, ('consistency', 'all_correct'))}/{_sum(t, ('consistency', 'repeated_terms'))}"
        ),
        "added_numbers": _sum(t, ("added_numbers",)),
        "abnormal_length_blocks": _sum(t, ("abnormal_length_blocks",)),
        "issues_total": _sum(t, ("issues",)),
        "untranslated_blocks": _sum(t, ("untranslated_blocks",)),
        "chrf_proxy_mean": round(sum(chrfs) / len(chrfs), 2) if chrfs else None,
        "prompt_tokens": _sum(t, ("usage", "prompt_tokens")),
        "completion_tokens": _sum(t, ("usage", "completion_tokens")),
        "translation_s": round(sum(float(r.get("translation_ms") or 0) for r in t) / 1000, 1),
    }


def aggregate(documents: list[dict]) -> dict:
    out: dict[str, Any] = {"by_variant": {}, "by_pair": {}, "by_category": {}}
    variants = sorted({v for d in documents for v in d["variants"]})
    for variant in variants:
        rows = [d["variants"][variant] for d in documents if variant in d["variants"]]
        out["by_variant"][variant] = summarize(rows)
        for key, field in (("by_pair", "pair"), ("by_category", "category")):
            groups = defaultdict(list)
            for d in documents:
                if variant in d["variants"]:
                    groups[d[field]].append(d["variants"][variant])
            for group, rows_g in sorted(groups.items()):
                out[key].setdefault(group, {})[variant] = summarize(rows_g)
    b_docs = [d for d in documents if d.get("B_identical_to_A") is not None]
    for label, keep in (("translated", True), ("plan_only", False)):
        group = [d for d in b_docs if bool(d["variants"]["B"].get("translated")) is keep]
        out[f"B_identical_to_A_{label}"] = (
            f"{sum(bool(d['B_identical_to_A']) for d in group)}/{len(group)}"
        )
    out["C_blocks_changed_total"] = sum(int(d.get("C_blocks_changed") or 0) for d in documents)
    out["notice"] = (
        "Mesures objectives par construction sur corpus SYNTHÉTIQUE ; chrF = indicateur de "
        "substitution contre références candidates NON humaines ; fidélité sémantique NON MESURÉE "
        "(aucun annotateur) ; validation humaine obligatoire quel que soit le score."
    )
    return out


PACK_COLUMNS = (
    "document",
    "pair",
    "category",
    "block",
    "translation_label",
    "source",
    "translation",
    "terminology",
    "accuracy",
    "numbers_dates_ids",
    "fluency",
    "register",
    "severity",
    "comment",
)


def annotation_pack(expected_dir: Path, dump_dir: Path, out: Path, seed: int) -> dict:
    """Paquet d'annotation aveugle (docs/rag/ANNOTATION-HUMAINE.md) : pack.csv + key.json."""
    docs_dir = expected_dir.parent / "docs"
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o700)
    rng = random.Random(seed)
    key: dict[str, dict[str, str]] = {}
    rows = []
    for path in sorted(expected_dir.glob("*.json")):
        exp = json.loads(path.read_text(encoding="utf-8"))
        name = exp["document"]
        dumps = {v: dump_dir / f"{name}.{v}.json" for v in ("A", "C")}
        source_path = docs_dir / f"{name}.json"
        if not all(d.exists() for d in dumps.values()) or not source_path.exists():
            continue
        labels = ["X", "Y"]
        rng.shuffle(labels)
        key[name] = {labels[0]: "A", labels[1]: "C"}
        ir = json.loads(source_path.read_text(encoding="utf-8"))["ir"]
        sources = {b["id"]: b["text"] for page in ir["pages"] for b in page["blocks"]}
        translations = {
            label: json.loads(dumps[variant].read_text(encoding="utf-8")).get("translations") or {}
            for label, variant in key[name].items()
        }
        for block in sorted(sources):
            for label in sorted(translations):
                rows.append(
                    {
                        "document": name,
                        "pair": f"{exp['source_language']}>{exp['target_language']}",
                        "category": exp["category"],
                        "block": block,
                        "translation_label": label,
                        "source": sources[block],
                        "translation": translations[label].get(block, ""),
                    }
                )
    with (out / "pack.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PACK_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    (out / "key.json").write_text(json.dumps(key, indent=1, sort_keys=True), encoding="utf-8")
    for name in ("pack.csv", "key.json"):
        (out / name).chmod(0o600)
    return {"documents": len(key), "rows": len(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--translations", type=Path, required=True)
    parser.add_argument("--report", type=Path, action="append", required=True)
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--annotation-pack", type=Path, default=None, help="dossier HORS dépôt du paquet aveugle"
    )
    parser.add_argument("--pack-seed", type=int, default=20261030)
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if ROOT in out.parents:
        raise SystemExit("--out doit être hors du dépôt")
    if args.annotation_pack is not None:
        pack = args.annotation_pack.resolve()
        if pack == ROOT or ROOT in pack.parents:
            raise SystemExit("--annotation-pack doit être hors du dépôt (textes)")
        print(json.dumps(annotation_pack(args.expected, args.translations, pack, args.pack_seed)))
    result = evaluate(args.expected, args.translations, args.report, args.db_url)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result["aggregates"]["by_variant"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
