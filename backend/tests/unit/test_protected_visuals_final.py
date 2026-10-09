"""Protected visuals on scans (prompt final, §10): stamps/logos/signatures stay
protected, but a contact with the corner of a paragraph no longer freezes the
whole paragraph. Human annotations and native PDFs stay strict."""

from __future__ import annotations

from app.documents.protected_visuals import (
    protect_ir,
    reclassify_text_candidates,
    significant_overlap,
)

PARAGRAPH = [60.0, 200.0, 530.0, 240.0]  # 470 x 40 pt


def test_corner_contact_is_not_significant_but_real_cover_is():
    stamp_on_corner = [500.0, 230.0, 580.0, 300.0]  # 30x10 pt of a 470x40 block
    assert not significant_overlap(PARAGRAPH, stamp_on_corner)
    stamp_over_text = [60.0, 200.0, 260.0, 240.0]  # 42 % of the block
    assert significant_overlap(PARAGRAPH, stamp_over_text)
    small_logo_inside = [100.0, 205.0, 120.0, 225.0]  # fully inside: half of the candidate
    assert significant_overlap(PARAGRAPH, small_logo_inside)


def _ir(tmp_path, scanned=True, regions=()):
    source = tmp_path / "scan.png"
    source.write_bytes(b"synthetic-scan")
    return {
        "format": "png",
        "source_path": str(source),
        "pages": [
            {
                "number": 1,
                "width": 595.0,
                "height": 842.0,
                "scanned": scanned,
                "blocks": [
                    {
                        "id": "p001-b0000",
                        "text": "Le salarie exerce ses fonctions",
                        "bbox": PARAGRAPH,
                        "confidence": 0.93,
                    }
                ],
            }
        ],
        "tables": [],
        "protected_visual_regions": list(regions),
    }


def _region(box, provenance="automatic_candidate:preprocessing", **extra):
    return {
        "page": 1,
        "bbox": box,
        "provenance": provenance,
        "subtype": "stamp_or_logo_candidate",
        **extra,
    }


def test_scan_corner_contact_is_recorded_as_near_not_protected(tmp_path):
    ir = protect_ir(_ir(tmp_path, regions=[_region([500.0, 230.0, 580.0, 300.0], id="stamp-1")]))
    block = ir["pages"][0]["blocks"][0]
    assert block["protected"] is False
    assert block["near_protected_regions"] == ["stamp-1"]
    assert (
        ir["protected_visual_regions"][0]["editable"] is False
    )  # the stamp itself stays protected


def test_human_annotation_contact_still_protects(tmp_path):
    region = _region(
        [500.0, 230.0, 580.0, 300.0], provenance="user_annotation_unvalidated", id="u1"
    )
    block = protect_ir(_ir(tmp_path, regions=[region]))["pages"][0]["blocks"][0]
    assert block["protected"] is True and block["protected_by"] == ["u1"]


def test_native_pdf_page_stays_strict(tmp_path):
    region = _region([500.0, 230.0, 580.0, 300.0], id="n1")
    block = protect_ir(_ir(tmp_path, scanned=False, regions=[region]))["pages"][0]["blocks"][0]
    assert block["protected"] is True


def _page_with_lines(lines):
    return {
        "pages": [{"number": 1, "width": 595.0, "height": 842.0, "scanned": True, "blocks": lines}],
        "protected_visual_regions": [],
    }


def test_form_frame_enclosing_text_is_reclassified_with_trace():
    lines = [
        {"id": "a", "text": "Nom du salarie", "bbox": [70, 410, 200, 420], "confidence": 0.9},
        {"id": "b", "text": "Fonction occupee", "bbox": [70, 430, 210, 440], "confidence": 0.9},
    ]
    ir = _page_with_lines(lines)
    frame = _region([60.0, 400.0, 540.0, 460.0], detector="conservative_dark_contour")
    ir["protected_visual_regions"] = [frame]
    reclassify_text_candidates(ir)
    assert ir["protected_visual_regions"] == []
    moved = ir["reclassified_visual_candidates"][0]
    assert moved["reason"] == "text_container_frame" and moved["line_ids"] == ["a", "b"]
    assert ir["warnings"][0]["code"] == "PROTECTED_CANDIDATE_RECLASSIFIED_TEXT"


def test_small_dark_contour_with_one_line_stays_protected():
    lines = [{"id": "a", "text": "Signature", "bbox": [70, 410, 140, 420], "confidence": 0.9}]
    ir = _page_with_lines(lines)
    ir["protected_visual_regions"] = [
        _region([60.0, 400.0, 180.0, 470.0], detector="conservative_dark_contour")
    ]
    reclassify_text_candidates(ir)
    assert len(ir["protected_visual_regions"]) == 1


def test_coloured_title_letters_are_text_but_a_logo_beside_them_is_kept():
    lines = [
        {
            "id": "t",
            "text": "Attestation de travail",
            "bbox": [200, 100, 400, 116],
            "confidence": 0.92,
        }
    ]
    ir = _page_with_lines(lines)
    letters = _region([205.0, 101.0, 260.0, 115.0], detector="color_connected_components")
    logo = _region([450.0, 60.0, 560.0, 140.0], detector="color_connected_components")
    ir["protected_visual_regions"] = [letters, logo]
    reclassify_text_candidates(ir)
    assert [r["bbox"] for r in ir["protected_visual_regions"]] == [logo["bbox"]]
    assert ir["reclassified_visual_candidates"][0]["reason"] == "colored_text_glyphs"


def _scan_pdf(tmp_path, paint):
    import io

    import fitz
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (595 * 2, 842 * 2), (250, 250, 248))
    paint(ImageDraw.Draw(image))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    path = tmp_path / "scan.pdf"
    doc.save(path)
    return str(path)


def test_multicolour_pictogram_inside_an_ocr_line_stays_protected(tmp_path):
    """Final corpus: a logo pictogram (orange + green) read by OCR as part of
    the company line was reclassified as coloured glyphs; a translation of
    that line would have painted over the logo."""

    def paint(draw):
        draw.polygon(
            [(710, 210), (750, 250), (710, 290), (670, 250)], fill=(240, 130, 40)
        )  # orange
        draw.ellipse([700, 196, 730, 214], fill=(40, 160, 70))  # green leaf
        draw.rectangle([420, 470, 520, 500], fill=(30, 60, 160))  # blue title letters

    lines = [
        {
            "id": "logo-line",
            "text": "Esimerkkilän kirjastopalvelu",
            "bbox": [330, 100, 470, 146],
            "confidence": 0.9,
        },
        {
            "id": "title",
            "text": "Employment certificate",
            "bbox": [200, 232, 300, 252],
            "confidence": 0.92,
        },
    ]
    ir = _page_with_lines(lines)
    ir["source_path"] = _scan_pdf(tmp_path, paint)
    pictogram = _region([334.0, 97.0, 376.0, 146.0], detector="color_connected_components")
    letters = _region([209.0, 234.0, 261.0, 251.0], detector="color_connected_components")
    ir["protected_visual_regions"] = [pictogram, letters]
    reclassify_text_candidates(ir)
    assert [r["bbox"] for r in ir["protected_visual_regions"]] == [pictogram["bbox"]]
    assert ir["protected_visual_regions"][0]["reclassification_veto"]["reason"] == "multicolor_logo"
    assert [m["reason"] for m in ir["reclassified_visual_candidates"]] == ["colored_text_glyphs"]
    assert any(w["code"] == "PROTECTED_CANDIDATE_MULTICOLOR_KEPT" for w in ir["warnings"])


def test_single_hue_highlight_is_not_a_logo():
    import numpy as np

    from app.documents.protected_visuals import multicolor_evidence

    pink = np.zeros((40, 200, 3), dtype=np.uint8)
    pink[:] = (245, 160, 205)
    pink[10:30, 20:60] = (20, 20, 20)
    assert multicolor_evidence(pink)["multicolor"] is False
    logo = pink.copy()
    logo[:, 100:] = (40, 160, 70)
    assert multicolor_evidence(logo)["multicolor"] is True


def test_human_and_native_regions_are_never_reclassified():
    lines = [
        {"id": "a", "text": "Nom du salarie", "bbox": [70, 410, 200, 420], "confidence": 0.9},
        {"id": "b", "text": "Fonction occupee", "bbox": [70, 430, 210, 440], "confidence": 0.9},
    ]
    ir = _page_with_lines(lines)
    human = _region(
        [60.0, 400.0, 540.0, 460.0],
        provenance="user_annotation",
        detector="conservative_dark_contour",
    )
    native = _region([60.0, 400.0, 540.0, 460.0], provenance="pdf_embedded_image_original")
    ir["protected_visual_regions"] = [human, native]
    reclassify_text_candidates(ir)
    assert len(ir["protected_visual_regions"]) == 2
