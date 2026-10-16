"""Run18 measurement v2 - one method for every run (baseline, run17, run18...).

Why v2 (defects of the v1 tool found in the run18 audit):
  * v1 took each block's language from the run's own analysis; the detectors
    differed between runs, so the denominators were not comparable;
  * v1 credited the rewriting of a FRENCH block as a translation;
  * v1 counted three RENDER_*_MISSING codes carrying the same count (x3);
  * v1 "written" accepted the first three target words anywhere on the page.

v2, for every run and document:
  1. recomputes each block's language from its SOURCE TEXT with the same chain
     (application detector, then the offline lexical refinement), whatever the
     run's own analysis said, and decides the EXPECTED scope from the source
     text only (``expected_scope``): a run that over-protects or over-guards
     does not shrink its own denominator;
  2. classifies every block with ``app.documents.block_status.classify_blocks``
     (statuses of run18 §10) on that recomputed language;
  3. measures in the candidate PDF what the reader actually gets
     (``render_outcome.measure_candidate``: WRITTEN / PARTIAL / ABSENT,
     text over residual ink, colliding words, words out of page), independent
     of the renderer's own alerts.

Outputs counters only (no text, no file name, no hash) into a directory that
must be outside the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.ai.translation.typography import typography_equivalent  # noqa: E402
from app.documents.block_status import (  # noqa: E402  # noqa: E402
    _NUMERIC,
    STATUSES,
    _proper_name_or_reference,
    classify_blocks,
)
from app.documents.language_evidence import (  # noqa: E402
    VERSION as LEXICON_VERSION,
)
from app.documents.language_evidence import (  # noqa: E402
    available,
    has_linguistic_content,
    identical_in_french,  # noqa: E402
    refine_language,
)
from app.documents.line_verification import identifier_only  # noqa: E402
from app.documents.pipeline import _requires_translation  # noqa: E402
from app.domain.classification import detect_language  # noqa: E402
from render_outcome import measure_candidate  # noqa: E402

VERSION = "measure-v2.1-run18"  # v2.1: symmetric search zone (render_outcome._zone)


def _norm(text: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", text or "").split()).casefold()


def changed(source: str, target: str | None) -> bool:
    if not target or not target.strip():
        return False
    return _norm(source) != _norm(target) and not typography_equivalent(source, target)


def _is_french(code: str | None) -> bool:
    return str(code or "").lower() in {"fr", "fra", "fre", "french"}


def recompute_language(text: str, document_languages: list) -> str:
    if not has_linguistic_content(text):
        return "unknown"
    detected = detect_language(text)[0]
    refined = refine_language(text, detected, document_languages)
    return refined["language"] if refined else detected


def expected_scope(text: str, language: str, document_languages: list) -> str | None:
    """Run-INDEPENDENT decision, from the source text only: return None when
    the block must be translated, else the reason it is out of scope. A run's
    own flags (protection, guards, OCR reliability) never shrink the
    denominator; they only explain why an expected block was not written."""
    source = text.strip()
    if not has_linguistic_content(source):
        return "no_linguistic_content"
    if _is_french(language):
        return "already_french"
    if identifier_only(source) or not _requires_translation(source) or _NUMERIC.fullmatch(source):
        return "identifier_or_number"
    languages = [language, *document_languages]
    if identical_in_french(source, languages):
        return "identical_in_french"
    if _proper_name_or_reference(source, languages):
        return "proper_name_or_reference"
    return None


def _dedupe(issues: list) -> list[dict]:
    seen, out = set(), []
    for issue in issues or []:
        if not isinstance(issue, dict):
            continue
        key = json.dumps(issue, sort_keys=True, ensure_ascii=False, default=str)
        if key not in seen:
            seen.add(key)
            out.append(issue)
    return out


def measure_doc(doc_dir: Path) -> dict:
    ir = json.loads((doc_dir / "analysis.json").read_text())
    tr = json.loads((doc_dir / "translation.json").read_text())
    translations = tr.get("translations") or {}
    issues = _dedupe(tr.get("issues"))
    languages = [x.get("code") if isinstance(x, dict) else x for x in ir.get("languages") or []]
    # 1. same language rule for every run
    for page in ir.get("pages", []):
        for block in page.get("blocks", []):
            block["language_run"] = block.get("language")
            block["language"] = recompute_language(str(block.get("text") or ""), languages)
    # 2. same status rule
    status = classify_blocks(ir, translations, issues)["blocks"]
    # 3. same rendering measure
    candidate = doc_dir / "candidate.pdf"
    outcome = (
        measure_candidate(candidate, ir.get("pages", []), translations, changed)
        if candidate.is_file()
        else {"blocks": {}, "aggregate": {}}
    )
    c = Counter()
    chars = Counter()
    reasons = Counter()
    scopes = Counter()
    not_attempted = Counter()
    absent_by_reason = Counter()
    for page in ir.get("pages", []):
        for block in page.get("blocks", []):
            bid = str(block.get("id"))
            source = str(block.get("text") or "")
            n = len(source.strip())
            st = status[bid]["status"]
            reasons[f"{st}:{status[bid]['reason']}"] += 1
            c[f"status:{st}"] += 1
            chars[f"status:{st}"] += n
            tgt = translations.get(bid)
            is_changed = changed(source, tgt)
            scope = expected_scope(source, block["language"], languages)
            if scope is not None:
                scopes[scope] += n
                if scope == "already_french" and is_changed:
                    c["french_rewritten"] += 1
                    chars["french_rewritten"] += n
                elif is_changed:  # e.g. an identifier rewritten: visible, never credited
                    c["changed_outside_expected"] += 1
                    chars["changed_outside_expected"] += n
                continue
            chars["expected"] += n
            c["expected"] += 1
            if not is_changed:
                chars["not_attempted"] += n
                not_attempted[f"{st}:{status[bid]['reason']}"] += n
                continue
            chars["attempted"] += n
            rendered = (outcome["blocks"].get(bid) or {}).get("status", "ABSENT")
            chars[f"render:{rendered}"] += n
            if rendered in {"ABSENT", "PARTIAL"}:
                absent_by_reason[f"{rendered}:{st}:{status[bid]['reason']}"] += n
            c[f"render:{rendered}"] += 1
    expected = chars["expected"] or 0
    written = chars["render:WRITTEN"] + chars["render:NO_TOKENS"]
    codes = Counter(str(i.get("code")) for i in issues)
    critical = Counter(str(i.get("code")) for i in issues if i.get("severity") == "critical")
    summary_path = doc_dir / "interim-run-summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.is_file() else {}
    return {
        "blocks": sum(len(p.get("blocks", [])) for p in ir.get("pages", [])),
        "pages": len(ir.get("pages", [])),
        "status_blocks": {s: c[f"status:{s}"] for s in STATUSES},
        "status_chars": {s: chars[f"status:{s}"] for s in STATUSES},
        "status_reasons": dict(sorted(reasons.items())),
        "expected_chars": expected,
        "attempted_chars": chars["attempted"],
        "written_chars": written,
        "partial_chars": chars["render:PARTIAL"],
        "absent_chars": chars["render:ABSENT"],
        "not_attempted_chars": chars["not_attempted"],
        "not_attempted_chars_by_status_reason": dict(sorted(not_attempted.items())),
        "partial_or_absent_chars_by_status_reason": dict(sorted(absent_by_reason.items())),
        "out_of_scope_chars": dict(sorted(scopes.items())),
        "coverage_attempted": round(chars["attempted"] / expected, 4) if expected else None,
        "coverage_written": round(written / expected, 4) if expected else None,
        "changed_outside_expected_chars": chars["changed_outside_expected"],
        "french_rewritten_blocks": c["french_rewritten"],
        "french_rewritten_chars": chars["french_rewritten"],
        "render": outcome["aggregate"],
        "issue_codes": dict(sorted(codes.items())),
        "critical_codes": dict(sorted(critical.items())),
        "requests_sent": summary.get("requests_sent"),
        "budget": summary.get("budget"),
        "served_model": summary.get("served_model"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", action="append", required=True, help="label=run_out_dir (repeat)")
    ap.add_argument("--out", type=Path, required=True, help="JSON output (outside the repo)")
    ap.add_argument("--only", action="append", help="document id (repeat)")
    args = ap.parse_args()
    out = args.out.resolve()
    if REPO in out.parents:
        sys.exit("refusing to write measurements inside the repository")
    result = {
        "version": VERSION,
        "lexicon": {"available": available(), "version": LEXICON_VERSION},
        "runs": {},
    }
    for spec in args.run:
        label, path = spec.split("=", 1)
        run_dir = Path(path)
        docs = sorted(p for p in run_dir.iterdir() if (p / "analysis.json").is_file())
        if args.only:
            docs = [p for p in docs if p.name in args.only]
        result["runs"][label] = {}
        for doc_dir in docs:
            result["runs"][label][doc_dir.name] = measure_doc(doc_dir)
            print(label, doc_dir.name, "ok", flush=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
