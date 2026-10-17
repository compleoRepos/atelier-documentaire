"""RUN27 render regressions F30-F33 (synthetic rasters and invented texts only;
no document of the private corpus is used).

- F30: a shrunk line mask gives up the side removing the LEAST area.
- F31: the shrunk mask is completed by the parts of the full mask touching no
  neighbour kept as original, only when that ink is the line's own (no
  coloured ink in the line, no foreign stroke running beyond).
- F32: mask coverage is the area of the UNION of the masks.
- F33: repeated identical punctuation is typography, never a translation.
"""

from __future__ import annotations

import io

import fitz
import numpy as np
import pytest
from PIL import Image

from app.ai.translation.typography import typography_equivalent
from app.ai.vision.scorer import _validate_masks
from app.documents.block_status import classify_blocks
from app.documents.geometry import union_area
from app.documents.pdf_fidelity import (
    _apply_full_covers,
    _cover_pieces,
    _drop_text_over_source_ink,
    _piece_owned,
    _shrink_away,
    _uncovered_source_ink,
)
from app.documents.render_metrics import _mask_coverage_issues

IR_SCANNED = {"pages": [{"number": 1, "scanned": True}]}

# Geometry shared by the F30/F31 cases (points; the raster is 1 px per point).
NEIGHBOUR = [60.0, 40.0, 180.0, 53.5]  # label printed just above-left of the value
FULL = [98.0, 50.0, 292.0, 66.0]  # full cover of the value's line
SHRUNK = [98.0, 54.0, 292.0, 66.0]  # cover shrunk away from the label (F30)
TOP_RIGHT = [180.5, 50.0, 292.0, 54.0]  # glyph tops the shrink left visible


def _scan_doc(arr: np.ndarray) -> fitz.Document:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=arr.shape[1], height=arr.shape[0])
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc


def _raster() -> np.ndarray:
    """Label stems inside its own box; value stems whose tops (rows 50-53) lie
    in the strip the shrink removed."""
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    for x in range(62, 179, 3):
        arr[42:50, x : x + 1] = 0  # the label's own ink (kept original)
    for x in range(100, 290, 3):
        arr[50:63, x : x + 1] = 0  # the value's own ink
    return arr


def _value_item(text: str = "Valeur traduite " * 7) -> dict:
    return {
        "page": 1,
        "rect": [98.0, 52.0, 292.0, 66.0],
        "inner": [98.0, 52.0, 292.0, 66.0],
        "text": text,
        "size": 10.0,
        "style": {},
        "align": 0,
        "block_ids": ["value"],
        "table": False,
        "source_rects": [list(SHRUNK)],
        "shrunk_source_rects": [list(SHRUNK)],
        "full_source_rects": [list(FULL)],
        "full_overlap_ids": [["label"]],
        "full_overlap_boxes": [[("label", list(NEIGHBOUR))]],
        "cover_fills": [[1.0, 1.0, 1.0]],
        "cover": None,
    }


# --- F30 -----------------------------------------------------------------------


def test_f30_label_just_above_cuts_the_thin_top_strip_not_the_left_part():
    # Before F30 the horizontal side won (label centre left of the value
    # centre): the whole left part of the value's mask was cut away.
    assert _shrink_away(list(FULL), [list(NEIGHBOUR)]) == SHRUNK


def test_f30_narrow_neighbour_on_the_right_still_cuts_horizontally():
    assert _shrink_away([100.0, 50.0, 300.0, 66.0], [[280.0, 40.0, 320.0, 80.0]]) == [
        100.0,
        50.0,
        279.5,
        66.0,
    ]


# --- F31 -----------------------------------------------------------------------


def test_f31_pieces_avoid_the_kept_neighbour_and_the_shrunk_cover():
    pieces = _cover_pieces(list(FULL), [list(NEIGHBOUR)], list(SHRUNK))
    assert pieces == [TOP_RIGHT]
    margin = [NEIGHBOUR[0] - 0.5, NEIGHBOUR[1] - 0.5, NEIGHBOUR[2] + 0.5, NEIGHBOUR[3] + 0.5]
    for piece in pieces:
        assert piece[0] >= margin[2] or piece[1] >= margin[3]  # disjoint from the label


def test_f31_own_glyph_tops_are_masked_and_reported(monkeypatch):
    # RUN29 isolation: IR_SCANNED carries no OCR box, so the RUN29 F50 cut-glyph
    # guard would see the label's ink as orphan. F50 is covered with a consistent
    # IR in test_run29_render_regressions.py; the F31 assertions are unchanged.
    import app.documents.pdf_fidelity as pf

    monkeypatch.setattr(pf, "_CUT_GLYPH_CHECK", False)
    doc = _scan_doc(_raster())
    item = _value_item()
    _apply_full_covers([item], doc)
    assert item["source_rects"] == [SHRUNK, TOP_RIGHT]
    assert item["cover_pieces"] == 1
    assert item["cover_fills"] == [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]  # aligned per rect
    issues: list[dict] = []
    kept = _drop_text_over_source_ink(doc, IR_SCANNED, [_value_item()], issues)
    assert len(kept) == 1
    codes = [issue["code"] for issue in issues]
    assert "SCAN_TEXT_OVER_SOURCE_INK" not in codes
    assert "SCAN_COVER_COMPLETED_AWAY_FROM_KEPT_NEIGHBOUR" in codes


def test_f31_counter_proof_without_pieces_own_glyph_tops_stay_visible(monkeypatch):
    # The residual-ink guard only measures under the DRAWN text lines, so the
    # glyph tops left by the shrink were invisible to it (value placed, source
    # fragments still showing). Measured directly in the strip: F31 masks them
    # all; with pieces disabled they stay uncovered.
    import app.documents.pdf_fidelity as pf

    # Window taller than the strip: inside the 4 pt strip alone the stems fill
    # whole columns and are (rightly) discarded as vertical rules.
    window = [TOP_RIGHT[0], 44.0, TOP_RIGHT[2], 60.0]
    doc = _scan_doc(_raster())
    item = _value_item()
    _apply_full_covers([item], doc)
    assert _uncovered_source_ink(doc[0], window, item["source_rects"])[0] == 0
    monkeypatch.setattr(pf, "_piece_owned", lambda *args, **kwargs: False)
    bare = _value_item()
    _apply_full_covers([bare], doc)
    uncovered, measured = _uncovered_source_ink(doc[0], window, bare["source_rects"])
    assert uncovered > 100 and measured > 0


def test_f31_coloured_ink_in_the_line_refuses_every_piece():
    arr = _raster()
    arr[56:62, 240:250] = (40, 40, 200)  # a pale-blue stamp fragment in the line
    doc = _scan_doc(arr)
    assert not _piece_owned(doc[0], TOP_RIGHT, FULL, [FULL, SHRUNK])
    item = _value_item()
    _apply_full_covers([item], doc)
    assert item["source_rects"] == [SHRUNK] and item["cover_pieces"] == 0


def test_f31_foreign_stroke_running_beyond_the_line_refuses_the_piece():
    arr = _raster()
    arr[5:53, 270:272] = 0  # a signature stroke coming from far above
    doc = _scan_doc(arr)
    assert not _piece_owned(doc[0], TOP_RIGHT, FULL, [FULL, SHRUNK])
    item = _value_item()
    _apply_full_covers([item], doc)
    assert item["cover_pieces"] == 0


def test_f31_no_document_means_no_piece():
    item = _value_item()
    _apply_full_covers([item])
    assert item["source_rects"] == [SHRUNK] and item["cover_pieces"] == 0


def test_f31_replaced_neighbour_still_uses_the_full_cover():
    doc = _scan_doc(_raster())
    item = _value_item()
    label = {
        "page": 1,
        "block_ids": ["label"],
        "source_rects": [list(NEIGHBOUR)],
    }
    _apply_full_covers([item, label], doc)
    assert item["source_rects"] == [FULL] and item["extended_cover_lines"] == 1
    assert item["cover_pieces"] == 0


# --- F32 -----------------------------------------------------------------------


def test_f32_union_area_is_exact():
    assert union_area([]) == 0.0
    assert union_area([[0, 0, 10, 10], [0, 0, 10, 10]]) == 100.0
    assert union_area([[0, 0, 10, 10], [5, 5, 15, 15]]) == 175.0
    assert union_area([[0, 0, 10, 10], [20, 0, 30, 10]]) == 200.0
    assert union_area([[0, 0, 10, 10], [2, 2, 4, 4]]) == 100.0
    assert union_area([[0, 0, 0, 10], [5, 5, 1, 1], ["x", 0, 1, 1]]) == 0.0


def _overlapping_masks():
    # line masks and their block mask: 3 rectangles over the SAME 30 % area
    return [
        {"page": 1, "bbox": [0, 0, 60, 50]},
        {"page": 1, "bbox": [0, 0, 60, 25]},
        {"page": 1, "bbox": [0, 25, 60, 50]},
        {"page": 1, "bbox": [0, 0, 60, 50.0001]},
    ]


def test_f32_render_metrics_do_not_double_count_overlapping_masks():
    pages = [{"number": 1, "width": 100.0, "height": 100.0}]
    assert _mask_coverage_issues(_overlapping_masks(), pages) == []  # sum = 60 %
    large = [{"page": 1, "bbox": [0, 0, 100, 40]}, {"page": 1, "bbox": [0, 40, 100, 80]}]
    issues = _mask_coverage_issues(large, pages)
    assert [i["code"] for i in issues] == ["RENDER_TEXT_MASK_TOO_LARGE"]
    assert issues[0]["coverage"] == pytest.approx(0.8)


def test_f32_visual_scorer_uses_the_union_too():
    ir = {"pages": [{"number": 1, "width": 100.0, "height": 100.0}]}
    valid, issues, total = _validate_masks(ir, {"text_masks": _overlapping_masks()}, 0.35)
    assert len(valid) == 4 and issues == [] and total == pytest.approx(3000.0, rel=1e-3)
    large = [{"page": 1, "bbox": [0, 0, 100, 40]}, {"page": 1, "bbox": [0, 40, 100, 80]}]
    _, issues, _ = _validate_masks(ir, {"text_masks": large}, 0.35)
    assert [i["code"] for i in issues] == ["VISUAL_MASK_TOO_LARGE"]


# --- F33 -----------------------------------------------------------------------


def test_f33_doubled_punctuation_is_typography():
    assert typography_equivalent("Tel//Fax: 01-23-45", "Tel/Fax : 01-23-45")
    assert typography_equivalent("Ref.. 12 -- suite", "Ref. 12 - suite")


def test_f33_words_digits_and_distinct_marks_are_never_equivalent():
    assert not typography_equivalent("Tel//Fax: 01-23-45", "Tel/Fax : 01-23-46")
    assert not typography_equivalent("Tel//Fax: 01-23-45", "Tél/Fax : 01-23-45")
    assert not typography_equivalent("a-/b", "a-b")
    assert not typography_equivalent("Fax: 0123", "Fax: 01 23")


def test_f33_re_typeset_source_line_is_not_counted_as_translated():
    source = "RC: 4410 - Licence : 77120 - Tel//Fax: 01-23-45"
    ir = {
        "language": "eng",
        "languages": ["eng"],
        "pages": [{"number": 1, "blocks": [{"id": "b1", "text": source, "language": "eng"}]}],
    }
    status = classify_blocks(ir, {"b1": "RC : 4410 — Licence : 77120 — Tel/Fax : 01-23-45"}, [])
    assert status["blocks"]["b1"]["status"] != "TRANSLATED"
