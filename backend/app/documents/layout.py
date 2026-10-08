"""Deterministic, evidence-first layout candidates for scanned and native pages.

The detector deliberately reports *candidates*, not semantic truth.  It can find
geometry from PDF drawings or a raster without downloading a model.  Text blocks
are never copied into cells: cells link the IDs already present in the page IR.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

PROVENANCE = "candidate_unvalidated"

# Raster scans can contain thousands of short glyph strokes.  These bounds are
# deliberately conservative: when evidence exceeds them we report uncertainty
# instead of silently truncating a grid and manufacturing cells.
_MAX_RASTER_AXIS_GROUPS = 128
_MAX_RASTER_RECTANGLES = 4096
_MAX_GRID_CELLS = 4096
# Upper bound on line-presence evaluations for raster rectangle search on one
# page. Reaching it is reported (RASTER_RECTANGLE_LIMIT_REQUIRES_REVIEW), never
# silently treated as full coverage.
_MAX_RASTER_PRESENCE_CHECKS = 1_500_000


def _rect(values: Any) -> list[float] | None:
    if values is None:
        return None
    try:
        values = list(values)
        if len(values) < 4:
            return None
        x0, y0, x1, y1 = map(float, values[:4])
    except (TypeError, ValueError):
        return None
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if x1 - x0 <= 1 or y1 - y0 <= 1:
        return None
    return [x0, y0, x1, y1]


def _area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection(a: list[float], b: list[float]) -> list[float] | None:
    hit = [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]
    return hit if hit[2] > hit[0] and hit[3] > hit[1] else None


def _group(values: list[float], tolerance: float = 3.0) -> list[float]:
    if not values:
        return []
    result: list[list[float]] = []
    for value in sorted(values):
        if result and abs(value - sum(result[-1]) / len(result[-1])) <= tolerance:
            result[-1].append(value)
        else:
            result.append([value])
    return [sum(group) / len(group) for group in result]


def _line_groups(
    lines: list[dict[str, float]],
    *,
    tolerance: float = 2.0,
    minimum_span: float = 0.0,
    limit: int | None = None,
) -> tuple[list[float], bool]:
    """Group line coordinates, retaining the strongest bounded evidence.

    Grouping is performed once over sorted coordinates.  If there are more
    groups than the limit, the longest groups win; the boolean tells callers
    that a review marker is required rather than pretending the input was
    complete.
    """
    candidates = [
        (float(line["coord"]), float(line["end"] - line["start"]))
        for line in lines
        if line["end"] - line["start"] >= minimum_span
    ]
    if not candidates:
        return [], False
    grouped: list[list[float]] = []
    strongest: list[float] = []
    for coord, span in sorted(candidates):
        if grouped and abs(coord - sum(grouped[-1]) / len(grouped[-1])) <= tolerance:
            grouped[-1].append(coord)
            strongest[-1] = max(strongest[-1], span)
        else:
            grouped.append([coord])
            strongest.append(span)
    records = [
        (sum(group) / len(group), span)
        for group, span in zip(grouped, strongest, strict=True)
    ]
    limited = False
    if limit is not None and len(records) > limit:
        records = sorted(records, key=lambda item: item[1], reverse=True)[:limit]
        limited = True
    return sorted(coord for coord, _ in records), limited


class _LineSpatialIndex:
    """Coordinate index for line presence queries.

    Queries inspect only lines whose axis coordinate is within tolerance,
    rather than scanning every segment for every candidate rectangle/cell.
    """

    def __init__(self, lines: list[dict[str, float]]):
        self.lines = sorted(lines, key=lambda line: line["coord"])
        self.coords = [line["coord"] for line in self.lines]
        self._starts = np.asarray([line["start"] for line in self.lines], dtype=float)
        self._ends = np.asarray([line["end"] for line in self.lines], dtype=float)

    def present(self, coord: float, start: float, end: float, tolerance: float = 3.0) -> bool:
        needed = max(8.0, end - start)
        first = bisect_left(self.coords, coord - tolerance)
        last = bisect_right(self.coords, coord + tolerance)
        if last - first <= 16:
            for line in self.lines[first:last]:
                overlap = max(0.0, min(end, line["end"]) - max(start, line["start"]))
                if overlap / needed >= 0.55:
                    return True
            return False
        # Same predicate, vectorised for dense windows (text-heavy scan rows).
        overlap = np.minimum(end, self._ends[first:last]) - np.maximum(
            start, self._starts[first:last]
        )
        return bool(np.any(np.maximum(overlap, 0.0) / needed >= 0.55))


def _drawing_segments(page: Any) -> tuple[list[dict[str, float]], list[list[float]]]:
    horizontal: list[dict[str, float]] = []
    vertical: list[dict[str, float]] = []
    rectangles: list[list[float]] = []
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    for drawing in drawings:
        for item in drawing.get("items", []):
            if not item:
                continue
            op = item[0]
            if op == "l" and len(item) >= 3:
                p0, p1 = item[1], item[2]
                x0, y0, x1, y1 = float(p0.x), float(p0.y), float(p1.x), float(p1.y)
                if abs(y1 - y0) <= 2 and abs(x1 - x0) > 8:
                    horizontal.append(
                        {
                            "axis": "h",
                            "coord": (y0 + y1) / 2,
                            "start": min(x0, x1),
                            "end": max(x0, x1),
                        }
                    )
                elif abs(x1 - x0) <= 2 and abs(y1 - y0) > 8:
                    vertical.append(
                        {
                            "axis": "v",
                            "coord": (x0 + x1) / 2,
                            "start": min(y0, y1),
                            "end": max(y0, y1),
                        }
                    )
            elif op == "re" and len(item) >= 2:
                box = _rect(item[1])
                if box:
                    rectangles.append(box)
                    horizontal.extend(
                        (
                            {"axis": "h", "coord": box[1], "start": box[0], "end": box[2]},
                            {"axis": "h", "coord": box[3], "start": box[0], "end": box[2]},
                        )
                    )
                    vertical.extend(
                        (
                            {"axis": "v", "coord": box[0], "start": box[1], "end": box[3]},
                            {"axis": "v", "coord": box[2], "start": box[1], "end": box[3]},
                        )
                    )
    return horizontal + vertical, rectangles


def _raster_segments(
    image: Any,
) -> tuple[list[dict[str, float]], list[list[float]], tuple[int, int] | None]:
    segments, rectangles, size, _limited = _raster_segments_with_status(image)
    return segments, rectangles, size


def _raster_segments_with_status(
    image: Any,
) -> tuple[list[dict[str, float]], list[list[float]], tuple[int, int] | None, bool]:
    """Raster lines and closed small boxes, plus whether the search was bounded."""
    if image is None:
        return [], [], None, False
    try:
        from PIL import Image

        if isinstance(image, (str, Path)):
            image = Image.open(image)
        if hasattr(image, "convert"):
            image = image.convert("L")
            array = np.asarray(image)
        else:
            array = np.asarray(image)
            if array.ndim == 3:
                array = array[..., :3].mean(axis=2)
    except Exception:
        return [], [], None, False
    if array.ndim != 2 or not array.size:
        return [], [], None, False
    dark = array < 190
    height, width = dark.shape
    horizontal: list[dict[str, float]] = []
    vertical: list[dict[str, float]] = []
    # This pure-numpy fallback catches ruled lines without making OpenCV a
    # mandatory runtime dependency.  Runs are retained, not text pixels.
    for y, row in enumerate(dark):
        indexes = np.flatnonzero(row)
        if len(indexes) < max(6, min(12, int(width * 0.20))):
            continue
        starts = np.split(indexes, np.where(np.diff(indexes) > 2)[0] + 1)
        for run in starts:
            if len(run) >= 6:
                horizontal.append(
                    {"axis": "h", "coord": float(y), "start": float(run[0]), "end": float(run[-1])}
                )
    for x, column in enumerate(dark.T):
        indexes = np.flatnonzero(column)
        if len(indexes) < max(6, min(12, int(height * 0.20))):
            continue
        starts = np.split(indexes, np.where(np.diff(indexes) > 2)[0] + 1)
        for run in starts:
            if len(run) >= 6:
                vertical.append(
                    {"axis": "v", "coord": float(x), "start": float(run[0]), "end": float(run[-1])}
                )
    rectangles: list[list[float]] = []
    # Reconstruct small closed boxes from four near-complete raster lines. This
    # intentionally reports geometry only; checked/unchecked state is human
    # uncertainty, never an inferred semantic value.
    h_groups, _ = _line_groups(
        horizontal, tolerance=2.0, minimum_span=6.0, limit=_MAX_RASTER_AXIS_GROUPS
    )
    v_groups, _ = _line_groups(
        vertical, tolerance=2.0, minimum_span=6.0, limit=_MAX_RASTER_AXIS_GROUPS
    )
    horizontal_index = _LineSpatialIndex(horizontal)
    vertical_index = _LineSpatialIndex(vertical)
    # Equivalent to the exhaustive y0<y1, x0<x1 scan (same predicate, same
    # output order), without its O(G^4) Python cost: for each horizontal pair
    # the vertical edges are filtered once, and horizontal checks are cached.
    # Groups are sorted, so an axis gap above 80 ends the inner loop.
    checks = 0
    horizontal_cache: dict[tuple[float, float, float], bool] = {}

    def horizontal_present(y: float, x0: float, x1: float) -> bool:
        nonlocal checks
        key = (y, x0, x1)
        cached = horizontal_cache.get(key)
        if cached is None:
            checks += 1
            cached = horizontal_index.present(y, x0, x1, 3)
            horizontal_cache[key] = cached
        return cached

    for y0_index, y0 in enumerate(h_groups):
        for y1 in h_groups[y0_index + 1 :]:
            if y1 - y0 > 80:
                break
            if y1 - y0 < 5:
                continue
            if checks + len(v_groups) > _MAX_RASTER_PRESENCE_CHECKS:
                return horizontal + vertical, rectangles, (width, height), True
            checks += len(v_groups)
            edges = [x for x in v_groups if vertical_index.present(x, y0, y1, 3)]
            for x0_index, x0 in enumerate(edges):
                for x1 in edges[x0_index + 1 :]:
                    if x1 - x0 > 80:
                        break
                    if x1 - x0 < 5:
                        continue
                    if horizontal_present(y0, x0, x1) and horizontal_present(y1, x0, x1):
                        rectangles.append([x0, y0, x1, y1])
                        if len(rectangles) >= _MAX_RASTER_RECTANGLES:
                            return horizontal + vertical, rectangles, (width, height), True
                    if checks > _MAX_RASTER_PRESENCE_CHECKS:
                        return horizontal + vertical, rectangles, (width, height), True
    return horizontal + vertical, rectangles, (width, height), False


def _raster_grid_lines(
    lines: list[dict[str, float]],
) -> list[dict[str, float]]:
    """Keep likely ruled geometry, excluding short pseudo-text strokes.

    The threshold is relative to the strongest line on the same axis, with a
    floor for small pages.  Thus a 20px checkbox survives alone, while it does
    not get combined with a 260px table merely because both are on the page.
    """
    if not lines:
        return []
    longest = max(line["end"] - line["start"] for line in lines)
    threshold = max(12.0, longest * 0.10)
    return [line for line in lines if line["end"] - line["start"] >= threshold]


def _line_present(
    lines: list[dict[str, float]],
    coord: float,
    start: float,
    end: float,
    tolerance: float = 3.0,
    index: _LineSpatialIndex | None = None,
) -> bool:
    return (index or _LineSpatialIndex(lines)).present(coord, start, end, tolerance)


def _link_blocks(box: list[float], blocks: list[dict[str, Any]]) -> list[str]:
    linked: list[str] = []
    for block in blocks:
        block_box = _rect(block.get("bbox"))
        if not block_box:
            continue
        hit = _intersection(box, block_box)
        if hit and _area(hit) / max(1.0, _area(block_box)) >= 0.05:
            linked.append(str(block["id"]))
            continue
        cx = (block_box[0] + block_box[2]) / 2
        cy = (block_box[1] + block_box[3]) / 2
        if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
            linked.append(str(block["id"]))
    return linked


def _cell_candidates(
    x_coords: list[float],
    y_coords: list[float],
    horizontal: list[dict[str, float]],
    vertical: list[dict[str, float]],
    blocks: list[dict[str, Any]],
    page_number: int,
    table_index: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw: dict[tuple[int, int], dict[str, Any]] = {}
    horizontal_index = _LineSpatialIndex(horizontal)
    vertical_index = _LineSpatialIndex(vertical)
    for row in range(len(y_coords) - 1):
        for column in range(len(x_coords) - 1):
            box = [x_coords[column], y_coords[row], x_coords[column + 1], y_coords[row + 1]]
            raw[(row, column)] = {
                "row": row,
                "column": column,
                "bbox": box,
                "block_ids": _link_blocks(box, blocks),
            }
    parent = {key: key for key in raw}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    # Missing internal dividers are evidence for a merge.  The outer grid
    # remains atomic and is never cut to fit a translation.
    for row in range(len(y_coords) - 1):
        for column in range(len(x_coords) - 2):
            boundary = x_coords[column + 1]
            if not _line_present(
                vertical, boundary, y_coords[row], y_coords[row + 1], index=vertical_index
            ):
                union((row, column), (row, column + 1))
    for row in range(len(y_coords) - 2):
        for column in range(len(x_coords) - 1):
            boundary = y_coords[row + 1]
            if not _line_present(
                horizontal, boundary, x_coords[column], x_coords[column + 1], index=horizontal_index
            ):
                union((row, column), (row + 1, column))
    groups: dict[Any, list[tuple[int, int]]] = defaultdict(list)
    for key in raw:
        groups[find(key)].append(key)
    cells: list[dict[str, Any]] = []
    merges: list[dict[str, Any]] = []
    for index, members in enumerate(sorted(groups.values(), key=lambda values: min(values))):
        rows = [item[0] for item in members]
        columns = [item[1] for item in members]
        box = [
            x_coords[min(columns)],
            y_coords[min(rows)],
            x_coords[max(columns) + 1],
            y_coords[max(rows) + 1],
        ]
        linked = sorted({block_id for member in members for block_id in raw[member]["block_ids"]})
        cell = {
            "id": f"p{page_number:03d}-table-{table_index:03d}-cell-{index:03d}",
            "row": min(rows),
            "column": min(columns),
            "row_span": max(rows) - min(rows) + 1,
            "column_span": max(columns) - min(columns) + 1,
            "bbox": box,
            "block_ids": linked,
            "text": "",  # Text is resolved by existing block IDs; never duplicated.
            "provenance": PROVENANCE,
        }
        cells.append(cell)
        if cell["row_span"] > 1 or cell["column_span"] > 1:
            merges.append(
                {
                    "cell_id": cell["id"],
                    "row_span": cell["row_span"],
                    "column_span": cell["column_span"],
                }
            )
    return cells, merges


def _unruled_candidate(
    blocks: list[dict[str, Any]], page_number: int, table_index: int
) -> dict[str, Any] | None:
    positioned = []
    for block in blocks:
        box = _rect(block.get("bbox"))
        if box and str(block.get("text", "")).strip():
            positioned.append((box, block))
    if len(positioned) < 4:
        return None
    positioned.sort(key=lambda item: ((item[0][1] + item[0][3]) / 2, item[0][0]))
    rows: list[list[tuple[list[float], dict[str, Any]]]] = []
    for box, block in positioned:
        cy = (box[1] + box[3]) / 2
        if not rows or abs(
            cy - sum((item[0][1] + item[0][3]) / 2 for item in rows[-1]) / len(rows[-1])
        ) > max(8, (box[3] - box[1]) * 1.2):
            rows.append([])
        rows[-1].append((box, block))
    if len(rows) < 2 or not all(len(row) >= 2 for row in rows):
        return None
    all_boxes = [item[0] for item in positioned]
    outer = [
        min(box[0] for box in all_boxes),
        min(box[1] for box in all_boxes),
        max(box[2] for box in all_boxes),
        max(box[3] for box in all_boxes),
    ]
    cells = []
    for row_index, row in enumerate(rows):
        for column_index, (box, block) in enumerate(sorted(row, key=lambda item: item[0][0])):
            cells.append(
                {
                    "id": f"p{page_number:03d}-table-{table_index:03d}-cell-{len(cells):03d}",
                    "row": row_index,
                    "column": column_index,
                    "row_span": 1,
                    "column_span": 1,
                    "bbox": box,
                    "block_ids": [str(block["id"])],
                    "text": "",
                    "provenance": PROVENANCE,
                }
            )
    return {
        "id": f"table-p{page_number:03d}-{table_index:03d}",
        "page": page_number,
        "bbox": outer,
        "rows": len(rows),
        "columns": max(len(row) for row in rows),
        "cells": cells,
        "merges": [],
        "confidence": 0.32,
        "provenance": PROVENANCE,
        "human_uncertainty": ["UNRULED_TABLE_REQUIRES_REVIEW"],
        "candidate_reason": "text_row_clustering_without_ruled_lines",
        "atomic": True,
    }


def detect_layout(
    source: Any = None,
    *,
    page: Any = None,
    blocks: list[dict[str, Any]] | None = None,
    page_number: int = 1,
    width: float | None = None,
    height: float | None = None,
) -> dict[str, Any]:
    """Return conservative graphical candidates linked to existing text blocks."""
    blocks = list(blocks or [])
    segments: list[dict[str, float]] = []
    drawing_segments: list[dict[str, float]] = []
    rectangles: list[list[float]] = []
    raster_size = None
    if page is not None:
        drawing_segments, rectangles = _drawing_segments(page)
        segments.extend(drawing_segments)
    raster_segments, raster_rectangles, raster_size, raster_search_limited = (
        _raster_segments_with_status(source)
    )
    if raster_segments:
        segments.extend(raster_segments)
    rectangles.extend(raster_rectangles)
    unique_rectangles: list[list[float]] = []
    seen_rectangles: set[tuple[float, ...]] = set()
    for box in rectangles:
        key = tuple(box)
        if key not in seen_rectangles:
            seen_rectangles.add(key)
            unique_rectangles.append(box)
    rectangles = unique_rectangles
    if raster_size:
        width, height = raster_size
    width = float(width or 0)
    height = float(height or 0)
    # Raster segments need orientation recovery from span and page dimensions;
    # a line longer than its opposite axis is horizontal/vertical by coordinate
    # family. Drawing extraction already supplies one coordinate per orientation.
    horizontal = [
        item for item in segments if item.get("axis") == "h" and item["end"] - item["start"] > 8
    ]
    vertical = [
        item for item in segments if item.get("axis") == "v" and item["end"] - item["start"] > 8
    ]
    raster_horizontal = [
        item
        for item in raster_segments
        if item.get("axis") == "h" and item["end"] - item["start"] > 8
    ]
    raster_vertical = [
        item
        for item in raster_segments
        if item.get("axis") == "v" and item["end"] - item["start"] > 8
    ]
    drawing_horizontal = [
        item for item in drawing_segments if item.get("axis") == "h" and item["end"] - item["start"] > 8
    ]
    drawing_vertical = [
        item for item in drawing_segments if item.get("axis") == "v" and item["end"] - item["start"] > 8
    ]
    grid_horizontal = drawing_horizontal + _raster_grid_lines(raster_horizontal)
    grid_vertical = drawing_vertical + _raster_grid_lines(raster_vertical)
    x_coords, x_limited = _line_groups(
        grid_vertical, tolerance=3.0, minimum_span=8.0, limit=_MAX_RASTER_AXIS_GROUPS
    )
    y_coords, y_limited = _line_groups(
        grid_horizontal, tolerance=3.0, minimum_span=8.0, limit=_MAX_RASTER_AXIS_GROUPS
    )
    uncertainty = ["SIGNATURE_OR_STAMP_IDENTITY_NOT_INFERRED"]
    if x_limited or y_limited:
        uncertainty.append("GRAPHICAL_GRID_LIMIT_REQUIRES_REVIEW")
    if raster_segments:
        _, raster_rect_groups_limited = _line_groups(
            raster_horizontal, tolerance=2.0, minimum_span=6.0, limit=_MAX_RASTER_AXIS_GROUPS
        )
        _, raster_col_groups_limited = _line_groups(
            raster_vertical, tolerance=2.0, minimum_span=6.0, limit=_MAX_RASTER_AXIS_GROUPS
        )
        if raster_rect_groups_limited or raster_col_groups_limited:
            uncertainty.append("RASTER_RECTANGLE_LIMIT_REQUIRES_REVIEW")
        if len(raster_rectangles) >= _MAX_RASTER_RECTANGLES:
            uncertainty.append("RASTER_RECTANGLE_LIMIT_REQUIRES_REVIEW")
    if raster_search_limited:
        uncertainty.append("RASTER_RECTANGLE_LIMIT_REQUIRES_REVIEW")
    grid_too_large = (len(x_coords) - 1) * (len(y_coords) - 1) > _MAX_GRID_CELLS
    if grid_too_large:
        uncertainty.append("GRAPHICAL_GRID_LIMIT_REQUIRES_REVIEW")
    uncertainty = list(dict.fromkeys(uncertainty))
    tables: list[dict[str, Any]] = []
    if len(x_coords) >= 2 and len(y_coords) >= 2 and not (x_limited or y_limited or grid_too_large):
        # Reject a page-spanning accidental combination of unrelated lines.
        box = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
        if box[2] - box[0] > 24 and box[3] - box[1] > 18:
            cells, merges = _cell_candidates(
                x_coords, y_coords, horizontal, vertical, blocks, page_number, 0
            )
            tables.append(
                {
                    "id": f"table-p{page_number:03d}-000",
                    "page": page_number,
                    "bbox": box,
                    "rows": len(y_coords) - 1,
                    "columns": len(x_coords) - 1,
                    "cells": cells,
                    "merges": merges,
                    "confidence": 0.68,
                    "provenance": PROVENANCE,
                    "human_uncertainty": ["GRAPHICAL_TABLE_CANDIDATE_REQUIRES_REVIEW"],
                    "atomic": True,
                }
            )
    if not tables:
        candidate = _unruled_candidate(blocks, page_number, 0)
        if candidate:
            tables.append(candidate)
    checkboxes: list[dict[str, Any]] = []
    for box in rectangles:
        w, h = box[2] - box[0], box[3] - box[1]
        if 6 <= w <= 40 and 6 <= h <= 40 and 0.55 <= w / max(h, 1) <= 1.8:
            checkboxes.append(
                {
                    "id": f"p{page_number:03d}-checkbox-{len(checkboxes):03d}",
                    "bbox": box,
                    "kind": "checkbox_candidate",
                    "provenance": PROVENANCE,
                    "human_uncertainty": ["CHECKBOX_STATE_REQUIRES_REVIEW"],
                }
            )
    figures = [
        {
            "id": f"p{page_number:03d}-graphic-{index:03d}",
            "bbox": box,
            "kind": "graphic_candidate",
            "provenance": PROVENANCE,
            "human_uncertainty": ["GRAPHIC_SEMANTICS_REQUIRES_REVIEW"],
        }
        for index, box in enumerate(rectangles)
        if box not in [item.get("bbox") for item in checkboxes]
    ]
    forms = []
    for table in tables:
        if checkboxes:
            forms.append(
                {
                    "id": f"p{page_number:03d}-form-{len(forms):03d}",
                    "bbox": table["bbox"],
                    "kind": "form_region_candidate",
                    "provenance": PROVENANCE,
                    "human_uncertainty": ["FORM_FIELD_SEMANTICS_REQUIRES_REVIEW"],
                    "checkbox_ids": [item["id"] for item in checkboxes],
                }
            )
    return {
        "tables": tables,
        "figures": figures,
        "forms": forms,
        "checkboxes": checkboxes,
        "provenance": PROVENANCE,
        "human_uncertainty": uncertainty,
        "coverage": {
            "line_segments": len(horizontal) + len(vertical),
            "rectangles": len(rectangles),
            "text_blocks_linked": sum(
                bool(cell.get("block_ids")) for table in tables for cell in table["cells"]
            ),
        },
    }


# Explicit alias for callers that use the page-oriented name.
def detect_page_layout(*args, **kwargs):
    return detect_layout(*args, **kwargs)
