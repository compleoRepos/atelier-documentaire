"""RUN26 scorecard: documentary confidence per document and per run, computed
ONLY from produced artefacts, with the product module
``app.documents.confidence_score`` (single formula, single source of truth).

Inputs per run: an out dir with DOC-xxx/{analysis.json, translation.json,
interim-service-result.json, interim-run-summary.json, candidate.pdf} and, when the
run produced it, ``execution-journal.jsonl``; the measure_v2 JSON of the same
runs (coverage, rendering) and the compare_runs_sheets dir (visual regions).

Output: anonymised JSON (counts, ratios, codes; never text), written OUTSIDE the
repository. Usage:

  PYTHONPATH=backend:tools/recette python tools/recette/scorecard.py \
      --metrics M.json --sheets SHEETS_DIR --run run25=DIR --run run26=DIR --out OUT.json
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import fitz
from app.documents import confidence_score as cs
from app.documents.language_evidence import (
    COMMON_ZIPF,
    FOREIGN_MARGIN,
    _other_isos,
    _zipf,
    available,
)
from measure_v2 import changed, expected_scope, recompute_language

REPO = Path(__file__).resolve().parents[2]
VERSION = "scorecard-1"
MAX_CONTEXT = 32768
OCR_TRUSTED = 0.80
OCR_UNRELIABLE = 0.60
LENGTH_MIN_SOURCE = 20
LENGTH_HIGH = 3.0
LENGTH_LOW = 1 / 3
FOREIGN_SHARE_MAX = 0.2
LATIN_SHARE = 0.5
_DIGITS = re.compile(r"\d+")
_WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_ADDRESS = re.compile(r"\S+@\S+|https?://\S+|www\.\S+", re.IGNORECASE)
GENERATION_MODES = {
    "NEW_MODEL_GENERATION",
    "MIXED_MEMORY_AND_NEW_GENERATION",
    "TRANSLATION_MEMORY_REUSE_ONLY",
    "NO_MODEL_CALL",
    "RECORDED_RESULT_REPLAY",
}


def _ascii_digits(text: str) -> str:
    return "".join(
        str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch for ch in text
    )


def digit_sequence(text: str | None) -> list[str]:
    return _DIGITS.findall(_ascii_digits(text or ""))


def _latin_letter_share(text: str) -> float | None:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return None
    latin = sum("LATIN" in unicodedata.name(ch, "") for ch in letters)
    return latin / len(letters)


def target_is_french(target: str, languages: list | None = None) -> bool | None:
    """Is a produced target French?

    * mostly non-Latin letters (< 50 %) -> not French;
    * evaluated words: Latin, >= 3 letters, lower-case or ALL-CAPS. Title-case
      words are left out: proper names, companies and places are kept
      verbatim on purpose and are no evidence either way;
    * informative word: common (zipf >= 3) in French or a document language;
    * foreign word: common in a document language and more common there than
      in French by the language_evidence margin (1.0);
    * French when foreign words are at most 20 % of informative words; None
      (not evaluable) when no informative word remains.
    """
    share = _latin_letter_share(target)
    if share is None:
        return None
    if share < LATIN_SHARE:
        return False
    isos = _other_isos(languages)
    informative = foreign = 0
    for raw in _WORD.findall(_ADDRESS.sub(" ", target)):
        if raw[0].isupper() and not raw.isupper():
            continue
        word = raw.lower()
        if not all("a" <= c <= "z" or "\u00c0" <= c <= "\u024f" for c in word):
            continue
        fr = _zipf(word, "fr")
        best = max(_zipf(word, iso) for iso in isos)
        if max(fr, best) < COMMON_ZIPF:
            continue
        informative += 1
        if best >= COMMON_ZIPF and best >= fr + FOREIGN_MARGIN:
            foreign += 1
    if not informative:
        return None
    return foreign / informative <= FOREIGN_SHARE_MAX


def _ratio(num: float, den: float):
    return cs.NOT_APPLICABLE if den <= 0 else max(0.0, min(1.0, num / den))


def _load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def _journal(run_dir: Path) -> list[dict]:
    path = run_dir / "execution-journal.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def document_components(run_dir: Path, doc: str, metrics: dict, regions: dict, label: str):
    d = run_dir / doc
    ir = _load(d / "analysis.json")
    tr = _load(d / "translation.json")
    service = _load(d / "interim-service-result.json")
    summary = _load(d / "interim-run-summary.json")
    telemetry = service.get("translation_telemetry") or tr.get("translation_telemetry") or {}
    translations = tr.get("translations") or {}
    languages = [x.get("code") if isinstance(x, dict) else x for x in ir.get("languages") or []]
    blocks = [b for p in ir.get("pages", []) for b in p.get("blocks", [])]
    info = Counter()

    fr_ok = fr_eval = 0
    digit_blocks = digit_ok = 0
    defects = Counter()
    exp_chars = exp_trusted = 0
    tr_chars = unreliable_chars = length_chars = 0
    for b in blocks:
        src = str(b.get("text") or "")
        tgt = translations.get(str(b["id"]))
        language = recompute_language(src, languages)
        size = len(src.strip())
        if expected_scope(src, language, languages) is None:
            exp_chars += size
            conf = b.get("confidence")
            if isinstance(conf, (int, float)) and conf >= OCR_TRUSTED:
                exp_trusted += size
        if not changed(src, tgt):
            continue
        tr_chars += size
        verdict = target_is_french(tgt, languages)
        if verdict is not None:
            fr_eval += size
            fr_ok += size if verdict else 0
        s_digits, t_digits = digit_sequence(src), digit_sequence(tgt)
        if s_digits or t_digits:
            digit_blocks += 1
            if s_digits == t_digits:
                digit_ok += 1
            elif Counter(s_digits) != Counter(t_digits):
                defects["ENTITY_DIGITS_MISMATCH"] += 1
            else:
                defects["ENTITY_DIGITS_REORDERED"] += 1
        conf = b.get("confidence")
        if isinstance(conf, (int, float)) and conf < OCR_UNRELIABLE:
            unreliable_chars += size
        if size >= LENGTH_MIN_SOURCE:
            ratio = len(tgt.strip()) / max(1, size)
            if ratio > LENGTH_HIGH or ratio < LENGTH_LOW:
                length_chars += size

    m = metrics.get(doc) or {}
    render = m.get("render") or {}
    measured_blocks = sum(
        int(render.get(k) or 0)
        for k in ("blocks_written", "blocks_partial", "blocks_absent", "blocks_no_tokens")
    )
    inserted = int(render.get("inserted_words") or 0)
    candidate = d / "candidate.pdf"
    try:
        with fitz.open(candidate) as pdf:
            candidate_pages = len(pdf)
    except Exception:  # missing or unreadable candidate
        candidate_pages = None
    region_total = int(regions.get("regions") or 0)
    region_altered = (regions.get("altered") or {}).get(label)

    sent = telemetry.get("requests_sent")
    traces = telemetry.get("request_trace")
    provenance = (telemetry.get("block_provenance") or {}).get("blocks") or {}
    reconciled = (
        isinstance(traces, list)
        and isinstance(sent, int)
        and len(traces) == sent
        and all(t.get("correlation_id") and t.get("response_id") for t in traces)
    )
    journal = _journal(run_dir)
    starts = [e for e in journal if e.get("event") == "run_start"]
    ends = [e for e in journal if e.get("event") == "document_end" and e.get("document_id") == doc]
    budget = summary.get("budget") or {}
    reserved = budget.get("max_reserved_total_tokens")
    components = {
        "coverage": {"written_share": m.get("coverage_written")},
        "translation": {
            "target_language": _ratio(fr_ok, fr_eval) if available() else None,
            "semantic_accuracy": None,
        },
        "source_fidelity": {
            "pages_preserved": None
            if candidate_pages is None
            else float(candidate_pages == len(ir.get("pages", []))),
            "regions_unaltered": cs.NOT_APPLICABLE
            if region_total == 0
            else (None if region_altered is None else 1 - region_altered / region_total),
        },
        "entities": {"digit_sequences": _ratio(digit_ok, digit_blocks)},
        "layout": {
            "no_text_over_ink": _ratio(
                measured_blocks - int(render.get("blocks_over_ink") or 0), measured_blocks
            ),
            "no_collision": _ratio(inserted - int(render.get("words_colliding") or 0), inserted),
            "in_page": _ratio(inserted - int(render.get("words_out_of_page") or 0), inserted),
            "not_truncated": _ratio(
                measured_blocks - int(render.get("blocks_partial") or 0), measured_blocks
            ),
        },
        "ocr": {
            "engine_confidence": _ratio(exp_trusted, exp_chars)
            if any(p.get("scanned") for p in ir.get("pages", []))
            else cs.NOT_APPLICABLE,
            "character_accuracy": None
            if any(p.get("scanned") for p in ir.get("pages", []))
            else cs.NOT_APPLICABLE,
        },
        "hallucination": {
            "no_unreliable_source_translated": _ratio(tr_chars - unreliable_chars, tr_chars),
            "no_length_anomaly": _ratio(tr_chars - length_chars, tr_chars),
            "proven_by_reference": None,
        },
        "evidence": {
            "original_unchanged": float(summary.get("original_sha256_unchanged") is True),
            "block_provenance": float(
                bool(blocks) and all(str(b["id"]) in provenance for b in blocks)
            ),
            "request_reconciliation": float(reconciled),
            "generation_mode": float(summary.get("generation_mode") in GENERATION_MODES),
            "execution_journal": float(
                bool(starts)
                and bool(ends)
                and all(e.get("code_fingerprint") and e.get("git_head") for e in starts)
            ),
            "candidate_produced": float(candidate_pages is not None),
            "budget_respected": float(
                budget.get("violations") == 0
                and (not sent or (isinstance(reserved, int) and reserved <= MAX_CONTEXT))
            ),
        },
    }
    critical = [
        {"code": code, "count": int(n), "source": "product"}
        for code, n in sorted((m.get("critical_codes") or {}).items())
    ] + [
        {"code": code, "count": int(n), "source": "scorecard"}
        for code, n in sorted(defects.items())
    ]
    blocking = []
    if summary.get("original_sha256_unchanged") is not True:
        blocking.append("ORIGINAL_INTEGRITY_NOT_PROVEN")
    if candidate_pages is None:
        blocking.append("CANDIDATE_MISSING")
    if any(i.get("code") == "EVIDENCE_REQUEST_COUNT_MISMATCH" for i in tr.get("issues") or []):
        blocking.append("EVIDENCE_REQUEST_COUNT_MISMATCH")
    info.update(
        {
            "expected_chars": int(m.get("expected_chars") or 0),
            "written_chars": int(m.get("written_chars") or 0),
            "partial_chars": int(m.get("partial_chars") or 0),
            "absent_chars": int(m.get("absent_chars") or 0),
            "not_attempted_chars": int(m.get("not_attempted_chars") or 0),
            "translated_chars_evaluated": tr_chars,
            "digit_blocks": digit_blocks,
            "regions": region_total,
            "regions_altered": region_altered,
            "requests_sent": sent,
        }
    )
    extra = {
        "status_blocks": m.get("status_blocks"),
        "generation_mode": summary.get("generation_mode"),
        "block_provenance_summary": summary.get("block_provenance_summary"),
        "counts": dict(info),
    }
    return components, critical, blocking, extra


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--metrics", required=True, type=Path)
    ap.add_argument("--sheets", required=True, type=Path)
    ap.add_argument("--run", action="append", required=True, help="label=out_dir")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--docs", nargs="*", default=[f"DOC-00{n}" for n in range(1, 9)])
    args = ap.parse_args()
    out = args.out.resolve()
    if REPO == out or REPO in out.parents:
        raise SystemExit("--out doit être hors du dépôt")
    metrics = json.loads(args.metrics.read_text())
    result = {
        "version": VERSION,
        "score_version": cs.VERSION,
        "metrics_version": metrics.get("version"),
        "runs": {},
    }
    for spec in args.run:
        label, path = spec.split("=", 1)
        run_dir = Path(path)
        run_metrics = (metrics.get("runs") or {}).get(label)
        if run_metrics is None:
            raise SystemExit(f"{label}: absent du fichier de mesure")
        docs = {}
        for doc in args.docs:
            regions = _load(args.sheets / doc / "visual-regions.json")
            components, critical, blocking, extra = document_components(
                run_dir, doc, run_metrics, regions, label
            )
            scored = cs.score_document(components, critical, blocking=blocking)
            docs[doc] = {**scored, **extra}
        result["runs"][label] = {"documents": docs, "corpus": cs.score_corpus(docs)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True))
    for label, run in result["runs"].items():
        corpus = run["corpus"]
        print(f"{label}: score {corpus['score']} [max {corpus['score_max']}]")


if __name__ == "__main__":
    main()
