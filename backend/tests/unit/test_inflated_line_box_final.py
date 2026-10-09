"""Inflated OCR line boxes (prompt final, run9 visual audit, synthetic only).

1. A crest fragment read as a tall "word" made a 7 pt line box 22.5 pt tall:
   font 12.7 pt and a mask erasing the line above. It is now isolated by OCR.
2. A one-line section heading whose box was taller than its print wrapped its
   translation onto the table row below. One source line now stays one line:
   reduced (>= 72 %), extended right, or LAYOUT_OVERFLOW — never wrapped.
"""

from __future__ import annotations

from test_ocr_line_gap_split import _item
from test_scan_render_plan_final import _plan

from app.ai.ocr.tesseract import split_line_at_gaps


def test_tall_graphic_word_is_isolated_from_the_line_it_inflates():
    item = _item(
        [
            ("2", 68, 80, 79, 102, 0.6),  # crest fragment, 23 px tall
            ("Y", 84, 90, 92, 100, 0.9),
            ("ASUNTOS", 93, 150, 92, 100, 0.9),
            ("GENERAL", 154, 190, 92, 100, 0.9),
        ]
    )
    segments = split_line_at_gaps(item)
    assert [s["text"] for s in segments] == ["2", "Y ASUNTOS GENERAL"]
    assert segments[1]["bbox"] == [84, 92, 190, 100]  # true print height restored


def test_ascenders_and_descenders_never_isolate_a_word():
    item = _item(
        [
            ("on", 10, 30, 104, 112, 0.9),  # x-height only
            ("Typography", 34, 120, 100, 118, 0.9),  # ascender + descender
            ("is", 124, 134, 100, 112, 0.9),
            ("nice", 138, 170, 100, 112, 0.9),
        ]
    )
    assert [s["text"] for s in split_line_at_gaps(item)] == ["on Typography is nice"]


def _heading(box_height: float):
    text = "DETALLES DEL AÑO DE APORTACIONES"
    box = [60.0, 284.0, 172.0, 284.0 + box_height]
    return {
        "id": "p001-b0032",
        "page": 1,
        "text": text,
        "bbox": box,
        "confidence": 0.93,
        "role": "heading",
        "font_size": 6.4,
        "line_count": 1,
        "line_heights": [box_height],
        "source_lines": [{"id": "l0", "text": text, "bbox": box, "confidence": 0.93}],
        "style": {"align": "left", "bold": True, "color": None, "highlight": False},
    }


def test_one_line_heading_in_a_tall_box_is_not_wrapped_onto_the_next_row():
    target = "RÉCAPITULATIF ANNUEL DE TOUS LES APPORTS"
    item, issues, overflow = _plan(_heading(14.0), target)
    assert item is not None and not overflow
    x0, y0, x1, y1 = item["inner"]
    assert y1 - y0 <= 1.45 * 9.0 + 1e-6  # one line height at most (body 9 pt)
    assert x1 > 172.0  # extended into the blank space on the right instead


def _other(block_id: str, bbox: list[float]):
    return _heading(14.0) | {
        "id": block_id,
        "bbox": bbox,
        "source_lines": [{"id": f"{block_id}-l0", "text": "x", "bbox": bbox, "confidence": 0.9}],
    }


def test_one_line_heading_without_room_reports_overflow_instead_of_wrapping():
    target = "RÉCAPITULATIF ANNUEL DE TOUS LES APPORTS " * 4
    right = _other("p001-b0099", [176.0, 284.0, 530.0, 298.0])
    # The next table row starts inside the tall OCR box: the old obstacle filter
    # ignored it because it overlaps the block's own box.
    row_below = _other("p001-b0100", [60.0, 296.0, 172.0, 306.0])
    item, issues, overflow = _plan(_heading(14.0), target, others=[right, row_below])
    assert item is None and overflow
    assert any(i["code"] == "LAYOUT_OVERFLOW" and i["severity"] == "critical" for i in issues)
    assert not any(i["code"] == "SINGLE_LINE_WRAPPED_INTO_BLANK" for i in issues)


def test_one_line_block_may_wrap_only_into_space_proven_blank():
    target = "RÉCAPITULATIF ANNUEL DE TOUS LES APPORTS " * 2
    right = _other("p001-b0099", [176.0, 284.0, 530.0, 298.0])
    item, issues, overflow = _plan(_heading(14.0), target, others=[right])
    assert item is not None and not overflow  # blank paper below, no box, no stamp
    assert any(
        i["code"] == "SINGLE_LINE_WRAPPED_INTO_BLANK" and i["severity"] == "info" for i in issues
    )
    x0, y0, x1, y1 = item["inner"]
    assert x1 <= 176.0 + 1e-6  # never over the neighbour on the right


def test_ink_under_a_one_line_block_forbids_the_wrap_fallback():
    """A table rule or label printed under the line (no OCR box) is ink: the
    translation must not be wrapped over it; LAYOUT_OVERFLOW stays visible."""
    import io

    import fitz
    from PIL import Image, ImageDraw

    from app.documents.pdf_fidelity import _plan_scan_block

    image = Image.new("RGB", (595, 842), (250, 250, 248))
    ImageDraw.Draw(image).rectangle([40, 300, 560, 304], fill=(20, 20, 20))  # ruled row
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    block = _heading(14.0)
    right = _other("p001-b0099", [176.0, 284.0, 530.0, 298.0])
    item, issues, overflow = _plan_scan_block(
        block=block,
        target="RÉCAPITULATIF ANNUEL DE TOUS LES APPORTS " * 2,
        page=doc[0],
        page_number=1,
        ir_blocks=[block, right],
        protected_regions=[],
        body_size=9.0,
        body_right=532.0,
        source_bytes=doc.tobytes(),
        bound=None,
    )
    assert item is None and overflow
    assert not any(i["code"] == "SINGLE_LINE_WRAPPED_INTO_BLANK" for i in issues)
