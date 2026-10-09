"""Scan replacement planning (prompt final, §6): per-line paper covers, measured
style, bounded font reduction, overflow reported (never silently truncated),
protected stamps avoided or blocking. Synthetic scanned page only."""

from __future__ import annotations

import io

import fitz
from PIL import Image

from app.documents.pdf_fidelity import _plan_scan_block, _scan_body_size, _scan_font_size


def _scanned_page():
    buffer = io.BytesIO()
    Image.new("RGB", (595, 842), (250, 250, 248)).save(buffer, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    return doc, doc.tobytes()


def _paragraph(style=None, line_boxes=None, block_id="p001-b0000"):
    line_boxes = line_boxes or [[60, 200, 530, 210], [60, 213, 532, 223], [60, 226, 200, 236]]
    texts = [
        "Nora Dubois has been our permanent Office Coordinator since the",
        "services county from 4.11.2021 until today and she was in charge of",
        "the daily planning.",
    ][: len(line_boxes)]
    xs0, ys0, xs1, ys1 = zip(*line_boxes, strict=True)
    return {
        "id": block_id,
        "page": 1,
        "text": " ".join(texts),
        "bbox": [min(xs0), min(ys0), max(xs1), max(ys1)],
        "confidence": 0.93,
        "role": "paragraph" if len(line_boxes) > 1 else "line",
        "line_count": len(line_boxes),
        "line_heights": [b[3] - b[1] for b in line_boxes],
        "line_pitch": 13.0 if len(line_boxes) > 1 else None,
        "source_lines": [
            {"id": f"{block_id}-l{i}", "text": t, "bbox": b, "confidence": 0.93}
            for i, (t, b) in enumerate(zip(texts, line_boxes, strict=True))
        ],
        "style": style or {"align": "left", "bold": False, "color": None, "highlight": False},
    }


def _plan(block, target, regions=(), others=()):
    doc, source = _scanned_page()
    return _plan_scan_block(
        block=block,
        target=target,
        page=doc[0],
        page_number=1,
        ir_blocks=[block, *others],
        protected_regions=list(regions),
        body_size=9.0,
        body_right=532.0,
        source_bytes=source,
        bound=None,
    )


FR = (
    "Nora Dubois a travaillé à temps plein comme assistante de direction au sein du comté "
    "de services depuis le 4.11.2021 et elle était chargée de la planification quotidienne."
)


def test_grouped_paragraph_gets_one_cover_per_source_line_and_one_text_box():
    item, issues, overflow = _plan(_paragraph(), FR)
    assert item is not None and not overflow
    assert len(item["source_rects"]) == 3  # every OCR line masked, not a page-wide rectangle
    assert item["source_line_ids"] == ["p001-b0000-l0", "p001-b0000-l1", "p001-b0000-l2"]
    for cover, line in zip(item["source_rects"], _paragraph()["source_lines"], strict=True):
        assert cover[0] <= line["bbox"][0] and cover[2] >= line["bbox"][2]
        assert cover[3] - cover[1] <= (line["bbox"][3] - line["bbox"][1]) + 3.01  # bounded padding
    assert item["size"] >= 0.72 * item["measured_size"]


def test_measured_bold_and_highlight_are_applied():
    style = {
        "align": "left",
        "bold": True,
        "color": [0.7, 0.1, 0.1],
        "highlight": True,
        "background": [1.0, 0.92, 0.43],
    }
    item, _, _ = _plan(_paragraph(style=style), FR)
    assert item["style"]["bold"] is True and item["style"]["color"] == [0.7, 0.1, 0.1]
    assert all(fill == [1.0, 0.92, 0.43] for fill in item["cover_fills"])


def test_overflow_is_reported_and_source_kept_instead_of_truncating():
    obstacle = {
        "id": "below",
        "text": "Signature",
        "bbox": [60, 212, 300, 222],
        "source_lines": None,
    }
    block = _paragraph(line_boxes=[[60, 200, 200, 210]])
    item, issues, overflow = _plan(block, FR * 3, others=[obstacle])
    assert item is None and overflow is True
    issue = next(i for i in issues if i["code"] == "LAYOUT_OVERFLOW")
    assert issue["severity"] == "critical" and issue["block_id"] == "p001-b0000"


def test_stamp_touching_the_corner_is_avoided_not_overwritten():
    stamp = {
        "id": "s1",
        "page": 1,
        "bbox": [480, 220, 580, 300],
        "provenance": "automatic_candidate:preprocessing",
    }
    item, issues, _ = _plan(_paragraph(), FR, regions=[stamp])
    assert item is not None
    inner = item["inner"]
    assert not (inner[0] < 580 and inner[2] > 480 and inner[1] < 300 and inner[3] > 220)
    for cover in item["source_rects"]:
        assert not (cover[0] < 580 and cover[2] > 480 and cover[1] < 300 and cover[3] > 220)


def test_stamp_covering_the_text_blocks_the_replacement():
    stamp = {
        "id": "s2",
        "page": 1,
        "bbox": [60, 195, 300, 240],
        "provenance": "automatic_candidate:preprocessing",
    }
    item, issues, _ = _plan(_paragraph(), FR, regions=[stamp])
    assert item is None
    assert any(i["code"] == "PROTECTED_TRANSLATION_NOT_APPLIED" for i in issues)


def test_body_lines_share_one_size_and_headings_keep_theirs():
    first = _paragraph()
    second = _paragraph(
        line_boxes=[[60, 300, 528, 309.4], [60, 313, 531, 322.6]], block_id="p001-b0004"
    )
    body = _scan_body_size([first, second])
    assert body is not None
    # Same body text keeps ONE size despite OCR box jitter.
    assert _scan_font_size(first, body) == _scan_font_size(second, body) == body
    heading = _paragraph(line_boxes=[[60, 150, 330, 166]], block_id="p001-b0009")
    heading["text"] = heading["source_lines"][0]["text"] = "Employment certificate"
    heading["role"] = "heading"
    assert _scan_font_size(heading, body) > 1.2 * body
