"""Corpus acceptance metrics. Emits counters only, never document text.

Usage:
  measure_corpus_metrics.py <run_out_dir> <label> --dest-dir <private_dir>
                            [--ocr] [--union-with <reference_run_out_dir>]

<run_out_dir> holds one directory per document (analysis.json, translation.json,
interim-run-summary.json, candidate.pdf) as written by tools/interim_owner_corpus_run.py.
Inputs and outputs are private: the tool refuses a destination inside this
repository (metrics are anonymised counters, but the OCR cache is not).

Metrics per document (character-weighted so that line-level (baseline) and
paragraph-level (grouped) segmentations are comparable):
  * coverage: translated source chars / (translated + reported untranslated) chars
  * written: translated chars whose target text is found on the candidate page
  * silent_missing: translated, not found on the page and not flagged by any issue
  * residual source words (--ocr): OCR of the candidate page at 200 dpi, source
    words (>=5 letters, absent from every target text of the document) still
    readable; calibrated by OCR recall of the same words on the original page
  * protected visual regions: pixel comparison original vs candidate (200 dpi)
  * font consistency on scanned pages: inserted span sizes
  * issue counts by category, request budget (input+output+margin <= 32768)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
OCR_CACHE = Path(os.environ.get("RECETTE_OCR_CACHE", "/nonexistent"))
DPI = 200
APP_LIMIT = 32768
TESS = {
    "fra": "fra",
    "eng": "eng",
    "deu": "deu",
    "spa": "spa",
    "ita": "ita",
    "nld": "nld",
    "ara": "ara",
}

CATEGORIES = {
    "overflow": {"LAYOUT_OVERFLOW"},
    "clipped_or_missing": {
        "RENDER_TEXT_CLIPPED_OR_MISSING",
        "RENDER_TRANSLATED_TEXT_MISSING",
        "RENDER_SOURCE_TEXT_MISSING",
    },
    "mask_too_large": {"RENDER_TEXT_MASK_TOO_LARGE", "VISUAL_MASK_TOO_LARGE"},
    "overlap": {"NATIVE_REDACTION_OVERLAP", "PROTECTED_OVERLAP_REVIEW"},
    "table": {
        "PDF_TABLE_STRUCTURE_CHANGED",
        "UNMAPPED_TABLE_CONTENT",
        "PDF_TABLE_CELL_TARGET_MISSING",
        "PDF_CELL_SOURCE_TEXT_UNMAPPED",
        "TABLE_AMBIGUOUS_CELL_LINK",
    },
    "table_cell_fallback": {"TABLE_CELL_FALLBACK_TO_BLOCKS"},
    "protected_visual": {
        "PROTECTED_REGION_CHANGED",
        "PROTECTED_REGION_PIXEL_DIMENSIONS_CHANGED",
        "VISUAL_GEOMETRY_REGRESSION",
        "VISUAL_STRUCTURE_CHANGED",
        "PROTECTED_REGION_UNMEASURABLE",
    },
    "protected_text_kept": {"PROTECTED_TRANSLATION_NOT_APPLIED"},
    "critical_data": {
        "CRITICAL_ENTITY_MISSING",
        "CRITICAL_ENTITY_MODIFIED",
        "CRITICAL_ENTITY_EXTRA",
        "CRITICAL_ENTITY_ORDER_CHANGED",
        "HALLUCINATION_ENTITY_ADDED",
        "HALLUCINATION_ENTITY_MODIFIED",
        "HALLUCINATION_ENTITY_ORDER_CHANGED",
        "PROTECTED_ENTITY_CHANGED",
        "HALLUCINATION_UNIT_CHANGED",
    },
    "untranslated": {"UNTRANSLATED", "CONTEXT_OVERFLOW", "MISSING_TRANSLATION_BLOCK"},
    "ocr_unreliable_reported": {"OCR_UNRELIABLE_NOT_TRANSLATED"},
    "ocr_script_inconsistent": {"OCR_SCRIPT_INCONSISTENT_NOT_TRANSLATED"},
    "text_over_source_ink": {"SCAN_TEXT_OVER_SOURCE_INK"},
    "ocr_entity_disagreement": {"OCR_CRITICAL_ENTITY_DISAGREEMENT"},
    "highlight_approximated": {"HIGHLIGHT_SPAN_APPROXIMATED"},
    "font_reduced": {"FONT_REDUCED", "PDF_FONT_REDUCTION_REQUIRES_REVIEW"},
}
VISUAL_SUBTYPES = {"stamp_or_logo_candidate", "monochrome_visual_candidate"}
VISUAL_WORDS = (
    "stamp",
    "logo",
    "signature",
    "seal",
    "photo",
    "qr",
    "barcode",
    "handwriting",
    "figure",
)


def is_visual(r: dict) -> bool:
    sub = str(r.get("subtype") or r.get("type") or "").lower()
    return sub in VISUAL_SUBTYPES or any(w in sub for w in VISUAL_WORDS)


def dedupe(issues: list[dict]) -> list[dict]:
    seen, out = set(), []
    for i in issues:
        key = json.dumps(i, sort_keys=True, ensure_ascii=False, default=str)
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower().replace("\u2019", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^\w'@./:+-]+", " ", s)).strip()


def _changed(src: str, tgt: str | None) -> bool:
    """A target counts as translated only if it is not the source up to typography.

    Same rule as the application (final audit D27, app.ai.translation.typography).
    """
    from app.ai.translation.typography import typography_equivalent

    return bool(
        tgt and norm(tgt) and norm(tgt) != norm(src) and not typography_equivalent(tgt, src)
    )


def words(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.findall(r"[^\W\d_]{5,}", s)


def render(pdf: Path, page_index: int) -> np.ndarray:
    doc = fitz.open(pdf)
    pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72), alpha=False)
    arr = (
        np.frombuffer(pix.samples, dtype=np.uint8)
        .reshape(pix.height, pix.width, pix.n)[:, :, :3]
        .copy()
    )
    doc.close()
    return arr


def ocr_words(pdf: Path, page_index: int, langs: str) -> set[str]:
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()[:24]
    OCR_CACHE.mkdir(parents=True, exist_ok=True)
    cache = OCR_CACHE / f"{digest}-{page_index}-{langs}.json"
    if cache.exists():
        return set(json.loads(cache.read_text()))
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "p.png"
        Image.fromarray(render(pdf, page_index)).save(img)
        out = subprocess.run(
            ["tesseract", str(img), "stdout", "-l", langs, "--psm", "3"],
            capture_output=True,
            text=True,
            timeout=600,
            env={"OMP_THREAD_LIMIT": "1", "PATH": "/usr/bin:/bin"},
        )
    found = sorted(set(words(out.stdout)))
    cache.write_text(json.dumps(found))
    return set(found)


def issue_blocks(issue: dict) -> list[str]:
    ids = [issue.get("block_id")] if issue.get("block_id") else []
    return ids + list(issue.get("block_ids") or [])


# Why a non-French block was NOT translated (first match wins). Every such block
# counts in the strict coverage denominator: guards keep the original on
# purpose, but the text is still untranslated for the reader.
NOT_TRANSLATED_REASONS = (
    ("entity_disagreement", {"OCR_CRITICAL_ENTITY_DISAGREEMENT"}),
    ("form_structure", {"FORM_STRUCTURE_PRESERVED"}),
    ("identifier_only", {"IDENTIFIER_ONLY_KEPT"}),
    ("ocr_script_inconsistent", {"OCR_SCRIPT_INCONSISTENT_NOT_TRANSLATED"}),
    ("ocr_unreliable", {"OCR_UNRELIABLE_NOT_TRANSLATED"}),
    ("protected", {"PROTECTED_TRANSLATION_NOT_APPLIED"}),
    ("reported_untranslated", {"UNTRANSLATED", "CONTEXT_OVERFLOW", "MISSING_TRANSLATION_BLOCK"}),
)


def is_french(language: object) -> bool:
    return str(language or "").lower().startswith("fr")


def _identifier_only(text: str) -> bool:
    """Same rule as the application (line_verification.identifier_only), applied
    to BOTH runs so a baseline that rewrote RIB/ICE lines identically is not
    credited with a 'translation' the final run deliberately does not make."""
    from app.documents.line_verification import identifier_only

    return identifier_only(text)


def measure_doc(d: Path, with_ocr: bool, union_dir: Path | None = None) -> dict:
    a = json.load(open(d / "analysis.json"))
    tr = json.load(open(d / "translation.json"))
    tr["issues"] = dedupe(tr["issues"])
    summary = json.load(open(d / "interim-run-summary.json"))
    original = Path(a["source_path"])
    candidate = d / "candidate.pdf"
    blocks = {b["id"]: (p["number"], b) for p in a["pages"] for b in p["blocks"]}
    scanned = {p["number"]: bool(p.get("scanned")) for p in a["pages"]}
    T = tr.get("translations") or {}
    untranslated = set(tr.get("untranslated_blocks") or [])
    flagged = {bid for i in tr["issues"] for bid in issue_blocks(i)}
    codes_by_block: dict[str, set[str]] = defaultdict(set)
    for issue in tr["issues"]:
        for bid in issue_blocks(issue):
            codes_by_block[bid].add(issue["code"])
    doc_language = a.get("language")
    not_translated = Counter()
    text_cov = Counter()
    cand = fitz.open(candidate)
    orig = fitz.open(original)
    ptext = {i + 1: norm(cand[i].get_text()) for i in range(len(cand))}
    pwords = {i: set(t.split()) for i, t in ptext.items()}

    c = Counter()
    target_words_doc: set[str] = set()
    changed_by_page: dict[int, list[str]] = defaultdict(list)
    for bid, (pno, b) in blocks.items():
        src = b.get("text") or ""
        n = len(src)
        c["source_chars"] += n
        c["ocr_lines"] += int(b.get("line_count") or len(b.get("source_lines") or []) or 1)
        tgt = T.get(bid)
        if _changed(src, tgt):
            target_words_doc.update(words(tgt))
            changed_by_page[pno].append(bid)
            c["translated_blocks"] += 1
            c["translated_chars"] += n
            probe = " ".join(norm(tgt).split()[:3])
            toks = [t for t in norm(tgt).split() if len(t) > 2]
            frac = (sum(t in pwords.get(pno, set()) for t in toks) / len(toks)) if toks else 1.0
            if probe in ptext.get(pno, "") or frac >= 0.8:
                c["written_chars"] += n
                c["written_blocks"] += 1
            elif bid in flagged:
                c["flagged_not_written_chars"] += n
            else:
                c["silent_missing_chars"] += n
                c["silent_missing_blocks"] += 1
        elif bid in untranslated:
            c["untranslated_chars"] += n
            c["untranslated_blocks"] += 1
        if not _changed(src, tgt) and src.strip():
            if is_french(b.get("language") or doc_language):
                c["french_source_chars"] += n
            else:
                codes = codes_by_block.get(bid, set())
                reason = next(
                    (name for name, wanted in NOT_TRANSLATED_REASONS if codes & wanted),
                    "unchanged_no_issue",
                )
                not_translated[reason] += n
                if not _identifier_only(src):
                    text_cov["missing"] += n
        elif _changed(src, tgt) and not _identifier_only(src):
            text_cov["translated"] += n
    need = c["translated_chars"] + c["untranslated_chars"]
    need_strict = c["translated_chars"] + sum(not_translated.values())
    need_translatable = need_strict - not_translated["identifier_only"]
    need_text = text_cov["translated"] + text_cov["missing"]

    # residual source words via OCR (scanned pages) or text layer (native pages)
    residual = Counter()
    if with_ocr:
        langs = "+".join(
            dict.fromkeys(["fra"] + [TESS[x] for x in (a.get("languages") or []) if x in TESS])
        )
        for pno, bids in changed_by_page.items():
            eligible = set()
            for bid in bids:
                eligible.update(
                    w for w in words(blocks[bid][1].get("text")) if w not in target_words_doc
                )
            if not eligible:
                continue
            if scanned.get(pno):
                cand_words = ocr_words(candidate, pno - 1, langs)
                orig_words = ocr_words(original, pno - 1, langs)
            else:
                cand_words = set(words(cand[pno - 1].get_text()))
                orig_words = set(words(orig[pno - 1].get_text()))
            residual["eligible_source_words"] += len(eligible)
            residual["recall_on_original"] += len(eligible & orig_words)
            residual["residual_on_candidate"] += len(eligible & orig_words & cand_words)

    # protected visual regions: pixel preservation original vs candidate, measured on the
    # union of visual regions of this run and of the reference run (so that a region
    # dropped by reclassification is still checked)
    pv = Counter()
    regions = a.get("protected_visual_regions") or []
    for r in regions:
        pv[f"subtype:{r.get('subtype') or r.get('type')}"] += 1
    own = {(int(r["page"]), tuple(round(v, 1) for v in r["bbox"])) for r in regions if is_visual(r)}
    union = set(own)
    if union_dir is not None and (union_dir / d.name / "analysis.json").exists():
        ref = json.load(open(union_dir / d.name / "analysis.json"))
        ref_vis = {
            (int(r["page"]), tuple(round(v, 1) for v in r["bbox"]))
            for r in ref.get("protected_visual_regions") or []
            if is_visual(r)
        }
        pv["visual_only_in_reference"] = len(ref_vis - own)
        pv["visual_only_in_this_run"] = len(own - ref_vis)
        union |= ref_vis
    by_page = defaultdict(list)
    for pno, bbox in union:
        by_page[pno].append({"bbox": bbox, "own": (pno, bbox) in own})
    pv["visual_regions_checked"] = len(union)
    for pno, rs in by_page.items():
        o = render(original, pno - 1)
        k = render(candidate, pno - 1)
        if o.shape != k.shape:
            pv["visual_page_shape_changed"] += len(rs)
            continue
        s = DPI / 72
        for r in rs:
            x0, y0, x1, y1 = (int(round(v * s)) for v in r["bbox"])
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(o.shape[1], x1), min(o.shape[0], y1)
            if x1 - x0 < 2 or y1 - y0 < 2:
                pv["visual_degenerate"] += 1
                continue
            diff = np.abs(o[y0:y1, x0:x1].astype(int) - k[y0:y1, x0:x1].astype(int)).max(axis=2)
            changed = float((diff > 40).mean())
            pv["visual_measured"] += 1
            if changed <= 0.01:
                pv["visual_preserved"] += 1
            elif changed <= 0.05:
                pv["visual_slightly_touched"] += 1
            else:
                pv["visual_altered"] += 1
                pv[
                    "visual_altered_" + ("protected_in_run" if r["own"] else "not_protected_in_run")
                ] += 1
            pv["visual_max_changed_permille"] = max(
                pv["visual_max_changed_permille"], int(changed * 1000)
            )

    # font consistency on scanned pages (every span is inserted text there)
    sizes = Counter()
    for i in range(len(cand)):
        if not scanned.get(i + 1):
            continue
        for blk in cand[i].get_text("dict")["blocks"]:
            for line in blk.get("lines", []):
                for sp in line.get("spans", []):
                    if sp["text"].strip():
                        sizes[round(sp["size"] * 2) / 2] += len(sp["text"].strip())
    total_sz = sum(sizes.values())
    font = {
        "distinct_sizes": len(sizes),
        "modal_share": round(max(sizes.values()) / total_sz, 3) if total_sz else None,
        "min_size": min(sizes) if sizes else None,
        "chars_below_7pt_share": round(sum(v for k, v in sizes.items() if k < 7) / total_sz, 3)
        if total_sz
        else None,
    }

    codes = Counter()
    for i in tr["issues"]:
        codes[i["code"]] += int(i.get("count") or 1)
    sev = Counter(i.get("severity") for i in tr["issues"])
    cats = {k: sum(codes[x] for x in v) for k, v in CATEGORIES.items()}
    tel = tr.get("translation_telemetry") or {}
    chunks = tel.get("chunks") or []
    usage = tel.get("usage") or {}
    over = sum(1 for ch in chunks if (ch.get("reserved_total_tokens") or 0) > APP_LIMIT)
    usage_over = sum(
        1 for ch in chunks if ((ch.get("usage") or {}).get("total_tokens") or 0) > APP_LIMIT
    )
    row = {
        "doc": d.name,
        "pages_original": len(orig),
        "pages_candidate": len(cand),
        "scanned_pages": sum(scanned.values()),
        "ir_blocks": len(blocks),
        "ocr_lines": c["ocr_lines"],
        "tables": len(a.get("tables") or []),
        "chars": {
            k: c[k]
            for k in (
                "source_chars",
                "translated_chars",
                "untranslated_chars",
                "written_chars",
                "flagged_not_written_chars",
                "silent_missing_chars",
                "french_source_chars",
            )
        },
        "coverage_chars": round(c["translated_chars"] / need, 4) if need else None,
        "coverage_chars_strict": round(c["translated_chars"] / need_strict, 4)
        if need_strict
        else None,
        # What the reader actually gets: translated AND found on the candidate page.
        "coverage_chars_written_strict": round(c["written_chars"] / need_strict, 4)
        if need_strict
        else None,
        "coverage_chars_translatable": round(c["translated_chars"] / need_translatable, 4)
        if need_translatable
        else None,
        "coverage_chars_text": round(text_cov["translated"] / need_text, 4) if need_text else None,
        "text_coverage_chars": dict(text_cov),
        "not_translated_chars_by_reason": dict(not_translated),
        "written_share_of_translated": round(c["written_chars"] / c["translated_chars"], 4)
        if c["translated_chars"]
        else None,
        "blocks": {
            k: c[k]
            for k in (
                "translated_blocks",
                "written_blocks",
                "untranslated_blocks",
                "silent_missing_blocks",
            )
        },
        "residual_source": dict(residual) if with_ocr else "NOT_MEASURED",
        "protected_regions": dict(pv),
        "font": font,
        "issue_categories": cats,
        "severity": dict(sev),
        "critical_codes": dict(
            Counter(i["code"] for i in tr["issues"] if i.get("severity") == "critical")
        ),
        "issue_codes": dict(codes),
        "requests": summary.get("requests_sent"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "max_reserved_total": max([ch.get("reserved_total_tokens") or 0 for ch in chunks] or [0]),
        "max_usage_total": max(
            [(ch.get("usage") or {}).get("total_tokens") or 0 for ch in chunks] or [0]
        ),
        "requests_reserved_over_32768": over,
        "requests_usage_over_32768": usage_over,
        "budget_violations": (summary.get("budget") or {}).get("violations"),
        "original_sha_unchanged": summary.get("original_sha256_unchanged"),
        "line_verification": a.get("line_verification") or "NOT_EXECUTED",
        "multicolor_vetoes": len(a.get("reclassification_vetoes") or []),
        "reclassified_visual_candidates": len(a.get("reclassified_visual_candidates") or []),
        "quality_status": summary.get("quality_status"),
        "human_reference_validated": summary.get("human_reference_validated"),
    }
    cand.close()
    orig.close()
    return row


def main() -> int:
    global OCR_CACHE
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("label")
    parser.add_argument("--dest-dir", type=Path, required=True)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--union-with", type=Path)
    args = parser.parse_args()
    dest_dir = args.dest_dir.resolve()
    if dest_dir == REPO_ROOT or REPO_ROOT in dest_dir.parents:
        print("REFUSED: destination inside the repository", file=sys.stderr)
        return 2
    OCR_CACHE = dest_dir / "ocr-cache"
    out_dir, label, with_ocr, union_dir = args.out_dir, args.label, args.ocr, args.union_with
    docs = sorted(p for p in out_dir.glob("DOC-00*") if (p / "translation.json").exists())
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda d: measure_doc(d, with_ocr, union_dir), docs))
    total = Counter()
    for r in rows:
        for k, v in r["chars"].items():
            total[k] += v
        for k in (
            "pages_original",
            "ir_blocks",
            "ocr_lines",
            "requests",
            "prompt_tokens",
            "completion_tokens",
            "requests_reserved_over_32768",
            "requests_usage_over_32768",
        ):
            total[k] += r[k] or 0
        for k, v in r["issue_categories"].items():
            total[f"cat:{k}"] += v
        if isinstance(r["residual_source"], dict):
            for k, v in r["residual_source"].items():
                total[f"residual:{k}"] += v
        for k, v in r["protected_regions"].items():
            if k.startswith("visual_") and k != "visual_max_changed_permille":
                total[f"pv:{k}"] += v
        for k, v in r["not_translated_chars_by_reason"].items():
            total[f"not_translated:{k}"] += v
        for k, v in r["text_coverage_chars"].items():
            total[f"text_coverage:{k}"] += v
    total = dict(total)
    need = total.get("translated_chars", 0) + total.get("untranslated_chars", 0)
    total["coverage_chars"] = round(total.get("translated_chars", 0) / need, 4) if need else None
    not_tr = sum(v for k, v in total.items() if k.startswith("not_translated:"))
    strict = total.get("translated_chars", 0) + not_tr
    translatable = strict - total.get("not_translated:identifier_only", 0)
    total["coverage_chars_strict"] = (
        round(total.get("translated_chars", 0) / strict, 4) if strict else None
    )
    total["coverage_chars_written_strict"] = (
        round(total.get("written_chars", 0) / strict, 4) if strict else None
    )
    total["coverage_chars_translatable"] = (
        round(total.get("translated_chars", 0) / translatable, 4) if translatable else None
    )
    text_need = total.get("text_coverage:translated", 0) + total.get("text_coverage:missing", 0)
    total["coverage_chars_text"] = (
        round(total.get("text_coverage:translated", 0) / text_need, 4) if text_need else None
    )
    total["max_reserved_total"] = max(r["max_reserved_total"] for r in rows)
    total["max_usage_total"] = max(r["max_usage_total"] for r in rows)
    dest = dest_dir / f"metrics-{label}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {"label": label, "dpi": DPI, "rows": rows, "total": total}, indent=1, ensure_ascii=False
        )
    )
    for r in rows:
        print(
            r["doc"],
            "cov",
            r["coverage_chars"],
            "written",
            r["written_share_of_translated"],
            "silent",
            r["chars"]["silent_missing_chars"],
            "resid",
            r["residual_source"],
            "pv",
            {k: v for k, v in r["protected_regions"].items() if k.startswith("visual_")},
            "cats",
            {k: v for k, v in r["issue_categories"].items() if v},
            "req",
            r["requests"],
            "maxRes",
            r["max_reserved_total"],
            "status",
            r["quality_status"],
        )
    print("TOTAL", total)
    print("saved", dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
