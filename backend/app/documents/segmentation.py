"""Semantic segmentation of OCR lines into translation units (scanned pages).

OCR engines return *physical* lines. Translating line by line breaks
sentences, grammar and typography (a sentence split over three lines becomes
three unrelated fragments). This module groups lines that belong to the same
paragraph, list item, multi-line heading or table cell into a single block,
while keeping every source line (text, bbox, confidence, provenance) so the
renderer can cover the exact source ink and the audit can trace each line.

Grouping is deliberately conservative: when in doubt, lines stay apart. A
single line is a valid (if less fluent) unit; a wrong merge would mix two
form fields or two columns, which is worse. Every decision is traced.

Protected lines (stamps, signatures, logos) are never merged with text.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Callable, Iterable
from typing import Any

VERSION = "ocr-segmentation-v1"

_TERMINAL = re.compile(r"[.!?…]['\"»)\]]*\s*$")
_COLON_END = re.compile(r":\s*$")
_BULLET = re.compile(
    r"^\s*(?:[-–—•·▪●○■□✓➢►*]\s+|\(?\d{1,3}[.)]\s+|\(?[a-zA-Z][.)]\s+|[ivxIVX]{1,5}[.)]\s+)"
)
_SECTION = re.compile(r"^\s*(?:\d{1,2}(?:\.\d{1,2})*[.)]?|[IVXLC]{1,5}[.)])\s+\S")
_FIELD = re.compile(r"^[^:\d]{2,48}:\s*(?:\S.*)?$")
_LEADER = re.compile(r"\.{4,}|_{4,}|…{2,}")
_ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]")


def _box(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        box = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    return box


def _area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _inter(a: list[float], b: list[float]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return (x1 - x0) * (y1 - y0) if x1 > x0 and y1 > y0 else 0.0


def _union(boxes: Iterable[list[float]]) -> list[float]:
    boxes = list(boxes)
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def _median(values: list[float], default: float) -> float:
    values = [v for v in values if v and v > 0]
    return float(statistics.median(values)) if values else default


def _percentile(values: list[float], q: float, default: float) -> float:
    values = sorted(values)
    if not values:
        return default
    index = min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))
    return float(values[index])


def _letters(text: str) -> list[str]:
    return [c for c in text if c.isalpha()]


def caps_ratio(text: str) -> float:
    letters = _letters(text)
    if len(letters) < 3:
        return 0.0
    return sum(c.isupper() for c in letters) / len(letters)


def is_heading_text(text: str) -> bool:
    value = (text or "").strip()
    words = value.split()
    if not value or len(words) > 14:
        return False
    if caps_ratio(value) >= 0.75 and len(_letters(value)) >= 3:
        return True
    return bool(_SECTION.match(value)) and len(value) <= 70 and not value.endswith(",")


def is_bullet_text(text: str) -> bool:
    return bool(_BULLET.match(text or ""))


def _is_field(text: str, width: float, body_width: float) -> bool:
    value = (text or "").strip()
    if _LEADER.search(value):
        return True
    return bool(_FIELD.match(value)) and width < 0.6 * max(body_width, 1.0)


def _script(text: str) -> str:
    return "arabic" if _ARABIC.search(text or "") else "latin"


_WORD4 = re.compile(r"[^\W\d_]{4,}", re.UNICODE)
# Measured OCR confidence under which a block is never sent to a model.
OCR_NO_CONFIDENCE = 0.10


def is_unreliable_ocr(text: str, confidence: float) -> bool:
    """Low confidence AND no alphabetic word of 4+ letters: OCR noise.

    Measured on the corpus: low-confidence lines include real titles
    (``CLÁUSULAS``) which must stay translatable, and pure noise
    (``LEE? RS)``, ``ak wg``) which must not be sent to a model.

    A *measured* confidence below ``OCR_NO_CONFIDENCE`` is unreliable even
    when it looks like a word: Tesseract had no evidence at all (final audit:
    a 0.00 fragment read inside an overprinted footer was translated and
    written over the original). ``None`` (no measurement) keeps the
    historical rule only.
    """
    if confidence is not None and float(confidence) < OCR_NO_CONFIDENCE:
        return True
    return float(confidence or 0.0) < 0.45 and not _WORD4.search(text or "")


def join_line_texts(texts: list[str]) -> str:
    """Join physical lines into one logical text.

    A trailing hyphen is kept (``bien-`` + ``être`` -> ``bien-être``): removing
    it would corrupt compound words, keeping it never loses information.
    """
    out = ""
    for raw in texts:
        text = (raw or "").strip()
        if not text:
            continue
        if not out:
            out = text
        elif out.endswith("-") and len(out) >= 2 and out[-2].isalpha():
            out = out + text
        else:
            out = out + " " + text
    return out


# --------------------------------------------------------------------------
# Style evidence measured on the ORIGINAL raster (never on the enhanced copy)
# --------------------------------------------------------------------------


_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONTS: dict[str, Any] = {}


def width_font_size(text: str, width: float, bold: bool = False) -> float | None:
    """Font size (pt) at which the RENDERING font draws ``text`` with the
    measured source width. OCR box heights are swollen by accents, descenders
    and nearby ink (13.5 pt boxes measured for 7 pt text); the width of a line
    of >= 8 characters is a far more stable size estimate, and it calibrates
    the metric difference between the source font and the rendering font."""
    clean = " ".join(str(text).split())
    if len(clean) < 8 or width <= 0:
        return None
    path = _FONT_BOLD if bold else _FONT_REGULAR
    try:
        import fitz

        font = _FONTS.get(path)
        if font is None:
            font = _FONTS[path] = fitz.Font(fontfile=path)
        unit = float(font.text_length(clean, fontsize=1))
    except Exception:
        return None
    return width / unit if unit > 0 else None


def line_style_evidence(
    rgb: Any, box_px: list[float], points_per_pixel: float | None = None
) -> dict[str, Any] | None:
    """Stroke thickness, ink colour and background measured inside one line box.

    ``rgb`` is an HxWx3 uint8 array of the original page; ``box_px`` is the
    line bbox in the same pixel space. Values are *evidence* for bold/colour
    decisions, not ground truth: they are stored with the block for audit.
    """
    import numpy as np

    try:
        height, width = rgb.shape[:2]
        x0 = max(0, int(box_px[0]))
        y0 = max(0, int(box_px[1]))
        x1 = min(width, int(round(box_px[2])))
        y1 = min(height, int(round(box_px[3])))
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        crop = np.asarray(rgb[y0:y1, x0:x1], dtype=np.float32)
        gray = crop.mean(axis=2)
        background_level = float(np.percentile(gray, 90))
        ink_level = float(np.percentile(gray, 5))
        if background_level - ink_level < 40:
            return None
        threshold = (background_level + ink_level) / 2.0
        ink = gray < threshold
        ink_pixels = int(ink.sum())
        if ink_pixels < 12:
            return None
        import cv2

        distance = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
        stroke = float(distance[ink].mean()) / max(1.0, float(y1 - y0))
        ink_rgb = np.median(crop[ink], axis=0) / 255.0
        paper = ~ink & (gray >= np.percentile(gray, 60))
        paper_rgb = (
            np.median(crop[paper], axis=0) / 255.0 if paper.any() else np.array([1.0, 1.0, 1.0])
        )
        stroke_px = float(distance[ink].mean())
        return {
            "stroke_ratio": round(stroke, 5),
            "stroke_px": round(stroke_px, 4),
            **(
                {"stroke_pt": round(stroke_px * float(points_per_pixel), 5)}
                if points_per_pixel
                else {}
            ),
            "ink_rgb": [round(float(v), 4) for v in ink_rgb],
            "paper_rgb": [round(float(v), 4) for v in paper_rgb],
            "ink_fraction": round(ink_pixels / float(ink.size), 4),
        }
    except Exception:
        return None


def _chroma(rgb: list[float] | None) -> float:
    if not rgb:
        return 0.0
    return max(rgb) - min(rgb)


# --------------------------------------------------------------------------
# Grouping
# --------------------------------------------------------------------------


class _Line:
    __slots__ = (
        "block",
        "box",
        "h",
        "text",
        "conf",
        "protected",
        "cells",
        "band",
        "script",
        "heading",
        "bullet",
        "field",
        "letters",
    )

    def __init__(self, block: dict[str, Any], box: list[float]):
        self.block = block
        self.box = box
        self.h = box[3] - box[1]
        self.text = str(block.get("text") or "").strip()
        self.conf = float(block.get("confidence") or 0.0)
        self.protected = bool(block.get("protected"))
        self.cells: list[str] = []
        self.band = "body"
        self.script = _script(self.text)
        self.heading = is_heading_text(self.text)
        self.bullet = is_bullet_text(self.text)
        self.field = False
        self.letters = len(_letters(self.text))


class _Group:
    def __init__(self, line: _Line):
        self.lines = [line]
        self.reasons: list[str] = []

    @property
    def last(self) -> _Line:
        return self.lines[-1]

    @property
    def first(self) -> _Line:
        return self.lines[0]

    def heights(self) -> list[float]:
        return [ln.h for ln in self.lines]

    def box(self) -> list[float]:
        return _union(ln.box for ln in self.lines)


def _cell_map(tables: list[dict[str, Any]], page_number: int) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for table in tables or []:
        if int(table.get("page", page_number) or page_number) != page_number:
            continue
        for cell in table.get("cells", []) or []:
            cell_id = str(
                cell.get("id") or f"{table.get('id')}:{cell.get('row')}:{cell.get('col')}"
            )
            for block_id in cell.get("block_ids", []) or []:
                mapping.setdefault(str(block_id), []).append(cell_id)
    # Ambiguity (a line linked to several cells) is recomputed by the caller
    # after scan-frame cells are removed: a line inside a frame AND one real
    # cell belongs to that cell, it is not ambiguous.
    return mapping


def _frame_cells(tables: list[dict[str, Any]], page_number: int, page_area: float) -> set[str]:
    """Cells covering half the page are scan frames, not semantic cells."""
    frames: set[str] = set()
    for table in tables or []:
        if int(table.get("page", page_number) or page_number) != page_number:
            continue
        for cell in table.get("cells", []) or []:
            box = _box(cell.get("bbox"))
            if box and _area(box) >= 0.5 * page_area:
                frames.add(
                    str(cell.get("id") or f"{table.get('id')}:{cell.get('row')}:{cell.get('col')}")
                )
    return frames


def segment_page(
    page: dict[str, Any],
    tables: list[dict[str, Any]] | None = None,
    protected_regions: list[dict[str, Any]] | None = None,
    *,
    detect_language: Callable[[str], str] | None = None,
    debug: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Group the OCR lines of one scanned page.

    Returns ``(blocks, trace)``. ``blocks`` replaces ``page["blocks"]``; each
    block keeps ``source_lines`` with the original OCR lines. The id of a
    group is the id of its first line, so existing references stay valid.
    """
    number = int(page.get("number", 1))
    width = float(page.get("width") or 0.0) or 612.0
    height = float(page.get("height") or 0.0) or 792.0
    raw_blocks = [b for b in page.get("blocks", []) or [] if isinstance(b, dict)]
    lines: list[_Line] = []
    passthrough: list[dict[str, Any]] = []
    for block in raw_blocks:
        box = _box(block.get("bbox"))
        if box is None or not str(block.get("text") or "").strip():
            passthrough.append(block)
            continue
        lines.append(_Line(block, box))
    trace: dict[str, Any] = {
        "version": VERSION,
        "page": number,
        "input_lines": len(raw_blocks),
        "output_blocks": 0,
        "merged_groups": 0,
        "refusals": {},
    }
    if not lines:
        trace["output_blocks"] = len(raw_blocks)
        return raw_blocks, trace

    confident = [ln for ln in lines if ln.conf >= 0.8 and len(ln.text) >= 8]
    reference = confident or lines
    body_h = _median([ln.h for ln in reference], 10.0)
    body_left = _percentile([ln.box[0] for ln in reference], 0.1, 36.0)
    body_right = _percentile([ln.box[2] for ln in reference], 0.9, width - 36.0)
    body_width = max(body_right - body_left, 0.3 * width)
    cells = _cell_map(tables or [], number)
    frames = _frame_cells(tables or [], number, width * height)
    regions = [
        r
        for r in protected_regions or []
        if int(r.get("page", 0) or 0) == number and _box(r.get("bbox"))
    ]
    region_boxes = [_box(r["bbox"]) for r in regions]

    for ln in lines:
        ln.cells = [c for c in cells.get(str(ln.block.get("id")), []) if c not in frames]
        if ln.box[3] <= 0.07 * height:
            ln.band = "header"
        elif ln.box[1] >= 0.93 * height:
            ln.band = "footer"
        ln.field = _is_field(ln.text, ln.box[2] - ln.box[0], body_width)

    refusals: dict[str, int] = {}

    def refuse(reason: str) -> str:
        refusals[reason] = refusals.get(reason, 0) + 1
        return reason

    def can_join(group: _Group, cur: _Line) -> str | None:
        last = group.last
        if cur.protected or any(ln.protected for ln in group.lines):
            return refuse("protected_line")
        if cur.band != last.band:
            return refuse("header_footer_band")
        if len(cur.cells) > 1 or len(last.cells) > 1 or cur.cells != last.cells:
            return refuse("table_cell_boundary")
        if cur.conf < 0.5 or last.conf < 0.5 or cur.letters < 2 or last.letters < 2:
            return refuse("low_confidence_or_noise")
        if cur.script != last.script:
            return refuse("script_change")
        # OCR line boxes vary with ascenders/descenders (measured 0.57-1.39x
        # the page median inside one clause): the reference is clamped to the
        # page body height so one short line does not change the thresholds.
        href = min(max(_median(group.heights() + [cur.h], body_h), 0.75 * body_h), 1.4 * body_h)
        gap = cur.box[1] - last.box[3]
        if cur.box[1] < last.box[1] + 0.35 * href:
            return refuse("same_row")
        if gap > 0.75 * href or cur.box[1] - last.box[1] > 2.1 * href:
            return refuse("vertical_gap")
        ratio = cur.h / max(
            min(max(_median(group.heights(), cur.h), 0.75 * body_h), 1.4 * body_h), 0.1
        )
        if ratio > 1.75 or ratio < 0.57:
            return refuse("font_size_change")
        overlap = min(cur.box[2], last.box[2]) - max(cur.box[0], last.box[0])
        if overlap < 0.25 * min(cur.box[2] - cur.box[0], last.box[2] - last.box[0]):
            return refuse("no_horizontal_overlap")
        reference_x0 = (
            min(ln.box[0] for ln in group.lines[1:]) if len(group.lines) > 1 else group.first.box[0]
        )
        tolerance = max(1.6 * href, 10.0)
        aligned = abs(cur.box[0] - reference_x0) <= tolerance
        hanging = (
            group.first.bullet and group.first.box[0] <= cur.box[0] <= group.first.box[0] + 4 * href
        )
        centered = (
            abs((cur.box[0] + cur.box[2]) / 2 - (last.box[0] + last.box[2]) / 2)
            <= max(2 * href, 0.04 * width)
            and max(cur.box[2] - cur.box[0], last.box[2] - last.box[0]) < 0.85 * body_width
        )
        if not (aligned or hanging or centered):
            return refuse("left_alignment_change")
        if cur.bullet:
            return refuse("new_list_item")
        if last.heading != cur.heading:
            return refuse("heading_boundary")
        if last.field or cur.field:
            return refuse("form_field")
        if _COLON_END.search(last.text):
            return refuse("colon_introduces_next")
        short_last = last.box[2] < body_right - max(3 * href, 0.12 * body_width)
        if _TERMINAL.search(last.text) and short_last:
            return refuse("paragraph_end")
        if (
            short_last
            and aligned
            and not centered
            and not (last.heading and cur.heading)
            and not _CONTINUATION_END.search(last.text)
            and not _CONTINUATION_START.match(cur.text)
        ):
            # A short left-aligned line followed by a capitalised line is a
            # deliberate line break (signature block, address, name/title).
            return refuse("short_line_break")
        if len(group.lines) >= 2:
            group_right = max(ln.box[2] for ln in group.lines)
            if last.box[2] < group_right - max(4 * href, 0.2 * (group_right - reference_x0)):
                return refuse("short_line_ends_paragraph")
        if len(group.lines) >= 30:
            return refuse("max_lines")
        union = _union([group.box(), cur.box])
        members = {id(ln) for ln in group.lines} | {id(cur)}
        for other in lines:
            if id(other) in members:
                continue
            small_noise = (other.letters < 2 or other.conf < 0.5) and (
                other.box[2] - other.box[0] <= 2.5 * body_h and other.h <= 2.5 * body_h
            )
            if small_noise:
                continue
            hit = _inter(union, other.box)
            if hit > 0.15 * _area(other.box):
                return refuse("obstacle_line_inside_union")
        for rbox in region_boxes:
            if rbox and _inter(union, rbox) > 0:
                return refuse("protected_region_inside_union")
        return None

    ordered = sorted(lines, key=lambda ln: (ln.box[1], ln.box[0]))
    groups: list[_Group] = []
    open_groups: list[_Group] = []
    decisions: list[dict[str, Any]] = []
    for cur in ordered:
        open_groups = [g for g in open_groups if g.last.box[3] >= cur.box[1] - 3 * body_h]
        best: _Group | None = None
        best_gap = None
        nearest_reason = None
        nearest_gap = None
        for group in open_groups:
            reason = can_join(group, cur)
            gap = cur.box[1] - group.last.box[3]
            if reason is None:
                if best_gap is None or gap < best_gap:
                    best, best_gap = group, gap
            elif debug and (nearest_gap is None or abs(gap) < nearest_gap):
                overlap = min(cur.box[2], group.last.box[2]) - max(cur.box[0], group.last.box[0])
                if overlap > 0:
                    nearest_gap, nearest_reason = (
                        abs(gap),
                        (str(group.last.block.get("id")), reason),
                    )
        if debug:
            decisions.append(
                {
                    "line_id": str(cur.block.get("id")),
                    "joined": best is not None,
                    "nearest_refusal": None if best is not None else nearest_reason,
                }
            )
        if best is not None:
            best.lines.append(cur)
            continue
        group = _Group(cur)
        groups.append(group)
        open_groups.append(group)

    # Bold evidence: absolute stroke width relative to the WIDTH-based font
    # size (box heights are too noisy to normalise a stroke width).
    for ln in lines:
        ev = ln.block.get("style_evidence")
        size_w = width_font_size(ln.text, ln.box[2] - ln.box[0])
        size_b = width_font_size(ln.text, ln.box[2] - ln.box[0], bold=True)
        if isinstance(ev, dict) and ev.get("stroke_pt") and size_w:
            ev["relative_stroke"] = round(float(ev["stroke_pt"]) / size_w, 5)
            # Bold glyphs are ~13 % wider: under the bold hypothesis the size
            # must be estimated with the bold face, or bold is under-measured.
            if size_b:
                ev["relative_stroke_bold"] = round(float(ev["stroke_pt"]) / size_b, 5)
    page_strokes = [
        float(ev["relative_stroke"])
        for ln in reference
        if isinstance(ev := ln.block.get("style_evidence"), dict) and ev.get("relative_stroke")
    ]
    stroke_key = "relative_stroke"
    if len(page_strokes) < 3:
        stroke_key = "stroke_ratio"
        page_strokes = [
            float(ev["stroke_ratio"])
            for ln in reference
            if isinstance(ev := ln.block.get("style_evidence"), dict) and ev.get("stroke_ratio")
        ]
    stroke_median = _median(page_strokes, 0.0)

    out: list[dict[str, Any]] = []
    for group in groups:
        out.append(
            _group_block(
                group,
                number=number,
                width=width,
                body_left=body_left,
                body_right=body_right,
                body_width=body_width,
                body_h=body_h,
                stroke_median=stroke_median,
                stroke_key=stroke_key,
                regions=regions,
                cells_bbox=_cells_bbox(tables or [], number),
                detect_language=detect_language,
            )
        )
    out.extend(passthrough)
    out.sort(key=lambda b: (int(b.get("reading_order", 0)), str(b.get("id"))))
    out.sort(
        key=lambda b: (
            round(float((_box(b.get("bbox")) or [0, 0])[1]), 1),
            float((_box(b.get("bbox")) or [0])[0]),
        )
    )
    for order, block in enumerate(out):
        block["reading_order"] = order
    trace["output_blocks"] = len(out)
    trace["merged_groups"] = sum(len(g.lines) > 1 for g in groups)
    trace["merged_lines"] = sum(len(g.lines) for g in groups if len(g.lines) > 1)
    trace["refusals"] = dict(sorted(refusals.items()))
    trace["body_line_height"] = round(body_h, 3)
    if debug:
        trace["decisions"] = decisions
    return out, trace


def _cells_bbox(tables: list[dict[str, Any]], page_number: int) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for table in tables or []:
        if int(table.get("page", page_number) or page_number) != page_number:
            continue
        for cell in table.get("cells", []) or []:
            box = _box(cell.get("bbox"))
            if box:
                key = str(
                    cell.get("id") or f"{table.get('id')}:{cell.get('row')}:{cell.get('col')}"
                )
                result[key] = box
    return result


def _group_block(
    group: _Group,
    *,
    number: int,
    width: float,
    body_left: float,
    body_right: float,
    body_width: float,
    body_h: float,
    stroke_median: float,
    regions: list[dict[str, Any]],
    stroke_key: str = "stroke_ratio",
    cells_bbox: dict[str, list[float]],
    detect_language: Callable[[str], str] | None,
) -> dict[str, Any]:
    lines = group.lines
    first = lines[0].block
    texts = [ln.text for ln in lines]
    text = join_line_texts(texts)
    box = _union(ln.box for ln in lines)
    chars = [max(1, len(t)) for t in texts]
    confidence = sum(ln.conf * c for ln, c in zip(lines, chars, strict=True)) / sum(chars)
    heights = [round(ln.h, 3) for ln in lines]
    pitches = [lines[i + 1].box[1] - lines[i].box[1] for i in range(len(lines) - 1)]

    cell_id = lines[0].cells[0] if lines[0].cells else None
    frame = cells_bbox.get(cell_id) if cell_id else None
    left, right = (frame[0], frame[2]) if frame else (body_left, body_right)
    span = max(right - left, 1.0)
    align = "left"
    centers = [((ln.box[0] + ln.box[2]) / 2) for ln in lines]
    middle = (left + right) / 2
    if all(abs(c - middle) <= max(0.03 * width, 1.5 * body_h) for c in centers) and all(
        (ln.box[0] - left) > 2.5 * body_h for ln in lines
    ):
        align = "center"
    elif all(abs(ln.box[2] - right) <= 1.8 * body_h for ln in lines) and all(
        ln.box[0] > left + 0.25 * span for ln in lines
    ):
        align = "right"
    elif len(lines) >= 3 and all(
        ln.box[2] >= right - 1.5 * body_h and (ln.box[2] - ln.box[0]) >= 0.85 * span
        for ln in lines[:-1]
    ):
        align = "justify"

    evidence = [ev for ln in lines if isinstance(ev := ln.block.get("style_evidence"), dict)]
    style: dict[str, Any] = {"align": align, "evidence_lines": len(evidence)}
    if evidence:
        values = [float(ev[stroke_key]) for ev in evidence if ev.get(stroke_key)]
        stroke = _median(values, 0.0)
        bold_key = "relative_stroke_bold" if stroke_key == "relative_stroke" else stroke_key
        bold_values = [float(ev[bold_key]) for ev in evidence if ev.get(bold_key)]
        bold_stroke = _median(bold_values, stroke)
        ink = [
            round(
                _median([float(ev["ink_rgb"][k]) for ev in evidence if ev.get("ink_rgb")], 0.0), 4
            )
            for k in range(3)
        ]
        paper = [
            round(
                _median([float(ev["paper_rgb"][k]) for ev in evidence if ev.get("paper_rgb")], 1.0),
                4,
            )
            for k in range(3)
        ]
        style["stroke_ratio"] = round(stroke, 5)
        style["bold_stroke_ratio"] = (
            round(bold_stroke / stroke_median, 3) if stroke_median else None
        )
        style["bold"] = bool(stroke_median and bold_stroke >= 1.3 * stroke_median)
        style["color"] = ink if _chroma(ink) >= 0.18 else None
        style["background"] = paper
        style["highlight"] = bool(_chroma(paper) >= 0.12 and min(paper) < 0.92)
    else:
        style.update({"bold": None, "color": None, "background": None, "highlight": None})

    role = "line"
    if lines[0].band in {"header", "footer"}:
        role = lines[0].band
    elif cell_id:
        role = "table_cell"
    elif all(ln.heading for ln in lines):
        role = "heading"
    elif lines[0].bullet:
        role = "list_item"
    elif any(ln.field for ln in lines):
        role = "field"
    elif len(lines) >= 2:
        role = "paragraph"
    signature_like = {"signature", "stamp", "stamp_or_logo_candidate", "signature_candidate"}
    for region in regions:
        rbox = _box(region.get("bbox"))
        kind = str(region.get("type") or region.get("subtype") or "")
        if rbox and kind in signature_like and len(text.split()) <= 8:
            near = rbox[1] - 1.5 * body_h <= box[3] and box[1] <= rbox[3] + 1.5 * body_h
            overlap = min(rbox[2], box[2]) - max(rbox[0], box[0]) > 0
            if near and overlap:
                role = "signature_zone"
                break

    source_lines = [
        {
            "id": str(ln.block.get("id")),
            "text": ln.text,
            "bbox": [round(v, 3) for v in ln.box],
            "confidence": ln.conf,
            "provenance": ln.block.get("provenance"),
            "reading_order": ln.block.get("reading_order"),
            **(
                {"style_evidence": ln.block["style_evidence"]}
                if isinstance(ln.block.get("style_evidence"), dict)
                else {}
            ),
        }
        for ln in lines
    ]
    block = {
        **{k: v for k, v in first.items() if k not in {"style_evidence"}},
        "id": str(first.get("id")),
        "page": number,
        "text": text,
        "bbox": [round(v, 3) for v in box],
        "confidence": round(confidence, 4),
        "min_line_confidence": round(min(ln.conf for ln in lines), 4),
        "role": role,
        "line_count": len(lines),
        "line_heights": heights,
        "line_pitch": round(_median(pitches, 0.0), 3) if pitches else None,
        "source_lines": source_lines,
        "style": style,
        "protected": any(ln.protected for ln in lines),
        "ocr_unreliable": is_unreliable_ocr(text, confidence),
        "segmentation": {
            "version": VERSION,
            "merged": len(lines) > 1,
            "member_ids": [line["id"] for line in source_lines],
        },
    }
    if cell_id:
        block["table_cell_id"] = cell_id
    for key in ("near_protected_regions", "protected_by"):
        merged: list[str] = []
        for ln in lines:
            for item in ln.block.get(key) or []:
                if str(item) not in merged:
                    merged.append(str(item))
        if merged:
            block[key] = merged
        else:
            block.pop(key, None)
    if len(lines) > 1 and detect_language is not None:
        try:
            block["language"] = detect_language(text)
        except Exception:
            pass
    return block


_CONTINUATION_END = re.compile(
    r"([,\-\u2010\u2011\u2013/&(]|\b(and|or|of|the|to|for|in|with|at|by|de|du|des|la|le|les|et|ou|à|en|au|aux|pour|par|sur|con|del|y|e|per|di|und|der|die|das|van|het)|\b[a-zà-ÿ]{1,2})\s*$",
    re.IGNORECASE,
)
_CONTINUATION_START = re.compile(r"\s*[a-zà-ÿ0-9(\[«\"']")

_ID_KEYS = {"block_ids", "ambiguous_block_ids", "overlapping_block_ids", "block_id"}


def remap_block_ids(value: Any, mapping: dict[str, str]) -> Any:
    """Replace merged line ids by their group id in tables/layout references."""
    if isinstance(value, dict):
        for key, nested in list(value.items()):
            if key in _ID_KEYS:
                if isinstance(nested, list):
                    seen: list[str] = []
                    for item in nested:
                        new = mapping.get(str(item), str(item))
                        if new not in seen:
                            seen.append(new)
                    value[key] = seen
                elif isinstance(nested, str):
                    value[key] = mapping.get(nested, nested)
            elif key not in {"blocks", "source_lines"}:
                remap_block_ids(nested, mapping)
    elif isinstance(value, list):
        for nested in value:
            remap_block_ids(nested, mapping)
    return value


def segment_ir(
    ir: dict[str, Any], *, detect_language: Callable[[str], str] | None = None
) -> dict[str, Any]:
    """Segment every scanned page of an IR in place and record the trace."""
    traces = []
    mapping: dict[str, str] = {}
    for page in ir.get("pages", []) or []:
        if not page.get("scanned"):
            continue
        number = int(page.get("number", 1))
        page_tables = [
            t for t in ir.get("tables", []) or [] if int(t.get("page", number) or number) == number
        ]
        blocks, trace = segment_page(
            page,
            page_tables,
            ir.get("protected_visual_regions") or [],
            detect_language=detect_language,
        )
        for block in blocks:
            for line in block.get("source_lines", []) or []:
                if line["id"] != block["id"]:
                    mapping[line["id"]] = block["id"]
        page["blocks"] = blocks
        traces.append(trace)
    if mapping:
        remap_block_ids(ir.get("tables", []), mapping)
        for page in ir.get("pages", []) or []:
            remap_block_ids(page.get("layout"), mapping)
    ir["segmentation"] = {
        "version": VERSION,
        "pages": traces,
        "input_lines": sum(t["input_lines"] for t in traces),
        "output_blocks": sum(t["output_blocks"] for t in traces),
        "merged_groups": sum(t["merged_groups"] for t in traces),
        "merged_lines": sum(t.get("merged_lines", 0) for t in traces),
    }
    ir.setdefault("versions", {})["segmentation"] = VERSION
    return ir
