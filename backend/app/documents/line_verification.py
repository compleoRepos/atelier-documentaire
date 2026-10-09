"""Post-OCR verification of scanned lines on the ORIGINAL raster.

Two measured defects of the final corpus run motivate this step:

* **Highlight lost.** Style evidence took the paper colour from the 40 %
  brightest pixels of a line, i.e. the white paper; a marker highlight covering
  part of a line was never seen, so the translated line was redrawn without it.
  ``highlight_evidence`` measures the share of light *saturated* pixels and
  their horizontal extent per line.
* **Critical value misread under a highlight.** A pink-highlighted date
  was read with a wrong day digit by the primary OCR. The entity check
  compares the translation with the OCR source, so it cannot see an OCR error,
  and the renderer then wrote the wrong date over the original pixels.
  ``verify_lines`` re-reads every scanned line that carries a number of at
  least two digits *under a marker* on a highlight-neutral channel
  (max(R, G, B) turns a light coloured marker into paper while dark ink stays
  dark) and compares the digit sequences. A disagreement marks the block
  ``entity_read_disagreement``: it is not sent for translation, its original
  pixels stay untouched and a review issue is raised
  (``OCR_CRITICAL_ENTITY_DISAGREEMENT``). An empty or truncated second reading
  is *inconclusive*, never an agreement nor a disagreement.

Scope, measured on the corpus: on clean (non-highlighted) small bold text the
single-line second reading was *less* accurate than the page OCR (2 false
disagreements out of 3, checked visually) and max(R, G, B) erases coloured
ink. Lines without a marker are recorded ``not_checked_no_marker``: explicitly
not verified, never counted as an agreement.

* **Form structure destroyed.** Measured on the final corpus run: once form
  frames were no longer protected as a whole, one OCR line spanned three form
  cells (label/value/role) or a row of digit boxes (box rules read as extra
  digits), and two table rows were merged into one paragraph. Rewriting
  such a block moves values out of their cells and can alter digits.
  ``form_structure_evidence`` marks a block ``form_structure_risk`` when its
  OCR text contains ruling glyphs (``|``, ``7]``, ``[o]``...), when a vertical
  rule crosses one of its lines (a dark column covering the whole line box and
  extending well above *and* below it: glyph strokes stay inside the line box)
  or when a horizontal rule separates two of its lines. Such a block is not
  sent for translation; its original pixels are kept and a review issue is
  raised (``FORM_STRUCTURE_PRESERVED``).

Nothing read here is stored as text: only statuses, coverages and counts.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.documents.segmentation import is_unreliable_ocr

VERSION = "line-verification-4"
SCALE = 4.0
HIGHLIGHT_MIN_COVERAGE = 0.10
HIGHLIGHT_MIN_X_COVERAGE = 0.25
MARKER_MIN_COVERAGE = 0.08
RULE_DARK = 110
RULE_EXTENSION = 0.35
RULE_COLUMN_FILL = 0.92
RULE_ROW_FILL = 0.6
_NUMBER = re.compile(r"\d+")
_DIGIT_BOXES = re.compile(r"\d\]|\[\d|\[\w\]|_[|¦]|[|¦]_")
_EDGE_RULE = re.compile(r"^[_\W]{0,2}[|¦]|[|¦][_\W]{0,2}$")
_WORD = re.compile(r"[^\W\d_]{3,}")


def identifier_only(text: str) -> bool:
    """A line made only of identifiers/numbers (RIB, ICE, phone, date): it has
    a group of >= 3 digits and its only words are short upper-case acronyms
    (<= 4 letters: RIB, ICE, CNSS, IBAN). Measured on the corpus: rewriting such
    a footer line changed nothing translatable but erased the two logo marks
    OCR had read as letters. Upper-case headings ("1. DEFINITIONS") are words,
    not acronyms: a first version of this rule kept 33 such headings untranslated."""
    if not re.search(r"\d{3,}", text or ""):
        return False
    for word in _WORD.findall(text or ""):
        if not (word.upper() == word and word.lower() != word and len(word) <= 4):
            return False
    return True


def highlight_evidence(rgb: Any, box_px: list[float]) -> dict[str, Any] | None:
    """Share of light saturated (marker) pixels inside one line box."""
    import numpy as np

    height, width = rgb.shape[:2]
    x0, y0 = max(0, int(box_px[0])), max(0, int(box_px[1]))
    x1, y1 = min(width, int(round(box_px[2]))), min(height, int(round(box_px[3])))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    crop = np.asarray(rgb[y0:y1, x0:x1], dtype=np.int16)
    high, low = crop.max(axis=2), crop.min(axis=2)
    marker = ((high - low) >= 40) & (high >= 150)
    coverage = float(marker.mean())
    x_coverage = float((marker.mean(axis=0) >= 0.4).mean())
    result: dict[str, Any] = {"coverage": round(coverage, 3), "x_coverage": round(x_coverage, 3)}
    if coverage >= HIGHLIGHT_MIN_COVERAGE and x_coverage >= HIGHLIGHT_MIN_X_COVERAGE:
        colour = np.median(crop[marker], axis=0) / 255.0
        result["highlight"] = True
        result["rgb"] = [round(float(c), 4) for c in colour]
        result["partial"] = x_coverage < 0.8
    else:
        result["highlight"] = False
    return result


def digit_sequence(text: str) -> str:
    """Digits of every group of >= 2 digits, in reading order (separators and
    single digits ignored: spacing and isolated digits vary between readings)."""
    return "".join(g for g in _NUMBER.findall(text or "") if len(g) >= 2)


def ruling_glyphs(text: str) -> bool:
    """OCR evidence of form rules read as characters, for ONE line: a rule at the
    line edge (``| Label``, ``_| N/A``), digit boxes (``7] 2] 4]``, ``[o]``) or
    at least two bars. A single bar inside a sentence is more often a misread
    ``I``/``l``; it is left to the raster check (``vertical_rules_crossing``)."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    return bool(
        _EDGE_RULE.search(stripped)
        or _DIGIT_BOXES.search(stripped)
        or stripped.count("|") + stripped.count("¦") >= 2
    )


def _dark(rgb: Any, y0: int, y1: int, x0: int, x1: int) -> Any:
    import numpy as np

    crop = np.asarray(rgb[y0:y1, x0:x1], dtype=np.int16)
    return crop.mean(axis=2) < RULE_DARK


def vertical_rules_crossing(rgb: Any, box_px: list[float]) -> int:
    """Interior vertical rules crossing one line box (count of rule groups).

    A rule fills the whole line height and continues beyond the box above and
    below, or on one side only: a label at the top of a cell sits right under
    the horizontal rule where the cell separator starts. Glyph strokes never
    reach 0.35 line height beyond their own line box."""
    height, width = rgb.shape[:2]
    line_h = box_px[3] - box_px[1]
    if line_h < 4:
        return 0
    ext = RULE_EXTENSION * line_h
    x0 = max(0, int(box_px[0] + 0.5 * line_h))
    x1 = min(width, int(round(box_px[2] - 0.5 * line_h)))
    if x1 - x0 < 2:
        return 0
    y0, y1 = max(0, int(box_px[1] - ext)), min(height, int(round(box_px[3] + ext)))
    room_above = (box_px[1] - y0) >= 0.8 * ext
    room_below = (y1 - box_px[3]) >= 0.8 * ext
    if room_above and room_below:
        columns = _dark(rgb, y0, y1, x0, x1).mean(axis=0) >= RULE_COLUMN_FILL
        if columns.any():
            return _groups(columns)
    if not (room_above or room_below):
        return 0  # not enough room above/below to tell a rule from a glyph
    top, bottom = max(0, int(box_px[1])), min(height, int(round(box_px[3])))
    if bottom - top < 2:
        return 0
    inside = _dark(rgb, top, bottom, x0, x1).mean(axis=0) >= RULE_COLUMN_FILL
    beyond = inside & False
    if room_above and top - y0 >= 1:
        beyond = beyond | (_dark(rgb, y0, top, x0, x1).mean(axis=0) >= RULE_COLUMN_FILL)
    if room_below and y1 - bottom >= 1:
        beyond = beyond | (_dark(rgb, bottom, y1, x0, x1).mean(axis=0) >= RULE_COLUMN_FILL)
    return _groups(inside & beyond)


def _groups(columns: Any) -> int:
    groups, previous = 0, False
    for flag in columns.tolist():
        if flag and not previous:
            groups += 1
        previous = flag
    return groups


def horizontal_rule_between(rgb: Any, upper_px: list[float], lower_px: list[float]) -> bool:
    """A horizontal rule in the white gap separating two consecutive lines."""
    height, width = rgb.shape[:2]
    y0, y1 = int(round(upper_px[3])), int(lower_px[1])
    if y1 - y0 < 2:
        return False  # touching/overlapping boxes: no gap to inspect, no evidence
    x0 = max(0, int(max(upper_px[0], lower_px[0])))
    x1 = min(width, int(round(min(upper_px[2], lower_px[2]))))
    if x1 - x0 < 8:
        return False
    rows = _dark(rgb, max(0, y0), min(height, y1), x0, x1).mean(axis=1)
    return bool((rows >= RULE_ROW_FILL).any())


def form_structure_evidence(rgb: Any, lines: list[dict[str, Any]], scale: float) -> list[str]:
    """Reasons why rewriting this block would break a form/table structure."""
    reasons: set[str] = set()
    boxes = []
    for line in lines:
        if ruling_glyphs(str(line.get("text") or "")):
            reasons.add("ocr_ruling_glyphs")
        box = line.get("bbox")
        if not box:
            continue
        px = [float(v) * scale for v in box]
        boxes.append(px)
        if vertical_rules_crossing(rgb, px):
            reasons.add("vertical_rule_crosses_line")
    boxes.sort(key=lambda b: (b[1], b[0]))
    for upper, lower in zip(boxes, boxes[1:], strict=False):
        if horizontal_rule_between(rgb, upper, lower):
            reasons.add("horizontal_rule_between_lines")
            break
    return sorted(reasons)


def compare_readings(first: str, second: str | None) -> str:
    one, two = digit_sequence(first), digit_sequence(second or "")
    if not one:
        return "not_applicable"
    if not two:
        return "inconclusive"
    if one == two:
        return "agree"
    if two in one or one in two:
        return "inconclusive"  # truncated/extended reading: not a proof either way
    return "disagree"


def _tesseract_line(image: Any) -> str | None:
    try:
        import pytesseract

        return pytesseract.image_to_string(image, lang="eng", config="--psm 7", timeout=30)
    except Exception:  # noqa: BLE001 - an unavailable reader is inconclusive, never a pass
        return None


def second_reading(
    rgb: Any, box_px: list[float], reader: Callable[[Any], str | None]
) -> str | None:
    import numpy as np
    from PIL import Image

    height, width = rgb.shape[:2]
    pad = 0.15 * (box_px[3] - box_px[1])
    x0, y0 = max(0, int(box_px[0] - pad)), max(0, int(box_px[1] - pad))
    x1, y1 = min(width, int(round(box_px[2] + pad))), min(height, int(round(box_px[3] + pad)))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    channel = np.asarray(rgb[y0:y1, x0:x1]).max(axis=2).astype(np.uint8)
    image = Image.fromarray(channel)
    if image.height < 48:
        ratio = 48 / max(1, image.height)
        image = image.resize((max(1, int(image.width * ratio)), 48))
    return reader(image)


def _page_rasters(source: Path, pages: list[int], scale: float) -> dict[int, Any]:
    import fitz
    import numpy as np

    path = source
    if source.suffix.lower() != ".pdf":
        from .raster_adapter import raster_pdf_copy

        path = Path(raster_pdf_copy(source, source.parent / f".{source.stem}-line-verify.pdf"))
    rasters = {}
    with fitz.open(path) as doc:
        for number in pages:
            if 1 <= number <= len(doc):
                pix = doc[number - 1].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                rasters[number] = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n
                )[:, :, :3]
    return rasters


# An OCR line in a script that is marginal on its page, read with low
# confidence, is noise (tiny bold labels read as another alphabet): a model
# would "translate" it into plausible but invented words. Not sent; kept.
MINORITY_SCRIPT_MAX_PAGE_SHARE = 0.15
MINORITY_SCRIPT_MAX_CONFIDENCE = 0.7


def script_letters(text: str) -> dict[str, int]:
    """Letter counts per script family (arabic, latin, other)."""
    counts: dict[str, int] = {}
    for char in text:
        if not char.isalpha():
            continue
        name = unicodedata.name(char, "")
        family = "arabic" if "ARABIC" in name else "latin" if "LATIN" in name else "other"
        counts[family] = counts.get(family, 0) + 1
    return counts


def minority_script_noise(
    block: dict[str, Any], page_scripts: dict[str, int], page_letters: int
) -> bool:
    """True when the block's dominant script is marginal on the page and the
    OCR confidence is low."""
    letters = script_letters(str(block.get("text") or ""))
    if not letters or page_letters <= 0:
        return False
    confidence = block.get("confidence")
    if confidence is None or float(confidence) >= MINORITY_SCRIPT_MAX_CONFIDENCE:
        return False
    family = max(letters, key=letters.get)
    return page_scripts.get(family, 0) / page_letters < MINORITY_SCRIPT_MAX_PAGE_SHARE


def verify_lines(
    ir: dict[str, Any],
    source: str | Path,
    *,
    reader: Callable[[Any], str | None] | None = None,
    rasters: dict[int, Any] | None = None,
    scale: float = SCALE,
) -> dict[str, Any]:
    """Annotate scanned blocks with highlight evidence and entity double reading."""
    reader = reader or _tesseract_line
    scanned = [p for p in ir.get("pages", []) if p.get("scanned")]
    if rasters is None:
        rasters = _page_rasters(Path(source), [int(p["number"]) for p in scanned], scale)
    stats = {
        "version": VERSION,
        "lines": 0,
        "highlighted_lines": 0,
        "entity_lines": 0,
        "agree": 0,
        "disagree": 0,
        "inconclusive": 0,
        "not_checked_no_marker": 0,
        "blocks_disagreement": 0,
        "blocks_form_structure_risk": 0,
        "blocks_identifier_only": 0,
        "blocks_minority_script_low_confidence": 0,
        "blocks_ocr_unreliable_rechecked": 0,
    }
    reason_counts: dict[str, int] = {}
    for page in scanned:
        rgb = rasters.get(int(page["number"]))
        if rgb is None:
            continue
        page_scripts = script_letters(
            " ".join(str(b.get("text") or "") for b in page.get("blocks", []))
        )
        page_letters = sum(page_scripts.values())
        for block in page.get("blocks", []):
            lines = block.get("source_lines") or [block]
            line_status = []
            highlighted = []
            for line in lines:
                box = line.get("bbox")
                if not box:
                    continue
                stats["lines"] += 1
                px = [float(v) * scale for v in box]
                evidence = highlight_evidence(rgb, px)
                if evidence is not None:
                    line["highlight_evidence"] = evidence
                    if evidence.get("highlight"):
                        stats["highlighted_lines"] += 1
                        highlighted.append(evidence)
                if not digit_sequence(str(line.get("text") or "")):
                    continue
                stats["entity_lines"] += 1
                marker = evidence is not None and (
                    bool(evidence.get("highlight"))
                    or float(evidence.get("coverage") or 0.0) >= MARKER_MIN_COVERAGE
                )
                if not marker:
                    stats["not_checked_no_marker"] += 1
                    line["entity_double_read"] = "not_checked_no_marker"
                    continue
                status = compare_readings(
                    str(line.get("text") or ""), second_reading(rgb, px, reader)
                )
                stats[status] = stats.get(status, 0) + 1
                line["entity_double_read"] = status
                line_status.append((str(line.get("id") or block.get("id")), status))
            style = block.get("style") if isinstance(block.get("style"), dict) else None
            if highlighted and style is not None:
                style["highlight"] = True
                style["highlight_rgb"] = highlighted[0]["rgb"]
                style["highlight_lines"] = len(highlighted)
                style["highlight_partial"] = any(e.get("partial") for e in highlighted) or len(
                    highlighted
                ) < len(lines)
            disagreeing = [line_id for line_id, status in line_status if status == "disagree"]
            if disagreeing:
                block["entity_read_disagreement"] = {
                    "line_ids": disagreeing,
                    "count": len(disagreeing),
                }
                stats["blocks_disagreement"] += 1
            else:
                block.pop("entity_read_disagreement", None)
            reasons = form_structure_evidence(rgb, lines, scale)
            if reasons:
                block["form_structure_risk"] = {"reasons": reasons, "lines": len(lines)}
                stats["blocks_form_structure_risk"] += 1
                for reason in reasons:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
            else:
                block.pop("form_structure_risk", None)
            if identifier_only(str(block.get("text") or "")):
                block["identifier_only"] = True
                stats["blocks_identifier_only"] += 1
            else:
                block.pop("identifier_only", None)
            if minority_script_noise(block, page_scripts, page_letters):
                block["minority_script_low_confidence"] = True
                stats["blocks_minority_script_low_confidence"] += 1
            else:
                block.pop("minority_script_low_confidence", None)
            # Re-evaluated here so that a reused analysis gets the current
            # rule too (D19/D25). Only OCR blocks carry a measured confidence;
            # the flag is only ever raised, never cleared.
            if (
                block.get("source_lines")
                and block.get("confidence") is not None
                and not block.get("ocr_unreliable")
                and is_unreliable_ocr(str(block.get("text") or ""), block.get("confidence"))
            ):
                block["ocr_unreliable"] = True
                stats["blocks_ocr_unreliable_rechecked"] += 1
    stats["form_structure_reasons"] = reason_counts
    ir["line_verification"] = stats
    return stats
