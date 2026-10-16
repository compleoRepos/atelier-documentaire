"""Run25 anomaly register - one row per defective block, same rules for every run.

For every document of a run directory, every block is classified with the
measure_v2 rules (language recomputed from the source text, run-independent
expected scope, run18 §10 statuses, rendering measured in the candidate PDF)
and every anomaly gets one row:

  SOURCE_RESIDUAL         expected block whose target equals the source (the
                          reader still sees the source language), with reason;
  TARGET_MISSING          translated, but not found in the PDF (render refusal);
  TEXT_CUT                translated, only partly found in the PDF;
  TEXT_OVER_INK           translated words drawn over residual original ink;
  OUT_OF_SCOPE_REWRITTEN  French / identifier / name block rewritten;
  LOW_OCR_CONFIDENCE_TRANSLATED  translated and written from an OCR line whose
                          confidence is below the trusted-size threshold of the
                          renderer (risk: garbled OCR translated as valid text);
  CRITICAL_ENTITY_REVIEW  entity / hallucination alert attached to the block;
  PAGE_LEVEL              critical page/region alert without a block id.

Rows hold ids, page, rounded geometry, lengths, statuses and issue codes only:
no text, no file name, no hash. The output must be outside the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.documents.block_status import classify_blocks  # noqa: E402
from app.documents.pdf_fidelity import SCAN_TRUSTED_SIZE_CONFIDENCE  # noqa: E402
from measure_v2 import _dedupe, changed, expected_scope, recompute_language  # noqa: E402
from render_outcome import measure_candidate  # noqa: E402

VERSION = "anomaly-register-run25-1"
ENTITY_CODES = {
    "UNPROTECTED_ENTITY_REQUIRES_REVIEW",
    "PROTECTED_ENTITY_CHANGED",
    "OCR_CRITICAL_ENTITY_DISAGREEMENT",
    "HALLUCINATION_UNIT_CHANGED",
    "HALLUCINATION_NUMBER_CHANGED",
    "HALLUCINATION_DATE_CHANGED",
    "HALLUCINATION_AMOUNT_CHANGED",
}


def _issue_blocks(issue: dict) -> list[str]:
    ids = [str(issue["block_id"])] if issue.get("block_id") else []
    return ids + [str(b) for b in issue.get("block_ids") or [] if str(b) not in ids]


def _r(box) -> list[float] | None:
    return [round(float(v), 1) for v in box] if box else None


def register_doc(doc_dir: Path) -> dict:
    ir = json.loads((doc_dir / "analysis.json").read_text())
    tr = json.loads((doc_dir / "translation.json").read_text())
    translations = tr.get("translations") or {}
    issues = _dedupe(tr.get("issues"))
    languages = [x.get("code") if isinstance(x, dict) else x for x in ir.get("languages") or []]
    for page in ir.get("pages", []):
        for block in page.get("blocks", []):
            block["language"] = recompute_language(str(block.get("text") or ""), languages)
    status = classify_blocks(ir, translations, issues)["blocks"]
    candidate = doc_dir / "candidate.pdf"
    outcome = (
        measure_candidate(candidate, ir.get("pages", []), translations, changed)["blocks"]
        if candidate.is_file()
        else {}
    )
    by_block: dict[str, list[dict]] = defaultdict(list)
    page_level = []
    for issue in issues:
        ids = _issue_blocks(issue)
        for bid in ids:
            by_block[bid].append(issue)
        if not ids and issue.get("severity") == "critical":
            page_level.append(issue)
    rows = []
    for page in ir.get("pages", []):
        pno = int(page.get("number", 0))
        for block in page.get("blocks", []):
            bid = str(block.get("id"))
            source = str(block.get("text") or "")
            target = translations.get(bid)
            scope = expected_scope(source, block["language"], languages)
            is_changed = changed(source, target)
            st = status[bid]
            codes = sorted({str(i.get("code")) for i in by_block.get(bid, [])})
            render = outcome.get(bid) or {}
            base = {
                "page": pno,
                "block": bid,
                "bbox": _r(block.get("bbox")),
                "role": block.get("role"),
                "lines": int(block.get("line_count") or 1),
                "confidence": block.get("confidence"),
                "language": block["language"],
                "source_chars": len(source.strip()),
                "target_chars": len((target or "").strip()) if is_changed else 0,
                "scope": scope or "expected",
                "status": st["status"],
                "reason": st["reason"],
                "render": render.get("status") if is_changed else None,
                "recall": render.get("recall") if is_changed else None,
                "over_ink": render.get("over_ink") if is_changed else None,
                "codes": codes,
            }
            types = []
            if scope is None and not is_changed:
                types.append("SOURCE_RESIDUAL")
            if scope is None and is_changed:
                if render.get("status", "ABSENT") == "ABSENT":
                    types.append("TARGET_MISSING")
                elif render.get("status") == "PARTIAL":
                    types.append("TEXT_CUT")
            if is_changed and (render.get("over_ink") or 0) >= 0.3:
                types.append("TEXT_OVER_INK")
            if scope is not None and is_changed:
                types.append("OUT_OF_SCOPE_REWRITTEN")
            if (
                is_changed
                and render.get("status") in {"WRITTEN", "PARTIAL"}
                and block.get("confidence") is not None
                and float(block["confidence"]) < SCAN_TRUSTED_SIZE_CONFIDENCE
                and page.get("scanned")
            ):
                types.append("LOW_OCR_CONFIDENCE_TRANSLATED")
            if set(codes) & ENTITY_CODES:
                types.append("CRITICAL_ENTITY_REVIEW")
            for kind in types:
                rows.append({"type": kind, **base})
    for issue in page_level:
        rows.append(
            {
                "type": "PAGE_LEVEL",
                "page": issue.get("page"),
                "block": None,
                "bbox": _r(issue.get("bbox")) if isinstance(issue.get("bbox"), list) else None,
                "codes": [str(issue.get("code"))],
                "region_id": issue.get("region_id"),
            }
        )
    counts = Counter(r["type"] for r in rows)
    chars = Counter()
    for r in rows:
        chars[r["type"]] += r.get("source_chars") or 0
    return {"rows": rows, "counts": dict(counts), "source_chars": dict(chars)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", action="append", required=True, help="label=run_out_dir (repeat)")
    ap.add_argument("--out", type=Path, required=True, help="JSON output (outside the repo)")
    ap.add_argument("--only", action="append", help="document id (repeat)")
    args = ap.parse_args()
    out = args.out.resolve()
    if REPO in out.parents or out == REPO:
        sys.exit("refusing to write the register inside the repository")
    result = {"version": VERSION, "runs": {}}
    for spec in args.run:
        label, path = spec.split("=", 1)
        docs = sorted(p for p in Path(path).iterdir() if (p / "analysis.json").is_file())
        if args.only:
            docs = [p for p in docs if p.name in args.only]
        result["runs"][label] = {d.name: register_doc(d) for d in docs}
        print(label, "ok", flush=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
