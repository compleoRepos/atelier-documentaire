from __future__ import annotations

import zipfile

import fitz

from app.documents.docx_analysis import collect_docx_content
from app.documents.pipeline import analyze_document, reconstruct_document
from app.documents.render_metrics import _geometry, _match_candidate, measure_render_fidelity

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def test_docx_wrappers_and_note_parts_are_not_silently_omitted(tmp_path):
    source = tmp_path / "source.docx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W}"><w:body><w:sdt><w:sdtContent><w:p><w:r><w:t>Wrapped source</w:t></w:r></w:p></w:sdtContent></w:sdt><w:ins><w:p><w:r><w:t>Inserted source</w:t></w:r></w:p></w:ins><w:p><w:r><w:t>Direct source</w:t></w:r></w:p></w:body></w:document>',
        )
        archive.writestr(
            "word/footnotes.xml",
            f'<w:footnotes xmlns:w="{W}"><w:footnote w:id="1"><w:p><w:r><w:t>Footnote source</w:t></w:r></w:p></w:footnote></w:footnotes>',
        )
    blocks, _, _ = collect_docx_content(
        source, lambda text, bid, order, ref: {"text": text, "id": bid, "source_ref": ref}
    )
    assert [b["text"] for b in blocks] == [
        "Wrapped source",
        "Inserted source",
        "Direct source",
        "Footnote source",
    ]
    assert all(b["source_ref"]["paragraph_path"] for b in blocks)


def test_unchanged_source_block_disappearance_is_critical_even_with_translation():
    source = {
        "pages": [
            {
                "number": 1,
                "width": 200,
                "height": 100,
                "scanned": False,
                "blocks": [
                    {"id": "a", "page": 1, "text": "Old", "bbox": [10, 10, 40, 25]},
                    {"id": "b", "page": 1, "text": "Keep", "bbox": [10, 40, 40, 55]},
                ],
            }
        ]
    }
    candidate = {
        "pages": [
            {
                "number": 1,
                "width": 200,
                "height": 100,
                "blocks": [{"id": "new", "page": 1, "text": "New", "bbox": [10, 10, 40, 25]}],
            }
        ]
    }
    metrics, issues = _geometry(source, candidate, source, {"a": "New"})
    assert metrics["translated_block_count"] == 1
    assert metrics["candidate_blocks_seen"] == 1
    assert metrics["missing_block_count"] == 1
    assert any(i["code"] == "RENDER_SOURCE_TEXT_MISSING" for i in issues)


def test_wrong_page_and_subword_match_cannot_prove_text_presence():
    source = {"page": 1, "bbox": [10, 10, 40, 25], "text": "Original"}
    pages = [
        {
            "number": 1,
            "blocks": [
                {"id": "subword", "page": 1, "bbox": [10, 10, 40, 25], "text": "Totalement"}
            ],
        },
        {
            "number": 2,
            "blocks": [{"id": "wrong-page", "page": 2, "bbox": [10, 10, 40, 25], "text": "Total"}],
        },
    ]
    assert _match_candidate(source, "Total", pages, set()) is None


def test_protected_bbox_outside_page_is_not_measured_as_preserved(tmp_path):
    source = tmp_path / "source.pdf"
    with fitz.open() as doc:
        doc.new_page(width=100, height=100)
        doc.save(source)
    result = measure_render_fidelity(
        source,
        source,
        protected_regions=[{"page": 1, "bbox": [150, 150, 180, 180]}],
        work_dir=tmp_path / "proof",
    )
    assert result["protected_region_results"][0]["preserved"] is None
    assert result["protected_region_results"][0]["measured"] is False
    assert any(i["code"] == "PROTECTED_REGION_OUTSIDE_PAGE" for i in result["issues"])


def test_vector_graphic_inside_table_cell_blocks_replacement_and_preserves_pixels(tmp_path):
    source = tmp_path / "source.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=180)
        for row in range(2):
            for col in range(2):
                rect = fitz.Rect(20 + col * 130, 30 + row * 55, 150 + col * 130, 85 + row * 55)
                page.draw_rect(rect, color=(0, 0, 1), fill=(0.9, 0.9, 0.9))
                page.insert_text(
                    (rect.x0 + 6, rect.y0 + 22), f"Cell source {row}{col}", fontsize=10
                )
        page.draw_circle((90, 67), 9, color=(1, 0, 0), fill=(1, 0, 0))
        doc.save(source)
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    assert any(r["subtype"] == "vector_graphic_candidate" for r in ir["protected_visual_regions"])
    block = ir["pages"][0]["blocks"][0]
    render = reconstruct_document(ir, {block["id"]: "Target"}, str(tmp_path / "candidate.pdf"))
    assert render["changed_blocks"] == 0
    assert any(i["code"] == "PROTECTED_TRANSLATION_NOT_APPLIED" for i in render["issues"])
    assert all(r["preserved"] is True for r in render["protected_region_results"])


def test_disjoint_text_ranges_can_share_pdf_block_without_double_using_glyphs():
    block = {"id": "row", "page": 1, "bbox": [10, 10, 180, 30], "text": "Texte cellule 1234"}
    pages = [{"number": 1, "blocks": [block]}]
    first = _match_candidate({"page": 1, "bbox": [10, 10, 70, 30]}, "Texte cellule", pages, set())
    used = {(first["id"], *first["matched_text_range"])}
    assert (
        _match_candidate({"page": 1, "bbox": [100, 10, 150, 30]}, "1234", pages, used) is not None
    )
    assert _match_candidate({"page": 1, "bbox": [10, 10, 70, 30]}, "cellule", pages, used) is None


def test_filled_table_rect_with_no_stroke_width_is_supported():
    from app.documents.protected_visuals import is_table_geometry

    drawing = {"width": None, "items": [("re", fitz.Rect(0, 0, 100, 50), 1)]}
    assert is_table_geometry(
        drawing, [{"bbox": [0, 0, 100, 50], "cells": [{"bbox": [0, 0, 100, 50]}]}]
    )
