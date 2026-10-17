"""RUN29 layout regressions F43/F44/F45 (synthetic rasters and invented text
only; no document of the private corpus is used, no text of it either).

- F43: a paper cover stopped a fraction of a point short of a protected region
  (checkbox, stamp, signature) shares a raster pixel with the region's edge at
  any preview resolution; the cover edge is moved back by one point, but only
  across a strip proven free of ink on the original raster.
- F44: a one-line block whose translation needs two lines at the bounded
  reduction is wrapped between its nearest neighbours (never across them,
  never over ink outside the cover) instead of being refused.
- F45: as a last resort, a tight line box (lineheight 1.0) is tried on the
  same proven-free frames with the same size floor.

Each fix has a counter-proof showing the RUN28 behaviour when it is switched
off.
"""

from __future__ import annotations

import io

import fitz
import numpy as np
import pytest
from PIL import Image

from app.documents import pdf_fidelity as pf
from app.documents.pdf_fidelity import _plan_scan_block

CONDENSED_INSTALLED = pf._condensed_available({})
needs_condensed = pytest.mark.skipif(
    not CONDENSED_INSTALLED, reason="fonts-dejavu-extra (DejaVuSansCondensed) not installed"
)

# ---------------------------------------------------------------- F43 ------
# Raster at 1 px per point; the ink map is computed at _INK_ZOOM (2 px/pt).


def _scan_doc(arr: np.ndarray) -> fitz.Document:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=arr.shape[1], height=arr.shape[0])
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc


BOX = [100.0, 100.0, 110.0, 110.0]  # protected region (an empty checkbox)


def _checkbox_raster(label_from: int | None = None) -> np.ndarray:
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    arr[100, 100:110] = 0
    arr[109, 100:110] = 0
    arr[100:110, 100] = 0
    arr[100:110, 109] = 0
    if label_from is not None:  # label ink glued to the box
        arr[102:108, label_from : label_from + 30] = 0
    return arr


def test_f43_cover_edge_is_moved_one_point_away_from_the_checkbox():
    page = _scan_doc(_checkbox_raster())[0]
    padded = [110.2, 98.0, 200.0, 112.0]  # 0.2 pt from the box: shares a pixel
    out = pf._clear_protected_regions(page, padded, [BOX])
    assert out[0] == pytest.approx(BOX[2] + pf._PROTECTED_CLEARANCE)
    assert out[1:] == padded[1:]  # only the edge facing the region moves
    assert padded == [110.2, 98.0, 200.0, 112.0]  # input untouched


def test_f43_counter_proof_without_clearance_the_cover_touches_the_box(monkeypatch):
    # RUN28 behaviour: the cover kept its 0.2 pt margin (< 1 preview pixel).
    monkeypatch.setattr(pf, "_PROTECTED_CLEARANCE", 0.0)
    page = _scan_doc(_checkbox_raster())[0]
    padded = [110.2, 98.0, 200.0, 112.0]
    assert pf._clear_protected_regions(page, padded, [BOX]) == padded


def test_f43_edge_is_kept_when_the_strip_carries_ink():
    # A label starting right after the box: moving the edge would uncover it.
    page = _scan_doc(_checkbox_raster(label_from=110))[0]
    padded = [110.2, 98.0, 200.0, 112.0]
    assert pf._clear_protected_regions(page, padded, [BOX]) == padded


def test_f43_far_regions_and_other_sides():
    page = _scan_doc(_checkbox_raster())[0]
    far = [113.0, 98.0, 200.0, 112.0]  # already more than one point away
    assert pf._clear_protected_regions(page, far, [BOX]) == far
    left = [20.0, 98.0, 99.8, 112.0]  # cover on the left of the box
    out = pf._clear_protected_regions(page, left, [BOX])
    assert out[2] == pytest.approx(BOX[0] - pf._PROTECTED_CLEARANCE)
    above = [100.0, 80.0, 110.0, 99.8]  # cover above the box
    out = pf._clear_protected_regions(page, above, [BOX])
    assert out[3] == pytest.approx(BOX[1] - pf._PROTECTED_CLEARANCE)


# ------------------------------------------------------- F44 / F45 scene ---


def _line_block(block_id: str = "p001-b0100") -> dict:
    box = [60.0, 200.0, 200.0, 210.0]
    text = "Invented source line for a narrow form cell"
    return {
        "id": block_id,
        "page": 1,
        "text": text,
        "bbox": box,
        "confidence": 0.93,
        "role": "line",
        "line_count": 1,
        "line_heights": [10.0],
        "line_pitch": None,
        "source_lines": [{"id": f"{block_id}-l0", "text": text, "bbox": box, "confidence": 0.93}],
        "style": {"align": "left", "bold": False, "color": None, "highlight": False},
    }


def _obstacles(below_top: float) -> list[dict]:
    return [
        {
            "id": "below",
            "text": "Invented",
            "bbox": [60, below_top, 300, below_top + 10],
            "source_lines": None,
        },
        {"id": "right", "text": "Code", "bbox": [204, 199, 320, 211], "source_lines": None},
    ]


def _plan(target: str, below_top: float = 212.0, rule_at: float | None = None):
    arr = np.full((842, 595, 3), (250, 250, 248), dtype=np.uint8)
    if rule_at is not None:  # unboxed ink (a rule) between the two lines
        arr[int(rule_at), 60:200] = 0
    buffer = io.BytesIO()
    Image.fromarray(arr).save(buffer, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    block = _line_block()
    return _plan_scan_block(
        block=block,
        target=target,
        page=doc[0],
        page_number=1,
        ir_blocks=[block, *_obstacles(below_top)],
        protected_regions=[],
        body_size=9.0,
        body_right=532.0,
        source_bytes=doc.tobytes(),
        bound=None,
    )


def _target(n: int) -> str:
    """Invented French text of about ``2 * n`` characters (fine-grained)."""
    return ("mot clé " * 80)[: 2 * n].rstrip()


def _codes(issues: list[dict]) -> list[str]:
    return [issue["code"] for issue in issues]


# ---------------------------------------------------------------- F44 ------
# Lower neighbour at 214 pt: two nominal lines (2 x 1.25 x size) spill onto
# it, two lines at the bounded reduction fit above it.


def test_f44_one_line_wraps_between_its_neighbours():
    item, issues, overflow = _plan(_target(40), below_top=214.0)
    assert item is not None and not overflow
    assert "SINGLE_LINE_WRAPPED_BETWEEN_NEIGHBOURS" in _codes(issues)
    f44 = next(i for i in issues if i["code"] == "SINGLE_LINE_WRAPPED_BETWEEN_NEIGHBOURS")
    assert f44["severity"] == "info"
    assert "LAYOUT_OVERFLOW" not in _codes(issues)
    inner = item["inner"]
    assert inner[1] >= 200.0 - 1e-6  # never above the line's own box
    assert inner[3] <= 214.0 - 0.6 + 1e-6  # never into the neighbour below
    base, _i, _o = _plan(_target(4), below_top=214.0)
    assert item["size"] >= base["size"] * pf._SCAN_MIN_FONT_RATIO - 1e-6


def test_f44_counter_proof_without_it_the_line_is_refused(monkeypatch):
    # RUN28 behaviour (F44 and the later F45 resort both off).
    monkeypatch.setattr(pf, "_SCAN_WRAP_BETWEEN_NEIGHBOURS", False)
    monkeypatch.setattr(pf, "_SCAN_TIGHT_LINE_HEIGHT", None)
    item, issues, overflow = _plan(_target(40), below_top=214.0)
    assert item is None and overflow
    assert "LAYOUT_OVERFLOW" in _codes(issues)


def test_f44_unboxed_ink_between_the_lines_forbids_the_wrap():
    # A rule outside the cover inside the two-line frame: never drawn over.
    item, issues, overflow = _plan(_target(40), below_top=214.0, rule_at=212.0)
    assert "SINGLE_LINE_WRAPPED_BETWEEN_NEIGHBOURS" not in _codes(issues)
    if item is not None:
        assert item["inner"][3] <= 212.0 + 1e-6


def test_f44_abstains_when_two_reduced_lines_do_not_fit():
    # Neighbour at 212 pt: less than two lines at the floor size.
    _item, issues, _overflow = _plan(_target(40), below_top=212.0)
    assert "SINGLE_LINE_WRAPPED_BETWEEN_NEIGHBOURS" not in _codes(issues)


def test_f44_text_fitting_on_one_line_is_unchanged():
    item, issues, overflow = _plan(_target(20), below_top=214.0)
    assert item is not None and not overflow
    assert "SINGLE_LINE_WRAPPED_BETWEEN_NEIGHBOURS" not in _codes(issues)
    assert item["inner"][3] <= 210.0 + 1e-6


# ---------------------------------------------------------------- F45 ------
# Lower neighbour at 212 pt: F44 abstains; the tight line box is the last
# resort before LAYOUT_OVERFLOW.


def test_f45_font_kwargs_pass_the_tight_line_box_only_when_set():
    assert pf._font_kwargs(8.0, {"lineheight": 1.0}, 0)["lineheight"] == 1.0
    assert pf._font_kwargs(8.0, {}, 0)["lineheight"] is None  # PyMuPDF default


def test_f45_tight_line_box_is_the_last_resort_before_overflow():
    item, issues, overflow = _plan(_target(40))
    assert item is not None and not overflow
    assert "SCAN_TIGHT_LINE_HEIGHT" in _codes(issues)
    assert item["style"].get("lineheight") == pf._SCAN_TIGHT_LINE_HEIGHT
    assert "LAYOUT_OVERFLOW" not in _codes(issues)
    base, _i, _o = _plan(_target(4))
    assert item["size"] >= base["size"] * pf._SCAN_MIN_FONT_RATIO - 1e-6
    assert item["inner"][3] <= 212.0 + 1e-6  # same proven-free frame


def test_f45_counter_proof_without_it_the_line_is_refused(monkeypatch):
    monkeypatch.setattr(pf, "_SCAN_TIGHT_LINE_HEIGHT", None)
    item, issues, overflow = _plan(_target(40))
    assert item is None and overflow
    assert "LAYOUT_OVERFLOW" in _codes(issues)


def test_f45_text_fitting_with_the_default_line_box_is_unchanged():
    item, issues, overflow = _plan(_target(20))
    assert item is not None and not overflow
    assert item["style"].get("lineheight") is None
    assert "SCAN_TIGHT_LINE_HEIGHT" not in _codes(issues)


@needs_condensed
def test_f45_never_hides_a_real_overflow():
    item, issues, overflow = _plan(_target(299))
    assert item is None and overflow
    assert "LAYOUT_OVERFLOW" in _codes(issues)
