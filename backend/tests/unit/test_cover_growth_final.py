"""Final regressions (09/10, D22-D24) on scanned pages, synthetic rasters only:

- D22: a line mask may extend over a neighbouring OCR box only when that
  neighbour is itself replaced (masks are drawn before every text);
- D23: a cell separator that leaves a line on one side only is a table rule;
- D24: a translated frame never grows into original ink (rules, labels).
No document of the private corpus is used.
"""

from __future__ import annotations

import io

import fitz
import numpy as np
from PIL import Image

from app.documents.line_verification import form_structure_evidence, vertical_rules_crossing
from app.documents.pdf_fidelity import (
    _apply_full_covers,
    _drop_text_over_source_ink,
    _growth_is_blank,
    _ink_obstacles,
)

IR_SCANNED = {"pages": [{"number": 1, "scanned": True}]}


def _scan_doc(arr: np.ndarray) -> fitz.Document:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=arr.shape[1], height=arr.shape[0])
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc


def _blank(width: int = 300, height: int = 200) -> np.ndarray:
    return np.full((height, width, 3), 255, dtype=np.uint8)


def _stems(arr: np.ndarray, x0: int, y0: int, x1: int, height: int = 6) -> None:
    """Glyph-like stems (1 pt every 3 pt): text, not a solid rule."""
    for x in range(x0, x1, 3):
        arr[y0 : y0 + height, x : x + 1] = 0


def _item(block_id, inner, shrunk, full=None, overlaps=None, text="Bonjour"):
    return {
        "page": 1,
        "rect": list(inner),
        "inner": list(inner),
        "text": text,
        "size": 10.0,
        "style": {},
        "align": 0,
        "block_ids": [block_id],
        "table": False,
        "source_rects": [list(c) for c in shrunk],
        "shrunk_source_rects": [list(c) for c in shrunk],
        "full_source_rects": [list(c) for c in full] if full else None,
        "full_overlap_ids": overlaps,
        "cover": None,
    }


# --- D22: full covers only over replaced neighbours -------------------------


def test_full_cover_is_used_only_when_every_overlapped_neighbour_is_replaced():
    a = _item("a", [20, 20, 200, 40], [[20, 22, 40, 34]], [[20, 22, 72, 34]], [["b"]])
    b = _item("b", [20, 120, 200, 140], [[20, 122, 60, 134]])
    _apply_full_covers([a, b])
    assert a["source_rects"] == [[20, 22, 72, 34]] and a["extended_cover_lines"] == 1
    _apply_full_covers([a])  # neighbour "b" kept as original: never masked
    assert a["source_rects"] == [[20, 22, 40, 34]] and a["extended_cover_lines"] == 0


def test_extended_cover_recovers_a_block_whose_own_source_was_left_unmasked():
    arr = _blank()
    _stems(arr, 22, 25, 70)  # the block's own source line
    doc = _scan_doc(arr)
    a = _item("a", [20, 20, 200, 40], [[20, 22, 40, 34]], [[20, 22, 72, 34]], [["b"]])
    b = _item("b", [20, 150, 200, 170], [[20, 152, 60, 164]])
    issues: list[dict] = []
    kept = _drop_text_over_source_ink(doc, IR_SCANNED, [a, b], issues)
    assert a in kept and b in kept
    codes = [i["code"] for i in issues]
    assert codes == ["SCAN_COVER_EXTENDED_OVER_REPLACED_NEIGHBOUR"]
    assert issues[0]["severity"] == "info" and issues[0]["lines"] == 1


def test_fixed_point_shrinks_back_the_cover_when_the_neighbour_is_dropped():
    arr = _blank()
    _stems(arr, 22, 25, 70)  # own source of "a", only the full cover hides it
    _stems(arr, 22, 155, 90)  # unmasked ink under the text of "b"
    doc = _scan_doc(arr)
    a = _item("a", [20, 20, 200, 40], [[20, 22, 40, 34]], [[20, 22, 72, 34]], [["b"]])
    b = _item("b", [20, 150, 200, 170], [])
    issues: list[dict] = []
    kept = _drop_text_over_source_ink(doc, IR_SCANNED, [a, b], issues)
    # "b" overlaps unmasked ink -> dropped; "a" may then no longer mask "b"'s
    # pixels -> its own source is exposed -> dropped too. Never silent.
    assert kept == []
    dropped = sorted(i["block_id"] for i in issues if i["code"] == "SCAN_TEXT_OVER_SOURCE_INK")
    assert dropped == ["a", "b"]
    assert all(i["severity"] == "critical" for i in issues if i["block_id"] in {"a", "b"})


# --- D23: cell separator on one side of the line ------------------------------


def _cell_raster():
    arr = _blank(300, 120)
    arr[20:21, :] = 0  # horizontal rule at the top of the cell row
    arr[20:70, 100:101] = 0  # cell separator starting at that rule, going down
    return arr


def test_cell_separator_leaving_the_line_on_one_side_is_a_rule():
    arr = _cell_raster()
    box = [50.0, 22.0, 200.0, 32.0]  # label right under the top rule
    assert vertical_rules_crossing(arr, box) >= 1
    lines = [{"text": "LABEL ONE LABEL TWO", "bbox": box}]
    assert "vertical_rule_crosses_line" in form_structure_evidence(arr, lines, 1.0)


def test_glyph_stems_inside_the_line_box_are_not_rules():
    arr = _blank(300, 120)
    _stems(arr, 52, 23, 190, height=9)
    assert vertical_rules_crossing(arr, [50.0, 22.0, 200.0, 32.0]) == 0


def test_rule_crossing_on_both_sides_is_still_detected():
    arr = _blank(300, 120)
    arr[5:100, 120:121] = 0
    assert vertical_rules_crossing(arr, [50.0, 40.0, 200.0, 50.0]) >= 1


# --- D24: frames never grow into original ink --------------------------------


def test_horizontal_rule_above_the_box_stops_and_rejects_upward_growth():
    arr = _blank()
    arr[40:41, :] = 0  # cell rule 2 pt above the label
    _stems(arr, 52, 43, 90, height=4)  # the label itself
    doc = _scan_doc(arr)
    page = doc[0]
    box = [50.0, 42.0, 95.0, 47.5]
    ink_box, obstacles = _ink_obstacles(page, box, 280.0, 30.0)
    assert any(o[1] <= 40.5 <= o[3] + 0.6 and o[3] <= box[1] for o in obstacles)
    assert not _growth_is_blank(page, [50.0, 37.0, 95.0, 47.5], ink_box)  # crosses the rule
    assert _growth_is_blank(page, [50.0, 42.0, 95.0, 52.0], ink_box)  # blank below


def test_rule_touching_the_box_is_an_obstacle_never_absorbed():
    arr = _blank()
    arr[48:49, :] = 0  # rule right under the line box
    _stems(arr, 52, 42, 90, height=6)
    doc = _scan_doc(arr)
    ink_box, obstacles = _ink_obstacles(doc[0], [50.0, 41.5, 95.0, 48.0], 280.0, 30.0)
    assert ink_box[3] <= 48.6  # not extended through the rule
    assert any(o[1] < 49.0 and o[3] > 48.0 for o in obstacles)


def test_own_glyph_ink_past_the_ocr_box_is_absorbed_not_an_obstacle():
    arr = _blank()
    _stems(arr, 52, 40, 90, height=10)  # glyphs 1 pt taller than the OCR box
    doc = _scan_doc(arr)
    box = [50.0, 40.0, 95.0, 49.0]
    ink_box, obstacles = _ink_obstacles(doc[0], box, 280.0, 30.0)
    assert ink_box[3] > box[3]
    assert not [o for o in obstacles if o[1] >= box[3] and o[2] - o[0] > 1.5]
    assert _growth_is_blank(doc[0], [50.0, 40.0, 95.0, 60.0], ink_box)


def test_ink_to_the_right_of_the_box_stops_right_growth():
    arr = _blank()
    _stems(arr, 52, 42, 90, height=6)
    arr[30:70, 150:151] = 0  # cell border to the right
    doc = _scan_doc(arr)
    box = [50.0, 41.5, 92.0, 48.5]
    ink_box, obstacles = _ink_obstacles(doc[0], box, 280.0, 30.0)
    assert any(o[2] - o[0] <= 1.01 and 149.0 <= o[0] <= 151.0 for o in obstacles)
    assert not _growth_is_blank(doc[0], [50.0, 41.5, 200.0, 48.5], ink_box)
