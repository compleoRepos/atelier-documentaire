"""RUN29 render regressions F48/F49 (synthetic rasters only; no document of
the private corpus is used, no text of it either).

- F48: a scanned table rule with a scanning drop-out (a hole of 1-2 px) is
  still recognised by the F38 rule test and kept out of the paper cover; a
  wider hole (a word space) is not bridged, a dense text row is still not a
  rule.
- F49: a structural rule of the original that is no longer drawn where a text
  mask was painted is reported as RENDER_RULE_ERASED (critical); an intact
  rule, an underline lying inside the text area or a thick text row are not.
- F50: a planned cover that cuts source glyphs whose rest stays visible outside
  every cover and every OCR box (OCR box smaller than the print) refuses the
  replacement (SCAN_COVER_CUTS_SOURCE_GLYPHS, original kept); a kept
  neighbour's ink nicked by the cover is inside its own OCR box and is not
  counted. F50b: a thin long rule crossing the cover is not a glyph (left to
  F49).
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

from app.documents import pdf_fidelity as pf
from app.documents import render_metrics as rm
from app.documents.render_metrics import measure_render_fidelity

# ---------------------------------------------------------------- F48 ------


def _scan_doc(arr: np.ndarray) -> fitz.Document:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=arr.shape[1], height=arr.shape[0])
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc


COVER = [50.0, 99.5, 250.0, 112.0]


def _holed_rule_raster(hole: int = 1, text_rows: bool = True) -> np.ndarray:
    """A 1 px scanned rule descending 2 px (0.5 deg) with ONE hole of ``hole``
    image pixels in its first third, then text stems under it."""
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    for x in range(40, 261):
        if 110 <= x < 110 + hole:
            continue
        arr[100 + int(round(2 * (x - 40) / 220)), x] = 0
    if text_rows:
        for x in range(56, 246, 3):
            arr[105:111, x : x + 1] = 0
    return arr


def test_f48_rule_with_a_scanning_hole_is_kept_out_of_the_cover():
    doc = _scan_doc(_holed_rule_raster(hole=1))
    clipped = pf._clip_cover_off_rules(doc[0], COVER)
    assert clipped is not None
    assert clipped[1] >= 102.0  # below every row of the rule
    assert clipped[1] <= 105.0  # never into the line's own glyphs
    assert clipped[0] == COVER[0] and clipped[2] == COVER[2] and clipped[3] == COVER[3]


def test_f48_counter_proof_without_bridging_the_cover_erases_the_rule(monkeypatch):
    # RUN28 behaviour: the hole cut the longest run below 85 % of the width.
    monkeypatch.setattr(pf, "_RULE_GAP_PX", 0)
    doc = _scan_doc(_holed_rule_raster(hole=1))
    assert pf._clip_cover_off_rules(doc[0], COVER) is None


def test_f48_a_word_space_wide_hole_is_not_bridged():
    # 3 image px = 6 px at the ink zoom: wider than _RULE_GAP_PX, the two
    # halves are judged separately (each < 85 % of the cover).
    doc = _scan_doc(_holed_rule_raster(hole=3, text_rows=False))
    assert pf._clip_cover_off_rules(doc[0], [50.0, 99.5, 250.0, 112.0]) is None
    assert pf._RULE_GAP_PX * 2 <= 6  # documented bound (pixels at _INK_ZOOM)


def test_f48_dense_text_row_is_still_not_a_rule():
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    for x in range(42, 258, 2):  # dense stems with one-pixel gaps
        arr[99:111, x : x + 1] = 0
    doc = _scan_doc(arr)
    assert pf._clip_cover_off_rules(doc[0], COVER) is None


def test_f48_bridge_gaps_fills_only_inner_holes_up_to_the_bound():
    line = np.array([0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0], dtype=bool)
    out = pf._bridge_gaps(line, 2)
    assert out.tolist() == [0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0]  # 4-px hole kept
    assert line.tolist() == [0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0]  # input untouched
    assert pf._bridge_gaps(line, 0).tolist() == line.tolist()


# ---------------------------------------------------------------- F49 ------

PAGE = {"number": 1, "width": 400.0, "height": 200.0}
SCALE = 2  # preview pixels per point


def _preview(path: Path, draw) -> Path:
    arr = np.full((int(PAGE["height"] * SCALE), int(PAGE["width"] * SCALE)), 250, np.uint8)
    draw(arr)
    Image.fromarray(arr).save(path)
    return path


def _rule(arr, y_pt=100.0, x0_pt=20.0, x1_pt=380.0, skip=None):
    for x in range(int(x0_pt * SCALE), int(x1_pt * SCALE)):
        if skip and skip[0] * SCALE <= x < skip[1] * SCALE:
            continue
        y = int(y_pt * SCALE) + (x // 160)  # descends 1 px every 80 pt
        arr[y : y + 2, x] = 60


MASK = [{"page": 1, "bbox": [100.0, 92.0, 300.0, 108.0]}]


def test_f49_rule_erased_under_a_text_mask_is_reported(tmp_path):
    src = _preview(tmp_path / "o.png", _rule)
    tgt = _preview(tmp_path / "t.png", lambda a: _rule(a, skip=(120.0, 280.0)))
    summary, issues = rm._erased_rule_issues([src], [tgt], MASK, [PAGE])
    assert summary == {"available": True, "pages_checked": 1, "erased_rules": 1}
    (issue,) = issues
    assert issue["code"] == "RENDER_RULE_ERASED" and issue["severity"] == "critical"
    assert issue["orientation"] == "horizontal" and issue["page"] == 1
    assert 155.0 <= issue["erased_pt"] <= 161.0
    assert 119.0 <= issue["erased_bbox"][0] <= 121.0 and 279.0 <= issue["erased_bbox"][2] <= 281.0
    assert 99.0 <= issue["bbox"][1] <= 101.0


def test_f49_intact_rule_is_not_reported(tmp_path):
    src = _preview(tmp_path / "o.png", _rule)
    tgt = _preview(tmp_path / "t.png", _rule)
    assert rm._erased_rule_issues([src], [tgt], MASK, [PAGE])[1] == []


def test_f49_short_erasure_below_the_bound_is_not_reported(tmp_path):
    src = _preview(tmp_path / "o.png", _rule)
    tgt = _preview(tmp_path / "t.png", lambda a: _rule(a, skip=(150.0, 155.0)))
    assert rm._erased_rule_issues([src], [tgt], MASK, [PAGE])[1] == []


def test_f49_underline_inside_the_text_area_is_not_structural(tmp_path):
    # Known limit, kept on purpose: a line that never leaves the masks may be
    # an underline of the source text that the translation does not reproduce.
    src = _preview(tmp_path / "o.png", lambda a: _rule(a, x0_pt=110.0, x1_pt=290.0))
    tgt = _preview(tmp_path / "t.png", lambda a: None)
    assert rm._erased_rule_issues([src], [tgt], MASK, [PAGE])[1] == []


def test_f49_thick_text_row_replaced_by_the_translation_is_not_a_rule(tmp_path):
    def text_row(arr):
        for x in range(20 * SCALE, 380 * SCALE, 3):  # stems 8 px high, 2 px gaps
            arr[96 * SCALE : 100 * SCALE, x] = 40
        arr[98 * SCALE, 20 * SCALE : 380 * SCALE] = 40  # a bar through them

    src = _preview(tmp_path / "o.png", text_row)
    tgt = _preview(tmp_path / "t.png", lambda a: None)
    assert rm._erased_rule_issues([src], [tgt], MASK, [PAGE])[1] == []


def test_f49_vertical_rule_erased_under_a_mask_is_reported(tmp_path):
    def vrule(arr, skip=False):
        for y in range(10 * SCALE, 190 * SCALE):
            if skip and 60 * SCALE <= y < 140 * SCALE:
                continue
            arr[y, 200 * SCALE : 200 * SCALE + 2] = 60

    mask = [{"page": 1, "bbox": [150.0, 50.0, 250.0, 150.0]}]
    src = _preview(tmp_path / "o.png", vrule)
    tgt = _preview(tmp_path / "t.png", lambda a: vrule(a, skip=True))
    (issue,) = rm._erased_rule_issues([src], [tgt], mask, [PAGE])[1]
    assert issue["orientation"] == "vertical"
    assert 59.0 <= issue["erased_bbox"][1] <= 61.0 and 139.0 <= issue["erased_bbox"][3] <= 141.0


def test_f49_counter_proof_previous_metrics_did_not_see_the_erasure(tmp_path):
    # Same pair as the first test: the raster similarity excludes the masked
    # area, so it is blind to what a cover erased there (the RUN29 finding).
    src = _preview(tmp_path / "o.png", _rule)
    tgt = _preview(tmp_path / "t.png", lambda a: _rule(a, skip=(120.0, 280.0)))
    score, _coverage, issues = rm._raster_similarity(
        [src], [tgt], MASK, PAGE["width"], PAGE["height"], [PAGE]
    )
    assert score is not None and score > 0.999
    assert issues == []


def test_f49_missing_previews_are_not_a_pass(tmp_path):
    summary, issues = rm._erased_rule_issues([], [], MASK, [PAGE])
    assert summary["available"] is False and issues == []


def test_f49_measure_render_fidelity_reports_it_end_to_end(tmp_path):
    # Real preview rendering of two images (no mock): the check runs inside
    # measure_render_fidelity and its summary is exposed.  An image page is
    # measured with 1 px = 1 pt, so the mask is given in image pixels.
    source = tmp_path / "source.png"
    candidate = tmp_path / "candidate.png"
    width, height = 800, 400
    original = np.full((height, width), 250, np.uint8)
    original[200:201, 40:760] = 60  # a 1 pt rule
    target = original.copy()
    target[195:207, 240:560] = 250  # a "cover" painted over the rule
    Image.fromarray(original).save(source)
    Image.fromarray(target).save(candidate)
    result = measure_render_fidelity(
        source,
        candidate,
        text_masks=[{"page": 1, "bbox": [235.0, 192.0, 565.0, 210.0]}],
        work_dir=tmp_path / "render",
    )
    assert result["rule_integrity"]["available"] is True
    codes = [issue["code"] for issue in result["issues"]]
    assert codes.count("RENDER_RULE_ERASED") == 1
    (issue,) = [i for i in result["issues"] if i["code"] == "RENDER_RULE_ERASED"]
    assert 236.0 <= issue["erased_bbox"][0] <= 244.0 and 556.0 <= issue["erased_bbox"][2] <= 564.0


def test_f49_counter_proof_end_to_end_intact_rule_gives_no_issue(tmp_path):
    source = tmp_path / "source.png"
    width, height = 800, 400
    original = np.full((height, width), 250, np.uint8)
    original[200:201, 40:760] = 60
    Image.fromarray(original).save(source)
    result = measure_render_fidelity(
        source,
        source,
        text_masks=[{"page": 1, "bbox": [235.0, 192.0, 565.0, 210.0]}],
        work_dir=tmp_path / "render",
    )
    assert result["rule_integrity"] == {"available": True, "pages_checked": 1, "erased_rules": 0}
    assert "RENDER_RULE_ERASED" not in [issue["code"] for issue in result["issues"]]


def test_f49_known_limit_rules_of_two_points_or_more_are_not_checked(tmp_path):
    # Recall limit kept on purpose (precision was measured on thin rules
    # only): a rule rendered >= 3 px thick fails the "paper 3 px above and
    # below" test and is not checked.  Widening it needs a new precision
    # measurement on real scans; this test makes that change deliberate.
    source = tmp_path / "source.png"
    candidate = tmp_path / "candidate.png"
    original = np.full((400, 800), 250, np.uint8)
    original[200:202, 40:760] = 0  # a 2 pt rule
    target = original.copy()
    target[195:207, 240:560] = 250
    Image.fromarray(original).save(source)
    Image.fromarray(target).save(candidate)
    result = measure_render_fidelity(
        source,
        candidate,
        text_masks=[{"page": 1, "bbox": [235.0, 192.0, 565.0, 210.0]}],
        work_dir=tmp_path / "render",
    )
    assert result["rule_integrity"]["erased_rules"] == 0


# ---------------------------------------------------------------- F50 ------
# Rasters at 2 px per point (the corpus rules F50b must ignore are 0.5 pt).
def _scan_doc_2x(arr: np.ndarray) -> fitz.Document:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=arr.shape[1] / 2, height=arr.shape[0] / 2)
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc


def _ink(arr: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> None:
    arr[int(y0 * 2) : int(y1 * 2), int(x0 * 2) : int(x1 * 2)] = 0


def _paper() -> np.ndarray:
    return np.full((400, 600, 3), 255, dtype=np.uint8)


def _stems(arr: np.ndarray, y0: float, y1: float) -> None:
    for x in range(60, 200, 6):
        _ink(arr, x, y0, x + 2, y1)  # 2 pt glyph stems


def _item(cover: list[float]) -> dict:
    return {
        "page": 1,
        "rect": list(cover),
        "inner": list(cover),
        "text": "Texte",
        "size": 5.0,
        "style": {},
        "align": 0,
        "block_ids": ["b-item"],
        "table": False,
        "source_rects": [list(cover)],
        "cover_fills": [[1.0, 1.0, 1.0]],
        "cover": None,
    }


def _ir(*boxes: list[float]) -> dict:
    blocks = [{"id": f"b{i}", "bbox": list(box)} for i, box in enumerate(boxes)]
    return {"pages": [{"number": 1, "scanned": True, "blocks": blocks}]}


SMALL_BOX = [58.0, 46.0, 202.0, 54.0]  # OCR box: middle third of the print only


def _codes(issues: list[dict]) -> list[str]:
    return [issue["code"] for issue in issues]


def test_f50_cover_cutting_glyphs_of_a_too_small_ocr_box_is_refused():
    arr = _paper()
    _stems(arr, 40, 60)  # printed 20 pt tall, OCR box 8 pt tall
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(arr), _ir(SMALL_BOX), [_item(SMALL_BOX)], issues
    )
    assert kept == []
    assert _codes(issues) == ["SCAN_COVER_CUTS_SOURCE_GLYPHS"]
    assert issues[0]["severity"] == "critical"
    assert issues[0]["cut_fragments"] >= 20  # one per cut stem
    assert issues[0]["block_id"] == "b-item"


def test_f50_counter_proof_without_the_guard_the_cut_glyphs_were_accepted(monkeypatch):
    monkeypatch.setattr(pf, "_CUT_GLYPH_CHECK", False)
    arr = _paper()
    _stems(arr, 40, 60)
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(arr), _ir(SMALL_BOX), [_item(SMALL_BOX)], issues
    )
    assert len(kept) == 1  # placed, half glyphs visible above and below
    assert "SCAN_TEXT_OVER_SOURCE_INK" not in _codes(issues)


def test_f50_cover_hiding_the_whole_print_is_kept():
    arr = _paper()
    _stems(arr, 40, 60)
    box = [58.0, 39.0, 202.0, 61.0]
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(_scan_doc_2x(arr), _ir(box), [_item(box)], issues)
    assert len(kept) == 1
    assert "SCAN_COVER_CUTS_SOURCE_GLYPHS" not in _codes(issues)


def test_f50_kept_neighbour_ink_nicked_by_the_cover_is_inside_its_ocr_box():
    arr = _paper()
    _stems(arr, 26, 44)  # kept neighbour line, its stems run into the cover top
    for x in range(63, 200, 6):
        _ink(arr, x, 46, x + 2, 58)  # the item's own print, inside its cover
    neighbour, cover = [58.0, 25.0, 202.0, 44.5], [58.0, 40.0, 202.0, 60.0]
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(arr), _ir(neighbour, cover), [_item(cover)], issues
    )
    assert len(kept) == 1
    assert "SCAN_COVER_CUTS_SOURCE_GLYPHS" not in _codes(issues)
    # The same nick with the neighbour unknown to OCR is orphan ink: refused.
    issues = []
    kept = pf._drop_text_over_source_ink(_scan_doc_2x(arr), _ir(cover), [_item(cover)], issues)
    assert kept == []
    assert _codes(issues) == ["SCAN_COVER_CUTS_SOURCE_GLYPHS"]


def _rule_crossing_raster() -> np.ndarray:
    arr = _paper()
    for x in range(63, 200, 6):
        _ink(arr, x, 47, x + 2, 53)  # the item's own print, inside its cover
    arr[60:118, 220] = 0  # vertical rule 0.5 pt thick, 29 pt long, x = 110 pt
    return arr


def test_f50b_thin_rule_crossing_the_cover_is_not_a_cut_glyph():
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(_rule_crossing_raster()), _ir(SMALL_BOX), [_item(SMALL_BOX)], issues
    )
    assert len(kept) == 1
    assert "SCAN_COVER_CUTS_SOURCE_GLYPHS" not in _codes(issues)


def test_f50b_counter_proof_without_the_rule_exclusion_the_rule_refused_it(monkeypatch):
    monkeypatch.setattr(pf, "_CUT_GLYPH_RULE_MAX_THICK_PT", 0.0)
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(_rule_crossing_raster()), _ir(SMALL_BOX), [_item(SMALL_BOX)], issues
    )
    assert kept == []
    assert _codes(issues) == ["SCAN_COVER_CUTS_SOURCE_GLYPHS"]


def test_f50_block_status_reports_the_refusal_explicitly():
    from app.documents.block_status import _RENDER_FAILURES, VERSION

    assert _RENDER_FAILURES["SCAN_COVER_CUTS_SOURCE_GLYPHS"] == "render_source_glyphs_cut"
    assert VERSION.startswith("block-status-6")


# ---------------------------------------------------------------- F50c -----
# The item's own print (12 pt) inside its OCR box; the cover was shrunk at the
# bottom (away from a kept line below) and leaves the last 3 pt of every stem
# visible under the translation, inside the OCR box: F50's orphan rule is blind.
OWN_BOX, SHRUNK_COVER = [58.0, 45.0, 202.0, 59.0], [58.0, 44.0, 202.0, 55.0]


def _own_descenders_raster() -> np.ndarray:
    arr = _paper()
    for x in range(63, 200, 6):
        _ink(arr, x, 46, x + 2, 58)
    return arr


def test_f50c_own_glyph_rests_left_under_a_shrunk_cover_are_refused():
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(_own_descenders_raster()), _ir(OWN_BOX), [_item(SHRUNK_COVER)], issues
    )
    assert kept == []
    assert _codes(issues) == ["SCAN_COVER_CUTS_SOURCE_GLYPHS"]
    assert issues[0]["cut_fragments"] >= 20


def test_f50c_counter_proof_without_it_the_rests_inside_the_ocr_box_were_accepted(monkeypatch):
    monkeypatch.setattr(pf, "_CUT_GLYPH_OWN_CHECK", False)
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(_own_descenders_raster()), _ir(OWN_BOX), [_item(SHRUNK_COVER)], issues
    )
    assert len(kept) == 1
    assert "SCAN_COVER_CUTS_SOURCE_GLYPHS" not in _codes(issues)


def test_f50c_a_cover_reaching_the_whole_print_is_still_kept():
    issues: list[dict] = []
    full = [58.0, 44.0, 202.0, 59.0]
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(_own_descenders_raster()), _ir(OWN_BOX), [_item(full)], issues
    )
    assert len(kept) == 1
    assert "SCAN_COVER_CUTS_SOURCE_GLYPHS" not in _codes(issues)


def test_f50c_a_neighbour_glyph_mostly_outside_the_cover_is_not_its_own():
    # Stems 26-44 pt nicked over 4 of their 18 pt (22 % erased): a kept
    # neighbour's ink inside its OCR box, as in the F50 neighbour test.
    arr = _paper()
    _stems(arr, 26, 44)
    for x in range(63, 200, 6):
        _ink(arr, x, 46, x + 2, 58)
    neighbour, cover = [58.0, 25.0, 202.0, 44.5], [58.0, 40.0, 202.0, 60.0]
    issues: list[dict] = []
    kept = pf._drop_text_over_source_ink(
        _scan_doc_2x(arr), _ir(neighbour, cover), [_item(cover)], issues
    )
    assert len(kept) == 1
    assert "SCAN_COVER_CUTS_SOURCE_GLYPHS" not in _codes(issues)
