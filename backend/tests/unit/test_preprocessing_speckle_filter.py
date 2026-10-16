"""Colour-scan chroma speckles must not become stamp/logo candidates.

Regression observed on a real colour scan: about 2,800 tiny coloured JPEG
artefacts inside words were protected, which blocked most translations.
"""

from __future__ import annotations

import numpy as np

from app.documents.preprocessing import protected_candidates

# A4 at 150 dpi: 1240 x 1754 px, i.e. about 5.9 px per mm.
W, H = 1240, 1754
BLUE = (30, 60, 200)
PINK = (250, 120, 200)


def _page():
    return np.full((H, W, 3), 255, np.uint8)


def _stamps(rgb):
    return [r for r in protected_candidates(rgb) if r["subtype"] == "stamp_or_logo_candidate"]


def test_isolated_chroma_speckles_are_not_candidates():
    rgb = _page()
    rng = np.random.default_rng(7)
    # Isolated 3 px speckles on a jittered 40 px grid (about 7 mm apart).
    for gx in range(100, 1100, 40):
        for gy in range(100, 1600, 40):
            x, y = gx + int(rng.integers(-5, 6)), gy + int(rng.integers(-5, 6))
            rgb[y : y + 3, x : x + 3] = BLUE
    assert _stamps(rgb) == []


def test_sparse_speckle_cluster_is_rejected_by_ink_density():
    rgb = _page()
    for x in range(400, 440, 9):
        for y in range(600, 630, 9):
            rgb[y, x] = BLUE
    assert _stamps(rgb) == []


def test_real_stamp_and_highlight_are_still_candidates():
    rgb = _page()
    yy, xx = np.ogrid[:H, :W]
    ring = np.abs(np.hypot(xx - 900, yy - 1400) - 110) < 6  # ~37 mm round stamp
    rgb[ring] = BLUE
    rgb[400:440, 200:520] = PINK  # ~54 x 7 mm highlighter stroke
    boxes = [r["bbox"] for r in _stamps(rgb)]
    assert any(b[0] < 800 and b[2] > 1000 and b[1] < 1300 and b[3] > 1500 for b in boxes)
    assert any(b[0] <= 205 and b[2] >= 515 and b[1] <= 405 and b[3] >= 435 for b in boxes)
