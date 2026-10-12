"""run25 regressions (synthetic only, no corpus content).

F20  - overlapping OCR line boxes are split at the ink valley between the two
       lines instead of shrinking the cover to the neighbour's box edge.
F20b - one-line frames are anchored on the line's own print, not on the top of
       an inflated OCR box.
F21  - drawn check boxes misread by OCR as letters (LJ, L], |_|, [_]) without a
       detected check-box glyph make the line OCR-unreliable (source kept).
F22  - a paper cover never erases a table rule / frame line lying in its edge
       bands (continuous dark run that continues past the cover).
F22b - the same holds for the full cover used when every overlapped neighbour
       is itself replaced.
F23  - an OCR line read in a right-to-left context that carries a multi-group
       number (phone, fax...) is kept as the original image: the group order is
       not trustworthy. Synthetic numbers only.
"""

from __future__ import annotations

import collections
import io

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.documents.line_verification import flag_bidi_number_runs, flag_misread_checkbox_tokens
from app.documents.pdf_fidelity import (
    _clip_cover_off_rules,
    _glyph_band,
    _plan_scan_block,
    _pull_padding_off_foreign_ink,
    _scan_covers,
    _vertical_ink_split,
)

ZOOM = 4


def _page_with_lines(*lines: tuple[float, str], stroke: bool = False) -> tuple[object, object]:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    for baseline, text in lines:
        page.insert_text((20, baseline), text, fontsize=10, fontname="helv")
    if stroke:
        page.draw_line((100, 45), (100, 62), width=1.0)
    return doc, page


def _ink_rows(page, x0: float, x1: float, y0: float, y1: float) -> list[float]:
    """Page ordinates (pt) of pixel rows that carry dark ink in the band."""
    clip = fitz.Rect(x0, y0, x1, y1)
    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), clip=clip, colorspace=fitz.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, -1)[:, : pix.width]
    rows = np.nonzero((arr < 128).any(axis=1))[0]
    return [y0 + r / ZOOM for r in rows.tolist()]


UPPER = (50.0, "Synthetic upper line gyp")
LOWER = (64.0, "Synthetic lower line Hdk")


def _extents(page):
    upper = [y for y in _ink_rows(page, 18, 200, 38, 54) if y < 54]
    lower = [y for y in _ink_rows(page, 18, 200, 54, 70) if y >= 54]
    return max(upper), min(lower)


def test_f20_split_lies_in_the_ink_valley_between_two_lines():
    doc, page = _page_with_lines(UPPER, LOWER)
    upper_bottom, lower_top = _extents(page)
    box_a = [18.0, 40.0, 200.0, 59.0]  # inflated downwards
    box_b = [18.0, 51.0, 200.0, 68.0]  # inflated upwards over the upper descenders
    split = _vertical_ink_split(page, box_a, box_b)
    assert split is not None
    assert upper_bottom < split < lower_top
    doc.close()


def test_f20_split_refused_when_a_stroke_joins_both_lines():
    doc, page = _page_with_lines(UPPER, LOWER, stroke=True)
    assert _vertical_ink_split(page, [18.0, 40.0, 200.0, 59.0], [18.0, 51.0, 200.0, 68.0]) is None
    doc.close()


def test_f20_cover_reaches_own_descenders_without_touching_neighbour_print():
    doc, page = _page_with_lines(UPPER, LOWER)
    upper_bottom, lower_top = _extents(page)
    block = {
        "bbox": [18.0, 40.0, 200.0, 59.0],
        "source_lines": [{"bbox": [18.0, 40.0, 200.0, 59.0]}],
    }
    neighbour = [18.0, 51.0, 200.0, 68.0]
    old, _ = _scan_covers(block, [neighbour], [], page.rect)
    new, notes = _scan_covers(block, [neighbour], [], page.rect, page=page)
    assert old is not None and new is not None
    assert old[0][3] < upper_bottom  # previous behaviour: own descenders left visible
    assert upper_bottom < new[0][3] < lower_top
    assert "line_split_at_ink_valley" in notes
    doc.close()


def test_f20_without_page_keeps_previous_behaviour():
    doc, page = _page_with_lines(UPPER, LOWER)
    block = {
        "bbox": [18.0, 40.0, 200.0, 59.0],
        "source_lines": [{"bbox": [18.0, 40.0, 200.0, 59.0]}],
    }
    covers, notes = _scan_covers(block, [[18.0, 51.0, 200.0, 68.0]], [], page.rect)
    assert covers is not None and covers[0][3] <= 51.0
    assert "line_shrunk" in notes and "line_split_at_ink_valley" not in notes
    doc.close()


def test_f20b_glyph_band_ignores_ink_boxed_by_another_line():
    doc, page = _page_with_lines((36.0, "Neighbour line above Hgy"), UPPER)
    own = [y for y in _ink_rows(page, 18, 200, 41, 56)]
    inflated = [18.0, 30.0, 200.0, 54.0]  # reaches up over the neighbour's print
    neighbour = [18.0, 26.0, 200.0, 39.5]
    band = _glyph_band(page, inflated, [neighbour])
    assert band is not None
    assert min(own) - 0.5 <= band[0] and band[1] <= max(own) + 1.0
    doc.close()


def test_f20b_glyph_band_none_on_blank_box():
    doc, page = _page_with_lines()
    assert _glyph_band(page, [18.0, 30.0, 200.0, 54.0], []) is None
    doc.close()


def _block(text: str) -> dict:
    return {"source_lines": [{"text": text, "bbox": [10.0, 10.0, 200.0, 20.0]}]}


def test_f21_misread_checkbox_tokens_make_the_line_unreliable():
    stats: collections.Counter = collections.Counter()
    block = _block("LJ Option one, , rate LJ per day, L] per week")
    flag_misread_checkbox_tokens(block, {}, stats)
    assert block["ocr_unreliable"] is True
    assert block["ocr_unreliable_reason"] == "checkbox_misread_undetected"
    assert stats["checkbox_tokens_misread_undetected"] == 3
    assert stats["blocks_checkbox_misread_undetected"] == 1


def test_f21_detected_box_or_ordinary_text_is_not_flagged():
    for text, boxes in (
        ("LJ Option one", {0: [[10.0, 10.0, 16.0, 16.0]]}),  # the glyph is detected
        ("LJUBLJANA central office", {}),  # a word, not a box rendering
        ("[X] Option typed in the form", {}),  # typed marker, reproducible
        ("ALJ code and BLJ code", {}),  # glued to a preceding letter
    ):
        stats: collections.Counter = collections.Counter()
        block = _block(text)
        flag_misread_checkbox_tokens(block, boxes, stats)
        assert not block.get("ocr_unreliable"), text
        assert stats["blocks_checkbox_misread_undetected"] == 0


def _framed_heading() -> tuple[object, object]:
    """A framed cell whose heading OCR box was inflated up to the frame."""
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.draw_rect(fitz.Rect(10, 30, 250, 70), width=1.0)
    page.insert_text((20, 44), "Synthetic framed heading", fontsize=10, fontname="helv")
    return doc, page


FRAMED_BLOCK = {
    "bbox": [10.2, 30.2, 200.0, 47.0],
    "source_lines": [{"bbox": [10.2, 30.2, 200.0, 47.0]}],
}


def test_f22_cover_pulled_back_from_frame_rules_but_keeps_the_print():
    doc, page = _framed_heading()
    glyph_rows = _ink_rows(page, 18, 200, 32, 50)
    glyph_top, glyph_bottom = min(glyph_rows), max(glyph_rows)
    old, _ = _scan_covers(FRAMED_BLOCK, [], [], page.rect)
    new, notes = _scan_covers(FRAMED_BLOCK, [], [], page.rect, page=page)
    assert old is not None and new is not None
    assert old[0][1] < 30.0 and old[0][0] < 10.0  # previous cover swallowed both rules
    assert "cover_clipped_off_rule" in notes
    top, left = new[0][1], new[0][0]
    assert 30.4 <= top < glyph_top  # below the top rule, above the print
    assert 10.4 <= left < 20.0  # right of the left rule, left of the print
    assert new[0][3] > glyph_bottom  # the print itself stays covered
    doc.close()


def test_f22_dense_text_rows_are_not_mistaken_for_rules():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    for x in range(20, 200, 4):  # "letters": 3 pt ink, 1 pt gap -> 75 % dark rows
        page.draw_rect(fitz.Rect(x, 40, x + 3, 46), color=(0, 0, 0), fill=(0, 0, 0), width=0)
    assert _clip_cover_off_rules(page, [18.0, 38.5, 202.0, 47.5]) is None
    doc.close()


def test_f22_line_not_continuing_past_the_cover_is_not_a_rule():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.draw_line((30, 40), (170, 40), width=1.0)  # ends inside the cover
    assert _clip_cover_off_rules(page, [28.0, 39.0, 172.0, 52.0]) is None
    doc.close()


def test_f22_without_page_keeps_previous_behaviour():
    doc, page = _framed_heading()
    covers, notes = _scan_covers(FRAMED_BLOCK, [], [], page.rect)
    assert covers is not None and covers[0][1] < 30.0
    assert "cover_clipped_off_rule" not in notes
    doc.close()


def _scanned_framed_heading():
    """Scanned page (2 px/pt) with a frame whose top/left rules touch a heading."""
    img = Image.new("RGB", (1190, 1684), (250, 250, 248))
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [100, 400, 1090, 560], outline=(20, 20, 20), width=2
    )  # frame at 50..545 x 200..280 pt
    draw.text(
        (140, 412),
        "Synthetic framed heading",
        fill=(20, 20, 20),
        font=ImageFont.load_default(size=22),
    )
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    return doc, doc.tobytes()


def test_f22b_plan_full_cover_stays_off_frame_rules():
    doc, source = _scanned_framed_heading()
    box = [50.3, 200.3, 230.0, 218.0]  # OCR box inflated up to the frame rules
    block = {
        "id": "p001-b0000",
        "page": 1,
        "text": "Synthetic framed heading",
        "bbox": box,
        "confidence": 0.93,
        "role": "line",
        "line_count": 1,
        "line_heights": [box[3] - box[1]],
        "line_pitch": None,
        "source_lines": [
            {
                "id": "p001-b0000-l0",
                "text": "Synthetic framed heading",
                "bbox": box,
                "confidence": 0.93,
            }
        ],
        "style": {"align": "left", "bold": False, "color": None, "highlight": False},
    }
    item, _issues, overflow = _plan_scan_block(
        block=block,
        target="Titre encadré",
        page=doc[0],
        page_number=1,
        ir_blocks=[block],
        protected_regions=[],
        body_size=9.0,
        body_right=545.0,
        source_bytes=source,
        bound=None,
    )
    assert item is not None and not overflow
    for key in ("source_rects", "full_source_rects"):
        cover = item[key][0]
        assert cover[1] >= 200.9, (key, cover)  # top rule (200..201 pt) left visible
        assert cover[0] >= 50.9, (key, cover)  # left rule (50..51 pt) left visible
        assert cover[3] > 212.0, (key, cover)  # the heading print is still covered
    doc.close()


def _line_block(text):
    return {
        "id": "p001-b0000",
        "text": text,
        "source_lines": [{"id": "p001-b0000-l0", "text": text}],
    }


def test_f23_rtl_line_with_multi_group_number_is_kept_as_image():
    for text in (
        "\u0627\u0644\u0647\u0627\u062a\u0641: 6789 345 (012)",  # Arabic label + reversed groups
        "contact@ example.org\u200f : 44 33 22 11 00",  # Latin line read with a bidi mark
    ):
        block, stats = _line_block(text), collections.Counter()
        flag_bidi_number_runs(block, stats)
        assert block.get("ocr_unreliable") is True, text
        assert block["ocr_unreliable_reason"] == "bidi_number_order_unreliable"
        assert stats["blocks_bidi_number_order_unreliable"] == 1


def test_f23_single_numbers_or_ltr_context_are_not_flagged():
    for text in (
        "\u0628\u062a\u0627\u0631\u064a\u062e 2031/04/17",  # Arabic + one date token
        "\u0631\u0642\u0645 2 \u0627\u0644\u0637\u0627\u0628\u0642 1",  # numbers separated by words
        "\u0627\u0644\u0645\u0628\u0644\u063a 1.234,56",  # one amount token
        "Tel: (012) 345 6789",  # multi-group number, left-to-right context
        "Rue Exemple N\u00b0 2, 1er \u00e9tage\u200f",  # list "2, 1" is not a number run
    ):
        block, stats = _line_block(text), collections.Counter()
        flag_bidi_number_runs(block, stats)
        assert not block.get("ocr_unreliable"), text


# --- F24: cover padding stays off rules, underlines and a neighbour's glyph --------


def _letters(page, x0: float, x1: float, y0: float = 41.0, y1: float = 49.0) -> None:
    """Synthetic print: 3 pt strokes with 1 pt gaps (never a continuous run)."""
    x = x0
    while x + 3 <= x1:
        page.draw_rect(fitz.Rect(x, y0, x + 3, y1), color=(0, 0, 0), fill=(0, 0, 0), width=0)
        x += 4


LINE_BLOCK = {
    "bbox": [20.0, 40.0, 100.0, 50.0],
    "source_lines": [{"bbox": [20.0, 40.0, 100.0, 50.0]}],
}


def test_f24_underline_or_row_rule_in_the_padding_is_not_covered():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    _letters(page, 20, 100)
    page.draw_line((20, 51.0), (100, 51.0), width=0.8)  # underline in the bottom padding
    old, _ = _scan_covers(LINE_BLOCK, [], [], page.rect)
    new, notes = _scan_covers(LINE_BLOCK, [], [], page.rect, page=page)
    assert old is not None and new is not None
    assert old[0][3] == 51.5  # previous padding swallowed the underline
    assert "cover_padding_pulled_off_foreign_ink" in notes
    assert 50.0 <= new[0][3] <= 50.7  # stops before the underline, keeps the box
    assert _ink_rows(page, 20, 100, 50.5, 52.0)  # the underline itself is still there
    doc.close()


def test_f24_neighbour_glyph_after_a_blank_gap_is_not_covered():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    _letters(page, 20, 96)
    page.draw_rect(fitz.Rect(101.5, 41, 103.5, 49), color=(0, 0, 0), fill=(0, 0, 0), width=0)
    new, notes = _scan_covers(LINE_BLOCK, [], [], page.rect, page=page)
    assert new is not None and "cover_padding_pulled_off_foreign_ink" in notes
    assert 100.0 <= new[0][2] <= 101.5  # the neighbour's glyph stays visible
    doc.close()


def test_f24_separator_printed_on_the_box_edge_after_a_blank_margin():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    _letters(page, 20, 96)  # own print ends at 95, box edge at 100.4
    block = {
        "bbox": [20.0, 40.0, 100.4, 50.0],
        "source_lines": [{"bbox": [20.0, 40.0, 100.4, 50.0]}],
    }
    page.draw_line((100.25, 40), (100.25, 50), width=0.5, dashes="[1 1] 0")  # dotted separator
    page.draw_rect(fitz.Rect(101.0, 41, 103.0, 49), color=(0, 0, 0), fill=(0, 0, 0), width=0)
    new, _ = _scan_covers(block, [], [], page.rect, page=page)
    assert new is not None and new[0][2] <= 101.0  # the glyph after the separator survives
    doc.close()


def test_f24_accents_and_own_overhang_are_still_covered():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    _letters(page, 20, 96)
    for x in (24, 40, 60):  # accents in the top padding: short marks, not rules
        page.draw_rect(fitz.Rect(x, 38.7, x + 1.2, 39.6), color=(0, 0, 0), fill=(0, 0, 0), width=0)
    page.draw_rect(
        fitz.Rect(96, 41, 101.6, 49), color=(0, 0, 0), fill=(0, 0, 0), width=0
    )  # own overhang
    assert (
        _pull_padding_off_foreign_ink(page, [20.0, 40.0, 100.0, 50.0], [17.0, 38.5, 103.0, 51.5])
        is None
    )
    doc.close()
