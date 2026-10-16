"""Targeted regressions required by the final audit (§16) that had no dedicated
test: residual source text, low contrast, and the real-OCR second reading of a
highlighted critical value. Synthetic documents only.
"""

from __future__ import annotations

import json
import shutil

import fitz
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.documents.line_verification import verify_lines
from app.documents.pdf_fidelity import render_pdf
from app.documents.render_metrics import measure_render_fidelity

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract absent")
SOURCE = "Employment certificate for the employee"
TARGET = "Attestation de travail du salarié"


def _native(tmp_path):
    path = tmp_path / "source.pdf"
    with fitz.open() as doc:
        doc.new_page(width=595, height=842).insert_text((72, 100), SOURCE, fontsize=11)
        doc.save(path)
    with fitz.open(path) as doc:
        bbox = list(doc[0].get_text("dict")["blocks"][0]["bbox"])
    ir = {
        "format": "pdf",
        "pages": [
            {
                "number": 1,
                "width": 595,
                "height": 842,
                "scanned": False,
                "blocks": [
                    {
                        "id": "p001-b0000",
                        "page": 1,
                        "kind": "text",
                        "text": SOURCE,
                        "bbox": bbox,
                        "font_size": 11,
                        "language": "eng",
                    }
                ],
            }
        ],
    }
    return path, ir


def test_residual_source_text_is_detected_when_translation_is_not_rendered(tmp_path):
    source, ir = _native(tmp_path)
    result = measure_render_fidelity(
        source,
        source,
        source_ir=ir,
        translations={"p001-b0000": TARGET},
        work_dir=tmp_path / "proof",
    )
    codes = {i["code"] for i in result["issues"]}
    assert "RENDER_TRANSLATED_TEXT_MISSING" in codes
    assert all(
        i["severity"] == "critical" for i in result["issues"] if i["code"].startswith("RENDER_")
    )


def test_rendered_translation_leaves_no_source_text(tmp_path):
    source, ir = _native(tmp_path)
    out = tmp_path / "candidate.pdf"
    render_pdf(ir, {"p001-b0000": TARGET}, source, out)
    with fitz.open(out) as doc:
        text = doc[0].get_text()
    assert TARGET in text and "Employment" not in text
    result = measure_render_fidelity(
        source, out, source_ir=ir, translations={"p001-b0000": TARGET}, work_dir=tmp_path / "proof"
    )
    assert not [i for i in result["issues"] if i["code"].startswith("RENDER_")]


@needs_tesseract
def test_low_contrast_scan_gets_contrast_variant_and_keeps_values(tmp_path):
    from app.ai.ocr.tesseract import TesseractOCR
    from app.documents.preprocessing import diagnose, preprocess_image

    image = Image.new("RGB", (1700, 500), (232, 232, 228))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 44)
    draw.text((80, 120), "The employee started work on 10/12/2021", fill=(178, 178, 172), font=font)
    draw.text((80, 240), "Monthly salary paid by bank transfer", fill=(178, 178, 172), font=font)
    assert diagnose(np.asarray(image))["contrast"] < 140
    result = preprocess_image(image, TesseractOCR(languages="eng"), tmp_path / "pp", max_variants=6)
    assert "clahe" in json.dumps(result.metadata.get("variants"))
    text = " ".join(b["text"] for b in result.ocr.blocks)
    assert "10/12/2021" in text and "salary" in text


def _highlighted_date_raster():
    rgb = Image.new("RGB", (2400, 400), (250, 250, 248))
    draw = ImageDraw.Draw(rgb)
    draw.rectangle([170, 186, 1150, 258], fill=(245, 160, 205))
    draw.text(
        (190, 192), "Start date 10/12/2021", fill=(25, 25, 25), font=ImageFont.truetype(FONT, 56)
    )
    return np.asarray(rgb)


@needs_tesseract
@pytest.mark.parametrize(
    ("primary", "expected"),
    [("Start date 30/12/2021", "disagree"), ("Start date 10/12/2021", "agree")],
)
def test_real_second_reading_under_highlight(primary, expected):
    block = {
        "id": "p001-b0000",
        "page": 1,
        "text": primary,
        "bbox": [42, 46, 290, 65],
        "style": {"align": "left", "highlight": False},
        "source_lines": [{"id": "p001-b0000-l0", "text": primary, "bbox": [42, 46, 290, 65]}],
    }
    ir = {"pages": [{"number": 1, "scanned": True, "width": 600, "height": 100, "blocks": [block]}]}
    stats = verify_lines(ir, "unused.pdf", rasters={1: _highlighted_date_raster()})
    assert block["source_lines"][0]["entity_double_read"] == expected
    assert stats[expected] == 1
    assert block["style"]["highlight"] is True
    assert ("entity_read_disagreement" in block) is (expected == "disagree")
