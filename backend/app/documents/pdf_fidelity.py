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


def _fit_on_scratch(
    source_bytes: bytes,
    page_number: int,
    rect: fitz.Rect,
    text: str,
    size: float,
    style: dict[str, Any],
    align: int,
) -> tuple[bool, float, float]:
    scratch = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        result = -1.0
        current = size
        minimum = max(4.0, min(size, rect.height * 0.32))
        for _ in range(8):
            kwargs = _font_kwargs(current, style, align)
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            result = scratch[page_number - 1].insert_textbox(rect, text, **kwargs)
            if result >= 0:
                return True, result, current
            current *= 0.86
            if current < minimum:
                break
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


def _line_count(text: str) -> int:
    return max(1, len([line for line in str(text).splitlines() if line.strip()]))


def _scan_line_size(block: dict[str, Any]) -> float | None:
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
    # Same body text keeps one size; only genuinely smaller print keeps its own.
    size = body if body and own >= 0.75 * body else own
    return max(6.0, min(14.0, size))


def _shrink_away(box: list[float], others: list[list[float]]) -> list[float] | None:
    """Shrink ``box`` on the side of each overlapping neighbour (OCR line boxes
    swollen by nearby handwriting). Refused if less than 40 % would remain."""
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    for other in others:
        if not _strict_overlap([x0, y0, x1, y1], other):
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ox, oy = (other[0] + other[2]) / 2, (other[1] + other[3]) / 2
        if ox > cx and other[0] > x0 + 0.4 * width:
            x1 = min(x1, other[0] - 0.5)
        elif ox < cx and other[2] < x1 - 0.4 * width:
            x0 = max(x0, other[2] + 0.5)
        elif oy > cy:
            y1 = min(y1, other[1] - 0.5)
        else:
            y0 = max(y0, other[3] + 0.5)
    shrunk = [x0, y0, x1, y1]
    if x1 - x0 < 0.4 * width or y1 - y0 < 0.4 * height:
        return None
    if any(_strict_overlap(shrunk, other) for other in others):
        return None
    return shrunk


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


def _grow_right(box: list[float], limit: float, obstacles: list[list[float]]) -> list[float]:
    x0, y0, x1, y1 = box
    while x1 + 2 <= limit and not any(_strict_overlap([x1, y0, x1 + 2, y1], o) for o in obstacles):
        x1 += 2
    return [x0, y0, x1, y1]


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
                    ok, remainder, used_size = _fit_on_scratch(
                        source_bytes,
                        page_number,
                        fitz.Rect(*inner),
                        target_text,
                        size,
                        style,
                        align,
                    )
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
                            "source_rects": [list(b["bbox"]) for b in blocks],
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
        for item in valid:
            checkpoint = doc.tobytes()
            page = doc[item["page"] - 1]
            for source_rect in item["source_rects"]:
                page.add_redact_annot(fitz.Rect(*source_rect), fill=None)
            scanned_page = next(
                (
                    p.get("scanned", False)
                    for p in ir.get("pages", [])
                    if p.get("number") == item["page"]
                ),
                False,
            )
            try:
                # Images are never modified (0 = keep): re-encoding scan strips
                # alters pixels outside the box. Only a hidden text layer is removed.
                page.apply_redactions(images=0, graphics=0, text=0)
            except TypeError:
                page.apply_redactions(images=0, graphics=0)
            if scanned_page:
                cover = item.get("cover")
                from .cover_layer import cover_ocg

                layer = cover_ocg(doc)
                for source_rect in item["source_rects"]:
                    fill = cover or _paper_color(page, source_rect)
                    page.draw_rect(
                        fitz.Rect(*source_rect), color=None, fill=fill, overlay=True, oc=layer
                    )
            kwargs = _font_kwargs(item["size"], item["style"], item["align"])
            kwargs = {key: value for key, value in kwargs.items() if value is not None}
            result = page.insert_textbox(fitz.Rect(*item["inner"]), item["text"], **kwargs)
            if result < 0:
                overflow_count += 1
                issues.append(
                    _warn(
                        "LAYOUT_OVERFLOW",
                        "Insertion finale divergente: source de cette cellule restaurée.",
                        "critical",
                        cell_id=item.get("cell_id"),
                        overflow=float(result),
                    )
                )
                doc.close()
                doc = fitz.open(stream=checkpoint, filetype="pdf")
                continue
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
            for target_block in _blocks_from_page(page, item["page"]):
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
