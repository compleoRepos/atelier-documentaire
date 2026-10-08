from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import fitz
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[2]))
from app.documents.pipeline import (
    analyze_document,
    evaluate_document,
    reconstruct_document,
    translate_document,
)


def make_pdf(path: Path, text: str = "Employee salary 1234"):
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 40), text, fontsize=12)
    doc.save(path)
    doc.close()


def test_native_pdf_ignores_whitespace_residue_and_preserves_original(tmp_path):
    source = tmp_path / "source.pdf"
    make_pdf(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    ir = analyze_document(str(source), str(tmp_path / "work"))
    assert ir["format"] == "pdf" and len(ir["pages"]) == 1
    assert any(b["text"] for b in ir["pages"][0]["blocks"])
    out = tmp_path / "candidate.pdf"
    result = reconstruct_document(
        ir, {ir["pages"][0]["blocks"][0]["id"]: "Employee salary 1234"}, str(out)
    )
    assert out.exists() and result["pages_preserved"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_scan_image_and_preview(tmp_path):
    image = tmp_path / "scan.png"
    Image.new("RGB", (220, 100), "white").save(image)
    ir = analyze_document(str(image), str(tmp_path / "work"), {"ocr_languages": ["eng"]})
    assert ir["format"] == "png" and ir["pages"][0]["scanned"]
    assert (tmp_path / "work" / "previews" / "original-001.png").exists()


def test_docx_structure_mapping_and_candidate(tmp_path):
    docx = pytest.importorskip("docx")
    source = tmp_path / "source.docx"
    d = docx.Document()
    d.add_paragraph("Employee name")
    t = d.add_table(rows=1, cols=1)
    t.cell(0, 0).text = "Salary 1234"
    d.save(source)
    ir = analyze_document(str(source), str(tmp_path / "work"))
    assert ir["format"] == "docx" and any("source_ref" in b for b in ir["pages"][0]["blocks"])
    tr = asyncio.run(
        translate_document(
            ir,
            str(tmp_path / "work"),
            {"engine": "offline", "memory": {"Employee name": "Nom salarié"}},
        )
    )
    assert Path(tr["versions"]["candidate"]).exists()


def test_entity_change_is_critical_and_scores_are_null_without_reference(tmp_path):
    ir = {"pages": [{"number": 1, "blocks": [{"id": "b1", "text": "Amount 1234", "page": 1}]}]}
    result = evaluate_document(ir, {"b1": "Montant 9999"})
    assert result["critical_entity_errors"]
    assert result["translation_score"] is None and result["semantic_score"] is None
    assert result["status"] == "REVIEW_REQUIRED"


def test_overflow_is_blocking(tmp_path):
    source = tmp_path / "source.pdf"
    make_pdf(source, "short")
    ir = analyze_document(str(source), str(tmp_path / "work"))
    bid = ir["pages"][0]["blocks"][0]["id"]
    result = reconstruct_document(ir, {bid: "x" * 2000}, str(tmp_path / "candidate.pdf"))
    assert result["output_path"] and any(i["code"] == "LAYOUT_OVERFLOW" for i in result["issues"])
