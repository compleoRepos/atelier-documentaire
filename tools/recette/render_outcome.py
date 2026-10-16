"""Independent measurement of what the reader actually gets in a candidate PDF.

Same method for every run (baseline, run17, run18...): it reads only the candidate
PDF (text layer and rendering) plus, from the run being measured, each block's
geometry and target text. It never relies on the renderer's own alerts, so a run
that truncated silently and a run that reported its overflows are measured alike.

Per translated block (target differs from source):
  * ``recall``  share of the target's tokens found in inserted text near the block
                (tokens are consumed once, nearest block first);
  * ``status``  WRITTEN (recall >= 0.85), PARTIAL (>= 0.25, i.e. cut/clipped),
                ABSENT (< 0.25), NO_TOKENS (nothing measurable, e.g. one symbol);
  * ``over_ink`` share of its inserted words printed over source ink that is still
                visible underneath (measured on the page rendered WITHOUT the
                inserted text, long rules removed so table lines do not count).
Per page: inserted words colliding with another inserted word, words out of page.

Scanned pages only for ink/collision measures: on such pages every text-layer word
was inserted by the renderer (the original is an image).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path

import fitz
import numpy as np

DPI = 150
WRITTEN = 0.85
PARTIAL = 0.25
OVER_INK_SHARE = 0.05
_TOKEN = re.compile(r"[^\W_]{2,}", re.UNICODE)


def tokens(text: str | None) -> list[str]:
    s = unicodedata.normalize("NFKC", text or "").lower().replace("\u2019", "'")
    return _TOKEN.findall(s)


def _zone(bbox, line_count: int) -> tuple[float, float, float, float]:
    """Search zone of a block's inserted words.

    Horizontally symmetric (method v2.1): a renderer may legitimately grow a
    frame to the right (LTR overflow) or to the LEFT (right-aligned / RTL cell,
    run18 F5). The v2 zone extended far to the right but only 3 pt to the left,
    so a fully written right-anchored translation was measured PARTIAL while a
    right overflow counted as WRITTEN: a bias depending on the growth
    direction, not on what the reader gets. Same zone for every run."""
    x0, y0, x1, y1 = bbox
    lh = max(4.0, (y1 - y0) / max(1, line_count))
    grow = 0.5 * (x1 - x0) + 2 * lh
    return (x0 - grow, y0 - 0.6 * lh, x1 + grow, y1 + 3.2 * lh)


def _dist(cx: float, cy: float, bbox) -> float:
    x0, y0, x1, y1 = bbox
    dx = max(x0 - cx, 0.0, cx - x1)
    dy = max(y0 - cy, 0.0, cy - y1)
    return (dx * dx + dy * dy) ** 0.5


def _background_gray(pdf: Path, page_index: int) -> np.ndarray:
    """Page rendered with every text-layer word removed (images and vector masks kept)."""
    doc = fitz.open(pdf)
    page = doc[page_index]
    for w in page.get_text("words"):
        page.add_redact_annot(fitz.Rect(w[:4]), fill=False)
    page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_NONE,
        graphics=fitz.PDF_REDACT_LINE_ART_NONE,
        text=fitz.PDF_REDACT_TEXT_REMOVE,
    )
    pix = page.get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72), colorspace=fitz.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()
    return arr


def _ink_share(gray: np.ndarray, rect) -> float:
    s = DPI / 72
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    x0, x1 = x0 + 0.1 * w, x1 - 0.1 * w
    y0, y1 = y0 + 0.15 * h, y1 - 0.15 * h
    a = gray[max(0, int(y0 * s)) : max(0, int(y1 * s)), max(0, int(x0 * s)) : max(0, int(x1 * s))]
    if a.size < 4 or a.shape[0] < 2 or a.shape[1] < 2:
        return 0.0
    dark = a < 140
    # long straight rules (table/form lines) are not "source text under the new text"
    rows = dark.mean(axis=1) > 0.85
    cols = dark.mean(axis=0) > 0.85
    dark[rows, :] = False
    dark[:, cols] = False
    return float(dark.mean())


def measure_candidate(
    candidate: Path,
    pages: list[dict],
    translations: dict[str, str],
    changed,
) -> dict:
    """``pages``: IR pages (number, scanned, blocks with id/bbox/line_count/text).

    ``changed(src, tgt)`` decides whether a block counts as translated (same rule
    for every run). Returns per-block outcomes and per-document aggregates."""
    doc = fitz.open(candidate)
    per_block: dict[str, dict] = {}
    agg = Counter()
    for p in pages:
        pno = int(p["number"])
        if pno - 1 >= len(doc):
            continue
        page = doc[pno - 1]
        words = page.get_text("words")
        wt = [(fitz.Rect(w[:4]), tokens(w[4])) for w in words]
        blocks = []
        for b in p["blocks"]:
            tgt = translations.get(b["id"])
            if not changed(b.get("text") or "", tgt):
                continue
            toks = tokens(tgt)
            blocks.append(
                {
                    "id": b["id"],
                    "bbox": b["bbox"],
                    "zone": _zone(b["bbox"], int(b.get("line_count") or 1)),
                    "need": Counter(toks),
                    "total": len(toks),
                    "matched": 0,
                    "words": [],
                }
            )
        # global greedy: (word token, block) pairs ordered by distance; each token once
        pairs = []
        for wi, (r, toks) in enumerate(wt):
            cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
            for bi, blk in enumerate(blocks):
                zx0, zy0, zx1, zy1 = blk["zone"]
                if not (zx0 <= cx <= zx1 and zy0 <= cy <= zy1):
                    continue
                for ti, tok in enumerate(toks):
                    if tok in blk["need"]:
                        pairs.append((_dist(cx, cy, blk["bbox"]), wi, ti, bi, tok))
        pairs.sort(key=lambda x: x[0])
        used = set()
        for _d, wi, ti, bi, tok in pairs:
            if (wi, ti) in used:
                continue
            blk = blocks[bi]
            if blk["need"][tok] <= 0:
                continue
            blk["need"][tok] -= 1
            blk["matched"] += 1
            used.add((wi, ti))
            if wi not in blk["words"]:
                blk["words"].append(wi)
        gray = _background_gray(candidate, pno - 1) if p.get("scanned") else None
        for blk in blocks:
            recall = blk["matched"] / blk["total"] if blk["total"] else None
            if recall is None:
                status = "NO_TOKENS"
            elif recall >= WRITTEN:
                status = "WRITTEN"
            elif recall >= PARTIAL:
                status = "PARTIAL"
            else:
                status = "ABSENT"
            over = None
            if gray is not None and blk["words"]:
                shares = [_ink_share(gray, wt[wi][0]) for wi in blk["words"]]
                over = round(sum(s > OVER_INK_SHARE for s in shares) / len(shares), 3)
            per_block[blk["id"]] = {
                "page": pno,
                "recall": None if recall is None else round(recall, 3),
                "status": status,
                "over_ink": over,
            }
            agg[f"blocks_{status.lower()}"] += 1
            if over is not None and over >= 0.3:
                agg["blocks_over_ink"] += 1
        if p.get("scanned") and wt:
            rects = np.array([[r.x0, r.y0, r.x1, r.y1] for r, _t in wt], dtype=float)
            area = np.maximum(0.01, (rects[:, 2] - rects[:, 0]) * (rects[:, 3] - rects[:, 1]))
            ix0 = np.maximum(rects[:, None, 0], rects[None, :, 0])
            iy0 = np.maximum(rects[:, None, 1], rects[None, :, 1])
            ix1 = np.minimum(rects[:, None, 2], rects[None, :, 2])
            iy1 = np.minimum(rects[:, None, 3], rects[None, :, 3])
            inter = np.clip(ix1 - ix0, 0, None) * np.clip(iy1 - iy0, 0, None)
            np.fill_diagonal(inter, 0)
            smaller = np.minimum(area[:, None], area[None, :])
            agg["words_colliding"] += int(((inter / smaller) > 0.3).any(axis=1).sum())
            pr = page.rect
            agg["words_out_of_page"] += int(
                (
                    (rects[:, 0] < pr.x0 - 1)
                    | (rects[:, 1] < pr.y0 - 1)
                    | (rects[:, 2] > pr.x1 + 1)
                    | (rects[:, 3] > pr.y1 + 1)
                ).sum()
            )
            agg["inserted_words"] += len(wt)
    doc.close()
    return {"blocks": per_block, "aggregate": dict(agg)}
