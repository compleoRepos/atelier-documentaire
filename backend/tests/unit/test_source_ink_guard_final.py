"""Final regressions (09/10): never draw a translation over unmasked source ink,
and never send minority-script low-confidence OCR noise to the model.

Synthetic rasters and texts only (no document of the private corpus).
"""

from __future__ import annotations

import io

import fitz
import httpx
import numpy as np
import pytest
from PIL import Image
from test_form_structure_guard_final import _page
from test_interim_owner_authorization import SHA, options
from test_line_verification_final import _response

from app.ai.translation.service import translate_blocks
from app.documents.line_verification import minority_script_noise, script_letters, verify_lines
from app.documents.pdf_fidelity import _drop_text_over_source_ink, _uncovered_source_ink


def _scan_doc(ink_boxes=(), rules_y=()):
    """One 300x200 pt page carrying a 1 px/pt raster. Ink boxes are drawn as
    glyph-like stems (1 pt every 3 pt, 6 pt tall): text, not a solid rule."""
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    for x0, y0, _x1, _y1 in ink_boxes:
        for x in range(x0, _x1, 3):
            arr[y0 + 1 : y0 + 7, x : x + 1] = 0
    for y in rules_y:
        arr[y : y + 1, :] = 0
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc


def _item(inner, covers, text="Bonjour", block_id="b1"):
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
        "source_rects": [list(c) for c in covers],
        "cover": None,
    }


IR_SCANNED = {"pages": [{"number": 1, "scanned": True}]}


def test_text_over_unmasked_source_ink_is_dropped_with_critical_issue():
    doc = _scan_doc(ink_boxes=[(22, 24, 70, 32)])
    issues = []
    kept = _drop_text_over_source_ink(doc, IR_SCANNED, [_item([20, 20, 200, 40], [])], issues)
    assert kept == []
    assert [i["code"] for i in issues] == ["SCAN_TEXT_OVER_SOURCE_INK"]
    assert issues[0]["severity"] == "critical" and issues[0]["block_id"] == "b1"
    assert issues[0]["ink_pixels"] >= 60


def test_masked_source_ink_does_not_block_the_replacement():
    doc = _scan_doc(ink_boxes=[(22, 24, 70, 32)])
    issues = []
    item = _item([20, 20, 200, 40], [[20, 22, 72, 34]])
    assert _drop_text_over_source_ink(doc, IR_SCANNED, [item], issues) == [item]
    assert issues == []


def test_table_rule_through_the_line_is_structure_not_residual_text():
    doc = _scan_doc(rules_y=[28])
    count, area = _uncovered_source_ink(doc[0], [20, 22, 200, 34], [])
    assert count == 0 and area > 0
    issues = []
    item = _item([20, 20, 200, 40], [])
    assert _drop_text_over_source_ink(doc, IR_SCANNED, [item], issues) == [item]


def test_ink_only_in_the_blank_part_of_a_grown_frame_is_not_under_drawn_text():
    # Frame grown far to the right; ink lies beyond the short drawn word.
    doc = _scan_doc(ink_boxes=[(230, 24, 290, 32)])
    issues = []
    item = _item([20, 20, 295, 40], [], text="Oui")
    assert _drop_text_over_source_ink(doc, IR_SCANNED, [item], issues) == [item]


def test_fixed_point_drops_items_that_relied_on_a_dropped_neighbour_mask():
    # A has uncovered ink under its own text; B's ink is hidden only by A's mask.
    doc = _scan_doc(ink_boxes=[(22, 24, 70, 32), (22, 104, 70, 112)])
    a = _item([20, 20, 200, 40], [[20, 98, 120, 116]], block_id="A")
    b = _item([20, 100, 200, 120], [], block_id="B")
    issues = []
    assert _drop_text_over_source_ink(doc, IR_SCANNED, [a, b], issues) == []
    assert sorted(i["block_id"] for i in issues) == ["A", "B"]


def test_native_pages_are_not_measured():
    doc = _scan_doc(ink_boxes=[(22, 24, 70, 32)])
    issues = []
    item = _item([20, 20, 200, 40], [])
    ir = {"pages": [{"number": 1, "scanned": False}]}
    assert _drop_text_over_source_ink(doc, ir, [item], issues) == [item] and issues == []


def test_minority_script_noise_rule():
    latin_page = script_letters("Resumen anual de aportaciones al regimen numero " * 4)
    arabic_page = script_letters("عقد إيجار سكن لمدة عام " * 6)
    noise = {"text": "مهمه", "confidence": 0.17}
    assert minority_script_noise(noise, latin_page, sum(latin_page.values()))
    # same script as the page, or a confident reading: genuine text
    assert not minority_script_noise(noise, arabic_page, sum(arabic_page.values()))
    confident = {"text": "مهمه", "confidence": 0.9}
    assert not minority_script_noise(confident, latin_page, sum(latin_page.values()))
    latin_low = {"text": "Regimen", "confidence": 0.3}
    assert not minority_script_noise(latin_low, latin_page, sum(latin_page.values()))
    assert not minority_script_noise({"text": "1234", "confidence": 0.1}, latin_page, 100)


def test_verify_lines_marks_minority_script_noise_idempotently():
    noise = {
        "id": "p001-b0001",
        "text": "مهمه",
        "confidence": 0.17,
        "style": {},
        "source_lines": [{"id": "l1", "text": "مهمه", "bbox": [50, 60, 90, 70]}],
    }
    body = {
        "id": "p001-b0000",
        "text": "Resumen anual de las aportaciones de la sociedad en cada ejercicio",
        "confidence": 0.93,
        "style": {},
        "source_lines": [{"id": "l0", "text": "Datos", "bbox": [50, 40, 400, 50]}],
    }
    ir = {"pages": [{"number": 1, "scanned": True, "blocks": [body, noise]}]}
    stats = verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters={1: _page()})
    assert noise.get("minority_script_low_confidence") is True
    assert "minority_script_low_confidence" not in body
    assert stats["blocks_minority_script_low_confidence"] == 1
    noise["confidence"] = 0.95
    verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters={1: _page()})
    assert "minority_script_low_confidence" not in noise


@pytest.mark.asyncio
async def test_minority_script_noise_is_never_sent_and_is_reported(tmp_path):
    seen = []

    def handler(request):
        import json

        blocks = json.loads(json.loads(request.content)["messages"][1]["content"])["blocks"]
        seen.extend(b["id"] for b in blocks)
        return _response([(b["id"], f"Traduction {b['id']}.") for b in blocks])

    ir = {
        "language": "es",
        "domain": "HR",
        "versions": {"source_sha256": SHA},
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {
                        "id": "b1",
                        "text": "مهمه",
                        "language": "ara",
                        "minority_script_low_confidence": True,
                    },
                    {"id": "b2", "text": "El trabajador presta servicios.", "language": "spa"},
                ],
            }
        ],
    }
    result = await translate_blocks(ir, options(tmp_path, httpx.MockTransport(handler)))
    assert seen == ["b2"]
    assert result["translations"]["b1"] == "مهمه"
    noise = [i for i in result["issues"] if i["code"] == "OCR_SCRIPT_INCONSISTENT_NOT_TRANSLATED"]
    assert noise and noise[0]["severity"] == "warning" and noise[0]["block_id"] == "b1"
