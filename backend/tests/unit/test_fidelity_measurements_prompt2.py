from __future__ import annotations

import asyncio
import json
import zipfile

import fitz
from docx import Document
from PIL import Image

from app.documents.ooxml_integrity import compare_ooxml_integrity
from app.documents.pdf_fidelity import compare_pdf_tables
from app.documents.pipeline import analyze_document, reconstruct_document, translate_document
from app.documents.render_metrics import measure_render_fidelity


def grid(path, fill=(0.9, 0.9, 0.9)):
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=200)
        for row in range(2):
            for col in range(2):
                rect = fitz.Rect(30 + col * 120, 40 + row * 55, 150 + col * 120, 95 + row * 55)
                page.draw_rect(rect, color=(0, 0, 1), fill=fill, width=1.2)
                page.insert_text((rect.x0 + 8, rect.y0 + 25), f"Cell {row}{col}", fontsize=11)
        doc.save(path)


def test_pdf_measures_missing_table_and_changed_fill(tmp_path):
    source, candidate = tmp_path / "source.pdf", tmp_path / "candidate.pdf"
    grid(source)
    with fitz.open() as doc:
        doc.new_page(width=300, height=200)
        doc.save(candidate)
    missing = compare_pdf_tables(source, candidate)
    assert missing["structure_metrics"]["tables"]["score"] == 0
    assert any(i["code"] == "PDF_TABLE_STRUCTURE_CHANGED" for i in missing["issues"])
    grid(candidate, fill=(1, 0, 0))
    changed = compare_pdf_tables(source, candidate)
    assert changed["structure_metrics"]["tables"]["score"] == 0


def test_pdf_cell_target_is_measured_in_actual_candidate_not_source_bbox(tmp_path):
    source, candidate = tmp_path / "source.pdf", tmp_path / "candidate.pdf"
    grid(source)
    grid(candidate)
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    block = ir["pages"][0]["blocks"][0]
    report = compare_pdf_tables(
        source, candidate, source_ir=ir, translations={block["id"]: "Cible absente"}
    )
    assert report["targets"][0]["contained"] is False
    assert report["structure_metrics"]["cell_targets"]["score"] == 0


def test_pdf_cell_renderer_keeps_fill_and_actual_target(tmp_path):
    source, candidate = tmp_path / "source.pdf", tmp_path / "candidate.pdf"
    grid(source)
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    block = ir["pages"][0]["blocks"][0]
    render = reconstruct_document(ir, {block["id"]: "Texte cellule traduit"}, str(candidate))
    assert render["changed_blocks"] == 1
    assert render["structure_metrics"]["tables"]["score"] == 1
    assert render["pdf_structure"]["targets"][0]["contained"] is True
    assert render["structure_metrics"]["cell_targets"]["score"] == 1
    assert render["table_render_trace"][0]["status"] == "ready"


def test_ooxml_detects_size_numbering_hyperlink_and_relationship_changes(tmp_path):
    source, candidate = tmp_path / "source.docx", tmp_path / "candidate.docx"
    doc = Document()
    doc.add_paragraph("Original")
    doc.save(source)
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(candidate, "w") as after:
        for item in before.infolist():
            data = before.read(item)
            if item.filename == "word/document.xml":
                data = data.replace(b"<w:r>", b'<w:r><w:rPr><w:sz w:val="8"/></w:rPr>', 1)
            after.writestr(item, data)
    report = compare_ooxml_integrity(source, candidate)
    assert report["preserved"] is False
    assert "word/document.xml" in report["changed_parts"]


def test_multi_page_mask_scales_by_each_original_page(tmp_path):
    source, candidate = tmp_path / "source.pdf", tmp_path / "candidate.pdf"
    with fitz.open() as doc:
        doc.new_page(width=100, height=100)
        page = doc.new_page(width=200, height=200)
        doc.save(source)
        page.draw_rect(fitz.Rect(140, 140, 160, 160), fill=(0, 0, 0), color=None)
        doc.save(candidate)
    render = measure_render_fidelity(
        source,
        candidate,
        text_masks=[{"page": 2, "bbox": [138, 138, 162, 162]}],
        work_dir=tmp_path / "proof",
    )
    assert render["raster_similarity"] == 1


def test_visual_artifacts_are_actual_render_not_golden_and_null_not_pass(tmp_path):
    source = tmp_path / "source.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=240, height=160)
        page.insert_text((20, 40), "Bonjour document")
        doc.save(source)
    work = tmp_path / "work"
    ir = analyze_document(str(source), str(work))
    result = asyncio.run(translate_document(ir, str(work), {"engine": "offline"}))
    artifacts = work / "fidelity-artifacts"
    for name in ("original.png", "translated.png", "diff.png"):
        with Image.open(artifacts / "page-001" / name) as image:
            assert image.width > 0 and image.height > 0
    metrics = json.loads((artifacts / "metrics.json").read_text())
    summary = json.loads((artifacts / "result.json").read_text())
    assert metrics["source_page_count"] == metrics["candidate_page_count"] == 1
    assert summary["scores"]["GLOBAL_SCORE"] is None
    assert summary["status"] == "REVIEW_REQUIRED"
    assert result["quality"]["reference_status"] == "not_evaluated"


def test_large_visual_mask_cannot_hide_structure_change(tmp_path):
    source, candidate = tmp_path / "source.pdf", tmp_path / "candidate.pdf"
    with fitz.open() as doc:
        doc.new_page(width=100, height=100)
        doc.save(source)
        doc.save(candidate)
    result = measure_render_fidelity(
        source,
        candidate,
        text_masks=[{"page": 1, "bbox": [0, 0, 100, 100]}],
        work_dir=tmp_path / "proof",
    )
    assert result["raster_similarity"] is None
    assert any(i["code"] == "RENDER_TEXT_MASK_TOO_LARGE" for i in result["issues"])


def test_missing_render_proof_is_explicit_unavailable_not_pass(tmp_path):
    result = measure_render_fidelity(
        tmp_path / "absent.docx", tmp_path / "absent-target.docx", work_dir=tmp_path / "proof"
    )
    assert result["layout_score"] is None
    assert result["execution_status"] == "NOT_AVAILABLE_IN_ENVIRONMENT"
    assert any(i["code"] == "RENDER_PROOF_UNAVAILABLE" for i in result["issues"])
