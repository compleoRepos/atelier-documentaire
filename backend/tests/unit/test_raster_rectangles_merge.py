"""Raster rectangle search: exact equivalence, bounded cost, visible limits."""

from __future__ import annotations

import time

import numpy as np
from PIL import Image

from app.documents import layout
from app.documents.layout import _line_groups, _LineSpatialIndex, _raster_segments_with_status


def _reference_rectangles(segments):
    """Exhaustive O(G^4) definition used before the merge (behavioural oracle)."""
    horizontal = [s for s in segments if s["axis"] == "h"]
    vertical = [s for s in segments if s["axis"] == "v"]
    h_groups, _ = _line_groups(horizontal, tolerance=2.0, minimum_span=6.0, limit=128)
    v_groups, _ = _line_groups(vertical, tolerance=2.0, minimum_span=6.0, limit=128)
    hi, vi = _LineSpatialIndex(horizontal), _LineSpatialIndex(vertical)
    found = []
    for a, y0 in enumerate(h_groups):
        for y1 in h_groups[a + 1 :]:
            if not 5 <= y1 - y0 <= 80:
                continue
            for b, x0 in enumerate(v_groups):
                for x1 in v_groups[b + 1 :]:
                    if not 5 <= x1 - x0 <= 80:
                        continue
                    if (
                        hi.present(y0, x0, x1, 3)
                        and hi.present(y1, x0, x1, 3)
                        and vi.present(x0, y0, y1, 3)
                        and vi.present(x1, y0, y1, 3)
                    ):
                        found.append([x0, y0, x1, y1])
                        if len(found) >= 4096:
                            return found
    return found


def _random_page(seed, size=320):
    rng = np.random.default_rng(seed)
    img = np.full((size, size), 255, dtype=np.uint8)
    for _ in range(int(rng.integers(3, 12))):
        y0, x0 = int(rng.integers(0, size - 30)), int(rng.integers(0, size - 30))
        y1 = min(size - 1, y0 + int(rng.integers(6, 90)))
        x1 = min(size - 1, x0 + int(rng.integers(6, 90)))
        img[y0, x0:x1] = 0
        img[y1, x0:x1] = 0
        img[y0:y1, x0] = 0
        img[y0:y1, x1] = 0
    img[rng.random((size, size)) < 0.03] = 0
    return img


def test_rectangles_are_identical_to_exhaustive_reference_including_order():
    for seed in range(12):
        segments, rectangles, _size, _limited = _raster_segments_with_status(
            Image.fromarray(_random_page(seed))
        )
        assert rectangles == _reference_rectangles(segments)


def test_dense_ruled_page_is_bounded_in_time_and_reports_saturation():
    img = np.full((1400, 1000), 255, dtype=np.uint8)
    img[::12, :] = 0  # dense form grid: worst case for the former O(G^4) scan
    img[:, ::12] = 0
    started = time.perf_counter()
    _segments, rectangles, _size, limited = _raster_segments_with_status(Image.fromarray(img))
    assert time.perf_counter() - started < 20
    assert limited is True
    assert len(rectangles) == layout._MAX_RASTER_RECTANGLES


def test_work_budget_is_reported_as_review_not_as_full_coverage(monkeypatch):
    monkeypatch.setattr(layout, "_MAX_RASTER_PRESENCE_CHECKS", 10)
    img = np.full((300, 300), 255, dtype=np.uint8)
    img[::20, :] = 0
    img[:, ::20] = 0
    _segments, _rects, _size, limited = _raster_segments_with_status(Image.fromarray(img))
    assert limited is True
    result = layout.detect_layout(Image.fromarray(img), page_number=1)
    assert "RASTER_RECTANGLE_LIMIT_REQUIRES_REVIEW" in result["human_uncertainty"]
