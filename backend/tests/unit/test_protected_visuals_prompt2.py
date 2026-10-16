from __future__ import annotations

import hashlib

import fitz
import pytest
from PIL import Image

from app.documents.pipeline import analyze_document, reconstruct_document
from app.documents.protected_visuals import normalize_regions, protect_ir


def test_region_coordinates_fail_closed():
    pages = [{"number": 1, "width": 100, "height": 100}]
    for bbox in ([0, 0, float("nan"), 30], [-1, 0, 20, 20], [0, 0, 101, 20], [20, 20, 0, 0]):
        with pytest.raises(ValueError):
            normalize_regions([{"bbox": bbox}], pages, "source")
    result = normalize_regions(
        [{"bbox": [0, 0, 20, 20], "editable": True, "subtype": "stamp"}], pages, "source"
    )
    assert result[0]["editable"] is False
    assert result[0]["authenticity_verified"] is False


def test_embedded_original_image_is_protected_without_identity_claim(tmp_path):
    source = tmp_path / "source.pdf"
    image = tmp_path / "mark.png"
    Image.new("RGB", (40, 40), "blue").save(image)
    with fitz.open() as document:
        page = document.new_page(width=240, height=160)
        page.insert_text((20, 40), "Original text")
        page.insert_image(fitz.Rect(170, 90, 210, 130), filename=str(image))
        document.save(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    protect_ir(ir)
    region = next(r for r in ir["protected_visual_regions"] if r["subtype"] == "image_candidate")
    assert region["bbox"] == [170, 90, 210, 130]
    assert region["editable"] is False
    assert region["authenticity_verified"] is False
    block = ir["pages"][0]["blocks"][0]
    result = reconstruct_document(
        ir, {block["id"]: "Texte traduit"}, str(tmp_path / "candidate.pdf")
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == sha
    assert result["protected_region_results"][0]["preserved"] is True


def test_output_cannot_overwrite_original_or_alias(tmp_path):
    source = tmp_path / "source.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((40, 40), "Source immutable")
        document.save(source)
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    original = source.read_bytes()
    with pytest.raises(ValueError, match="original|source|Original"):
        reconstruct_document(ir, {}, str(source))
    alias = tmp_path / "alias.pdf"
    alias.symlink_to(source)
    with pytest.raises(ValueError):
        reconstruct_document(ir, {}, str(alias))
    assert source.read_bytes() == original


def test_source_hash_mismatch_blocks_reconstruction(tmp_path):
    source = tmp_path / "source.pdf"
    with fitz.open() as document:
        document.new_page()
        document.save(source)
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    source.write_bytes(source.read_bytes() + b"\n%changed")
    with pytest.raises(ValueError, match="SHA|immutable|hash"):
        reconstruct_document(ir, {}, str(tmp_path / "candidate.pdf"))


def test_widget_visual_and_form_value_remain_original(tmp_path):
    source = tmp_path / "form.pdf"
    with fitz.open() as document:
        page = document.new_page(width=240, height=160)
        page.insert_text((20, 35), "Original heading")
        widget = fitz.Widget()
        widget.field_name = "synthetic-field"
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(30, 80, 200, 105)
        widget.field_value = "Protected value"
        page.add_widget(widget)
        document.save(source)
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    block = next(b for b in ir["pages"][0]["blocks"] if b["text"] == "Original heading")
    out = tmp_path / "candidate.pdf"
    reconstruct_document(ir, {block["id"]: "Titre traduit"}, str(out))
    with fitz.open(out) as candidate:
        widgets = list(candidate[0].widgets())
        assert len(widgets) == 1 and widgets[0].field_value == "Protected value"
