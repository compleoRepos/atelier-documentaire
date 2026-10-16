from __future__ import annotations

import asyncio
import hashlib
import zipfile
from pathlib import Path

import fitz
import pytest
from PIL import Image

from app.documents.pipeline import (
    analyze_document,
    evaluate_document,
    reconstruct_document,
    translate_document,
)
from app.domain.classification import classify_document


def _pdf(path: Path, text: str = "ORIGINAL 1234") -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 40), text, fontsize=12)
    page.draw_rect(fitz.Rect(230, 20, 280, 70), color=(1, 0, 0), fill=(1, 0, 0))
    doc.save(path)
    doc.close()


def test_classifier_has_six_explainable_types_and_domains():
    corpus = {
        "employment_certificate": (
            "Attestation de travail de l employeur et rémunération du salarié",
            "HR",
        ),
        "contract": ("Contrat de prestation entre les parties, clause et signatures", "LEGAL"),
        "bank_statement": ("Relevé bancaire IBAN solde débit crédit transaction", "BANKING"),
        "invoice": ("Facture fournisseur montant dû total TTC TVA échéance", "FINANCE"),
        "diploma": ("Diplôme de master délivré par l université", "ACADEMIC"),
        "administrative_form": (
            "Formulaire administratif CERFA déclaration préfecture",
            "ADMINISTRATION",
        ),
    }
    for expected, (text, domain) in corpus.items():
        result = classify_document(text, ["fra"])
        assert result["document_type"] == expected
        assert result["domain"] == domain
        assert result["confidence"] > 0


def test_classifier_multilingual_and_unknown_warning():
    assert (
        classify_document("Bank statement account balance debit credit", ["eng"])["document_type"]
        == "bank_statement"
    )
    assert (
        classify_document("Arbeitsvertrag Klausel Parteien", ["deu"])["document_type"] == "contract"
    )
    result = classify_document("Completely unrelated prose", ["eng"])
    assert result["document_type"] == "unknown"
    assert any(item["code"] == "UNKNOWN_DOCUMENT_TYPE" for item in result["warnings"])


def test_native_pdf_redaction_removes_source_and_preserves_source_file(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    ir = analyze_document(str(source), str(tmp_path / "work"))
    block = ir["pages"][0]["blocks"][0]
    output = tmp_path / "candidate.pdf"
    result = reconstruct_document(ir, {block["id"]: "Français 1234"}, str(output))
    assert result["changed_blocks"] == 1
    assert "ORIGINAL" not in fitz.open(output)[0].get_text()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


def test_native_pdf_keeps_graphic_outside_changed_bbox(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    ir = analyze_document(str(source), str(tmp_path / "work"))
    block = ir["pages"][0]["blocks"][0]
    output = tmp_path / "candidate.pdf"
    reconstruct_document(ir, {block["id"]: "Français 1234"}, str(output))
    page = fitz.open(output)[0]
    assert page.get_pixmap(clip=fitz.Rect(230, 20, 280, 70), alpha=False).samples


def test_protected_translation_is_error_and_source_remains(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    ir = analyze_document(str(source), str(tmp_path / "work"))
    block = ir["pages"][0]["blocks"][0]
    output = tmp_path / "candidate.pdf"
    result = reconstruct_document(
        ir, {block["id"]: "Français 1234"}, str(output), [{"page": 1, "bbox": block["bbox"]}]
    )
    assert any(
        item["code"] == "PROTECTED_TRANSLATION_NOT_APPLIED" and item["severity"] == "error"
        for item in result["issues"]
    )
    assert "ORIGINAL" in fitz.open(output)[0].get_text()


def test_rtl_is_blocked_explicitly_when_shaping_not_configured(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    ir = analyze_document(str(source), str(tmp_path / "work"))
    block = ir["pages"][0]["blocks"][0]
    result = reconstruct_document(ir, {block["id"]: "مرحبا"}, str(tmp_path / "candidate.pdf"))
    assert any(
        item["code"] == "RTL_SHAPING_UNSUPPORTED" and item["severity"] == "error"
        for item in result["issues"]
    )


def test_evaluation_does_not_flag_unchanged_french_but_flags_non_french():
    base = {
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {"id": "fr", "text": "Bonjour", "language": "fra"},
                    {"id": "en", "text": "Hello", "language": "eng"},
                ],
            }
        ],
        "language": "fra",
    }
    result = evaluate_document(base, {"fr": "Bonjour", "en": "Hello"})
    assert "fr" not in result["untranslated_blocks"]
    assert "en" in result["untranslated_blocks"]


def test_evaluation_rejects_unknown_and_missing_ids():
    base = {
        "pages": [{"number": 1, "blocks": [{"id": "known", "text": "Hello", "language": "eng"}]}]
    }
    result = evaluate_document(base, {"unknown": "x"})
    codes = {item["code"] for item in result["issues"]}
    assert {"UNKNOWN_TRANSLATION_BLOCK", "MISSING_TRANSLATION_BLOCK"} <= codes


def test_docx_ir_keeps_body_order_and_real_pagination(tmp_path):
    docx = pytest.importorskip("docx")
    source = tmp_path / "source.docx"
    doc = docx.Document()
    doc.add_paragraph("Before")
    table = doc.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Inside"
    doc.add_paragraph("After")
    doc.save(source)
    ir = analyze_document(str(source), str(tmp_path / "work"))
    ids = [block["id"] for block in ir["pages"][0]["blocks"]]
    assert (
        ids.index("p001-par-0000")
        < ids.index("p001-cell-000-000-000-par-000")
        < ids.index("p001-par-0001")
    )
    assert ir["pages"][0]["coordinates_kind"] == "pdf"
    assert ir["versions"]["pagination"] == "libreoffice-pdf"


def test_docx_reconstruction_preserves_media_and_run_style(tmp_path):
    docx = pytest.importorskip("docx")
    source = tmp_path / "source.docx"
    image = tmp_path / "inline.png"
    Image.new("RGB", (8, 8), (20, 30, 40)).save(image)
    doc = docx.Document()
    paragraph = doc.add_paragraph()
    run = paragraph.add_run("Styled source")
    run.bold = True
    paragraph.add_run().add_picture(str(image))
    doc.save(source)
    ir = analyze_document(str(source), str(tmp_path / "work"))
    output = tmp_path / "candidate.docx"
    reconstruct_document(
        ir, {block["id"]: "Texte traduit" for block in ir["pages"][0]["blocks"]}, str(output)
    )
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(output) as candidate:
        assert candidate.read("word/media/image1.png") == original.read("word/media/image1.png")
        xml = candidate.read("word/document.xml")
        assert b"<w:b/>" in xml and b"w:drawing" in xml


def test_docx_reconstruction_measures_pagination_and_keeps_empty_paragraph(tmp_path):
    docx = pytest.importorskip("docx")
    source = tmp_path / "source.docx"
    doc = docx.Document()
    doc.add_paragraph("Text")
    doc.add_paragraph("")
    doc.save(source)
    ir = analyze_document(str(source), str(tmp_path / "work"))
    block = ir["pages"][0]["blocks"][0]
    output = tmp_path / "candidate.docx"
    result = reconstruct_document(ir, {block["id"]: "Traduction"}, str(output))
    assert result["pages_preserved"] is True
    assert result["pagination"] == "libreoffice-pdf"
    assert Path(result["candidate_pdf_path"]).is_file()
    assert 0 <= result["layout_score"] <= 1
    assert result["geometry_metrics"]["measured"] is True
    assert result["geometry_metrics"]["candidate_blocks_seen"] == 1
    with zipfile.ZipFile(output) as archive:
        assert archive.read("word/document.xml").count(b"<w:p") >= 3


def test_translation_versions_are_retained_and_visual_score_unvalidated(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source, "Bonjour 1234")
    ir = analyze_document(str(source), str(tmp_path / "work"))
    result = asyncio.run(
        translate_document(
            ir,
            str(tmp_path / "work"),
            {"engine": "offline", "memory": {"Bonjour 1234": "Hello 1234"}},
        )
    )
    assert 0 <= result["quality"]["visual_score"] <= 1
    assert result["quality"]["provenance"]["visual"]["preview_comparison"] is True
    assert result["quality"]["translation_score"] is None
    assert result["quality"]["semantic_score"] is None
    assert Path(result["versions"]["candidate"]).exists()
