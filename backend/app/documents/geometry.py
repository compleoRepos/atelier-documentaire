"""Exact planar geometry helpers shared by render and visual metrics.

F32 (run27): page mask coverage was the SUM of the mask areas. Line masks,
block masks and cover pieces overlap, so the same pixels were counted up to
twice: on a dense scanned letter every page reported 37-74 % "masked" while
the masks actually covered at most 28 % of the page (the text area). The
coverage is now the area of the UNION of the masks; the limit is unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def union_area(boxes: Iterable[Sequence[float]]) -> float:
    """Exact area of the union of axis-aligned rectangles ``[x0, y0, x1, y1]``.

    Sweep over the vertical slabs between consecutive x coordinates; in each
    slab the y intervals of the rectangles spanning it are merged. Degenerate
    or malformed rectangles contribute nothing."""
    rects = []
    for box in boxes:
        try:
            x0, y0, x1, y1 = (float(v) for v in box)
        except (TypeError, ValueError):
            continue
        if x1 > x0 and y1 > y0:
            rects.append((x0, y0, x1, y1))
    if not rects:
        return 0.0
    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    total = 0.0
    for left, right in zip(xs, xs[1:], strict=False):
        spans = sorted((r[1], r[3]) for r in rects if r[0] <= left and r[2] >= right)
        covered = 0.0
        start = end = None
        for low, high in spans:
            if end is None or low > end:
                if end is not None:
                    covered += end - start
                start, end = low, high
            else:
                end = max(end, high)
        if end is not None:
            covered += end - start
        total += covered * (right - left)
    return total
