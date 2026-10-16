"""Post-render verification of inserted translations (F26).

The renderer reports a block as rendered when its insertion did not fail.
That is a statement about the plan, not about the output: a translation can
still be clipped, partly covered or missing in the candidate PDF. This module
re-reads the candidate PDF and checks, for every placement really inserted by
the engine (the exact frame it used, not the OCR box), that the words of the
target text are present inside that frame.

* recall = matched target tokens / target tokens (multiset, case- and
  accent-insensitive, alphanumeric tokens only);
* a placement whose recall is below ``MIN_RECALL`` produces one critical
  ``RENDER_TARGET_NOT_VERIFIED`` issue per block; ``block_status`` maps it to
  ``FAILED / render_target_incomplete`` so a block is never reported as
  translated when its translation is not readable in the output;
* placements without any alphanumeric token are not measurable and are
  counted as such (never as verified).

No text is logged: the summary carries counts only.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

VERSION = "render-verification-2"
MIN_RECALL = 0.90
FRAME_TOLERANCE_PT = 1.5
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).casefold()
    return _TOKEN.findall(folded)


def token_recall(target: str, found: str) -> float | None:
    """Share of target tokens present in ``found`` (None when not measurable)."""
    wanted = Counter(_tokens(target))
    total = sum(wanted.values())
    if not total:
        return None
    have = Counter(_tokens(found))
    return sum(min(count, have[token]) for token, count in wanted.items()) / total


def _inside(word: tuple, frame: list[float], tolerance: float) -> bool:
    cx = (word[0] + word[2]) / 2
    cy = (word[1] + word[3]) / 2
    return (
        frame[0] - tolerance <= cx <= frame[2] + tolerance
        and frame[1] - tolerance <= cy <= frame[3] + tolerance
    )


def verify_placements(
    candidate: str | Path, placements: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (issues, summary) for the placements of a rendered candidate PDF."""
    import fitz

    issues: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "method": VERSION,
        "min_recall": MIN_RECALL,
        "placements": len(placements),
        "verified": 0,
        "not_verified": 0,
        "not_measurable": 0,
        "blocks_not_verified": 0,
        # F27: identifiers (never text) of blocks whose placement was verified.
        "verified_block_ids": [],
    }
    if not placements:
        return issues, summary
    doc = fitz.open(str(candidate))
    try:
        words_by_page: dict[int, list[tuple]] = {}
        for placement in placements:
            number = int(placement["page"])
            if number not in words_by_page:
                page = doc[number - 1] if 0 < number <= len(doc) else None
                words_by_page[number] = page.get_text("words") if page is not None else []
            frame = [float(v) for v in placement["inner"]]
            found = " ".join(
                str(w[4]) for w in words_by_page[number] if _inside(w, frame, FRAME_TOLERANCE_PT)
            )
            recall = token_recall(str(placement.get("text") or ""), found)
            if recall is None:
                summary["not_measurable"] += 1
                continue
            if recall >= MIN_RECALL:
                summary["verified"] += 1
                summary["verified_block_ids"].extend(
                    str(b) for b in placement.get("block_ids") or [] if b is not None
                )
                continue
            summary["not_verified"] += 1
            for block_id in placement.get("block_ids") or [None]:
                summary["blocks_not_verified"] += 1
                issues.append(
                    {
                        "code": "RENDER_TARGET_NOT_VERIFIED",
                        "message": (
                            "Traduction insérée mais non retrouvée intégralement dans son cadre "
                            "du PDF produit; bloc à revoir."
                        ),
                        "severity": "critical",
                        "block_id": block_id,
                        "cell_id": placement.get("cell_id"),
                        "page": number,
                        "recall": round(recall, 4),
                        "bbox": frame,
                    }
                )
    finally:
        doc.close()
    summary["verified_block_ids"] = sorted(set(summary["verified_block_ids"]))
    return issues, summary
