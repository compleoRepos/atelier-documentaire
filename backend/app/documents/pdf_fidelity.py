"""Evidence-first PDF rendering with table-aware, non-destructive replacement.

This module is intentionally standalone: it does not alter the legacy pipeline or
promote graphical table candidates to semantic truth.  Tables are re-detected from
the PDF whose structure is being inspected, and candidate structure is always
marked as unvalidated.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import fitz

from .layout import detect_layout

_FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_RTL = re.compile(r"[\u0590-\u08ff]")


def _rect(value: Any) -> list[float] | None:
    try:
        values = list(value)
        if len(values) < 4:
            return None
        x0, y0, x1, y1 = (float(item) for item in values[:4])
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        return None
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def _area(box: list[float] | None) -> float:
    return max(0.0, (box or [0, 0, 0, 0])[2] - (box or [0, 0, 0, 0])[0]) * max(
        0.0, (box or [0, 0, 0, 0])[3] - (box or [0, 0, 0, 0])[1]
    )


def _intersection(a: list[float] | None, b: list[float] | None) -> list[float] | None:
    if not a or not b:
        return None
    hit = [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]
    return hit if hit[2] > hit[0] and hit[3] > hit[1] else None


def _contains(outer: list[float], inner: list[float], tolerance: float = 1.0) -> bool:
    return (
        inner[0] >= outer[0] - tolerance
        and inner[1] >= outer[1] - tolerance
        and inner[2] <= outer[2] + tolerance
        and inner[3] <= outer[3] + tolerance
    )


def _rgb(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        values = list(value)
    except TypeError:
        return None
    if len(values) < 3:
        return None
    try:
        return [round(max(0.0, min(1.0, float(v))), 4) for v in values[:3]]
    except (TypeError, ValueError):
        return None


def _pdf_color(value: Any) -> list[float] | None:
    """Convert either a PDF integer color or an RGB sequence to normalized RGB."""
    if isinstance(value, int):
        return [round(channel / 255.0, 4) for channel in fitz.sRGB_to_rgb(value)]
    return _rgb(value)


def _warn(code: str, message: str, severity: str = "warning", **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "severity": severity, "message": message}
    value.update(extra)
    return value


def _blocks_from_page(page: Any, page_number: int) -> list[dict[str, Any]]:
    """Extract real candidate-page line blocks, including span style evidence."""
    output: list[dict[str, Any]] = []
    try:
        raw_blocks = page.get_text("dict").get("blocks", [])
    except Exception:
        raw_blocks = []
    order = 0
    for raw in raw_blocks:
        if raw.get("type") != 0:
            continue
        for line in raw.get("lines", []):
            spans = [span for span in line.get("spans", []) if span.get("text", "").strip()]
            text = "".join(span.get("text", "") for span in spans).strip()
            box = _rect(line.get("bbox", raw.get("bbox")))
            if not text or not box:
                continue
            first = spans[0] if spans else {}
            output.append(
                {
                    "id": f"candidate-p{page_number:03d}-b{order:04d}",
                    "page": page_number,
                    "text": text,
                    "bbox": box,
                    "font_size": float(first.get("size", 0) or 0) or None,
                    "font_name": first.get("font", ""),
                    "color": _pdf_color(first.get("color")),
                    "flags": int(first.get("flags", 0) or 0),
                    "reading_order": order,
                    "provenance": "candidate_pdf_text",
                }
            )
            order += 1
    return output


def _drawing_records(page: Any) -> list[dict[str, Any]]:
    from .cover_layer import source_drawings

    drawings = source_drawings(page)
    records: list[dict[str, Any]] = []
    for drawing in drawings:
        items = drawing.get("items", [])
        boxes: list[list[float]] = []
        for item in items:
            if not item:
                continue
            if item[0] == "re" and len(item) > 1:
                box = _rect(item[1])
                if box:
                    boxes.append(box)
            elif item[0] == "l" and len(item) > 2:
                try:
                    p0, p1 = item[1], item[2]
                    box = [min(p0.x, p1.x), min(p0.y, p1.y), max(p0.x, p1.x), max(p0.y, p1.y)]
                except (AttributeError, TypeError):
                    box = None
                if box:
                    boxes.append(box)
        if not boxes:
            box = _rect(drawing.get("rect"))
            if box:
                boxes.append(box)
        if boxes:
            union = [
                min(box[0] for box in boxes),
                min(box[1] for box in boxes),
                max(box[2] for box in boxes),
                max(box[3] for box in boxes),
            ]
            records.append(
                {
                    "bbox": union,
                    "boxes": boxes,
                    "fill": _rgb(drawing.get("fill")),
                    "color": _rgb(drawing.get("color")),
                    "width": float(drawing.get("width", 0) or 0),
                    "opacity": float(drawing.get("opacity", 1) or 1),
                    "fill_opacity": float(drawing.get("fill_opacity", 1) or 1),
                    "closePath": bool(drawing.get("closePath", False)),
                }
            )
    return records


def _border_evidence(cell, records):
    sides = {name: None for name in ("top", "right", "bottom", "left")}
    for record in records:
        for box in record.get("boxes", []):
            x0, y0, x1, y1 = box
            for side, coord, axis, first, last in (
                ("top", cell[1], "h", cell[0], cell[2]),
                ("bottom", cell[3], "h", cell[0], cell[2]),
                ("left", cell[0], "v", cell[1], cell[3]),
                ("right", cell[2], "v", cell[1], cell[3]),
            ):
                edges = [y0, y1] if axis == "h" else [x0, x1]
                start, stop = (x0, x1) if axis == "h" else (y0, y1)
                overlap = max(0.0, min(stop, last) - max(start, first))
                if min(abs(c - coord) for c in edges) <= 2.5 and overlap >= 0.9 * (last - first):
                    sides[side] = {
                        "color": record.get("color"),
                        "width": record.get("width", 0),
                        "opacity": record.get("opacity", 1),
                    }
    return sides


def _drawing_fill(cell: list[float], records: list[dict[str, Any]]) -> list[float] | None:
    best: tuple[float, list[float] | None] = (0.0, None)
    for record in records:
        fill = record.get("fill")
        if fill is None:
            continue
        hit = _intersection(cell, record["bbox"])
        if hit and _area(hit) / max(1.0, _area(cell)) > best[0]:
            best = (_area(hit) / max(1.0, _area(cell)), fill)
    return best[1]


def _infer_style(
    cell: dict[str, Any], blocks: list[dict[str, Any]], records: list[dict[str, Any]]
) -> None:
    box = _rect(cell.get("bbox"))
    if not box:
        return
    linked = [block for block in blocks if str(block.get("id")) in set(cell.get("block_ids", []))]
    if not linked:
        linked = [
            block for block in blocks if _contains(box, _rect(block.get("bbox")) or [0, 0, 0, 0])
        ]
    # Glyph extent is not a cell's right/bottom padding. Reuse observed
    # inset on the aligned side; spare width/height remains available to text.
    if linked:
        left = max(1.0, min(24.0, min(_rect(b["bbox"])[0] - box[0] for b in linked)))
        right = max(1.0, min(24.0, min(box[2] - _rect(b["bbox"])[2] for b in linked)))
        top = max(1.0, min(12.0, min(_rect(b["bbox"])[1] - box[1] for b in linked)))
        centers = [(_rect(b["bbox"])[0] + _rect(b["bbox"])[2]) / 2 for b in linked]
        center_delta = abs(sum(centers) / len(centers) - (box[0] + box[2]) / 2)
        align = "center" if center_delta <= 2 else ("left" if left <= right else "right")
        inset = min(left, right)
        padding = [inset, top, inset, min(top, 3.0)]
    else:
        padding, align = [4.0, 3.0, 4.0, 3.0], "left"
    sample = linked[0] if linked else {}
    # Independently obtain style from the real PDF spans, then keep IR ids.
    sample_box = _rect(sample.get("bbox"))
    if sample_box:
        real = [
            b
            for b in cell.get("_page_native_blocks", [])
            if _intersection(sample_box, _rect(b.get("bbox")))
        ]
        if real:
            sample = {**sample, **real[0]}
    style = {
        "fill": _drawing_fill(box, records),
        "border": _border_evidence(box, records),
        "padding": padding,
        "align": align,
        "font_size": sample.get("font_size"),
        "font_name": sample.get("font_name"),
        "color": sample.get("color"),
        "bold": bool(int(sample.get("flags", 0) or 0) & 16),
        "italic": bool(int(sample.get("flags", 0) or 0) & 2),
        "provenance": "candidate_style_inferred_from_drawings_and_text",
    }
    cell["padding"] = padding
    cell["align"] = align
    cell["fill"] = style["fill"]
    cell["border"] = style["border"]
    cell["style"] = style
    cell["row_span"] = int(cell.get("row_span", 1) or 1)
    cell["column_span"] = int(cell.get("column_span", 1) or 1)


def enrich_tables(
    page: Any, tables: list[dict[str, Any]], blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Enrich table candidates in place using page drawings and candidate text.

    No semantic value is inferred.  In particular, ``fill``, ``border``,
    ``padding`` and ``align`` are explicitly labelled candidate evidence.
    """
    records = _drawing_records(page)
    native_blocks = _blocks_from_page(page, page.number + 1)
    page_blocks = [
        block
        for block in blocks
        if int(block.get("page", 1)) == int(getattr(page, "number", 0) + 1)
    ]
    for table in tables:
        cells = table.setdefault("cells", [])
        for cell in cells:
            cell_box = _rect(cell.get("bbox"))
            if not cell_box:
                continue
            matched: list[dict[str, Any]] = []
            for block in page_blocks:
                block_box = _rect(block.get("bbox"))
                if not block_box:
                    continue
                if _contains(cell_box, block_box, 1.0) or (
                    _intersection(cell_box, block_box)
                    and _area(_intersection(cell_box, block_box)) / max(1.0, _area(block_box))
                    >= 0.5
                ):
                    matched.append(block)
            cell["block_ids"] = sorted(
                {str(block["id"]) for block in matched} | set(cell.get("block_ids", []))
            )
            cell["_page_native_blocks"] = native_blocks
            _infer_style(cell, page_blocks, records)
            cell.pop("_page_native_blocks", None)
        # A rectangular envelope around an L-shaped merge overlaps another
        # physical cell. Such candidates must never delete neighbouring content.
        overlapping_cells = [
            cell
            for cell in cells
            if any(
                other is not cell
                and _intersection(_rect(cell.get("bbox")), _rect(other.get("bbox")))
                for other in cells
            )
        ]
        if overlapping_cells:
            table["ambiguous_block_ids"] = sorted(
                {str(bid) for cell in overlapping_cells for bid in cell.get("block_ids", [])}
            )
            table.setdefault("human_uncertainty", []).append(
                "NON_RECTANGULAR_CELL_GEOMETRY_REQUIRES_REVIEW"
            )
        # A block spanning cells is an ambiguous/L-shaped link and must be reviewed.
        ambiguous: list[str] = []
        for block in page_blocks:
            block_box = _rect(block.get("bbox"))
            hits = [
                cell
                for cell in cells
                if block_box and _intersection(block_box, _rect(cell.get("bbox")))
            ]
            if len(hits) > 1:
                ratios = [
                    _area(_intersection(block_box, _rect(cell.get("bbox"))))
                    / max(1.0, _area(block_box))
                    for cell in hits
                ]
                if sum(ratio > 0.08 for ratio in ratios) > 1:
                    ambiguous.append(str(block.get("id")))
        if ambiguous:
            table["ambiguous_block_ids"] = sorted(
                set(ambiguous) | set(table.get("ambiguous_block_ids", []))
            )
            table.setdefault("human_uncertainty", []).append(
                "AMBIGUOUS_MULTI_CELL_LINK_REQUIRES_REVIEW"
            )
        table["style_provenance"] = "candidate_unvalidated"
    return tables


def _detect_tables(
    page: Any, page_number: int, blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    try:
        result = detect_layout(
            page=page,
            blocks=blocks,
            page_number=page_number,
            width=float(page.rect.width),
            height=float(page.rect.height),
        )
        tables = result.get("tables", [])
    except Exception:
        tables = []
    return enrich_tables(page, tables, blocks)


def _table_records(doc: Any) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for index, page in enumerate(doc):
        blocks = _blocks_from_page(page, index + 1)
        for table in _detect_tables(page, index + 1, blocks):
            # IDs are page-local detector evidence, not copied from an IR.
            table["source"] = "candidate_pdf_text_and_drawings"
            tables.append(table)
    return tables


def _normalize_structure(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for table in tables:
        normalized.append(
            {
                "id": table.get("id"),
                "page": table.get("page"),
                "bbox": list(table.get("bbox", [])),
                "rows": table.get("rows"),
                "columns": table.get("columns"),
                "cell_count": len(table.get("cells", [])),
                "cells": [
                    {
                        "id": cell.get("id"),
                        "bbox": list(cell.get("bbox", [])),
                        "row": cell.get("row"),
                        "column": cell.get("column"),
                        "row_span": cell.get("row_span", 1),
                        "column_span": cell.get("column_span", 1),
                        "block_ids": list(cell.get("block_ids", [])),
                        "fill": cell.get("fill"),
                        "border": cell.get("border"),
                        "padding": cell.get("padding"),
                        "align": cell.get("align"),
                    }
                    for cell in table.get("cells", [])
                ],
                "merges": list(table.get("merges", [])),
                "provenance": "candidate_pdf_unvalidated",
                "human_uncertainty": list(table.get("human_uncertainty", [])),
            }
        )
    return normalized


def _intersects(a: list[float] | None, b: list[float] | None) -> bool:
    return _intersection(a, b) is not None


def _protected(block: dict[str, Any], protected_regions: list[dict[str, Any]]) -> bool:
    return bool(block.get("protected")) or any(
        int(region.get("page", 0)) == int(block.get("page", 0))
        and _intersects(_rect(block.get("bbox")), _rect(region.get("bbox")))
        for region in protected_regions
    )


def _protected_box(
    page_number: int, box: list[float], protected_regions: list[dict[str, Any]]
) -> bool:
    return any(
        int(region.get("page", 0)) == int(page_number)
        and _intersects(box, _rect(region.get("bbox")))
        for region in protected_regions
    )


def _target_text(
    blocks: list[dict[str, Any]], translations: dict[str, str]
) -> tuple[str, str, bool]:
    ordered = sorted(blocks, key=lambda block: int(block.get("reading_order", 0)))
    source = "\n".join(str(block.get("text", "")) for block in ordered).strip()
    target = "\n".join(
        str(translations.get(str(block["id"]), block.get("text", ""))) for block in ordered
    ).strip()
    changed = any(
        str(translations.get(str(block["id"]), block.get("text", ""))) != str(block.get("text", ""))
        for block in ordered
    )
    return source, target, changed


def _font_kwargs(size: float, style: dict[str, Any], align: int) -> dict[str, Any]:
    variant = "DejaVuSans"
    if style.get("bold") and style.get("italic"):
        variant += "-BoldOblique"
    elif style.get("bold"):
        variant += "-Bold"
    elif style.get("italic"):
        variant += "-Oblique"
    font = Path(_FONT_FILE).with_name(variant + ".ttf")
    return {
        "fontsize": size,
        "fontname": variant,
        "fontfile": str(font) if font.is_file() else None,
        "align": align,
        "overlay": True,
        "color": style.get("color") or [0, 0, 0],
    }


_FONT_CACHE: dict[str, Any] = {}


def _longest_word_fits(text: str, width: float, size: float, kwargs: dict[str, Any]) -> bool:
    """True when every word fits on one line of ``width`` at ``size``.
    insert_textbox breaks a word that is wider than the frame mid-word
    (run18 audit: a translated label rendered as two fragments in a narrow
    table cell); such a fit is refused so a wider frame or a smaller font is
    tried, and otherwise the block is reported as an overflow."""
    words = [w for w in re.split(r"\s+", text) if w]
    if not words:
        return True
    key = str(kwargs.get("fontfile") or kwargs.get("fontname") or "helv")
    font = _FONT_CACHE.get(key)
    if font is None:
        try:
            font = (
                fitz.Font(fontfile=kwargs["fontfile"])
                if kwargs.get("fontfile")
                else fitz.Font("helv")
            )
        except Exception:
            font = fitz.Font("helv")
        _FONT_CACHE[key] = font
    usable = width - 2.0  # insert_textbox keeps a small inner margin
    return max(font.text_length(word, fontsize=size) for word in words) <= usable


def _fit_on_scratch(
    source_bytes: bytes,
    page_number: int,
    rect: fitz.Rect,
    text: str,
    size: float,
    style: dict[str, Any],
    align: int,
    min_ratio: float | None = None,
) -> tuple[bool, float, float]:
    scratch = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        result = -1.0
        current = size
        if min_ratio:
            # Scan path: never shrink below ``min_ratio`` of the measured size
            # (a smaller font is a fidelity defect, reported for review).
            minimum, step, tries = max(4.0, size * min_ratio), 0.95, 16
        else:
            minimum, step, tries = max(4.0, min(size, rect.height * 0.32)), 0.86, 8
        for _ in range(tries):
            kwargs = _font_kwargs(current, style, align)
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            result = scratch[page_number - 1].insert_textbox(rect, text, **kwargs)
            if result >= 0 and _longest_word_fits(text, rect.width, current, kwargs):
                return True, result, current
            if result >= 0:
                result = -1.0  # a word would be cut mid-word (run18, DOC-004)
            if current * step < minimum - 1e-6:
                break
            current *= step
        return False, result, current
    finally:
        scratch.close()


def _widget_boxes(page: Any) -> list[list[float]]:
    try:
        widgets = page.widgets()
        return [_rect(widget.rect) for widget in widgets or [] if _rect(widget.rect)]
    except Exception:
        return []


def _graphic_conflict(page: Any, rect: list[float]) -> bool:
    """Protect widgets and large/opaque graphics; table border lines are not blocked."""
    if any(_intersects(rect, box) for box in _widget_boxes(page)):
        return True
    for record in _drawing_records(page):
        hit = _intersection(rect, record["bbox"])
        if not hit:
            continue
        graphic_box = record["bbox"]
        # A rectangle that is the cell itself (or a thin border/filled cell
        # contained by it) is the table evidence we deliberately preserve, not
        # a watermark to protect from replacement.
        if (
            graphic_box[0] >= rect[0] - 3
            and graphic_box[1] >= rect[1] - 3
            and graphic_box[2] <= rect[2] + 3
            and graphic_box[3] <= rect[3] + 3
        ):
            continue
        ratio = _area(hit) / max(1.0, _area(rect))
        # Large, filled/transparent-overlaid graphics are likely watermark/form art.
        if ratio > 0.35 and (record.get("fill") is not None or record.get("opacity", 1) < 0.95):
            return True
    return False


# --- Scanned pages -----------------------------------------------------------
# On a scan the source text is raster ink. The source box is covered with the
# measured paper colour (the image stream itself is never re-encoded, so pixels
# outside the box stay bit-identical) and the translation is written on top.


def _strict_overlap(a: list[float], b: list[float], eps: float = 0.01) -> bool:
    return a[0] < b[2] - eps and b[0] < a[2] - eps and a[1] < b[3] - eps and b[1] < a[3] - eps


def _paper_color(page: Any, box: list[float]) -> list[float]:
    """Median colour of the lightest pixels just around ``box`` on the original."""
    try:
        clip = (fitz.Rect(*box) + (-2, -2, 2, 2)) & page.rect
        pix = page.get_pixmap(clip=clip, alpha=False, colorspace=fitz.csRGB)
    except Exception:
        return [1.0, 1.0, 1.0]
    width, height, stride, samples = pix.width, pix.height, pix.stride, pix.samples
    if width < 2 or height < 2:
        return [1.0, 1.0, 1.0]
    border = []
    for x in range(width):
        for y in (0, height - 1):
            i = y * stride + x * 3
            border.append(tuple(samples[i : i + 3]))
    for y in range(height):
        for x in (0, width - 1):
            i = y * stride + x * 3
            border.append(tuple(samples[i : i + 3]))
    border.sort(key=sum)
    light = border[len(border) // 2 :]
    return [sorted(c[k] for c in light)[len(light) // 2] / 255.0 for k in range(3)]


SCAN_TRUSTED_SIZE_CONFIDENCE = 0.8


def _band_is_blank(page: Any, rect: list[float], max_dark_share: float = 0.004) -> bool:
    """True when ``rect`` holds no ink on the page as rendered now (original
    raster plus anything already drawn): rules, labels, stamps or text."""
    try:
        clip = fitz.Rect(*rect) & page.rect
        if clip.is_empty or clip.width < 1 or clip.height < 1:
            return False
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, colorspace=fitz.csGRAY)
    except Exception:
        return False
    samples = pix.samples
    if not samples:
        return False
    dark = sum(1 for value in samples if value < 140)
    return dark / len(samples) <= max_dark_share


# A translation is never drawn over original ink that no mask hides (residual
# source under the new text). Thresholds at 2x: a few glyphs of a 6-7 pt line.
_SOURCE_INK_DARK = 140

# Frame growth outside the source box (vertical or to the right) must stay in
# space proven blank on the original raster: no rule, label, graphic or text
# that OCR did not box. Rows/columns this inky stop the growth.
_INK_ZOOM = 2.0
_GROWTH_ROW_SHARE = 0.02
_GROWTH_COL_SHARE = 0.05
_GROWTH_GAP = 0.6
_GROWTH_MAX_SHARE = 0.004
_GROWTH_MIN_PIXELS = 6


def _page_dark(page: Any) -> Any:
    """Dark-pixel mask of the page as rendered now, at _INK_ZOOM (cached on the
    page object: planning happens before any drawing)."""
    import numpy as np

    cached = getattr(page, "_atelier_dark_mask", None)
    if cached is not None:
        return cached
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(_INK_ZOOM, _INK_ZOOM), colorspace=fitz.csGRAY)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, -1)[:, : pix.width]
        dark = arr < _SOURCE_INK_DARK
    except Exception:
        return None
    try:
        page._atelier_dark_mask = dark
    except Exception:
        pass
    return dark


def _px(page: Any, value: float, axis: int) -> int:
    origin = page.rect.x0 if axis == 0 else page.rect.y0
    return int(round((value - origin) * _INK_ZOOM))


def _walk(
    shares: Any, start: int, step: int, stop: int, absorb: int, threshold: float
) -> tuple[int, int | None]:
    """Walk outward from a box edge over row/column dark shares. Ink contiguous
    with the box (its own glyphs past the OCR box) is absorbed up to ``absorb``
    pixels, except rules (>= _RULE_RUN_SHARE), which are obstacles at once.
    Returns (absorbed edge index, first obstacle index or None)."""
    edge, index, absorbing = start - step, start, True
    while (index < stop) if step > 0 else (index > stop):
        share = float(shares[index])
        if share >= _RULE_RUN_SHARE:
            return edge, index
        inky = share > threshold
        if absorbing:
            if inky and abs(index - start) < absorb:
                edge = index
            elif inky:
                return edge, index  # contiguous ink beyond own reach: a neighbour
            else:
                absorbing = False
        elif inky:
            return edge, index
        index += step
    return edge, None


def _ink_obstacles(
    page: Any,
    box: list[float],
    right_limit: float,
    reach: float,
    left_limit: float | None = None,
) -> tuple[list[float], list[list[float]]]:
    """(box extended over its own contiguous ink, synthetic obstacles at the
    nearest separate ink above/below over its width and to its right over its
    height). Rules touching the box are obstacles, never absorbed."""
    dark = _page_dark(page)
    if dark is None:
        return list(box), []
    height, width = dark.shape
    x0, x1 = max(0, _px(page, box[0], 0)), min(width, _px(page, box[2], 0))
    y0, y1 = max(0, _px(page, box[1], 1)), min(height, _px(page, box[3], 1))
    if x1 - x0 < 2 or y1 - y0 < 1:
        return list(box), []
    line_px = max(1, y1 - y0)
    span = int(round(reach * _INK_ZOOM))
    to_pt_y = lambda row: page.rect.y0 + row / _INK_ZOOM  # noqa: E731
    to_pt_x = lambda col: page.rect.x0 + col / _INK_ZOOM  # noqa: E731
    found: list[list[float]] = []
    ext = list(box)
    rows = dark[:, x0:x1].mean(axis=1)
    edge, hit = _walk(
        rows, y0 - 1, -1, max(-1, y0 - 1 - span), int(0.35 * line_px), _GROWTH_ROW_SHARE
    )
    ext[1] = min(box[1], to_pt_y(edge + 1))
    if hit is not None:
        found.append([box[0], to_pt_y(hit) - 0.5, box[2], to_pt_y(hit) + 0.5])
    edge, hit = _walk(rows, y1, 1, min(height, y1 + span), int(0.35 * line_px), _GROWTH_ROW_SHARE)
    ext[3] = max(box[3], to_pt_y(edge))
    if hit is not None:
        found.append([box[0], to_pt_y(hit) - 0.5, box[2], to_pt_y(hit) + 0.5])
    limit = min(width, _px(page, right_limit, 0))
    cols = dark[y0:y1, :].mean(axis=0)
    edge, hit = _walk(cols, x1, 1, max(x1, limit), int(0.5 * line_px), _GROWTH_COL_SHARE)
    ext[2] = max(box[2], to_pt_x(edge))
    if hit is not None:
        found.append([to_pt_x(hit) - 0.5, box[1], to_pt_x(hit) + 0.5, box[3]])
    if left_limit is not None:
        # Run18: right-aligned cells (Arabic labels) have their free space on
        # the LEFT; walk leftwards the same way.
        stop = max(-1, _px(page, left_limit, 0) - 1)
        edge, hit = _walk(
            cols, x0 - 1, -1, min(x0 - 1, stop), int(0.5 * line_px), _GROWTH_COL_SHARE
        )
        ext[0] = min(box[0], to_pt_x(edge))
        if hit is not None:
            found.append([to_pt_x(hit) - 0.5, box[1], to_pt_x(hit) + 0.5, box[3]])
    return ext, found


def _growth_is_blank(page: Any, rect: list[float], box: list[float]) -> bool:
    """True when every part of ``rect`` outside the source ``box`` (plus a small
    anti-aliasing gap) holds no ink on the original raster."""
    dark = _page_dark(page)
    if dark is None:
        return True
    height, width = dark.shape
    strips = []
    if rect[1] < box[1] - _GROWTH_GAP:
        strips.append([rect[0], rect[1], rect[2], box[1] - _GROWTH_GAP])
    if rect[3] > box[3] + _GROWTH_GAP:
        strips.append([rect[0], box[3] + _GROWTH_GAP, rect[2], rect[3]])
    if rect[2] > box[2] + _GROWTH_GAP:
        strips.append([box[2] + _GROWTH_GAP, rect[1], rect[2], rect[3]])
    if rect[0] < box[0] - _GROWTH_GAP:
        strips.append([rect[0], rect[1], box[0] - _GROWTH_GAP, rect[3]])
    for strip in strips:
        sx0, sx1 = max(0, _px(page, strip[0], 0)), min(width, _px(page, strip[2], 0))
        sy0, sy1 = max(0, _px(page, strip[1], 1)), min(height, _px(page, strip[3], 1))
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        part = dark[sy0:sy1, sx0:sx1]
        count = int(part.sum())
        if count >= _GROWTH_MIN_PIXELS and count / part.size > _GROWTH_MAX_SHARE:
            return False
    return True


_SOURCE_INK_MIN_PIXELS = 60
_SOURCE_INK_MIN_SHARE = 0.01
# Rows/columns this dark are table rules or frames (structure, not text).
_RULE_RUN_SHARE = 0.7


def _uncovered_source_ink(
    page: Any, inner: list[float], covers: list[list[float]], zoom: float = 2.0
) -> tuple[int, int]:
    """(dark original pixels no planned mask covers, measured pixels) in rect."""
    import numpy as np

    try:
        clip = fitz.Rect(*inner) & page.rect
        if clip.is_empty or clip.width < 1 or clip.height < 1:
            return 0, 0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=fitz.csGRAY)
    except Exception:
        return 0, 0
    if not pix.samples or pix.width < 1 or pix.height < 1:
        return 0, 0
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, -1)[:, : pix.width]
    dark = arr < _SOURCE_INK_DARK
    dark[dark.mean(axis=1) >= _RULE_RUN_SHARE, :] = False
    dark[:, dark.mean(axis=0) >= _RULE_RUN_SHARE] = False
    for cover in covers:
        part = fitz.Rect(*cover) & clip
        if part.is_empty:
            continue
        x0 = max(0, math.floor((part.x0 - clip.x0) * zoom) - 1)
        y0 = max(0, math.floor((part.y0 - clip.y0) * zoom) - 1)
        x1 = min(pix.width, math.ceil((part.x1 - clip.x0) * zoom) + 1)
        y1 = min(pix.height, math.ceil((part.y1 - clip.y0) * zoom) + 1)
        dark[y0:y1, x0:x1] = False
    count = int(dark.sum())
    return count, int(dark.size)


def _drawn_line_rects(scratch: Any, page_rect: Any, item: dict[str, Any]) -> list[list[float]]:
    """Line boxes of the glyphs this item will actually draw (same text, rect,
    size and style on a blank scratch page). The text frame can be larger than
    the drawn text (grown into blank space); only drawn lines can hide ink."""
    try:
        blank = scratch.new_page(width=page_rect.width, height=page_rect.height)
        kwargs = _font_kwargs(item["size"], item["style"], item["align"])
        kwargs = {key: value for key, value in kwargs.items() if value is not None}
        if blank.insert_textbox(fitz.Rect(*item["inner"]), item["text"], **kwargs) < 0:
            return [list(item["inner"])]
        rects = [
            list(line["bbox"])
            for block in blank.get_text("dict").get("blocks", [])
            for line in block.get("lines", [])
            if line.get("spans")
        ]
    except Exception:
        return [list(item["inner"])]
    return rects or [list(item["inner"])]


# F31: slivers thinner than this are not worth an extra mask.
_COVER_PIECE_MIN = 0.75


def _subtract_box(rect: list[float], obstacle: list[float]) -> list[list[float]]:
    """``rect`` minus ``obstacle`` as at most four disjoint rectangles."""
    x0, y0, x1, y1 = rect
    ix0, iy0 = max(x0, obstacle[0]), max(y0, obstacle[1])
    ix1, iy1 = min(x1, obstacle[2]), min(y1, obstacle[3])
    if ix0 >= ix1 or iy0 >= iy1:
        return [list(rect)]
    pieces = []
    if iy0 > y0:
        pieces.append([x0, y0, x1, iy0])
    if iy1 < y1:
        pieces.append([x0, iy1, x1, y1])
    if ix0 > x0:
        pieces.append([x0, iy0, ix0, iy1])
    if ix1 < x1:
        pieces.append([ix1, iy0, x1, iy1])
    return pieces


def _cover_pieces(
    full: list[float], kept_boxes: list[list[float]], shrunk: list[float]
) -> list[list[float]]:
    """F31 (run27): parts of a line's full cover that touch no neighbour kept as
    original (same 0.5 pt margin as ``_shrink_away``) and that the shrunk cover
    does not already mask. A single shrunk rectangle has to give up a whole
    strip (all the width, or all the height) to avoid a neighbour occupying only
    a corner: the line's own glyphs were left visible next to the translation."""
    obstacles = [[b[0] - 0.5, b[1] - 0.5, b[2] + 0.5, b[3] + 0.5] for b in kept_boxes]
    obstacles.append(list(shrunk))
    pieces = [list(full)]
    for obstacle in obstacles:
        pieces = [part for piece in pieces for part in _subtract_box(piece, obstacle)]
    return [
        piece
        for piece in pieces
        if piece[2] - piece[0] >= _COVER_PIECE_MIN and piece[3] - piece[1] >= _COVER_PIECE_MIN
    ]


# F31 guard: share of each touching dark component that must already lie in
# the masked area, and the context rendered around a piece to see it whole.
_PIECE_OWNED_SHARE = 0.9
_PIECE_CONTEXT = 24.0
# Coloured ink (stamp, seal, signature, annotation) in a piece: ownership of
# the pixels cannot be established from boxes, the piece is refused.
_PIECE_INK_GRAY = 200
_PIECE_COLOUR_SATURATION = 40
_PIECE_COLOUR_MIN_PIXELS = 5
_PIECE_COLOUR_MIN_SHARE = 0.02


def _piece_owned(
    page: Any,
    piece: list[float],
    line_cover: list[float],
    allowed: list[list[float]],
    zoom: float = 2.0,
) -> bool:
    """F31 guard: a cover piece may only mask the line's OWN glyph parts cut by
    the shrink. Every dark connected component touching the piece must lie (at
    least 90 %) inside ``allowed`` (the line's full cover and the masks of the
    blocks replaced on the page). A stamp, a signature stroke or rotated text
    running beyond is foreign ink: the piece is refused, the residual-ink check
    then keeps protecting it. When the line's full cover holds coloured ink
    (stamp, seal or signature inside the line's box: boxes cannot tell whose
    pixels they are), no piece of that line is accepted. Unreadable raster:
    refused (conservative)."""
    import cv2
    import numpy as np

    try:
        clip = (
            fitz.Rect(
                min(piece[0], line_cover[0]) - _PIECE_CONTEXT,
                min(piece[1], line_cover[1]) - _PIECE_CONTEXT,
                max(piece[2], line_cover[2]) + _PIECE_CONTEXT,
                max(piece[3], line_cover[3]) + _PIECE_CONTEXT,
            )
            & page.rect
        )
        if clip.is_empty or clip.width < 1 or clip.height < 1:
            return False
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=fitz.csRGB)
    except Exception:
        return False
    if not pix.samples or pix.width < 1 or pix.height < 1:
        return False
    rgb = np.ascontiguousarray(
        np.frombuffer(pix.samples, dtype=np.uint8)
        .reshape(pix.height, -1)[:, : pix.width * pix.n]
        .reshape(pix.height, pix.width, pix.n)[:, :, :3]
    )
    arr = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    saturation = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[:, :, 1]
    dark = (arr < _SOURCE_INK_DARK).astype(np.uint8)

    def window(rect: list[float]) -> tuple[slice, slice] | None:
        part = fitz.Rect(*rect) & clip
        if part.is_empty:
            return None
        return (
            slice(
                max(0, math.floor((part.y0 - clip.y0) * zoom)),
                math.ceil((part.y1 - clip.y0) * zoom),
            ),
            slice(
                max(0, math.floor((part.x0 - clip.x0) * zoom)),
                math.ceil((part.x1 - clip.x0) * zoom),
            ),
        )

    inside = window(piece)
    line = window(line_cover)
    if inside is None or line is None:
        return False
    ink = arr[line] < _PIECE_INK_GRAY
    coloured = int((ink & (saturation[line] > _PIECE_COLOUR_SATURATION)).sum())
    if coloured >= max(_PIECE_COLOUR_MIN_PIXELS, _PIECE_COLOUR_MIN_SHARE * int(ink.sum())):
        return False
    count, labels = cv2.connectedComponents(dark, connectivity=8)
    touching = set(np.unique(labels[inside]).tolist()) - {0}
    if not touching:
        return True
    masked = np.zeros(dark.shape, dtype=bool)
    for rect in allowed:
        area = window(rect)
        if area is not None:
            masked[area] = True
    for label in touching:
        component = labels == label
        total = int(component.sum())
        outside = int((component & ~masked).sum())
        if outside > max(3, (1.0 - _PIECE_OWNED_SHARE) * total):
            return False
    return True


def _apply_full_covers(kept: list[dict[str, Any]], doc: Any = None) -> None:
    """Per source line, use the full cover when every neighbouring block it
    overlaps is itself replaced (redrawn), else the cover shrunk away from it,
    completed (F31) by the parts of the full cover touching no kept neighbour
    whose ink is the line's own (``_piece_owned``; needs ``doc``).
    Recomputed at each fixed-point step: dropping an item can only shrink."""
    replaced = {(int(k["page"]), str(b)) for k in kept for b in k["block_ids"]}
    staged: list[
        tuple[dict[str, Any], list[list[float]], int, list[tuple[int, list[float], list[float]]]]
    ] = []
    page_covers: dict[int, list[list[float]]] = {}
    for item in kept:
        full, overlaps = item.get("full_source_rects"), item.get("full_overlap_ids")
        shrunk = item.get("shrunk_source_rects")
        if not full or overlaps is None or shrunk is None or len(full) != len(shrunk):
            page_covers.setdefault(int(item["page"]), []).extend(item.get("source_rects") or [])
            continue
        page = int(item["page"])
        boxes = item.get("full_overlap_boxes")
        chosen, extended, candidates = [], 0, []
        for index, cover in enumerate(full):
            if all((page, oid) in replaced for oid in overlaps[index]):
                chosen.append(list(cover))
                extended += cover != shrunk[index]
            else:
                chosen.append(list(shrunk[index]))
                if doc is not None and boxes is not None and index < len(boxes):
                    kept_boxes = [box for oid, box in boxes[index] if (page, oid) not in replaced]
                    for piece in _cover_pieces(cover, kept_boxes, shrunk[index]):
                        candidates.append((index, piece, list(cover)))
        page_covers.setdefault(page, []).extend(chosen)
        staged.append((item, chosen, extended, candidates))
    for item, chosen, extended, candidates in staged:
        page = int(item["page"])
        # Fills are indexed by source line; pieces are appended after the lines.
        line_fills = item.setdefault("line_cover_fills", list(item.get("cover_fills") or []))
        pieces, piece_fills = [], []
        for index, piece, cover in candidates:
            if not _piece_owned(doc[page - 1], piece, cover, [cover, *page_covers.get(page, [])]):
                continue
            pieces.append(piece)
            piece_fills.append(line_fills[index] if index < len(line_fills) else None)
        item["source_rects"] = chosen + pieces
        item["cover_fills"] = (list(line_fills) + [None] * len(chosen))[: len(chosen)] + piece_fills
        item["extended_cover_lines"] = extended
        item["cover_pieces"] = len(pieces)


def _drop_text_over_source_ink(
    doc: Any, ir: dict[str, Any], valid: list[dict[str, Any]], issues: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fixed point over all planned replacements of scanned pages: an item whose
    drawn text lines still lie over unmasked original ink is dropped (original
    kept, critical issue). Dropping removes its masks, which can only expose more
    ink under other items, so the loop is monotone and terminates."""
    scanned = {int(p.get("number", 0)) for p in ir.get("pages", []) if p.get("scanned")}
    if not any(int(item["page"]) in scanned for item in valid):
        return list(valid)
    scratch = fitz.open()
    drawn: dict[int, list[list[float]]] = {}
    for item in valid:
        if int(item["page"]) in scanned:
            drawn[id(item)] = _drawn_line_rects(scratch, doc[int(item["page"]) - 1].rect, item)
    scratch.close()
    kept = list(valid)
    while True:
        _apply_full_covers(kept, doc)
        covers: dict[int, list[list[float]]] = {}
        for item in kept:
            covers.setdefault(int(item["page"]), []).extend(item["source_rects"])
        dropped: list[tuple[dict[str, Any], int, float]] = []
        for item in kept:
            page_number = int(item["page"])
            if page_number not in scanned:
                continue
            count, area = 0, 0
            for line_rect in drawn.get(id(item), [item["inner"]]):
                line_count, line_area = _uncovered_source_ink(
                    doc[page_number - 1], line_rect, covers.get(page_number, [])
                )
                count += line_count
                area += line_area
            share = count / max(1, area)
            if count >= _SOURCE_INK_MIN_PIXELS and share >= _SOURCE_INK_MIN_SHARE:
                dropped.append((item, count, share))
        if not dropped:
            for item in kept:
                if item.get("cover_pieces"):
                    block_ids = [str(b) for b in item.get("block_ids") or []]
                    issues.append(
                        _warn(
                            "SCAN_COVER_COMPLETED_AWAY_FROM_KEPT_NEIGHBOUR",
                            "Masque réduit complété hors des voisins conservés (F31).",
                            "info",
                            block_id=block_ids[0] if len(block_ids) == 1 else None,
                            pieces=int(item["cover_pieces"]),
                        )
                    )
                if item.get("extended_cover_lines"):
                    block_ids = [str(b) for b in item.get("block_ids") or []]
                    issues.append(
                        _warn(
                            "SCAN_COVER_EXTENDED_OVER_REPLACED_NEIGHBOUR",
                            "Masque de ligne étendu sur un bloc voisin lui-même remplacé (masques dessinés avant les textes).",
                            "info",
                            block_id=block_ids[0] if len(block_ids) == 1 else None,
                            lines=int(item["extended_cover_lines"]),
                        )
                    )
            return kept
        gone = {id(item) for item, _, _ in dropped}
        for item, count, share in dropped:
            block_ids = [str(b) for b in item.get("block_ids") or []]
            issues.append(
                _warn(
                    "SCAN_TEXT_OVER_SOURCE_INK",
                    "La traduction recouvrirait du texte source non masqué; original conservé.",
                    "critical",
                    block_id=block_ids[0] if len(block_ids) == 1 else None,
                    block_ids=block_ids,
                    cell_id=item.get("cell_id"),
                    ink_pixels=count,
                    ink_share=round(share, 4),
                )
            )
        kept = [item for item in kept if id(item) not in gone]


def _line_count(text: str) -> int:
    return max(1, len([line for line in str(text).splitlines() if line.strip()]))


def _scan_line_size(block: dict[str, Any]) -> float | None:
    from .segmentation import width_font_size

    bold = (
        bool((block.get("style") or {}).get("bold"))
        if isinstance(block.get("style"), dict)
        else False
    )
    lines = block.get("source_lines") or [block]
    by_width = sorted(
        size
        for line in lines
        if float(line.get("confidence") or 0) >= 0.6
        and (box := _rect(line.get("bbox")))
        and (size := width_font_size(str(line.get("text", "")), box[2] - box[0], bold))
    )
    height_based = _height_line_size(block)
    if by_width:
        size = by_width[len(by_width) // 2]
        if height_based:
            size = max(0.5 * height_based, min(1.2 * height_based, size))
        return size
    return height_based


def _height_line_size(block: dict[str, Any]) -> float | None:
    heights = sorted(float(h) for h in block.get("line_heights") or [] if h and float(h) > 0)
    if heights:
        # Grouped block (segmentation): the paragraph box is NOT a line height.
        # Upper quartile = lines with ascenders and descenders; the line pitch
        # bounds it when OCR boxes are swollen by nearby ink.
        size = heights[int(round(0.75 * (len(heights) - 1)))] * 0.95
        pitch = block.get("line_pitch")
        if pitch and len(heights) >= 2 and float(pitch) > 0:
            size = min(size, float(pitch) / 1.12)
        return size
    box = _rect(block.get("bbox"))
    if not box:
        return None
    return (box[3] - box[1]) / _line_count(block.get("text", "")) * 0.95


def _scan_body_size(blocks: list[dict[str, Any]]) -> float | None:
    """Dominant body size of a scanned page. OCR line boxes are swollen by
    nearby ink (handwriting, underlines), so only confident text lines vote."""

    def sizes(min_confidence: float) -> list[float]:
        return sorted(
            size
            for block in blocks
            if len(str(block.get("text", "")).strip()) >= 8
            and float(block.get("confidence") or 0) >= min_confidence
            and (size := _scan_line_size(block)) is not None
        )

    values = sizes(0.85) or sizes(0.0)
    return values[len(values) // 2] if values else None


def _scan_font_size(block: dict[str, Any], body: float | None) -> float:
    own = _scan_line_size(block) or 10.0
    # Same body text keeps one size; genuinely smaller print and genuine
    # headings (role or >= 1.25 x body) keep their own measured size.
    heading = block.get("role") == "heading" or (body and own >= 1.25 * body)
    if heading:
        if (
            body
            and own > body
            and float(block.get("confidence") or 0) < SCAN_TRUSTED_SIZE_CONFIDENCE
        ):
            # Low-confidence OCR line much taller than the body text: its box is
            # swollen by a stamp/graphic crossing it (measured on the corpus:
            # confidence 0.56-0.74, 22 pt "lines" on a 9 pt letter, rendered as
            # a giant salutation). Its height is not a font size.
            return max(6.0, min(14.0, body))
        return max(6.0, min(22.0, own))
    size = body if body and own >= 0.75 * body else own
    return max(6.0, min(14.0, size))


def _shrink_away(box: list[float], others: list[list[float]]) -> list[float] | None:
    """Shrink ``box`` on the side of each overlapping neighbour (OCR line boxes
    swollen by nearby handwriting). Refused if less than 40 % would remain.

    F30 (run27): the side removing the LEAST area is used. The horizontal side
    used to win whenever the neighbour's centre was left/right of the box
    centre: a label printed just above a value (2 pt of vertical overlap) cut
    the whole left part of the value's mask, its own ink was left uncovered
    and the translated value was refused (residual source ink)."""
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    for other in others:
        if not _strict_overlap([x0, y0, x1, y1], other):
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ox, oy = (other[0] + other[2]) / 2, (other[1] + other[3]) / 2
        candidates: list[tuple[float, list[float]]] = []
        if ox > cx and other[0] > x0 + 0.4 * width:
            nx1 = min(x1, other[0] - 0.5)
            candidates.append(((x1 - nx1) * (y1 - y0), [x0, y0, nx1, y1]))
        elif ox < cx and other[2] < x1 - 0.4 * width:
            nx0 = max(x0, other[2] + 0.5)
            candidates.append(((nx0 - x0) * (y1 - y0), [nx0, y0, x1, y1]))
        if oy > cy:
            ny1 = min(y1, other[1] - 0.5)
            candidates.append(((y1 - ny1) * (x1 - x0), [x0, y0, x1, ny1]))
        else:
            ny0 = max(y0, other[3] + 0.5)
            candidates.append(((ny0 - y0) * (x1 - x0), [x0, ny0, x1, y1]))
        # Ties keep the historical preference (horizontal side first).
        x0, y0, x1, y1 = min(candidates, key=lambda candidate: candidate[0])[1]
    shrunk = [x0, y0, x1, y1]
    if x1 - x0 < 0.4 * width or y1 - y0 < 0.4 * height:
        return None
    if any(_strict_overlap(shrunk, other) for other in others):
        return None
    return shrunk


def _neighbour_obstacle(other: list[float], box: list[float]) -> list[float] | None:
    """F19 (run18 final audit): obstacle left by a neighbouring block.

    OCR boxes of consecutive lines overlap by a point or two (ascenders,
    descenders). Such a neighbour used to be dropped from the obstacles, so a
    longer translation grew over the neighbour's line, itself redrawn: two
    lines printed on top of each other. The neighbour is now kept, clipped to
    its part outside the box. A neighbour largely overlapping the box (grouping
    artefact, container) is still not an obstacle, as before."""
    if not _strict_overlap(other, box):
        return other
    ox0, oy0, ox1, oy1 = other
    bx0, by0, bx1, by1 = box
    inter_h = min(oy1, by1) - max(oy0, by0)
    inter_w = min(ox1, bx1) - max(ox0, bx0)
    vertical = inter_h < 0.5 * min(oy1 - oy0, by1 - by0)
    horizontal = inter_w < 0.5 * min(ox1 - ox0, bx1 - bx0)
    if not vertical and not horizontal:
        return None
    if vertical:
        above = (oy0 + oy1) / 2 < (by0 + by1) / 2
        clipped = [ox0, oy0, ox1, by0] if above else [ox0, by1, ox1, oy1]
    else:
        left = (ox0 + ox1) / 2 < (bx0 + bx1) / 2
        clipped = [ox0, oy0, bx0, oy1] if left else [bx1, oy0, ox1, oy1]
    if clipped[2] - clipped[0] < 1 or clipped[3] - clipped[1] < 1:
        return None
    return clipped


def _grow_vertical(
    box: list[float], need: float, obstacles: list[list[float]], page_rect: Any
) -> list[float]:
    x0, y0, x1, y1 = box
    while y1 - y0 < need:
        if y1 + 1 <= page_rect.y1 - 2 and not any(
            _strict_overlap([x0, y1, x1, y1 + 1], o) for o in obstacles
        ):
            y1 += 1
        elif y0 - 1 >= page_rect.y0 + 2 and not any(
            _strict_overlap([x0, y0 - 1, x1, y0], o) for o in obstacles
        ):
            y0 -= 1
        else:
            break
    return [x0, y0, x1, y1]


def _grow_left(box: list[float], limit: float, obstacles: list[list[float]]) -> list[float]:
    x0, y0, x1, y1 = box
    while x0 - 2 >= limit and not any(_strict_overlap([x0 - 2, y0, x0, y1], o) for o in obstacles):
        x0 -= 2
    return [x0, y0, x1, y1]


def _grow_right(box: list[float], limit: float, obstacles: list[list[float]]) -> list[float]:
    x0, y0, x1, y1 = box
    while x1 + 2 <= limit and not any(_strict_overlap([x1, y0, x1 + 2, y1], o) for o in obstacles):
        x1 += 2
    return [x0, y0, x1, y1]


_SCAN_MIN_FONT_RATIO = 0.72
# Max candidate height of a one-line block, in font sizes: 2 lines at 72 % need
# 2 x 1.2 x 0.72 = 1.73, so 1.45 keeps one line while allowing the ascent.
_SCAN_SINGLE_LINE_HEIGHT = 1.45
_ALIGN = {"left": 0, "center": 1, "right": 2, "justify": 3}


def _scan_style(block: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Style measured on the original raster by the segmentation (bold from
    stroke width, chromatic ink colour, alignment within its column/cell)."""
    style = block.get("style") if isinstance(block.get("style"), dict) else {}
    out: dict[str, Any] = {}
    if style.get("bold"):
        out["bold"] = True
    color = style.get("color")
    if isinstance(color, (list, tuple)) and len(color) == 3:
        out["color"] = [float(c) for c in color]
    align = _ALIGN.get(str(style.get("align") or "left"), 0)
    if align in (0, 3) and _rtl_dominant(str(block.get("text") or "")):
        # Run18: the alignment measure is left-edge based; a right-to-left
        # label is anchored on its right edge, so is its French replacement
        # (it can then grow left into the free part of the cell).
        align = 2
    return out, align


def _rtl_dominant(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    rtl = sum("\u0590" <= c <= "\u08ff" or "\ufb1d" <= c <= "\ufefc" for c in letters)
    return bool(letters) and rtl >= 0.6 * len(letters)


def _line_boxes(block: dict[str, Any]) -> list[list[float]]:
    lines = block.get("source_lines") or [{"bbox": block.get("bbox")}]
    return [box for line in lines if (box := _rect(line.get("bbox")))]


_SPLIT_ZOOM = 3.0


def _vertical_ink_split(page: Any, box: list[float], other: list[float]) -> float | None:
    """Ordinate that separates the glyphs of ``box`` from those of a vertically
    stacked neighbour line whose OCR box overlaps it, or None.

    run25 (F20): OCR line boxes are taller than their glyphs, so the boxes of
    two tightly spaced lines overlap. The cover of a line was shrunk to the
    neighbour's box edge, which cuts through the line's own glyphs when the
    neighbour is kept: the translation was then drawn over the source and
    refused (SCAN_TEXT_OVER_SOURCE_INK), and the refusal cascaded to the next
    line. The dark pixels of the overlap band are assigned to a line through
    connected components rooted in each line's exclusive rows. A split is only
    returned when ownership is unambiguous: no component touches both lines and
    no floating mark (dot, accent, stray ink) lies in the band without an owner.
    """
    import cv2
    import numpy as np

    ix0, ix1 = max(box[0], other[0]), min(box[2], other[2])
    if ix1 - ix0 < 0.3 * min(box[2] - box[0], other[2] - other[0]):
        return None
    below = (other[1] + other[3]) / 2 > (box[1] + box[3]) / 2
    if below:
        band, own_core, their_core = (other[1], box[3]), (box[1], other[1]), (box[3], other[3])
    else:
        band, own_core, their_core = (box[1], other[3]), (other[3], box[3]), (other[1], box[1])
    if band[1] <= band[0] or own_core[1] - own_core[0] < 1 or their_core[1] - their_core[0] < 1:
        return None
    try:
        clip = fitz.Rect(ix0, min(box[1], other[1]), ix1, max(box[3], other[3])) & page.rect
        if clip.is_empty or clip.width < 1 or clip.height < 1:
            return None
        pix = page.get_pixmap(
            matrix=fitz.Matrix(_SPLIT_ZOOM, _SPLIT_ZOOM), clip=clip, colorspace=fitz.csGRAY
        )
    except Exception:
        return None
    if not pix.samples or pix.width < 2 or pix.height < 3:
        return None
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, -1)[:, : pix.width]
    dark = arr < _SOURCE_INK_DARK
    dark[dark.mean(axis=1) >= _RULE_RUN_SHARE, :] = False
    dark[:, dark.mean(axis=0) >= _RULE_RUN_SHARE] = False
    _count, labels = cv2.connectedComponents(dark.astype(np.uint8), connectivity=8)

    def rows(span: tuple[float, float]) -> slice:
        y0 = max(0, math.floor((span[0] - clip.y0) * _SPLIT_ZOOM))
        y1 = min(pix.height, math.ceil((span[1] - clip.y0) * _SPLIT_ZOOM))
        return slice(y0, max(y0, y1))

    own = set(np.unique(labels[rows(own_core)]).tolist()) - {0}
    theirs = set(np.unique(labels[rows(their_core)]).tolist()) - {0}
    in_band = set(np.unique(labels[rows(band)]).tolist()) - {0}
    if own & theirs or not own:
        return None

    def extent(ids: set[int]) -> np.ndarray:
        return np.nonzero(np.isin(labels, list(ids)).any(axis=1))[0] if ids else np.array([])

    own_rows, their_rows = extent(own), extent(theirs)
    # Floating marks of the band (dots, accents, diacritics, specks) belong to
    # the line they are clearly nearer to; an ambiguous one blocks the split.
    for comp in in_band - own - theirs:
        comp_rows = extent({comp})
        if below:
            d_own = comp_rows.min() - own_rows.max()
            d_their = (their_rows.min() if their_rows.size else pix.height) - comp_rows.max()
        else:
            d_own = own_rows.min() - comp_rows.max()
            d_their = comp_rows.min() - (their_rows.max() if their_rows.size else 0)
        if d_own + 1 < d_their:
            own.add(comp)
        elif d_their + 1 < d_own:
            theirs.add(comp)
        else:
            return None
    if not in_band & own:
        return None  # nothing of this line in the band: the usual shrink is exact
    own_rows, their_rows = extent(own), extent(theirs)
    if below:
        edge = own_rows.max() + 1
        limit = their_rows.min() if their_rows.size else pix.height
        if edge > limit:
            return None
        return clip.y0 + (edge + limit) / 2 / _SPLIT_ZOOM
    edge = own_rows.min()
    limit = their_rows.max() + 1 if their_rows.size else 0
    if edge < limit:
        return None
    return clip.y0 + (edge + limit) / 2 / _SPLIT_ZOOM


# run25 (F22): share of a cover's height/width, from each edge, in which a
# table rule or frame line is excluded from the cover.
_COVER_RULE_EDGE_BAND = 0.35


def _longest_run(values: Any) -> int:
    best = run = 0
    for v in values.tolist():
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def _clip_cover_off_rules(page: Any, cover: list[float]) -> list[float] | None:
    """Pull a paper cover back from the table rules / frame lines lying in its
    edge bands.

    run25 (F22): covers are derived from padded OCR line boxes; a box touching
    the cell border made the cover erase that border under the translation.
    The residual-ink check could not see it (it looks for uncovered ink, not
    for structure that was covered). A rule here is a *continuous* dark run
    over >= 85 % of the cover width (90 % of its height for a vertical rule)
    that also continues past the cover: a dark-share threshold alone also
    matches dense or bold text rows inside a cover. If pulling back exposes
    the line's own print, the residual-ink check still refuses the block.
    Returns the clipped cover, or None when nothing changed."""
    dark = _page_dark(page)
    if dark is None:
        return None
    height, width = dark.shape
    x0, x1 = max(0, _px(page, cover[0], 0)), min(width, _px(page, cover[2], 0))
    y0, y1 = max(0, _px(page, cover[1], 1)), min(height, _px(page, cover[3], 1))
    if x1 - x0 < 4 or y1 - y0 < 2:
        return None
    reach = 2  # pixels a rule must continue past the cover

    def h_rule(row: int) -> bool:
        if _longest_run(dark[row, x0:x1]) < 0.85 * (x1 - x0):
            return False
        return bool(dark[row, max(0, x0 - reach) : x0].all() and x0 >= reach) or bool(
            dark[row, x1 : x1 + reach].all() and x1 + reach <= width
        )

    def v_rule(col: int) -> bool:
        if _longest_run(dark[y0:y1, col]) < 0.9 * (y1 - y0):
            return False
        return bool(dark[max(0, y0 - reach) : y0, col].all() and y0 >= reach) or bool(
            dark[y1 : y1 + reach, col].all() and y1 + reach <= height
        )

    band_y = max(1, int(_COVER_RULE_EDGE_BAND * (y1 - y0)))
    band_x = max(1, int(_COVER_RULE_EDGE_BAND * (x1 - x0)))
    top = max((r - y0 + 1 for r in range(y0, y0 + band_y) if h_rule(r)), default=0)
    bottom = min((r - y0 for r in range(y1 - band_y, y1) if h_rule(r)), default=y1 - y0)
    left = max((c - x0 + 1 for c in range(x0, x0 + band_x) if v_rule(c)), default=0)
    right = min((c - x0 for c in range(x1 - band_x, x1) if v_rule(c)), default=x1 - x0)
    if (top, bottom, left, right) == (0, y1 - y0, 0, x1 - x0):
        return None
    if bottom - top < 2 or right - left < 4:
        return None
    to_pt_y = lambda row: page.rect.y0 + row / _INK_ZOOM  # noqa: E731
    to_pt_x = lambda col: page.rect.x0 + col / _INK_ZOOM  # noqa: E731
    return [
        max(cover[0], to_pt_x(x0 + left)),
        max(cover[1], to_pt_y(y0 + top)),
        min(cover[2], to_pt_x(x0 + right)),
        min(cover[3], to_pt_y(y0 + bottom)),
    ]


def _pull_padding_off_foreign_ink(
    page: Any, box: list[float], padded: list[float]
) -> list[float] | None:
    """Keep a cover's padding off ink that is not the line's own print.
    run25 (F24): covers are the OCR line box plus a padding meant to swallow
    accents and anti-aliasing. A rule or underline lying in that padding just
    outside the box (row border, form line, underlined heading) and a
    neighbour's glyph hanging out of its own OCR box were erased under the
    translation; F22 only sees rules over >= 85 % of the cover that also
    continue past it. Only the padding bands are examined, never the box:
    - top/bottom band: a row holding a long continuous dark run (structure,
      not an accent) stops the cover before that row;
    - left/right band: after a blank column (or a blank inner margin at the
      box edge), further ink belongs to another mark, so the cover stops there.
    Returns the pulled-back cover, or None when nothing changed."""
    dark = _page_dark(page)
    if dark is None:
        return None
    height, width = dark.shape
    bx0, bx1 = max(0, _px(page, box[0], 0)), min(width, _px(page, box[2], 0))
    by0, by1 = max(0, _px(page, box[1], 1)), min(height, _px(page, box[3], 1))
    px0, px1 = max(0, _px(page, padded[0], 0)), min(width, _px(page, padded[2], 0))
    py0, py1 = max(0, _px(page, padded[1], 1)), min(height, _px(page, padded[3], 1))
    if bx1 - bx0 < 4 or by1 - by0 < 2:
        return None
    w_px, h_px = bx1 - bx0, by1 - by0
    long_run = max(4.0, min(max(0.3 * w_px, 2.5 * h_px), 0.9 * w_px))
    to_pt_y = lambda row: page.rect.y0 + row / _INK_ZOOM  # noqa: E731
    to_pt_x = lambda col: page.rect.x0 + col / _INK_ZOOM  # noqa: E731
    out = list(padded)
    for row in range(by0 - 1, py0 - 1, -1):
        if _longest_run(dark[row, bx0:bx1]) >= long_run:
            out[1] = max(out[1], min(box[1], to_pt_y(row + 1)))
            break
    for row in range(by1, py1):
        if _longest_run(dark[row, bx0:bx1]) >= long_run:
            out[3] = min(out[3], max(box[3], to_pt_y(row)))
            break
    # a blank inner margin at the box edge already separates the line's print
    # from anything beyond the box (OCR box ending on a separator)
    # columns lying fully inside the box (rounding of the edge would pull a
    # separator printed on the edge into the margin)
    in_x1 = math.floor((box[2] - page.rect.x0) * _INK_ZOOM)
    in_x0 = math.ceil((box[0] - page.rect.x0) * _INK_ZOOM)
    seen_blank = not dark[by0:by1, max(bx0, in_x1 - 2) : in_x1].any()
    for col in range(bx1, px1):
        if not dark[by0:by1, col].any():
            seen_blank = True
        elif seen_blank:
            out[2] = min(out[2], max(box[2], to_pt_x(col)))
            break
    seen_blank = not dark[by0:by1, in_x0 : min(bx1, in_x0 + 2)].any()
    for col in range(bx0 - 1, px0 - 1, -1):
        if not dark[by0:by1, col].any():
            seen_blank = True
        elif seen_blank:
            out[0] = max(out[0], min(box[0], to_pt_x(col + 1)))
            break
    if all(abs(a - b) < 1e-6 for a, b in zip(out, padded, strict=True)):
        return None
    return out


def _scan_covers(
    block: dict[str, Any],
    others: list[list[float]],
    regions: list[list[float]],
    page_rect: Any,
    page: Any = None,
) -> tuple[list[list[float]] | None, list[str]]:
    """Paper covers for every OCR source line, padded to swallow accents and
    anti-aliasing (bounded), never reaching another block or a protected
    region. Returns (None, reasons) when a line cannot be covered safely.

    With ``page`` (scan raster available), an overlap with a vertically
    stacked neighbour line is split at the ink valley between the two lines
    (F20) instead of shrinking the cover to the neighbour's box edge."""
    covers: list[list[float]] = []
    notes: list[str] = []
    for raw in _line_boxes(block):
        box = list(raw)
        resolved: list[tuple[list[float], bool, float]] = []
        touching_regions = [o for o in regions if _strict_overlap(box, o)]
        touching = [o for o in others if _strict_overlap(box, o)]
        if page is not None and touching:
            remaining = []
            for o in touching:
                split = _vertical_ink_split(page, box, o)
                if split is None:
                    remaining.append(o)
                    continue
                below = (o[1] + o[3]) / 2 > (box[1] + box[3]) / 2
                resolved.append((o, below, split))
            for _o, below, split in resolved:
                if below:
                    box[3] = min(box[3], split)
                else:
                    box[1] = max(box[1], split)
            if box[3] - box[1] < 0.4 * (raw[3] - raw[1]):
                box, resolved, remaining = list(raw), [], touching
            elif resolved:
                notes.append("line_split_at_ink_valley")
            touching = remaining
        exempt = [o for o, _below, _split in resolved]
        touching = touching + touching_regions
        if touching:
            shrunk = _shrink_away(box, touching)
            if not shrunk:
                return None, ["line_overlaps_neighbour_or_protected_region"]
            box = shrunk
            notes.append("line_shrunk")
        h = box[3] - box[1]
        pad_x, pad_y = min(0.3 * h, 3.0), min(0.15 * h, 1.5)
        padded = [
            max(page_rect.x0, box[0] - pad_x),
            max(page_rect.y0, box[1] - pad_y),
            min(page_rect.x1, box[2] + pad_x),
            min(page_rect.y1, box[3] + pad_y),
        ]
        for _o, below, split in resolved:
            # the cover never crosses the valley towards the neighbour's glyphs
            if below:
                padded[3] = min(padded[3], split)
            else:
                padded[1] = max(padded[1], split)
        checked = [o for o in others + regions if not any(o is e for e in exempt)]
        for o in checked:
            if not _strict_overlap(padded, o):
                continue
            if o[0] >= box[2]:
                padded[2] = min(padded[2], o[0] - 0.2)
            elif o[2] <= box[0]:
                padded[0] = max(padded[0], o[2] + 0.2)
            elif o[1] >= box[3]:
                padded[3] = min(padded[3], o[1] - 0.2)
            elif o[3] <= box[1]:
                padded[1] = max(padded[1], o[3] + 0.2)
        if any(_strict_overlap(padded, o) for o in checked):
            padded = box
        if page is not None:
            pulled = _pull_padding_off_foreign_ink(page, box, padded)
            if pulled is not None:
                padded = pulled
                notes.append("cover_padding_pulled_off_foreign_ink")
            clipped = _clip_cover_off_rules(page, padded)
            if clipped is not None:
                padded = clipped
                notes.append("cover_clipped_off_rule")
        covers.append(padded)
    return covers, notes


def _glyph_band(
    page: Any, box: list[float], others: list[list[float]]
) -> tuple[float, float] | None:
    """Vertical extent of the line's own print inside an OCR box taller than it.

    run25 (F20b): one-line frames were anchored at the top of the OCR box; when
    the box is inflated (2-3x the print height, often upwards over the
    neighbour line's descenders), the translation was drawn over the
    neighbour's ink or into the inter-line band, then refused for residual
    source ink. Ink inside any other OCR line box (a neighbour's spill, or a
    fragment boxed inside this one) is masked out first; the remaining rows
    carrying ink are grouped into bands (1-row gaps bridged) and the heaviest
    band is the line's print.
    """
    import numpy as np

    try:
        clip = fitz.Rect(*box) & page.rect
        if clip.is_empty or clip.width < 1 or clip.height < 1:
            return None
        pix = page.get_pixmap(
            matrix=fitz.Matrix(_SPLIT_ZOOM, _SPLIT_ZOOM), clip=clip, colorspace=fitz.csGRAY
        )
    except Exception:
        return None
    if not pix.samples or pix.width < 2 or pix.height < 3:
        return None
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, -1)[:, : pix.width]
    dark = arr < _SOURCE_INK_DARK
    dark[dark.mean(axis=1) >= _RULE_RUN_SHARE, :] = False
    dark[:, dark.mean(axis=0) >= _RULE_RUN_SHARE] = False
    for o in others:
        part = fitz.Rect(*o) & clip
        if part.is_empty:
            continue
        x0 = max(0, math.floor((part.x0 - clip.x0) * _SPLIT_ZOOM))
        y0 = max(0, math.floor((part.y0 - clip.y0) * _SPLIT_ZOOM))
        x1 = min(pix.width, math.ceil((part.x1 - clip.x0) * _SPLIT_ZOOM))
        y1 = min(pix.height, math.ceil((part.y1 - clip.y0) * _SPLIT_ZOOM))
        dark[y0:y1, x0:x1] = False
    profile = dark.sum(axis=1)
    bands: list[list[int]] = []
    for row, count in enumerate(profile.tolist()):
        if not count:
            continue
        if bands and row - bands[-1][1] <= 2:
            bands[-1][1] = row
            bands[-1][2] += count
        else:
            bands.append([row, row, count])
    if not bands:
        return None
    start, end, _mass = max(bands, key=lambda b: b[2])
    return clip.y0 + start / _SPLIT_ZOOM, clip.y0 + (end + 1) / _SPLIT_ZOOM


def _scan_region_protects(block: dict[str, Any], region: dict[str, Any]) -> bool:
    from .protected_visuals import carves_only, is_user_region, significant_overlap

    box, rbox = _rect(block.get("bbox")), _rect(region.get("bbox"))
    if not box or not rbox or not _intersects(box, rbox) or carves_only(region):
        return False
    return is_user_region(region) or significant_overlap(box, rbox)


def _plan_scan_block(
    *,
    block: dict[str, Any],
    target: str,
    page: Any,
    page_number: int,
    ir_blocks: list[dict[str, Any]],
    protected_regions: list[dict[str, Any]],
    body_size: float | None,
    body_right: float | None,
    source_bytes: bytes,
    bound: list[float] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], bool]:
    """Plan the replacement of one OCR block (line or grouped paragraph) on a
    scanned page. Returns (item | None, issues, overflow)."""
    block_id = str(block.get("id"))
    issues: list[dict[str, Any]] = []
    page_regions = [
        r
        for r in protected_regions
        if int(r.get("page", 0)) == page_number and _rect(r.get("bbox"))
    ]
    if block.get("protected") or any(_scan_region_protects(block, r) for r in page_regions):
        issues.append(
            _warn(
                "PROTECTED_TRANSLATION_NOT_APPLIED",
                "Le bloc fait partie d'une zone protégée (cachet, logo, signature ou annotation); revue humaine.",
                "error",
                block_id=block_id,
            )
        )
        return None, issues, False
    if _RTL.search(target):
        issues.append(
            _warn(
                "RTL_SHAPING_UNSUPPORTED",
                "Façonnage RTL non configuré; insertion bloquée.",
                "error",
                block_id=block_id,
            )
        )
        return None, issues, False
    box = _rect(block.get("bbox"))
    if not box:
        return None, issues, False
    region_boxes = [_rect(r.get("bbox")) for r in page_regions]
    others = [lb for o in ir_blocks if str(o.get("id")) != block_id for lb in _line_boxes(o)]
    other_ids = [
        (str(o.get("id")), lb)
        for o in ir_blocks
        if str(o.get("id")) != block_id
        for lb in _line_boxes(o)
    ]
    covers, notes = _scan_covers(block, others, region_boxes, page.rect, page=page)
    if covers is None:
        issues.append(
            _warn(
                "NATIVE_REDACTION_OVERLAP",
                "Une ligne source chevauche un autre bloc ou une zone protégée; masquage sûr impossible, revue humaine.",
                "error",
                block_id=block_id,
                reasons=notes,
            )
        )
        return None, issues, False
    if "line_shrunk" in notes:
        issues.append(
            _warn(
                "SCAN_REDACTION_SHRUNK",
                "Masque de ligne réduit pour ne pas toucher un bloc voisin ou une zone protégée.",
                "warning",
                block_id=block_id,
            )
        )
    if _graphic_conflict(page, box):
        issues.append(
            _warn(
                "PROTECTED_NATIVE_GRAPHIC",
                "Widget, formulaire ou graphique recouvert; remplacement refusé.",
                "error",
                block_id=block_id,
            )
        )
        return None, issues, False
    size = _scan_font_size(block, body_size)
    style, align = _scan_style(block)
    obstacles = [clipped for o in others if (clipped := _neighbour_obstacle(o, box))] + region_boxes
    inner = list(box)
    if bound:
        inner = [
            max(inner[0], bound[0]),
            max(inner[1], bound[1]),
            min(inner[2], bound[2]),
            min(inner[3], bound[3]),
        ]
        if inner[2] - inner[0] < 2 or inner[3] - inner[1] < 2:
            inner = list(box)
        bx0, by0, bx1, by1 = bound
        obstacles = obstacles + [
            [page.rect.x0, page.rect.y0, page.rect.x1, by0],
            [page.rect.x0, by1, page.rect.x1, page.rect.y1],
            [page.rect.x0, page.rect.y0, bx0, page.rect.y1],
            [bx1, page.rect.y0, page.rect.x1, page.rect.y1],
        ]
    # The text box must not cover any protected region (overlay text on a stamp).
    hit = [r for r in region_boxes if _strict_overlap(inner, r)]
    if hit:
        shrunk = _shrink_away(inner, hit)
        if not shrunk:
            issues.append(
                _warn(
                    "PROTECTED_OVERLAP_REVIEW",
                    "Zone de texte traduite chevauchant un élément protégé; revue humaine.",
                    "error",
                    block_id=block_id,
                )
            )
            return None, issues, False
        inner = shrunk
    lines = int(block.get("line_count") or _line_count(block.get("text", "")))
    right_limit = bound[2] if bound else (body_right or page.rect.width - 36)
    # Run18: text aligned right (or centred) keeps its anchor only if the box
    # grows to the left (right-aligned Arabic cell labels, DOC-004).
    grow_left = align in (1, 2)
    left_limit = None
    if grow_left:
        lefts = [
            r[0]
            for b in ir_blocks
            if (r := _rect(b.get("bbox"))) and len(str(b.get("text", "")).strip()) >= 8
        ]
        left_limit = bound[0] if bound else min(lefts or [page.rect.x0 + 36])
    # Growth stops at the nearest original ink (rules, labels, graphics, text
    # that OCR did not box) and every candidate is re-checked below.
    ink_box, ink_obstacles = _ink_obstacles(
        page, box, right_limit, size * 1.25 * lines * 2, left_limit=left_limit
    )
    obstacles = obstacles + ink_obstacles
    candidates = [_grow_vertical(inner, size * 1.25 * lines, obstacles, page.rect)]
    if align == 2:
        candidates.append(_grow_left(candidates[0], left_limit, obstacles))
    elif align == 1:
        wide_l = _grow_left(candidates[0], left_limit, obstacles)
        wide_r = _grow_right(candidates[0], right_limit, obstacles)
        extra = min(candidates[0][0] - wide_l[0], wide_r[2] - candidates[0][2])
        candidates.append(
            [
                candidates[0][0] - extra,
                candidates[0][1],
                candidates[0][2] + extra,
                candidates[0][3],
            ]
        )
    else:
        candidates.append(_grow_right(candidates[0], right_limit, obstacles))
    candidates.append(
        _grow_vertical(
            candidates[1], (candidates[1][3] - candidates[1][1]) * 1.6, obstacles, page.rect
        )
    )
    if lines == 1:
        # A one-line source stays one line: an OCR box taller than its print
        # (rule or graphic underneath) let a section heading wrap onto the row
        # below it. Shrink (>= 72 %) or extend right first; wrapping is only a
        # fallback into space proven blank (see below), else LAYOUT_OVERFLOW.
        single = size * _SCAN_SINGLE_LINE_HEIGHT
        top = None
        if box[3] - box[1] > 1.15 * single:
            # F20b: anchor the one-line frame on the line's own print, not on
            # the top of an inflated OCR box.
            glyphs = _glyph_band(page, box, others)
            if glyphs:
                centre = (glyphs[0] + glyphs[1]) / 2
                top = min(max(box[1], centre - single / 2), box[3] - single)
        if top is not None:
            candidates = [[r[0], max(r[1], top), r[2], r[3]] for r in candidates]
        candidates = [[r[0], r[1], r[2], min(r[3], r[1] + single)] for r in candidates]
    best = None
    ink_rejected = 0
    for rect in candidates:
        if not _growth_is_blank(page, rect, ink_box):
            ink_rejected += 1
            continue
        ok, remainder, used = _fit_on_scratch(
            source_bytes,
            page_number,
            fitz.Rect(*rect),
            target,
            size,
            style,
            align,
            _SCAN_MIN_FONT_RATIO,
        )
        if ok and (best is None or used > best[2] + 1e-6):
            best = (rect, remainder, used)
        if ok and used >= size * 0.97:
            break
    if ink_rejected:
        issues.append(
            _warn(
                "SCAN_FRAME_GROWTH_INK_REJECTED",
                "Cadre agrandi refusé : il recouvrirait de l'encre originale (filet, libellé, graphisme).",
                "info",
                block_id=block_id,
                candidates=ink_rejected,
            )
        )
    if best is None and lines == 1:
        # Fallback: wrap only where the extra area under the one-line source is
        # free of EVERY other OCR box (including those overlapping this box,
        # which the obstacle filter ignores), of protected zones and of ink.
        all_others = [
            lb for o in ir_blocks if str(o.get("id")) != block_id for lb in _line_boxes(o)
        ]
        # Explicit 2- and 3-line frames at the source width and at the
        # right-extended width (one-line candidates are too short to wrap).
        widths = sorted({round(candidates[0][2], 2), round(candidates[1][2], 2)})
        wrapped = [
            [inner[0], inner[1], x1, inner[1] + size * 1.25 * n] for n in (2, 3) for x1 in widths
        ]
        for rect in wrapped:
            if rect[3] > page.rect.y1 - 18:
                continue
            below = [rect[0], box[1] + size * _SCAN_SINGLE_LINE_HEIGHT, rect[2], rect[3]]
            if below[3] - below[1] < size:
                continue
            if any(_strict_overlap(below, o) for o in all_others + region_boxes):
                continue
            if not _band_is_blank(page, below):
                continue
            ok, remainder, used = _fit_on_scratch(
                source_bytes,
                page_number,
                fitz.Rect(*rect),
                target,
                size,
                style,
                align,
                _SCAN_MIN_FONT_RATIO,
            )
            if ok and (best is None or used > best[2] + 1e-6):
                best = (rect, remainder, used)
        if best is not None:
            issues.append(
                _warn(
                    "SINGLE_LINE_WRAPPED_INTO_BLANK",
                    "Ligne unique traduite sur plusieurs lignes dans un espace vérifié vide (aucun bloc, zone protégée ni encre).",
                    "info",
                    block_id=block_id,
                )
            )
    if best is None:
        issues.append(
            _warn(
                "LAYOUT_OVERFLOW",
                "Le texte traduit ne tient pas sans réduction excessive; source conservée, revue humaine.",
                "critical",
                block_id=block_id,
                font_size=round(size, 2),
                min_font_size=round(size * _SCAN_MIN_FONT_RATIO, 2),
            )
        )
        return None, issues, True
    rect, remainder, used = best
    if used < size * 0.85:
        issues.append(
            _warn(
                "FONT_REDUCED",
                "Taille de police réduite pour contenir la traduction (réduction bornée).",
                "info",
                block_id=block_id,
                font_size=round(size, 2),
                used_font_size=round(used, 2),
                ratio=round(used / size, 3),
            )
        )
    block_style = block.get("style") if isinstance(block.get("style"), dict) else {}
    background = block_style.get("background") if block_style.get("highlight") else None
    # Highlight measured per source line (line_verification) wins: a marker on
    # one line of a paragraph must not paint the others. Covers follow the
    # order of _line_boxes(block).
    line_marks = [
        (line.get("highlight_evidence") or {})
        for line in (block.get("source_lines") or [block])
        if _rect(line.get("bbox"))
    ]
    fills = []
    for index, cover in enumerate(covers):
        mark = line_marks[index] if index < len(line_marks) else {}
        if mark.get("highlight") and mark.get("rgb"):
            fills.append([float(c) for c in mark["rgb"]])
        elif background and not any(m.get("highlight") is not None for m in line_marks):
            fills.append([float(c) for c in background])
        else:
            fills.append(_paper_color(page, cover))
    # Full covers (shrunk only away from protected regions) and, per line, the
    # neighbouring blocks they overlap. The final phase uses a full cover only
    # when every overlapped neighbour is itself replaced (its pixels are
    # redrawn as translation): a neighbour kept as original is never masked.
    # F22b: the full cover must also stay off table rules / frame lines.
    full, _full_notes = _scan_covers(block, [], region_boxes, page.rect, page=page)
    full_overlaps: list[list[str]] | None = None
    full_overlap_boxes: list[list[tuple[str, list[float]]]] | None = None
    if full is not None and len(full) == len(covers):
        full_overlaps = [
            sorted({oid for oid, lb in other_ids if _strict_overlap(cover, lb)}) for cover in full
        ]
        full_overlap_boxes = [
            [(oid, list(lb)) for oid, lb in other_ids if _strict_overlap(cover, lb)]
            for cover in full
        ]
    else:
        full = None
    if any(m.get("highlight") and m.get("partial") for m in line_marks):
        issues.append(
            _warn(
                "HIGHLIGHT_SPAN_APPROXIMATED",
                "Surlignage partiel d'une ligne reproduit sur toute la ligne traduite (position des mots non transposable).",
                "info",
                block_id=block_id,
            )
        )
    item = {
        "page": page_number,
        "rect": box,
        "inner": rect,
        "text": target,
        "size": used,
        "measured_size": size,
        "style": style,
        "align": align,
        "block_ids": [block_id],
        "source_line_ids": [str(x.get("id")) for x in block.get("source_lines") or []],
        "table": False,
        "source_rects": covers,
        "shrunk_source_rects": [list(c) for c in covers],
        "full_source_rects": full,
        "full_overlap_ids": full_overlaps,
        "full_overlap_boxes": full_overlap_boxes,
        "cover_fills": fills,
        "cover": None,
    }
    return item, issues, False


def _page_ir_blocks(ir: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for page in ir.get("pages", []):
        result[int(page.get("number", len(result) + 1))] = list(page.get("blocks", []))
    return result


def render_pdf(
    ir: dict[str, Any],
    translations: dict[str, str],
    source: str | Path,
    out: str | Path,
    protected_regions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Render a translated PDF without mutating source and with atomic changes."""
    source_path = Path(source).resolve()
    out_path = Path(out).resolve()
    if source_path == out_path:
        raise ValueError("source and out must be different files")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    protected_regions = list(protected_regions or [])
    translations = {str(key): str(value) for key, value in (translations or {}).items()}
    issues: list[dict[str, Any]] = []
    changed_blocks = 0
    overflow_count = 0
    text_masks: list[dict[str, Any]] = []
    # F26: what was really inserted (frame used by the engine), for the
    # post-render verification of the candidate PDF.
    placements: list[dict[str, Any]] = []
    table_trace: list[dict[str, Any]] = []
    if ir.get("format") == "pdf":
        from .protected_visuals import detect_pdf_visuals

        automatic, _warnings = detect_pdf_visuals(
            source_path, ir.get("pages", []), ir.get("tables", [])
        )
        protected_regions.extend(automatic)
    source_bytes = source_path.read_bytes()
    if ir.get("format") in {"png", "jpg", "jpeg"}:
        from PIL import Image

        with Image.open(source_path) as image:
            width, height = image.size
        doc = fitz.open()
        page = doc.new_page(width=width, height=height)
        page.insert_image(page.rect, filename=str(source_path))
        source_bytes = doc.tobytes()
    else:
        doc = fitz.open(str(source_path))
    original_page_count = len(doc)
    ir_pages = _page_ir_blocks(ir)
    valid: list[dict[str, Any]] = []
    try:
        for page_number, page in enumerate(doc, 1):
            ir_blocks = ir_pages.get(page_number, [])
            if page.rotation and any(
                translations.get(str(b.get("id")), b.get("text")) != b.get("text")
                for b in ir_blocks
            ):
                issues.append(
                    _warn(
                        "PDF_NATIVE_ROTATION_REQUIRES_REVIEW",
                        "Coordonnées source PDF avec rotation native nécessitent un mapping validé; page inchangée.",
                        "error",
                        page=page_number,
                    )
                )
                continue
            source_tables = _detect_tables(page, page_number, ir_blocks)
            if ir.get("pages", [])[page_number - 1].get("scanned"):
                source_tables = [
                    dict(t) for t in ir.get("tables", []) if t.get("page") == page_number
                ]
                enrich_tables(page, source_tables, ir_blocks)
            table_block_ids = {
                str(block_id)
                for table in source_tables
                for cell in table.get("cells", [])
                for block_id in cell.get("block_ids", [])
            }
            ambiguous = {
                str(block_id)
                for table in source_tables
                for block_id in table.get("ambiguous_block_ids", [])
            }
            consumed: set[str] = set()
            # Blocks of a cell that cannot be replaced atomically (protected
            # region or native graphic inside the cell, e.g. a page frame
            # detected as a one-cell table around a logo/stamp) are retried one
            # by one; each block keeps its own protection/overlap/graphic checks.
            fallback_ids: set[str] = set()
            page_is_scan = bool(ir.get("pages", [])[page_number - 1].get("scanned"))
            scan_body = _scan_body_size(ir_blocks) if page_is_scan else None
            cell_bounds: dict[str, list[float]] = {}
            for table in source_tables:
                for cell in table.get("cells", []):
                    ids = [str(block_id) for block_id in cell.get("block_ids", [])]
                    blocks = [block for block in ir_blocks if str(block.get("id")) in ids]
                    source_text, target_text, changed = _target_text(blocks, translations)
                    trace = {
                        "page": page_number,
                        "table_id": table.get("id"),
                        "cell_id": cell.get("id"),
                        "block_ids": ids,
                        "status": "unchanged",
                    }
                    if not changed:
                        table_trace.append(trace)
                        consumed.update(ids)
                        continue
                    if any(block_id in ambiguous for block_id in ids):
                        if page_is_scan:
                            # Raster table detection is heuristic, while each OCR
                            # block has its own measured bbox: the cell link is not
                            # needed to place it. Blocks keep every individual check.
                            trace["status"] = "fallback_blocks_ambiguous_scan_cell"
                            issues.append(
                                _warn(
                                    "TABLE_CELL_FALLBACK_TO_BLOCKS",
                                    "Lien de cellule ambigu sur un scan; blocs OCR traités individuellement dans leur bbox.",
                                    "warning",
                                    page=page_number,
                                    cell_id=cell.get("id"),
                                    block_ids=ids,
                                )
                            )
                            table_trace.append(trace)
                            fallback_ids.update(ids)
                            continue
                        trace["status"] = "review_ambiguous_cell_link"
                        issues.append(
                            _warn(
                                "TABLE_AMBIGUOUS_CELL_LINK",
                                "Cellule liée à plusieurs cellules ou à une géométrie en L; remplacement refusé.",
                                "error",
                                page=page_number,
                                cell_id=cell.get("id"),
                                block_ids=ids,
                            )
                        )
                        table_trace.append(trace)
                        consumed.update(ids)
                        continue
                    box = _rect(cell.get("bbox"))
                    if not box:
                        # Never drop a translated cell silently.
                        trace["status"] = "fallback_blocks_no_cell_bbox"
                        issues.append(
                            _warn(
                                "TABLE_CELL_FALLBACK_TO_BLOCKS",
                                "Cellule sans bbox mesurée; blocs traités individuellement.",
                                "warning",
                                page=page_number,
                                cell_id=cell.get("id"),
                                block_ids=ids,
                            )
                        )
                        table_trace.append(trace)
                        fallback_ids.update(ids)
                        continue
                    if _protected_box(page_number, box, protected_regions) or any(
                        _protected(block, protected_regions) for block in blocks
                    ):
                        trace["status"] = "fallback_blocks_protected"
                        if page_is_scan and box:
                            cell_bounds.update({bid: box for bid in ids})
                        issues.append(
                            _warn(
                                "TABLE_CELL_FALLBACK_TO_BLOCKS",
                                "La cellule intersecte une zone protégée; remplacement atomique refusé, blocs traités individuellement.",
                                "warning",
                                page=page_number,
                                cell_id=cell.get("id"),
                                block_ids=ids,
                            )
                        )
                        table_trace.append(trace)
                        fallback_ids.update(ids)
                        continue
                    if _graphic_conflict(page, box):
                        trace["status"] = "fallback_blocks_graphic"
                        if page_is_scan and box:
                            cell_bounds.update({bid: box for bid in ids})
                        issues.append(
                            _warn(
                                "TABLE_CELL_FALLBACK_TO_BLOCKS",
                                "Widget, formulaire ou graphique dans la cellule; remplacement atomique refusé, blocs traités individuellement.",
                                "warning",
                                page=page_number,
                                cell_id=cell.get("id"),
                                block_ids=ids,
                            )
                        )
                        table_trace.append(trace)
                        fallback_ids.update(ids)
                        continue
                    if _RTL.search(target_text):
                        trace["status"] = "rtl_review"
                        issues.append(
                            _warn(
                                "RTL_SHAPING_UNSUPPORTED",
                                "Façonnage RTL non configuré; insertion bloquée plutôt que produire des glyphes incorrects.",
                                "error",
                                page=page_number,
                                cell_id=cell.get("id"),
                            )
                        )
                        table_trace.append(trace)
                        consumed.update(ids)
                        continue
                    native_in_cell = [
                        b
                        for b in _blocks_from_page(page, page_number)
                        if _contains(box, _rect(b["bbox"]), 1)
                    ]
                    covered_text = re.sub(r"\s+", "", source_text)
                    actual_text = re.sub(r"\s+", "", "\n".join(b["text"] for b in native_in_cell))
                    if native_in_cell and actual_text != covered_text:
                        trace["status"] = "incomplete_ir_text_coverage"
                        issues.append(
                            _warn(
                                "PDF_CELL_SOURCE_TEXT_UNMAPPED",
                                "Texte natif cellule absent ou différent de l'IR; remplacement bloqué.",
                                "error",
                                cell_id=cell["id"],
                            )
                        )
                        consumed.update(ids)
                        table_trace.append(trace)
                        continue
                    padding = cell.get("padding") or [4.0, 3.0, 4.0, 3.0]
                    inner = [
                        box[0] + float(padding[0]),
                        box[1] + float(padding[1]),
                        box[2] - float(padding[2]),
                        box[3] - float(padding[3]),
                    ]
                    page_area = float(page.rect.width * page.rect.height) or 1.0
                    if page_is_scan and (box[2] - box[0]) * (box[3] - box[1]) >= 0.5 * page_area:
                        # A raster "cell" covering half the page is the scan frame,
                        # not a table cell: one text flow would destroy the layout.
                        trace["status"] = "fallback_blocks_scan_frame_cell"
                        issues.append(
                            _warn(
                                "TABLE_CELL_FALLBACK_TO_BLOCKS",
                                "Cellule raster couvrant la page (cadre de scan); blocs OCR traités individuellement.",
                                "warning",
                                page=page_number,
                                cell_id=cell.get("id"),
                                block_ids=ids,
                            )
                        )
                        table_trace.append(trace)
                        fallback_ids.update(ids)
                        continue
                    if inner[2] <= inner[0] or inner[3] <= inner[1]:
                        if page_is_scan:
                            trace["status"] = "fallback_blocks_empty_scan_cell"
                            issues.append(
                                _warn(
                                    "TABLE_CELL_FALLBACK_TO_BLOCKS",
                                    "Bbox intérieure de cellule vide sur un scan; blocs OCR traités individuellement.",
                                    "warning",
                                    page=page_number,
                                    cell_id=cell.get("id"),
                                    block_ids=ids,
                                )
                            )
                            table_trace.append(trace)
                            fallback_ids.update(ids)
                            continue
                        trace["status"] = "overflow"
                        overflow_count += 1
                        issues.append(
                            _warn(
                                "LAYOUT_OVERFLOW",
                                "La bbox intérieure de cellule est vide.",
                                "critical",
                                page=page_number,
                                cell_id=cell.get("id"),
                                block_ids=ids,
                            )
                        )
                        table_trace.append(trace)
                        consumed.update(ids)
                        continue
                    style = cell.get("style") or {}
                    align_name = str(cell.get("align") or style.get("align") or "left").casefold()
                    align = {"left": 0, "center": 1, "right": 2}.get(align_name, 0)
                    size = float(
                        style.get("font_size")
                        or next(
                            (block.get("font_size") for block in blocks if block.get("font_size")),
                            max(6.0, min(14.0, (inner[3] - inner[1]) * 0.72)),
                        )
                    )
                    scan_covers = None
                    if page_is_scan:
                        main = max(blocks, key=lambda b: len(str(b.get("text", ""))), default={})
                        size = _scan_font_size(main, scan_body)
                        scan_style, scan_align = _scan_style(main)
                        style = {**style, **scan_style}
                        align = scan_align if (main.get("style") or {}).get("align") else align
                        others_cell = [
                            lb
                            for o in ir_blocks
                            if str(o.get("id")) not in ids
                            for lb in _line_boxes(o)
                        ]
                        region_cell = [
                            r
                            for region in protected_regions
                            if int(region.get("page", 0)) == page_number
                            and (r := _rect(region.get("bbox")))
                        ]
                        scan_covers = []
                        for member in blocks:
                            covers_m, _notes = _scan_covers(
                                member, others_cell, region_cell, page.rect, page=page
                            )
                            if covers_m is None:
                                scan_covers = None
                                break
                            scan_covers.extend(
                                [
                                    max(c[0], box[0]),
                                    max(c[1], box[1]),
                                    min(c[2], box[2]),
                                    min(c[3], box[3]),
                                ]
                                for c in covers_m
                            )
                    ok, remainder, used_size = _fit_on_scratch(
                        source_bytes,
                        page_number,
                        fitz.Rect(*inner),
                        target_text,
                        size,
                        style,
                        align,
                        _SCAN_MIN_FONT_RATIO if page_is_scan else None,
                    )
                    if page_is_scan and ok and scan_covers is None:
                        ok, remainder = False, -1.0
                    if not ok:
                        if page_is_scan:
                            # Each OCR block has its own measured bbox; rendering
                            # them individually beats keeping the whole cell source.
                            trace.update(
                                {
                                    "status": "fallback_blocks_scan_cell_overflow",
                                    "overflow": float(remainder),
                                }
                            )
                            cell_bounds.update({bid: box for bid in ids})
                            issues.append(
                                _warn(
                                    "TABLE_CELL_FALLBACK_TO_BLOCKS",
                                    "Texte de cellule trop long pour un rendu atomique sur scan; blocs OCR traités individuellement.",
                                    "warning",
                                    page=page_number,
                                    cell_id=cell.get("id"),
                                    block_ids=ids,
                                )
                            )
                            table_trace.append(trace)
                            fallback_ids.update(ids)
                            continue
                        trace.update(
                            {
                                "status": "overflow",
                                "overflow": float(remainder),
                                "font_size": used_size,
                            }
                        )
                        overflow_count += 1
                        issues.append(
                            _warn(
                                "LAYOUT_OVERFLOW",
                                "Le texte traduit ne tient pas dans la cellule après réduction bornée; source conservée.",
                                "critical",
                                page=page_number,
                                cell_id=cell.get("id"),
                                overflow=float(remainder),
                                block_ids=ids,
                            )
                        )
                        table_trace.append(trace)
                        consumed.update(ids)
                        continue
                    trace.update(
                        {
                            "status": "ready",
                            "font_size": used_size,
                            "fit": float(remainder),
                            "source_text": source_text,
                            "target_text": target_text,
                        }
                    )
                    valid.append(
                        {
                            "page": page_number,
                            "rect": box,
                            "inner": inner,
                            "text": target_text,
                            "size": used_size,
                            "style": style,
                            "align": align,
                            "block_ids": ids,
                            "cell_id": cell.get("id"),
                            "table_id": table.get("id"),
                            "table": True,
                            "source_rects": scan_covers
                            if page_is_scan and scan_covers
                            else [list(b["bbox"]) for b in blocks],
                        }
                    )
                    table_trace.append(trace)
                    consumed.update(ids)
            # Non-table blocks retain legacy simple behavior.
            scanned_flag = bool(ir.get("pages", [])[page_number - 1].get("scanned"))
            body_size = _scan_body_size(ir_blocks) if scanned_flag else None
            body_right = (
                max(
                    [
                        _rect(b.get("bbox"))[2]
                        for b in ir_blocks
                        if _rect(b.get("bbox")) and len(str(b.get("text", "")).strip()) >= 8
                    ]
                    or [page.rect.width - 36]
                )
                if scanned_flag
                else None
            )
            for block in ir_blocks:
                block_id = str(block.get("id"))
                if block_id in consumed or (
                    block_id in table_block_ids and block_id not in fallback_ids
                ):
                    continue
                original = str(block.get("text", ""))
                target = translations.get(block_id, original)
                if target == original:
                    continue
                if scanned_flag:
                    item, scan_issues, overflowed = _plan_scan_block(
                        block=block,
                        target=target,
                        page=page,
                        page_number=page_number,
                        ir_blocks=ir_blocks,
                        protected_regions=protected_regions,
                        body_size=body_size,
                        body_right=body_right,
                        source_bytes=source_bytes,
                        bound=cell_bounds.get(block_id),
                    )
                    issues.extend(scan_issues)
                    overflow_count += int(overflowed)
                    if item:
                        valid.append(item)
                    continue
                if _protected(block, protected_regions):
                    issues.append(
                        _warn(
                            "PROTECTED_TRANSLATION_NOT_APPLIED",
                            "La zone est protégée; remplacement non appliqué.",
                            "error",
                            block_id=block_id,
                        )
                    )
                    continue
                if _RTL.search(target):
                    issues.append(
                        _warn(
                            "RTL_SHAPING_UNSUPPORTED",
                            "Façonnage RTL non configuré; insertion bloquée.",
                            "error",
                            block_id=block_id,
                        )
                    )
                    continue
                box = _rect(block.get("bbox"))
                if not box:
                    continue
                if _protected_box(page_number, box, protected_regions):
                    issues.append(
                        _warn(
                            "PROTECTED_TRANSLATION_NOT_APPLIED",
                            "La zone est protégée; remplacement non appliqué.",
                            "error",
                            block_id=block_id,
                        )
                    )
                    continue
                overlaps = [
                    other.get("id")
                    for other in ir_blocks
                    if str(other.get("id")) != block_id
                    and _intersects(box, _rect(other.get("bbox")))
                ]
                if overlaps and scanned_flag:
                    shrunk = _shrink_away(
                        box,
                        [
                            _rect(o.get("bbox"))
                            for o in ir_blocks
                            if str(o.get("id")) in {str(x) for x in overlaps}
                        ],
                    )
                    if shrunk:
                        issues.append(
                            _warn(
                                "SCAN_REDACTION_SHRUNK",
                                "Boîte OCR réduite pour ne pas toucher un bloc voisin (annotation, bruit).",
                                "warning",
                                block_id=block_id,
                                original_bbox=box,
                                bbox=shrunk,
                                overlapping_block_ids=overlaps,
                            )
                        )
                        box = shrunk
                        overlaps = []
                if overlaps:
                    issues.append(
                        _warn(
                            "NATIVE_REDACTION_OVERLAP",
                            "La zone de redaction intersecte un autre bloc source; remplacement refusé.",
                            "error",
                            block_id=block_id,
                            overlapping_block_ids=overlaps,
                        )
                    )
                    continue
                if _graphic_conflict(page, box):
                    issues.append(
                        _warn(
                            "PROTECTED_NATIVE_GRAPHIC",
                            "Widget, formulaire ou graphique recouvert; remplacement refusé.",
                            "error",
                            block_id=block_id,
                        )
                    )
                    continue
                inner = box
                cover = None
                if scanned_flag:
                    size = _scan_font_size(block, body_size)
                    obstacles = [
                        r
                        for o in ir_blocks
                        if str(o.get("id")) != block_id and (r := _rect(o.get("bbox")))
                    ] + [
                        r
                        for region in protected_regions
                        if int(region.get("page", 0)) == page_number
                        and (r := _rect(region.get("bbox")))
                    ]
                    lines = _line_count(original)
                    inner = _grow_vertical(box, size * 1.25 * lines, obstacles, page.rect)
                    ok, remainder, used_size = _fit_on_scratch(
                        source_bytes, page_number, fitz.Rect(*inner), target, size, {}, 0
                    )
                    if not ok or used_size < size * 0.85:
                        wider = _grow_right(inner, body_right, obstacles)
                        retry = _fit_on_scratch(
                            source_bytes, page_number, fitz.Rect(*wider), target, size, {}, 0
                        )
                        if retry[0] and (not ok or retry[2] > used_size):
                            inner = wider
                            ok, remainder, used_size = retry
                    cover = _paper_color(page, box)
                else:
                    size = float(
                        block.get("font_size") or max(6.0, min(14.0, (box[3] - box[1]) * 0.72))
                    )
                    ok, remainder, used_size = _fit_on_scratch(
                        source_bytes, page_number, fitz.Rect(*box), target, size, {}, 0
                    )
                if not ok:
                    overflow_count += 1
                    issues.append(
                        _warn(
                            "LAYOUT_OVERFLOW",
                            "Le texte traduit ne tient pas; source conservée sans redaction.",
                            "critical",
                            block_id=block_id,
                            overflow=float(remainder),
                        )
                    )
                    continue
                valid.append(
                    {
                        "page": page_number,
                        "rect": box,
                        "inner": inner,
                        "text": target,
                        "size": used_size,
                        "style": {},
                        "align": 0,
                        "block_ids": [block_id],
                        "table": False,
                        "source_rects": [box],
                        "cover": cover,
                    }
                )
        # Transaction per cell/block: if final fit diverges, restore original
        # state for this unit while retaining earlier successful replacements.
        valid = _drop_text_over_source_ink(doc, ir, valid, issues)
        scanned_numbers = {int(p.get("number", 0)) for p in ir.get("pages", []) if p.get("scanned")}
        # Drawing units. Native page: one transaction per item (as before).
        # Scanned page: all masks of the page first, then all texts, so that no
        # mask (possibly extended over a replaced neighbour) can hide a drawn
        # translation. If a final insertion diverges, the unit is restored and
        # re-planned without that item (masks re-checked against source ink).
        units: dict[tuple[str, int], list[dict[str, Any]]] = {}
        queue: list[tuple[str, int]] = []
        for item in valid:
            key = (
                ("scan", int(item["page"]))
                if int(item["page"]) in scanned_numbers
                else ("item", id(item))
            )
            if key not in units:
                units[key] = []
                queue.append(key)
            units[key].append(item)
        while queue:
            key = queue.pop(0)
            items = units.get(key) or []
            if not items:
                continue
            checkpoint = doc.tobytes()
            page = doc[int(items[0]["page"]) - 1]
            scanned_page = key[0] == "scan"
            for item in items:
                for source_rect in item["source_rects"]:
                    page.add_redact_annot(fitz.Rect(*source_rect), fill=None)
            try:
                # Images are never modified (0 = keep): re-encoding scan strips
                # alters pixels outside the box. Only a hidden text layer is removed.
                page.apply_redactions(images=0, graphics=0, text=0)
            except TypeError:
                page.apply_redactions(images=0, graphics=0)
            if scanned_page:
                from .cover_layer import cover_ocg

                layer = cover_ocg(doc)
                for item in items:
                    cover = item.get("cover")
                    fills = item.get("cover_fills") or []
                    for index, source_rect in enumerate(item["source_rects"]):
                        fill = (
                            (fills[index] if index < len(fills) else None)
                            or cover
                            or _paper_color(page, source_rect)
                        )
                        page.draw_rect(
                            fitz.Rect(*source_rect), color=None, fill=fill, overlay=True, oc=layer
                        )
            failed: tuple[dict[str, Any], float] | None = None
            for item in items:
                kwargs = _font_kwargs(item["size"], item["style"], item["align"])
                kwargs = {key_: value for key_, value in kwargs.items() if value is not None}
                result = page.insert_textbox(fitz.Rect(*item["inner"]), item["text"], **kwargs)
                if result < 0:
                    failed = (item, float(result))
                    break
            if failed is not None:
                bad, result = failed
                overflow_count += 1
                block_ids = [str(b) for b in bad.get("block_ids") or []]
                issues.append(
                    _warn(
                        "LAYOUT_OVERFLOW",
                        "Insertion finale divergente: source de cette cellule restaurée.",
                        "critical",
                        cell_id=bad.get("cell_id"),
                        block_id=block_ids[0] if len(block_ids) == 1 else None,
                        overflow=result,
                    )
                )
                doc.close()
                doc = fitz.open(stream=checkpoint, filetype="pdf")
                remaining = [item for item in items if item is not bad]
                if remaining and scanned_page:
                    remaining = _drop_text_over_source_ink(doc, ir, remaining, issues)
                units[key] = remaining
                if remaining:
                    queue.insert(0, key)
                continue
            for item in items:
                placements.append(
                    {
                        "page": item["page"],
                        "inner": list(item["inner"]),
                        "block_ids": [str(b) for b in item.get("block_ids") or []],
                        "text": item["text"],
                        "cell_id": item.get("cell_id"),
                    }
                )
                original_fonts = [
                    b.get("font_size")
                    for b in ir_pages.get(item["page"], [])
                    if str(b.get("id")) in item["block_ids"] and b.get("font_size")
                ]
                if original_fonts and item["size"] < min(original_fonts) * 0.75:
                    issues.append(
                        _warn(
                            "PDF_FONT_REDUCTION_REQUIRES_REVIEW",
                            "Réduction typographique significative mesurée.",
                            "warning",
                            cell_id=item.get("cell_id"),
                            font_size=item["size"],
                        )
                    )
                changed_blocks += len(item["block_ids"])
                for source_rect in item["source_rects"]:
                    text_masks.append(
                        {"page": item["page"], "bbox": source_rect, "block_ids": item["block_ids"]}
                    )
            # Exclude only actual inserted text glyphs, not whole cells or borders.
            page_blocks = _blocks_from_page(page, int(items[0]["page"]))
            for item in items:
                for target_block in page_blocks:
                    box = _rect(target_block["bbox"])
                    if _contains(item["inner"], box, 1):
                        text_masks.append(
                            {"page": item["page"], "bbox": box, "cell_id": item.get("cell_id")}
                        )
        doc.save(str(out_path), garbage=4, deflate=True)
    finally:
        doc.close()
    candidate_doc = fitz.open(str(out_path))
    try:
        candidate_page_count = len(candidate_doc)
        candidate_tables = _table_records(candidate_doc)
        structure = _normalize_structure(candidate_tables)
    finally:
        candidate_doc.close()
    if not candidate_tables:
        structure_metrics = {
            "tables": {
                "score": None,
                "preserved": None,
                "measured": False,
                "reason": "pdf_table_structure_unvalidated",
            }
        }
    else:
        structure_metrics = {
            "tables": {
                "score": None,
                "preserved": None,
                "measured": False,
                "reason": "candidate_pdf_geometry_unvalidated_semantics",
            }
        }
    return {
        "output_path": str(out_path),
        "issues": issues,
        "changed_blocks": changed_blocks,
        "overflow_count": overflow_count,
        "text_masks": text_masks,
        "placements": placements,
        "table_render_trace": table_trace,
        "table_structure": structure,
        "structure_metrics": structure_metrics,
        "pages_preserved": candidate_page_count == original_page_count,
        "provenance": {"method": "candidate_pdf_drawings_and_text", "semantic_validation": False},
    }


def _cell_geometry(table: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "bbox": list(cell.get("bbox", [])),
            "row": cell.get("row"),
            "column": cell.get("column"),
            "row_span": cell.get("row_span", 1),
            "column_span": cell.get("column_span", 1),
            "fill": cell.get("fill"),
            "border": cell.get("border"),
            "block_ids": list(cell.get("block_ids", [])),
        }
        for cell in table.get("cells", [])
    ]


def _iou(a: list[float], b: list[float]) -> float:
    hit = _intersection(a, b)
    return _area(hit) / max(1.0, _area(a) + _area(b) - _area(hit)) if hit else 0.0


def compare_pdf_tables(
    source: str | Path,
    candidate: str | Path,
    source_ir: dict[str, Any] | None = None,
    translations: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compare independently detected geometry, never claim semantic validation."""
    source_path, candidate_path = Path(source).resolve(), Path(candidate).resolve()
    source_doc, candidate_doc = fitz.open(str(source_path)), fitz.open(str(candidate_path))
    try:
        source_tables = _table_records(source_doc)
        candidate_tables = _table_records(candidate_doc)
    finally:
        source_doc.close()
        candidate_doc.close()
    source_norm, candidate_norm = (
        _normalize_structure(source_tables),
        _normalize_structure(candidate_tables),
    )
    targets, issues, pairs = [], [], []
    with fitz.open(str(candidate_path)) as candidate_document:
        for page in (source_ir or {}).get("pages", []):
            for block in page.get("blocks", []):
                bid = str(block.get("id"))
                if bid not in (translations or {}) or translations[bid] == block.get("text"):
                    continue
                source_box = _rect(block.get("bbox"))
                source_cells = [
                    cell
                    for table in source_tables
                    if table["page"] == page["number"]
                    for cell in table["cells"]
                    if source_box and _contains(_rect(cell["bbox"]), source_box, 2)
                ]
                if not source_cells:
                    continue
                target_text = re.sub(r"\s+", " ", str(translations[bid])).strip()
                seen = False
                matched_ids = []
                for table in candidate_tables:
                    if table["page"] != page["number"]:
                        continue
                    for cell in table["cells"]:
                        box = _rect(cell["bbox"])
                        if any(
                            _iou(box, _rect(original["bbox"])) >= 0.98 for original in source_cells
                        ):
                            # Actual PDF text extracted inside corresponding candidate cell.
                            actual = re.sub(
                                r"\s+",
                                " ",
                                candidate_document[page["number"] - 1].get_textbox(fitz.Rect(box)),
                            ).strip()
                            matched_ids.append(cell["id"])
                            if target_text and target_text in actual:
                                seen = True
                targets.append(
                    {
                        "block_id": bid,
                        "page": page["number"],
                        "candidate_cell_ids": matched_ids,
                        "contained": seen,
                        "measured": True,
                        "semantic_validation": False,
                    }
                )
                if not seen:
                    issues.append(
                        _warn(
                            "PDF_TABLE_CELL_TARGET_MISSING",
                            "Texte cible absent de la cellule candidate correspondante.",
                            "critical",
                            block_id=bid,
                        )
                    )
    for original in source_tables:
        same_page = [table for table in candidate_tables if table["page"] == original["page"]]
        match = (
            max(same_page, key=lambda t: _iou(_rect(original["bbox"]), _rect(t["bbox"])))
            if same_page
            else None
        )
        equal = bool(
            match
            and original["rows"] == match["rows"]
            and original["columns"] == match["columns"]
            and len(original["cells"]) == len(match["cells"])
        )
        scores = []
        format_equal = equal
        if match:
            for cell in original["cells"]:
                candidates = match["cells"]
                other = (
                    max(candidates, key=lambda c: _iou(_rect(cell["bbox"]), _rect(c["bbox"])))
                    if candidates
                    else None
                )
                scores.append(_iou(_rect(cell["bbox"]), _rect(other["bbox"])) if other else 0.0)
                format_equal = format_equal and bool(
                    other
                    and all(
                        cell.get(k) == other.get(k)
                        for k in ("row_span", "column_span", "fill", "border")
                    )
                )
        else:
            scores = [0.0]
        pairs.append(
            {
                "source_table_id": original["id"],
                "candidate_table_id": match["id"] if match else None,
                "cell_geometry_score": sum(scores) / len(scores) if scores else 0.0,
                "structure_equal": equal,
                "graphic_format_equal": format_equal,
            }
        )
    if not source_tables and not candidate_tables:
        metrics = {
            "tables": {
                "score": None,
                "preserved": None,
                "measured": False,
                "reason": "no_real_table_detected",
            }
        }
    else:
        equal = len(source_tables) == len(candidate_tables) and all(
            p["structure_equal"] and p["graphic_format_equal"] for p in pairs
        )
        if not equal:
            issues.append(
                _warn(
                    "PDF_TABLE_STRUCTURE_CHANGED",
                    "Cellules/fusions/bordures/couleurs candidates différentes de la source.",
                    "critical",
                )
            )
        metrics = {
            "tables": {
                "score": float(equal),
                "preserved": equal,
                "measured": True,
                "reason": "independent_candidate_geometry_and_graphic_invariants",
                "semantically_validated": False,
            },
            "cell_targets": {
                "score": sum(t["contained"] for t in targets) / len(targets) if targets else None,
                "measured": bool(targets),
                "translated_cells": len(targets),
            },
        }
    return {
        "source": source_norm,
        "candidate": candidate_norm,
        "source_tables": source_norm,
        "candidate_tables": candidate_norm,
        "table_records": {"source": source_norm, "candidate": candidate_norm},
        "targets": targets,
        "matches": pairs,
        "structure_metrics": metrics,
        "issues": issues,
        "semantically_validated": False,
        "provenance": "independent_source_candidate_pdf_geometry",
    }
