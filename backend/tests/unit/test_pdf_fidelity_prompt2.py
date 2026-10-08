from __future__ import annotations

import hashlib
from pathlib import Path

import fitz

from app.documents.pdf_fidelity import compare_pdf_tables, enrich_tables, render_pdf


def _grid_pdf(path: Path, *, merged: bool = False, pages: int = 1) -> None:
    doc = fitz.open()
    for page_index in range(pages):
        page = doc.new_page(width=360, height=240)
        for x in (30, 180, 330):
            page.draw_line((x, 30), (x, 180), color=(0, 0, 0), width=1)
        for y in (30, 90, 180):
            page.draw_line((30, y), (330, y), color=(0, 0, 0), width=1)
        page.draw_rect((30, 30, 180, 90), color=(0, 0, 0), fill=(1, 0.9, 0.6))
        if merged:
            # Remove the internal horizontal divider in the second column to
            # provide real merge evidence while retaining the outer geometry.
            page.draw_rect((181, 89, 329, 91), color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
        page.insert_text((42, 62), f"Hello {page_index}", fontsize=11)
        page.insert_text((192, 62), "Right", fontsize=11)
        page.insert_text((42, 122), "Bottom", fontsize=11)
    doc.save(path)
    doc.close()


def _ir_for(source: Path, *, scanned: bool = False) -> dict:
    doc = fitz.open(source)
    blocks = []
    for number, page in enumerate(doc, 1):
        for _index, item in enumerate(page.get_text("dict").get("blocks", [])):
            if item.get("type") != 0:
                continue
            for line in item.get("lines", []):
                text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                if text:
                    blocks.append(
                        {
                            "id": f"p{number:03d}-b{len(blocks):04d}",
                            "page": number,
                            "text": text,
                            "bbox": list(line["bbox"]),
                            "font_size": 11.0,
                        }
                    )
    doc.close()
    return {
        "source_path": str(source),
        "format": "pdf",
        "pages": [
            {"number": n, "scanned": scanned, "blocks": [b for b in blocks if b["page"] == n]}
            for n in range(1, 3 if scanned else 2)
        ],
    }


def test_enrich_tables_keeps_candidate_style_evidence_in_place(tmp_path: Path):
    source = tmp_path / "grid.pdf"
    _grid_pdf(source)
    doc = fitz.open(source)
    page = doc[0]
    blocks = [{"id": "b", "page": 1, "bbox": [42, 45, 90, 65], "text": "Hello", "font_size": 11}]
    tables = [
        {
            "id": "t",
            "page": 1,
            "cells": [
                {
                    "id": "c",
                    "bbox": [30, 30, 180, 90],
                    "row": 0,
                    "column": 0,
                    "row_span": 1,
                    "column_span": 1,
                    "block_ids": ["b"],
                }
            ],
        }
    ]
    result = enrich_tables(page, tables, blocks)
    assert result is tables
    cell = tables[0]["cells"][0]
    assert cell["fill"] == [1.0, 0.9, 0.6]
    assert cell["padding"] and cell["align"] in {"left", "center", "right"}
    assert cell["row_span"] == cell["column_span"] == 1
    doc.close()


def test_render_table_replaces_whole_cell_and_reports_candidate_structure(tmp_path: Path):
    source = tmp_path / "grid.pdf"
    output = tmp_path / "candidate.pdf"
    _grid_pdf(source)
    ir = _ir_for(source)
    block = ir["pages"][0]["blocks"][0]
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = render_pdf(ir, {block["id"]: "Translated"}, source, output, [])
    assert result["changed_blocks"] == 1
    assert result["overflow_count"] == 0
    assert result["table_render_trace"]
    assert result["table_structure"]
    assert "Hello" not in fitz.open(output)[0].get_text()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_overflow_is_atomic_and_source_text_is_restored(tmp_path: Path):
    source = tmp_path / "grid.pdf"
    output = tmp_path / "candidate.pdf"
    _grid_pdf(source)
    ir = _ir_for(source)
    block = ir["pages"][0]["blocks"][0]
    result = render_pdf(ir, {block["id"]: "X" * 2000}, source, output, [])
    assert result["overflow_count"] >= 1
    assert any(issue["code"] == "LAYOUT_OVERFLOW" for issue in result["issues"])
    assert "Hello" in fitz.open(output)[0].get_text()


def test_protected_table_cell_is_not_redacted(tmp_path: Path):
    source = tmp_path / "grid.pdf"
    output = tmp_path / "candidate.pdf"
    _grid_pdf(source)
    ir = _ir_for(source)
    block = ir["pages"][0]["blocks"][0]
    result = render_pdf(
        ir, {block["id"]: "Translated"}, source, output, [{"page": 1, "bbox": block["bbox"]}]
    )
    assert result["changed_blocks"] == 0
    assert "Hello" in fitz.open(output)[0].get_text()
    assert any(issue["code"] == "PROTECTED_TRANSLATION_NOT_APPLIED" for issue in result["issues"])


def test_compare_tables_is_independent_and_unvalidated(tmp_path: Path):
    source = tmp_path / "source.pdf"
    candidate = tmp_path / "candidate.pdf"
    _grid_pdf(source)
    _grid_pdf(candidate, merged=True)
    result = compare_pdf_tables(source, candidate)
    assert result["source_tables"] and result["candidate_tables"]
    assert result["semantically_validated"] is False
    assert result["structure_metrics"]["tables"]["score"] is not None


def test_final_insertion_divergence_rolls_back_source_unit(tmp_path, monkeypatch):
    from app.documents import pdf_fidelity

    source = tmp_path / "rollback.pdf"
    out = tmp_path / "candidate.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=220, height=160)
        page.insert_text((20, 40), "Original preserved", fontsize=12)
        doc.save(source)
    ir = {
        "format": "pdf",
        "pages": [
            {
                "number": 1,
                "width": 220,
                "height": 160,
                "scanned": False,
                "blocks": [
                    {
                        "id": "b",
                        "page": 1,
                        "bbox": [20, 27, 130, 44],
                        "text": "Original preserved",
                        "font_size": 12,
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(pdf_fidelity, "_fit_on_scratch", lambda *args: (True, 1.0, 12.0))
    original_insert = fitz.Page.insert_textbox
    monkeypatch.setattr(fitz.Page, "insert_textbox", lambda *args, **kwargs: -10.0)
    result = pdf_fidelity.render_pdf(ir, {"b": "Target"}, source, out)
    monkeypatch.setattr(fitz.Page, "insert_textbox", original_insert)
    with fitz.open(out) as candidate:
        assert "Original preserved" in candidate[0].get_text()
    assert result["changed_blocks"] == 0
    assert result["overflow_count"] == 1
