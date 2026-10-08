"""Scan mosaics stored as same-width strips inside page margins are background,
while a separate small image on the scan stays protected. Synthetic PDFs only."""

from __future__ import annotations

import io

import fitz
from PIL import Image

from app.documents.protected_visuals import detect_pdf_visuals


def _png(width: int, height: int, shade: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (shade, shade, shade)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_margin_strips_are_background_but_separate_logo_is_protected(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    strip = _png(60, 6, 240)
    y = 60.0
    while y < 780:  # strips cover x 70..525 (76 % of the width)
        page.insert_image(fitz.Rect(70, y, 525, y + 12), stream=strip, keep_proportion=False)
        y += 12
    page.insert_image(fitz.Rect(30, 20, 60, 50), stream=_png(10, 10, 20))  # separate logo
    path = tmp_path / "scan.pdf"
    doc.save(path)
    regions, warnings = detect_pdf_visuals(path, [{"number": 1, "scanned": True, "blocks": []}], [])
    images = [r for r in regions if r["provenance"] == "pdf_embedded_image_original"]
    assert len(images) == 1
    assert images[0]["bbox"] == [30.0, 20.0, 60.0, 50.0]
    assert any(w.get("background_strips", 0) >= 50 for w in warnings)


def test_native_pdf_images_are_not_treated_as_scan_background(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for y in (100, 300):
        page.insert_image(
            fitz.Rect(70, y, 525, y + 180), stream=_png(40, 16, 120), keep_proportion=False
        )
    path = tmp_path / "native.pdf"
    doc.save(path)
    regions, _ = detect_pdf_visuals(path, [{"number": 1, "scanned": False, "blocks": []}], [])
    assert len([r for r in regions if r["provenance"] == "pdf_embedded_image_original"]) == 2
