"""Tesseract lines spanning separate zones are split at large blanks.

Measured on the authorised corpus (synthetic reproduction only): Tesseract put a
ministry name and a header 265 pt apart, four form cells, and a footer with its
far-right "Page No:" into single lines. The line box then spanned the blank: the
width-based size reached 19.9 pt for 7 pt print and translations were written
across cells.
"""

from __future__ import annotations

from PIL import Image
from test_segmentation_final import _line, _page
from test_tesseract_timeout_retry import _engine

from app.ai.ocr.tesseract import split_line_at_gaps
from app.documents.segmentation import segment_page


def _item(words):
    """words: (text, left, right, top, bottom, conf) in OCR reading order."""
    keys = ("text", "left", "right", "top", "bottom", "confidence")
    return {k: [w[i] for w in words] for i, k in enumerate(keys)}


def test_line_is_split_where_the_blank_exceeds_twice_the_word_height():
    item = _item(
        [
            ("MINISTERIO", 40, 160, 100, 120, 0.9),
            ("SERVICIO", 600, 700, 100, 120, 0.8),
            ("PÚBLICO", 708, 800, 100, 120, 0.7),
        ]
    )
    segments = split_line_at_gaps(item)
    assert [s["text"] for s in segments] == ["MINISTERIO", "SERVICIO PÚBLICO"]
    assert segments[0]["bbox"] == [40, 100, 160, 120]
    assert segments[1]["bbox"] == [600, 100, 800, 120]
    assert abs(segments[1]["confidence"] - 0.75) < 1e-9


def test_normal_and_justified_spaces_never_split():
    item = _item(
        [
            ("The", 10, 50, 100, 120, 0.9),
            ("employee", 56, 150, 100, 120, 0.9),  # normal space 6 px (0.3 h)
            ("works", 168, 230, 100, 120, 0.9),  # justified space 18 px (0.9 h)
            ("full", 262, 300, 100, 120, 0.9),  # wide justified space 32 px (1.6 h)
        ]
    )
    assert [s["text"] for s in split_line_at_gaps(item)] == ["The employee works full"]


def test_right_to_left_reading_order_is_kept_inside_a_segment():
    # OCR reading order for Arabic runs right to left: order 0 is the rightmost word.
    item = _item([("الهاتف", 400, 470, 100, 120, 0.9), ("رقم", 340, 392, 100, 120, 0.9)])
    assert [s["text"] for s in split_line_at_gaps(item)] == ["الهاتف رقم"]


def test_image_to_blocks_returns_one_block_per_zone_and_traces_the_split(monkeypatch):
    keys = ("text", "conf", "block_num", "par_num", "line_num", "left", "top", "width", "height")
    rows = [
        ("Company", "90", 10, 120),
        ("footer", "90", 125, 170),
        ("Page", "88", 900, 950),
        ("No:", "88", 955, 990),
    ]
    data = {k: [] for k in keys}
    for text, conf, left, right in rows:
        for k, v in zip(keys, (text, conf, 1, 1, 1, left, 100, right - left, 20), strict=True):
            data[k].append(v)
    engine = _engine(monkeypatch, [data], [])
    result = engine.image_to_blocks(Image.new("RGB", (1000, 200), "white"))
    assert [b["text"] for b in result.blocks] == ["Company footer", "Page No:"]
    split = [w for w in result.warnings if w["code"] == "OCR_LINE_SPLIT_AT_GAP"]
    assert split and split[0]["count"] == 1 and split[0]["severity"] == "info"


def test_side_by_side_segments_on_one_baseline_stay_separate_blocks():
    blocks = [
        _line(0, "Employer name and address of the company", 60, 200, 300),
        _line(1, "Page No: 2", 470, 200, 530),
    ]
    out, _trace = segment_page(_page(blocks))
    texts = sorted(b["text"] for b in out)
    assert texts == ["Employer name and address of the company", "Page No: 2"]
