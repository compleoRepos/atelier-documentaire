"""Line verification (final corpus audit): highlight evidence and critical-entity
double reading. Synthetic rasters and texts only; the OCR reader is injected.

Measured defects (DOC-006, final run): a pink-highlighted date read 30/12/2021
instead of 10/12/2021 was rewritten over the original; the highlight of
translated lines was lost because paper colour came from the brightest pixels.
"""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest
from test_interim_owner_authorization import SHA, options
from test_scan_render_plan_final import FR, _paragraph, _plan

from app.ai.translation.service import translate_blocks
from app.documents.line_verification import (
    compare_readings,
    digit_sequence,
    highlight_evidence,
    verify_lines,
)

PINK = (245, 160, 205)


def _raster(highlight_box=None):
    rgb = np.full((400, 2400, 3), 250, dtype=np.uint8)
    if highlight_box:
        x0, y0, x1, y1 = highlight_box
        rgb[y0:y1, x0:x1] = PINK
    rgb[210:230, 200:260] = 20  # dark "ink" strokes
    rgb[210:230, 400:470] = 20
    return rgb


def test_highlight_measured_on_saturated_light_pixels_not_paper():
    marked = highlight_evidence(_raster((180, 196, 1000, 244)), [180, 200, 1100, 240])
    assert marked["highlight"] is True and marked["coverage"] >= 0.10
    assert marked["rgb"][0] > marked["rgb"][1]  # pink, not white paper
    assert marked["partial"] is False
    plain = highlight_evidence(_raster(), [180, 200, 1100, 240])
    assert plain["highlight"] is False


def test_partial_highlight_is_reported_as_partial():
    mark = highlight_evidence(_raster((180, 196, 600, 244)), [180, 200, 1100, 240])
    assert mark["highlight"] is True and mark["partial"] is True


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("Start date 30/12/2021", "Start date 10/12/2021", "disagree"),
        ("Start date 10/12/2021", "Start date 10/12/2021", "agree"),
        ("Tel +44 (0) 20 7946 0716", "Tel +44 (0) 20 7946 0716", "agree"),
        ("Ref 113", "", "inconclusive"),
        ("17 September 2021", "17 September 2021 8", "agree"),
        ("Amount 12 450,00", "Amount 12 450", "inconclusive"),
        ("No digits here", "anything 99", "not_applicable"),
        ("Page 3", "Page 8", "not_applicable"),
    ],
)
def test_entity_readings_comparison(first, second, expected):
    assert compare_readings(first, second) == expected


def test_digit_sequence_ignores_spacing_and_single_digits():
    assert digit_sequence("+44 (0) 20 7946 0716") == "442079460716"
    assert digit_sequence("+44 (0)20 79460716") == digit_sequence("+44 (0) 20 7946 0716")


def _ir_with(lines):
    block = {
        "id": "p001-b0000",
        "page": 1,
        "text": " ".join(t for t, _ in lines),
        "bbox": [40, 50, 300, 50 + 15 * len(lines)],
        "style": {"align": "left", "highlight": False},
        "source_lines": [
            {"id": f"p001-b0000-l{i}", "text": t, "bbox": b, "confidence": 0.84}
            for i, (t, b) in enumerate(lines)
        ],
    }
    return {
        "pages": [{"number": 1, "scanned": True, "width": 600, "height": 100, "blocks": [block]}]
    }, block


def test_disagreeing_second_reading_marks_block_and_keeps_counts_only():
    ir, block = _ir_with([("Start date 30/12/2021", [45, 50, 275, 61])])
    stats = verify_lines(
        ir,
        "unused.pdf",
        reader=lambda _img: "Start date 10/12/2021",
        rasters={1: _raster((180, 196, 1100, 244))},
    )
    assert block["entity_read_disagreement"] == {"line_ids": ["p001-b0000-l0"], "count": 1}
    assert stats["disagree"] == 1 and stats["blocks_disagreement"] == 1
    assert block["style"]["highlight"] is True and "highlight_rgb" in block["style"]
    assert "10/12/2021" not in json.dumps(ir)  # the second reading is never stored


def test_agreeing_or_inconclusive_reading_does_not_block():
    ir, block = _ir_with(
        [("Start date 10/12/2021", [45, 50, 275, 61]), ("Ref 113", [45, 64, 120, 75])]
    )
    answers = iter(["Start date 10/12/2021", ""])
    stats = verify_lines(
        ir,
        "unused.pdf",
        reader=lambda _img: next(answers),
        rasters={1: _raster((180, 196, 1100, 304))},
    )
    assert "entity_read_disagreement" not in block
    assert stats["agree"] == 1 and stats["inconclusive"] == 1


def test_unavailable_reader_is_inconclusive_never_agreement():
    ir, block = _ir_with([("Start date 30/12/2021", [45, 50, 275, 61])])
    stats = verify_lines(
        ir, "unused.pdf", reader=lambda _img: None, rasters={1: _raster((180, 196, 1100, 244))}
    )
    assert stats["inconclusive"] == 1 and stats["agree"] == 0
    assert "entity_read_disagreement" not in block


def test_clean_line_is_explicitly_not_checked_never_agreement():
    """Corpus audit: on clean small bold text the single-line reader was less
    accurate than the page OCR (false disagreements), so no marker = no claim."""
    ir, block = _ir_with([("tel. 041 5550111 - fax 041 5550110", [45, 50, 275, 61])])

    def reader(_img):
        raise AssertionError("no second reading without a marker")

    stats = verify_lines(ir, "unused.pdf", reader=reader, rasters={1: _raster()})
    assert block["source_lines"][0]["entity_double_read"] == "not_checked_no_marker"
    assert stats["not_checked_no_marker"] == 1 and stats["agree"] == 0
    assert "entity_read_disagreement" not in block


def _response(pairs):
    content = json.dumps({"translations": [{"id": i, "text": t} for i, t in pairs]})
    return httpx.Response(
        200,
        json={
            "model": "gpt-5-mini",
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 10,
                "total_tokens": 130,
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
        },
    )


@pytest.mark.asyncio
async def test_disagreeing_block_is_never_sent_nor_rewritten(tmp_path):
    seen = []

    def handler(request):
        blocks = json.loads(json.loads(request.content)["messages"][1]["content"])["blocks"]
        seen.extend(b["id"] for b in blocks)
        return _response([(b["id"], f"Traduction {b['id']}.") for b in blocks])

    ir = {
        "language": "en",
        "domain": "HR",
        "versions": {"source_sha256": SHA},
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {
                        "id": "b1",
                        "text": "Start date 30/12/2021",
                        "language": "eng",
                        "entity_read_disagreement": {"line_ids": ["b1"], "count": 1},
                    },
                    {"id": "b2", "text": "The employee works full time.", "language": "eng"},
                ],
            }
        ],
    }
    result = await translate_blocks(ir, options(tmp_path, httpx.MockTransport(handler)))
    assert seen == ["b2"]
    assert result["translations"]["b1"] == "Start date 30/12/2021"
    issue = [i for i in result["issues"] if i["code"] == "OCR_CRITICAL_ENTITY_DISAGREEMENT"]
    assert issue and issue[0]["severity"] == "error" and issue[0]["block_id"] == "b1"


def test_renderer_fills_highlighted_line_with_measured_colour_only():
    block = _paragraph()
    rgb = [0.96, 0.63, 0.8]
    block["source_lines"][1]["highlight_evidence"] = {
        "highlight": True,
        "rgb": rgb,
        "partial": True,
    }
    block["source_lines"][0]["highlight_evidence"] = {"highlight": False}
    block["source_lines"][2]["highlight_evidence"] = {"highlight": False}
    item, issues, _ = _plan(block, FR)
    assert item is not None
    fills = item["cover_fills"]
    assert fills[1] == rgb
    assert fills[0] != rgb and fills[2] != rgb
    assert any(i["code"] == "HIGHLIGHT_SPAN_APPROXIMATED" for i in issues)
