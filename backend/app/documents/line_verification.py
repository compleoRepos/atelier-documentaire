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

import copy
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.documents.segmentation import is_unreliable_ocr, join_line_texts

VERSION = "line-verification-7"
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


_REF_LIST_KEYS = ("block_ids", "ambiguous_block_ids", "overlapping_block_ids")


def split_block_at_rules(
    block: dict[str, Any], rgb: Any, scale: float
) -> list[dict[str, Any]] | None:
    """Split a multi-line block where a horizontal rule separates two lines.

    Run18 audit: segmentation merged the lines of distinct form/table cells
    (8 Arabic lines of 8 rows of a bilingual table) into one paragraph; the
    form-structure guard then kept the WHOLE block in the source language
    (DOC-004: 1 197 characters never sent). Each part between two rules is now
    its own block, so cells are translated and rendered in their own row; a
    part that still crosses a structure is guarded on its own.
    """
    lines = [line for line in block.get("source_lines") or [] if line.get("bbox")]
    if len(lines) < 2 or block.get("protected"):
        return None
    indexed = sorted(
        enumerate(lines), key=lambda item: (float(item[1]["bbox"][1]), float(item[1]["bbox"][0]))
    )
    groups: list[list[tuple[int, dict[str, Any]]]] = [[indexed[0]]]
    for previous, current in zip(indexed, indexed[1:], strict=False):
        upper = [float(v) * scale for v in previous[1]["bbox"]]
        lower = [float(v) * scale for v in current[1]["bbox"]]
        if horizontal_rule_between(rgb, upper, lower):
            groups.append([current])
        else:
            groups[-1].append(current)
    if len(groups) < 2:
        return None
    return _build_parts(block, lines, groups, "horizontal_rule_between_lines")


CHECKBOX_MIN_HEIGHT = 0.6  # x OCR line height (x-height letters are ~0.5)
CHECKBOX_MAX_HEIGHT = 1.4
CHECKBOX_MIN_PX = 10  # at SCALE (2.5 pt)
CHECKBOX_HOLLOW_INK = 0.18
CHECKBOX_FILLED_INK = 0.85
CHECKBOX_PAD = 0.4
CHECKBOX_FLAT_TOLERANCE = 0.1
CHECKBOX_CORNER_DISTANCE = 0.12
CHECKBOX_ISOLATION = 0.7
# F17 (run18 final audit): Arabic OCR line boxes are inflated by ascenders,
# descenders and diacritics (58-66 px for 27-29 px drawn boxes at SCALE), so an
# empty box failed CHECKBOX_MIN_HEIGHT x line height and its mask erased it.
# Below that bound, a component is still a box when it is EMPTY (hollow) and
# taller than the typical glyph of its own line; filled components (bold dots,
# bullets: corpus 0.6-0.9 x the median glyph) stay rejected.
CHECKBOX_INFLATED_MIN_LINE = 0.35
CHECKBOX_INFLATED_GLYPH_RATIO = 1.5
CHECKBOX_GLYPH_MIN_PX = 5


def _flat_outline(cell: Any) -> bool:
    """True when the four outer profiles of a component are straight lines:
    for every column (row) of the central 80 %, the first inked pixel seen from
    the top/bottom (left/right) lies within a narrow band."""
    import numpy as np

    height, width = cell.shape
    tolerance = max(2, round(CHECKBOX_FLAT_TOLERANCE * min(height, width)))
    margin_x, margin_y = max(1, round(width * 0.1)), max(1, round(height * 0.1))
    columns = cell[:, margin_x : width - margin_x]
    rows = cell[margin_y : height - margin_y, :]
    if not columns.size or not rows.size:
        return False
    if not columns.any(axis=0).all() or not rows.any(axis=1).all():
        return False
    top = columns.argmax(axis=0)
    bottom = height - 1 - columns[::-1, :].argmax(axis=0)
    left = rows.argmax(axis=1)
    right = width - 1 - rows[:, ::-1].argmax(axis=1)
    return all(
        int(np.ptp(profile)) <= tolerance and int(np.median(np.abs(profile - edge))) <= tolerance
        for profile, edge in ((top, 0), (bottom, height - 1), (left, 0), (right, width - 1))
    )


def _square_corners(cell: Any) -> bool:
    """True when ink reaches the four corners of the component's bounding box.
    Round glyphs (o, O, D, e, a) keep their corners about 20 % of the side
    away from any ink, a drawn box does not."""
    import numpy as np

    height, width = cell.shape
    ink = np.argwhere(cell)
    if not len(ink):
        return False
    limit = max(1.5, CHECKBOX_CORNER_DISTANCE * min(height, width))
    for corner in ((0, 0), (0, width - 1), (height - 1, 0), (height - 1, width - 1)):
        if float(np.sqrt(((ink - np.array(corner)) ** 2).sum(axis=1)).min()) > limit:
            return False
    return True


def _isolated(rgb: Any, box: list[int]) -> bool:
    """A box glyph is separated from its label by a space: at least one side
    has blank columns over CHECKBOX_ISOLATION x its height (measured on the
    corpus: true boxes >= 0.81, a letter inside a word <= 0.46)."""
    x0, y0, x1, y1 = box
    height = max(1, y1 - y0)
    band = rgb[y0:y1].mean(axis=2) < 140
    need = int(round(CHECKBOX_ISOLATION * height))

    def blank_run(columns: range) -> int:
        count = 0
        for column in columns:
            if column < 0 or column >= band.shape[1]:
                return need  # page edge counts as blank
            if band[:, column].any():
                break
            count += 1
            if count >= need:
                break
        return count

    left = blank_run(range(x0 - 1, x0 - 1 - need, -1))
    right = blank_run(range(x1, x1 + need))
    return max(left, right) >= need


def checkbox_glyphs(rgb: Any, box_px: list[float]) -> list[dict[str, Any]]:
    """Square box glyphs (empty or ticked/filled check boxes) inside an OCR box.
    Run18 audit: Tesseract read the Arabic "No" + an empty box as one word
    (confidence 0.94); the word was translated and its mask erased the box.
    A component is a box when its bounding box is roughly square, as tall as
    the text, and either all four sides are inked with a light interior
    (empty box) or it is almost entirely inked (filled box); a box whose
    interior is partly inked is "marked" (ticked or crossed)."""
    import cv2
    import numpy as np

    height, width = rgb.shape[:2]
    line_h = max(1.0, float(box_px[3]) - float(box_px[1]))
    # OCR boxes often stop short of the box glyph: look a little around them.
    pad = max(2, round(line_h * CHECKBOX_PAD))
    x0, y0 = max(0, int(box_px[0]) - pad), max(0, int(box_px[1]) - pad)
    x1, y1 = min(width, int(box_px[2]) + pad), min(height, int(box_px[3]) + pad)
    if x1 - x0 < CHECKBOX_MIN_PX or y1 - y0 < CHECKBOX_MIN_PX:
        return []
    gray = rgb[y0:y1, x0:x1].mean(axis=2)
    dark = (gray < 140).astype(np.uint8)
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    min_height = max(CHECKBOX_MIN_PX, CHECKBOX_MIN_HEIGHT * line_h)
    glyph_heights = [
        int(stats[i][3])
        for i in range(1, count)
        if CHECKBOX_GLYPH_MIN_PX <= stats[i][3] <= CHECKBOX_MAX_HEIGHT * line_h and stats[i][2] >= 3
    ]
    glyph_h = float(np.median(glyph_heights)) if glyph_heights else 0.0
    found = []
    for index in range(1, count):
        cx, cy, cw, ch, _area = (int(v) for v in stats[index])
        if ch > CHECKBOX_MAX_HEIGHT * line_h:
            continue
        inflated_line = ch < min_height
        if inflated_line and not (
            ch >= max(CHECKBOX_MIN_PX, CHECKBOX_INFLATED_MIN_LINE * line_h)
            and glyph_h > 0
            and ch >= CHECKBOX_INFLATED_GLYPH_RATIO * glyph_h
        ):
            continue
        if not 0.75 <= cw / max(1, ch) <= 1.33:
            continue
        cell = dark[cy : cy + ch, cx : cx + cw].astype(bool)
        if not _flat_outline(cell) or not _square_corners(cell):
            continue  # curved/open letters (o, D, e, a, n, u) and bullets
        if not _isolated(rgb, [x0 + cx, y0 + cy, x0 + cx + cw, y0 + cy + ch]):
            continue  # a letter inside a word (degraded bold "e", run18 DOC-007)
        stroke = max(1, round(min(cw, ch) * 0.22))
        inner = cell[stroke : ch - stroke, stroke : cw - stroke]
        inner_ink = float(inner.mean()) if inner.size else 1.0
        if float(cell.mean()) >= CHECKBOX_FILLED_INK:
            state = "filled"
        elif inner_ink <= CHECKBOX_HOLLOW_INK:
            state = "empty"
        else:
            state = "marked"  # ticked / crossed box
        if inflated_line and state != "empty":
            continue  # only a hollow box may rely on the glyph-height reference
        found.append(
            {
                "state": state,
                "bbox_px": [x0 + cx, y0 + cy, x0 + cx + cw, y0 + cy + ch],
                **({"height_reference": "line_glyphs"} if inflated_line else {}),
            }
        )
    return found


def _build_parts(
    block: dict[str, Any],
    lines: list[dict[str, Any]],
    groups: list[list[tuple[int, dict[str, Any]]]],
    reason: str,
    suffix: str = "r",
) -> list[dict[str, Any]]:
    heights = block.get("line_heights")
    parts = []
    for number, group in enumerate(groups, start=1):
        group.sort(key=lambda item: item[0])  # keep the original reading order
        members = [line for _, line in group]
        part = copy.deepcopy({k: v for k, v in block.items() if k != "source_lines"})
        part["id"] = f"{block.get('id')}-{suffix}{number}"
        part["source_lines"] = copy.deepcopy(members)
        part["text"] = join_line_texts([str(line.get("text") or "") for line in members])
        boxes = [[float(v) for v in line["bbox"]] for line in members]
        part["bbox"] = [
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        ]
        part["line_count"] = len(members)
        if isinstance(heights, list) and len(heights) == len(lines):
            part["line_heights"] = [heights[index] for index, _ in group]
        confidences = [
            float(line["confidence"]) for line in members if line.get("confidence") is not None
        ]
        if confidences:
            part["confidence"] = round(sum(confidences) / len(confidences), 4)
            part["min_line_confidence"] = round(min(confidences), 4)
        if len(members) == 1 and part.get("role") == "paragraph":
            part["role"] = "line"
        part["split_from"] = {
            "id": block.get("id"),
            "reason": reason,
            "part": number,
            "parts": len(groups),
        }
        parts.append(part)
    return parts


_ENUMERATOR_END = re.compile(r"(?:^|\s)[.(]?(\d{1,2})[.)]?\s*$")
_ENUMERATOR_START = re.compile(r"^\s*[.(]?(\d{1,2})[.)]?(?:\s|$)")
_BIDI_MARKS = re.compile("[\u200e\u200f\u202a-\u202e]")
LIST_MIN_ITEMS = 3


def _enumerator(text: str) -> int | None:
    clean = _BIDI_MARKS.sub("", text).strip()
    for pattern in (_ENUMERATOR_START, _ENUMERATOR_END):
        match = pattern.search(clean)
        if match and clean != match.group(0).strip():
            return int(match.group(1))
    return None


def split_block_at_enumerators(block: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Split, line by line, a block whose lines are consecutive numbered items.
    Run18 audit: the 8 items of a numbered salary list (each aligned with its
    amount in the next column) were merged into one paragraph and reflowed
    by the renderer, so labels no longer faced their amounts. When >= 3 lines
    carry an enumerator (at the start or, in RTL OCR, at the end) forming a
    strictly consecutive sequence, every line becomes its own block, rendered
    in place."""
    lines = [line for line in block.get("source_lines") or [] if line.get("bbox")]
    if len(lines) < LIST_MIN_ITEMS or block.get("protected"):
        return None
    numbers = [_enumerator(str(line.get("text") or "")) for line in lines]
    found = [n for n in numbers if n is not None]
    if len(found) < LIST_MIN_ITEMS:
        return None
    if any(b - a != 1 for a, b in zip(found, found[1:], strict=False)):
        return None
    groups: list[list[tuple[int, dict[str, Any]]]] = []
    for index, (line, number) in enumerate(zip(lines, numbers, strict=True)):
        if number is not None or not groups:
            groups.append([(index, line)])
        else:
            groups[-1].append((index, line))  # wrapped continuation of the item
    return _build_parts(block, lines, groups, "enumerated_list_items", suffix="i")


_RTL_LETTER = re.compile("[\u0590-\u08ff\ufb1d-\ufdff\ufe70-\ufeff]")
_MIRRORED_BRACKETS = re.compile(r"\)([^()]{0,24}\d[^()]{0,24})\(")


def normalize_mirrored_brackets(text: str) -> tuple[str, int]:
    """Fix ")010(" -> "(010)" in RTL OCR lines (bidi mirroring by the OCR).
    Run18 audit: a phone number of a bilingual footer kept mirrored
    parentheses in the source and the translation. Only bracket pairs around
    digits in lines containing RTL letters are touched."""
    if not _RTL_LETTER.search(text):
        return text, 0
    return _MIRRORED_BRACKETS.subn(lambda m: f"({m.group(1)})", text)


def _expand_refs(value: Any, mapping: dict[str, list[str]]) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _REF_LIST_KEYS and isinstance(item, list):
                value[key] = [new for old in item for new in mapping.get(str(old), [old])]
            elif key == "block_id" and str(item) in mapping:
                value[key] = mapping[str(item)][0]
            else:
                _expand_refs(item, mapping)
    elif isinstance(value, list):
        for item in value:
            _expand_refs(item, mapping)
    return value


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


CHECKBOX_DETECTOR = "line_verification_checkbox"

CHECKBOX_START_TOLERANCE = 1.5  # pt between the box and the line reading start
CHECKBOX_TOKEN_MAX_CHARS = 2
CHECKBOX_REST_ZIPF = 3.0
_LETTERS = re.compile(r"[^\W\d_]", re.UNICODE)


def _rtl_line(text: str) -> bool:
    rtl = len(_RTL_LETTER.findall(text))
    return rtl > 0 and rtl >= len(_LETTERS.findall(text)) / 2


def box_at_reading_start(line_box: list[float], glyph_box: list[float], text: str) -> bool:
    """True when a check-box glyph sits where the OCR line starts to be read
    (left edge for LTR text, right edge for RTL text): the first OCR token is
    then the box itself, misread as letters (run18 audit: the box was read as
    "©", "O", "E", "S", "D", "t", "p" or Arabic letters)."""
    if not (glyph_box[1] < line_box[3] and glyph_box[3] > line_box[1]):
        return False
    if _rtl_line(text):
        return abs(float(glyph_box[2]) - float(line_box[2])) <= CHECKBOX_START_TOLERANCE
    return abs(float(glyph_box[0]) - float(line_box[0])) <= CHECKBOX_START_TOLERANCE


def _line_glyph_boxes(rgb: Any, line: dict[str, Any], scale: float) -> list[list[float]]:
    box = line.get("bbox")
    if not box:
        return []
    return [
        [float(v) / scale for v in glyph["bbox_px"]]
        for glyph in checkbox_glyphs(rgb, [float(v) * scale for v in box])
    ]


def split_block_at_checkboxes(
    block: dict[str, Any], rgb: Any, scale: float
) -> list[dict[str, Any]] | None:
    """Split a block whose lines are check-box options (run18 audit: the two
    options "box + yes, fixed term" / "box + yes, permanent" of a form were
    merged into one paragraph and reflowed across both boxes). Each line that
    starts on a box opens a new block; other lines are its continuations."""
    if block.get("protected") or not str(block.get("provenance") or "").startswith("ocr"):
        return None
    lines = [line for line in block.get("source_lines") or [] if line.get("bbox")]
    if len(lines) < 2:
        return None
    starts = [
        any(
            box_at_reading_start(line["bbox"], glyph, str(line.get("text") or ""))
            for glyph in _line_glyph_boxes(rgb, line, scale)
        )
        for line in lines
    ]
    if sum(starts) < 2:
        return None
    groups: list[list[tuple[int, dict[str, Any]]]] = []
    for index, (line, start) in enumerate(zip(lines, starts, strict=True)):
        if start or not groups:
            groups.append([(index, line)])
        else:
            groups[-1].append((index, line))
    if len(groups) < 2:
        return None
    return _build_parts(block, lines, groups, "checkbox_options", suffix="o")


CHECKBOX_SHORT_REST_ZIPF = 4.5  # two-letter remainders: only very common words
CHECKBOX_MAIN_LANGUAGE_SHARE = 0.15
_LEXICON_ISO = {"ara": "ar"}
# F18 (run18 final audit): once the box token is removed, an RTL option line
# that still carries one or two short Latin tokens is a degraded reading (the
# OCR mixed both models: "<ar> <ar> Het", "<ar> de <ar>", words missing); the
# model filled the gaps with invented words ("Oui, pas Het"). Not sent.
CHECKBOX_NOISE_MIN_RTL_LETTERS = 4
CHECKBOX_NOISE_MAX_TOKENS = 2
CHECKBOX_NOISE_MAX_LETTERS = 3


def mixed_script_noise(text: str) -> bool:
    """True for an RTL line holding 1-2 short Latin tokens (<= 3 letters)."""
    tokens = _BIDI_MARKS.sub("", text).split()
    rtl = sum(len(_RTL_LETTER.findall(token)) for token in tokens)
    if rtl < CHECKBOX_NOISE_MIN_RTL_LETTERS:
        return False
    latin = [
        token
        for token in tokens
        if script_letters(token).get("latin") and not _RTL_LETTER.search(token)
    ]
    return 1 <= len(latin) <= CHECKBOX_NOISE_MAX_TOKENS and all(
        script_letters(token).get("latin", 0) <= CHECKBOX_NOISE_MAX_LETTERS for token in latin
    )


def _frequent_word(word: str, isos: list[str]) -> bool:
    from .language_evidence import _zipf, available

    if not available():
        return False
    clean = "".join(_LETTERS.findall(word)).lower()
    if len(clean) < 2:
        return False
    threshold = CHECKBOX_REST_ZIPF if len(clean) >= 3 else CHECKBOX_SHORT_REST_ZIPF
    return any(_zipf(clean, iso) >= threshold for iso in isos)


def _document_isos(ir: dict[str, Any], block: dict[str, Any]) -> list[str]:
    """The block language plus the document's main languages (>= 15 % of the
    OCR characters); misdetected minor languages are ignored."""
    from .language_evidence import _ISO

    table = {**_ISO, **_LEXICON_ISO}
    chars: dict[str, int] = {}
    for page in ir.get("pages", []):
        for other in page.get("blocks", []):
            code = str(other.get("language") or "")
            chars[code] = chars.get(code, 0) + len(str(other.get("text") or ""))
    total = sum(v for k, v in chars.items() if k in table) or 1
    codes = [str(block.get("language") or "")]
    codes += [
        k
        for k, v in sorted(chars.items(), key=lambda kv: -kv[1])
        if k in table and v / total >= CHECKBOX_MAIN_LANGUAGE_SHARE
    ]
    isos: list[str] = []
    for code in codes:
        iso = table.get(code)
        if iso and iso != "fr" and iso not in isos:
            isos.append(iso)
    return isos


def strip_checkbox_tokens(
    ir: dict[str, Any],
    block: dict[str, Any],
    line_boxes: dict[int, list[list[float]]],
    stats: dict[str, Any],
) -> None:
    """Remove from the OCR text the token that is the check-box glyph itself.

    * first token of <= 2 characters followed by words: removed;
    * box fused with the first word: its first character is removed only when
      the remainder is a frequent word of a document language (wordfreq);
    * otherwise the line reading is unreliable: the block is flagged
      ``ocr_unreliable`` (UNCERTAIN, not sent to the model, source kept).
    The raw OCR text is kept in ``ocr_text_raw``; idempotent on reuse."""
    lines = block.get("source_lines") or []
    if not lines:
        return
    changed = False
    unreliable = 0
    noisy = 0
    readable = 0
    for index, line in enumerate(lines):
        text = str(line.get("text") or "")
        if text.strip():
            readable += 1
        if line.get("checkbox_token") in {"stripped", "fused_stripped"}:
            if mixed_script_noise(text):
                line["ocr_noise"] = "mixed_script"
                noisy += 1
            continue
        if line.get("checkbox_token") == "fused_unreliable":
            unreliable += 1
            continue
        boxes = line_boxes.get(index) or []
        if not any(box_at_reading_start(line["bbox"], g, text) for g in boxes):
            continue
        tokens = _BIDI_MARKS.sub("", text).split()
        if not tokens:
            continue
        first, rest = tokens[0], tokens[1:]
        if len(first) <= CHECKBOX_TOKEN_MAX_CHARS and any(
            len(_LETTERS.findall(t)) >= 2 for t in rest
        ):
            line["ocr_text_raw"] = text
            line["text"] = " ".join(rest)
            line["checkbox_token"] = "stripped"
            stats["checkbox_tokens_stripped"] += 1
            changed = True
            if mixed_script_noise(line["text"]):
                line["ocr_noise"] = "mixed_script"
                noisy += 1
            continue
        remainder = first[1:]
        if _frequent_word(remainder, _document_isos(ir, block)):
            line["ocr_text_raw"] = text
            line["text"] = " ".join([remainder, *rest])
            line["checkbox_token"] = "fused_stripped"
            stats["checkbox_tokens_stripped"] += 1
            changed = True
            if mixed_script_noise(line["text"]):
                line["ocr_noise"] = "mixed_script"
                noisy += 1
            continue
        line["checkbox_token"] = "fused_unreliable"
        stats["checkbox_lines_fused_unreliable"] += 1
        unreliable += 1
    if changed:
        block.setdefault("ocr_text_raw", block.get("text"))
        block["text"] = join_line_texts([str(line.get("text") or "") for line in lines])
    stats["checkbox_lines_mixed_script_noise"] = (
        stats.get("checkbox_lines_mixed_script_noise", 0) + noisy
    )
    if (unreliable or noisy) and unreliable + noisy >= readable:
        if not block.get("ocr_unreliable"):
            stats["blocks_checkbox_fused_unreliable"] += 1
        block["ocr_unreliable"] = True
        block["ocr_unreliable_reason"] = (
            "checkbox_glyph_fused" if unreliable else "checkbox_line_mixed_script_noise"
        )


def _declare_checkbox_regions(
    ir: dict[str, Any],
    page: dict[str, Any],
    block: dict[str, Any],
    rgb: Any,
    scale: float,
    stats: dict[str, Any],
) -> dict[int, list[list[float]]]:
    """Declare every check-box glyph of an OCR block as a protected visual
    region, so that the renderer never masks it (the block is then kept when
    the box is a significant part of it, or its masks are shrunk around the
    box). Idempotent: an existing region with the same box is reused."""
    regions = ir.setdefault("protected_visual_regions", [])
    number = int(page.get("number") or 0)
    known = {
        tuple(round(float(v), 1) for v in r.get("bbox") or [])
        for r in regions
        if r.get("detector") == CHECKBOX_DETECTOR and int(r.get("page") or 0) == number
    }
    states = []
    line_boxes: dict[int, list[list[float]]] = {}
    for line_index, line in enumerate(block.get("source_lines") or [block]):
        box = line.get("bbox")
        if not box:
            continue
        for glyph in checkbox_glyphs(rgb, [float(v) * scale for v in box]):
            width = float(page.get("width") or 1e9)
            height = float(page.get("height") or 1e9)
            x0, y0, x1, y1 = (float(v) / scale for v in glyph["bbox_px"])
            bbox = [
                round(max(0.0, x0), 2),
                round(max(0.0, y0), 2),
                round(min(width, x1), 2),
                round(min(height, y1), 2),
            ]
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                continue
            states.append(glyph["state"])
            line_boxes.setdefault(line_index, []).append(bbox)
            stats["checkbox_glyphs"] += 1
            key = tuple(round(v, 1) for v in bbox)
            if key in known:
                continue
            known.add(key)
            regions.append(
                {
                    "type": "protected_visual_region",
                    "subtype": "checkbox_glyph",
                    "id": f"checkbox-p{number:03d}-{len(known):03d}",
                    "page": number,
                    "bbox": bbox,
                    "provenance": "automatic_candidate:line_verification",
                    "candidate": True,
                    "authenticated": False,
                    "detector": CHECKBOX_DETECTOR,
                    "confidence": None,
                    "coordinates_kind": "original",
                    "state": glyph["state"],
                    "block_id": str(block.get("id")),
                }
            )
            stats["checkbox_regions_added"] += 1
    if states:
        block["checkbox_glyphs"] = states
    return line_boxes


def _normalize_block_brackets(block: dict[str, Any], stats: dict[str, Any]) -> None:
    fixed = 0
    for line in block.get("source_lines") or []:
        text, count = normalize_mirrored_brackets(str(line.get("text") or ""))
        if count:
            line["text"] = text
            fixed += count
    text, count = normalize_mirrored_brackets(str(block.get("text") or ""))
    if count:
        block["text"] = text
        fixed = max(fixed, count)
    if fixed:
        block["bidi_brackets_normalized"] = int(block.get("bidi_brackets_normalized") or 0) + fixed
        stats["bidi_brackets_normalized"] += fixed


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
    from app.documents.language_evidence import refine_block_languages

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
        "blocks_split_at_rules": 0,
        "blocks_from_rule_splits": 0,
        "blocks_split_at_list_items": 0,
        "checkbox_glyphs": 0,
        "checkbox_regions_added": 0,
        "blocks_split_at_checkbox_options": 0,
        "checkbox_tokens_stripped": 0,
        "checkbox_lines_fused_unreliable": 0,
        "blocks_checkbox_fused_unreliable": 0,
        "checkbox_lines_mixed_script_noise": 0,
        "bidi_brackets_normalized": 0,
    }
    split_maps: dict[str, list[str]] = {}
    reason_counts: dict[str, int] = {}
    for page in scanned:
        rgb = rasters.get(int(page["number"]))
        if rgb is None:
            continue
        mapping: dict[str, list[str]] = {}
        rule_split: list[str] = []
        rebuilt: list[dict[str, Any]] = []
        for block in page.get("blocks", []):
            parts = split_block_at_rules(block, rgb, scale)
            if parts:
                mapping[str(block.get("id"))] = [str(part["id"]) for part in parts]
                rule_split.append(str(block.get("id")))
            items: list[dict[str, Any]] = []
            for part in parts or [block]:
                pieces = split_block_at_enumerators(part)
                if pieces:
                    origin = str(block.get("id"))
                    ids = mapping.get(origin, [origin])
                    position = ids.index(str(part["id"])) if str(part["id"]) in ids else len(ids)
                    ids[position : position + 1] = [str(piece["id"]) for piece in pieces]
                    mapping[origin] = ids
                    stats["blocks_split_at_list_items"] += 1
                    items.extend(pieces)
                    continue
                options = split_block_at_checkboxes(part, rgb, scale)
                if options:
                    origin = str(block.get("id"))
                    ids = mapping.get(origin, [origin])
                    position = ids.index(str(part["id"])) if str(part["id"]) in ids else len(ids)
                    ids[position : position + 1] = [str(piece["id"]) for piece in options]
                    mapping[origin] = ids
                    stats["blocks_split_at_checkbox_options"] += 1
                    items.extend(options)
                else:
                    items.append(part)
            rebuilt.extend(items)
        if mapping:
            page["blocks"] = rebuilt
            for order, block in enumerate(rebuilt):
                block["reading_order"] = order
            for key in ("layout",):
                _expand_refs(page.get(key), mapping)
            split_maps.update(mapping)
            stats["blocks_split_at_rules"] += len(rule_split)
            stats["blocks_from_rule_splits"] += sum(len(mapping[k]) for k in rule_split)
        page_scripts = script_letters(
            " ".join(str(b.get("text") or "") for b in page.get("blocks", []))
        )
        page_letters = sum(page_scripts.values())
        for block in page.get("blocks", []):
            if str(block.get("provenance") or "").startswith("ocr"):
                line_boxes = _declare_checkbox_regions(ir, page, block, rgb, scale, stats)
                strip_checkbox_tokens(ir, block, line_boxes, stats)
                _normalize_block_brackets(block, stats)
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
    if split_maps:
        for key in ("tables", "warnings"):
            _expand_refs(ir.get(key), split_maps)
    # After the rule splits so every final block gets its own evidence (run18).
    stats["language_evidence"] = refine_block_languages(ir)
    stats["form_structure_reasons"] = reason_counts
    ir["line_verification"] = stats
    return stats
