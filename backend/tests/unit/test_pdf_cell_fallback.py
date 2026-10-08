"""A page frame detected as a one-cell table must not block every translation.

Regression observed on a real scanned attestation: the whole page was one
"table cell" intersecting the protected logo, so no translated text was written.
"""

from __future__ import annotations

import fitz

from app.documents.pdf_fidelity import render_pdf


def _scanned_like(path):
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=400)
        page.insert_text((40, 120), "Oggetto: Dichiarazione", fontsize=11)
        page.insert_text((40, 300), "Distinti saluti", fontsize=11)
        doc.save(path)
    with fitz.open(path) as doc:
        blocks = []
        for index, b in enumerate(doc[0].get_text("blocks")):
            blocks.append(
                {
                    "id": f"b{index}",
                    "bbox": [b[0], b[1], b[2], b[3]],
                    "text": b[4].strip(),
                    "language": "it",
                    "font_size": 11,
                }
            )
    return blocks


def _ir(path, blocks):
    return {
        "format": "pdf",
        "source_path": str(path),
        "pages": [{"number": 1, "scanned": True, "width": 300, "height": 400, "blocks": blocks}],
        "tables": [
            {
                "id": "frame",
                "page": 1,
                "bbox": [1, 1, 299, 399],
                "cells": [
                    {
                        "id": "frame-cell-0",
                        "bbox": [1, 1, 299, 399],
                        "block_ids": [b["id"] for b in blocks],
                    }
                ],
            }
        ],
    }


def test_page_frame_cell_touching_logo_falls_back_to_unprotected_blocks(tmp_path):
    source, out = tmp_path / "scan.pdf", tmp_path / "candidate.pdf"
    blocks = _scanned_like(source)
    logo = {
        "page": 1,
        "bbox": [200, 10, 290, 60],
        "type": "protected_visual_region",
        "subtype": "logo",
    }
    translations = {
        blocks[0]["id"]: "Objet : Déclaration",
        blocks[1]["id"]: "Salutations distinguées",
    }
    result = render_pdf(_ir(source, blocks), translations, source, out, [logo])
    assert result["changed_blocks"] == 2
    assert any(i["code"] == "TABLE_CELL_FALLBACK_TO_BLOCKS" for i in result["issues"])
    text = fitz.open(out)[0].get_text()
    assert "Déclaration" in text and "Salutations" in text
    assert "Dichiarazione" not in text


def test_fallback_still_refuses_a_block_inside_a_protected_region(tmp_path):
    source, out = tmp_path / "scan.pdf", tmp_path / "candidate.pdf"
    blocks = _scanned_like(source)
    stamp = {
        "page": 1,
        "bbox": [30, 285, 160, 310],
        "type": "protected_visual_region",
        "subtype": "stamp",
    }
    translations = {
        blocks[0]["id"]: "Objet : Déclaration",
        blocks[1]["id"]: "Salutations distinguées",
    }
    result = render_pdf(_ir(source, blocks), translations, source, out, [stamp])
    assert result["changed_blocks"] == 1
    assert any(i["code"] == "PROTECTED_TRANSLATION_NOT_APPLIED" for i in result["issues"])
    text = fitz.open(out)[0].get_text()
    assert "Déclaration" in text and "Distinti saluti" in text


def _ambiguous_ir(path, blocks, scanned):
    ids = [b["id"] for b in blocks]
    ir = _ir(path, blocks)
    ir["pages"][0]["scanned"] = scanned
    ir["tables"] = [
        {
            "id": "grid",
            "page": 1,
            "bbox": [1, 1, 299, 399],
            "ambiguous_block_ids": ids,
            "cells": [
                {"id": "grid-a", "bbox": [1, 1, 299, 200], "block_ids": ids},
                {"id": "grid-b", "bbox": [1, 200, 299, 399], "block_ids": ids},
            ],
        }
    ]
    return ir


def test_ambiguous_cell_on_scan_falls_back_to_blocks_once(tmp_path):
    source, out = tmp_path / "scan.pdf", tmp_path / "candidate.pdf"
    blocks = _scanned_like(source)
    translations = {
        blocks[0]["id"]: "Objet : Déclaration",
        blocks[1]["id"]: "Salutations distinguées",
    }
    result = render_pdf(_ambiguous_ir(source, blocks, True), translations, source, out, [])
    assert result["changed_blocks"] == 2
    codes = [i["code"] for i in result["issues"]]
    assert "TABLE_CELL_FALLBACK_TO_BLOCKS" in codes and "TABLE_AMBIGUOUS_CELL_LINK" not in codes
    text = fitz.open(out)[0].get_text()
    assert text.count("Déclaration") == 1 and text.count("Salutations") == 1


def test_ambiguous_cell_on_native_pdf_is_still_refused(tmp_path, monkeypatch):
    import app.documents.pdf_fidelity as pdf_fidelity

    source, out = tmp_path / "native.pdf", tmp_path / "candidate.pdf"
    blocks = _scanned_like(source)
    ir = _ambiguous_ir(source, blocks, False)
    # Native pages take their tables from the PDF itself, not from the IR.
    monkeypatch.setattr(pdf_fidelity, "_detect_tables", lambda *_args, **_kw: ir["tables"])
    translations = {
        blocks[0]["id"]: "Objet : Déclaration",
        blocks[1]["id"]: "Salutations distinguées",
    }
    result = render_pdf(ir, translations, source, out, [])
    assert result["changed_blocks"] == 0
    assert any(i["code"] == "TABLE_AMBIGUOUS_CELL_LINK" for i in result["issues"])
    assert "Dichiarazione" in fitz.open(out)[0].get_text()


def test_cell_without_bbox_is_never_dropped_silently(tmp_path):
    source, out = tmp_path / "scan.pdf", tmp_path / "candidate.pdf"
    blocks = _scanned_like(source)
    ir = _ir(source, blocks)
    ir["tables"][0]["cells"][0]["bbox"] = None
    translations = {
        blocks[0]["id"]: "Objet : Déclaration",
        blocks[1]["id"]: "Salutations distinguées",
    }
    result = render_pdf(ir, translations, source, out, [])
    assert result["changed_blocks"] == 2
    assert any(
        i["code"] == "TABLE_CELL_FALLBACK_TO_BLOCKS" and "bbox" in i["message"]
        for i in result["issues"]
    )


def test_page_frame_cell_without_protection_keeps_block_layout(tmp_path):
    """Real regression: 4 scanned pages whose frame was a one-cell table lost
    every translated block (whole-page text overflowed the single cell)."""
    source, out = tmp_path / "scan.pdf", tmp_path / "candidate.pdf"
    blocks = _scanned_like(source)
    translations = {
        blocks[0]["id"]: "Objet : Déclaration",
        blocks[1]["id"]: "Salutations distinguées",
    }
    result = render_pdf(_ir(source, blocks), translations, source, out, [])
    assert result["changed_blocks"] == 2
    codes = [i["code"] for i in result["issues"]]
    assert "TABLE_CELL_FALLBACK_TO_BLOCKS" in codes and "LAYOUT_OVERFLOW" not in codes
    page = fitz.open(out)[0]
    words = {w[4]: w[1] for w in page.get_text("words")}
    # Each translation stays at its own OCR line, not in one flowed paragraph.
    assert words["Déclaration"] < 200 < words["Salutations"]


def test_overflowing_scan_cell_falls_back_to_blocks(tmp_path):
    source, out = tmp_path / "scan.pdf", tmp_path / "candidate.pdf"
    blocks = _scanned_like(source)
    ir = _ir(source, blocks)
    first = blocks[0]["bbox"]
    ir["tables"][0]["bbox"] = ir["tables"][0]["cells"][0]["bbox"] = [
        first[0] - 2,
        first[1] - 2,
        first[2] + 2,
        first[3] + 2,
    ]
    ir["tables"][0]["cells"][0]["block_ids"] = [blocks[0]["id"]]
    long_text = " ".join(
        ["Objet : déclaration sur l'honneur relative à la situation professionnelle"] * 8
    )
    result = render_pdf(ir, {blocks[0]["id"]: long_text}, source, out, [])
    codes = [i["code"] for i in result["issues"]]
    assert "TABLE_CELL_FALLBACK_TO_BLOCKS" in codes
    assert not any(i["code"] == "LAYOUT_OVERFLOW" and i.get("cell_id") for i in result["issues"])
