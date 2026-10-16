from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from app.ai.vision.scorer import score_visual
from app.documents.pipeline import analyze_document, reconstruct_document
from app.documents.render_metrics import (
    compare_docx_structure,
    measure_render_fidelity,
    parse_docx_structure,
)


def _pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page(width=240, height=160)
    page.insert_text((20, 40), text, fontsize=12)
    document.save(path)
    document.close()


def test_pdf_metrics_use_actual_candidate_bbox_and_translated_denominator(tmp_path: Path):
    source = tmp_path / "source.pdf"
    candidate = tmp_path / "candidate.pdf"
    _pdf(source, "Source 1234")
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    block = ir["pages"][0]["blocks"][0]
    reconstruct_document(ir, {block["id"]: "Texte traduit 1234"}, str(candidate))

    result = measure_render_fidelity(
        source,
        candidate,
        source_ir=ir,
        translations={block["id"]: "Texte traduit 1234"},
        work_dir=tmp_path / "render",
    )

    geometry = result["geometry_metrics"]
    assert result["source_page_count"] == 1
    assert result["translated_page_count"] == 1
    assert geometry["translated_block_count"] == 1
    assert geometry["candidate_blocks_seen"] == 1
    assert geometry["provenance"] == "actual_pdf_get_text_dict_geometry"
    assert result["layout_score"] is not None
    assert result["layout_score"] < 1.0  # measured bbox/font displacement, not no-overflow=1
    assert len(result["source_previews"]) == result["source_page_count"]
    assert len(result["candidate_previews"]) == result["translated_page_count"]


def test_docx_structure_parses_tables_and_media_independently(tmp_path: Path):
    docx = __import__("docx")
    source = tmp_path / "source.docx"
    candidate = tmp_path / "candidate.docx"
    image = tmp_path / "image.png"
    Image.new("RGB", (8, 8), "red").save(image)
    document = docx.Document()
    table = document.add_table(rows=2, cols=2)
    table.rows[0]._tr.get_or_add_trPr().append(docx.oxml.OxmlElement("w:tblHeader"))
    table.cell(0, 0).text = "A"
    table.cell(0, 1).text = "B"
    table.cell(1, 0).text = "C"
    table.cell(1, 1).text = "D"
    document.add_paragraph().add_run().add_picture(str(image))
    document.save(source)
    document.save(candidate)

    parsed = parse_docx_structure(source)
    comparison = compare_docx_structure(source, candidate)
    table = parsed["tables"][0]
    assert table["rows"] == 2
    assert table["columns"] == 2
    assert table["header_rows"] == [0]
    assert [cell["reading_order"] for cell in table["cells"]] == [0, 1, 2, 3]
    assert len(parsed["media_hashes"]) == 1
    assert comparison["structure_metrics"]["tables"]["preserved"] is True
    assert comparison["structure_metrics"]["images"]["preserved"] is True


def test_docx_multirun_translation_does_not_fabricate_style_score(tmp_path: Path):
    docx = __import__("docx")
    source = tmp_path / "source.docx"
    candidate = tmp_path / "candidate.docx"
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("Bold").bold = True
    paragraph.add_run(" normal")
    document.save(source)
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    block = ir["pages"][0]["blocks"][0]
    reconstruct_document(ir, {block["id"]: "Texte traduit"}, str(candidate))

    result = compare_docx_structure(
        source, candidate, translations={block["id"]: "Texte traduit"}, source_ir=ir
    )
    assert result["structure_metrics"]["styles"]["score"] is None
    assert result["styles_verified"] is False
    assert any(issue["code"] == "DOCX_STYLES_UNVERIFIED" for issue in result["issues"])


def test_raster_metrics_keep_pixel_dimensions_and_bound_text_mask(tmp_path: Path):
    source = tmp_path / "source.png"
    candidate = tmp_path / "candidate.png"
    original = Image.new("RGB", (100, 80), "white")
    target = original.copy()
    ImageDraw.Draw(original).rectangle((10, 10, 20, 20), fill="black")
    original.save(source)
    target.save(candidate)

    result = measure_render_fidelity(
        source,
        candidate,
        text_masks=[{"page": 1, "bbox": [10, 10, 20, 20]}],
        protected_regions=[{"id": "signature-review", "page": 1, "bbox": [70, 60, 90, 75]}],
        work_dir=tmp_path / "render",
    )
    assert result["raster_coverage"]["pixel_constant"] is True
    # Le rendu à 120 dpi rééchantillonne le bord du masque : erreur mesurée,
    # pas une identité pixel inventée après interpolation.
    assert 0.99 <= result["raster_similarity"] <= 1.0
    assert result["protected_region_results"][0]["preserved"] is True
    assert result["protected_region_results"][0]["authenticity_verified"] is False

    scored = score_visual({"pages": [{"number": 1, "width": 100, "height": 80}]}, result)
    assert scored["components"]["geometry"] is not None
    assert (
        scored["provenance"]["text_replacement_masks_are_excluded_only_in_bounded_regions"] is True
    )


def test_pdf_table_structure_is_unvalidated_not_copied_from_source(tmp_path: Path):
    source = tmp_path / "source.pdf"
    candidate = tmp_path / "candidate.pdf"
    _pdf(source, "A B C D")
    _pdf(candidate, "A B C D")
    result = measure_render_fidelity(source, candidate, work_dir=tmp_path / "render")
    assert result["structure_metrics"]["tables"]["score"] is None
    assert result["structure_metrics"]["tables"]["measured"] is False
    assert result["docx_structure"]["available"] is False
