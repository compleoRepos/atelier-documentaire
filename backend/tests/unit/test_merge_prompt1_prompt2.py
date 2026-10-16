"""Merge contract between prompt 1 (preprocessing) and prompt 2 (fidelity).

These tests guard the integration decisions taken when both branches were
merged: automatic raster candidates must never be labelled as user
annotations, a candidate equal to a detected table frame must not block the
cell renderer, and a visual that only partially overlaps a table stays
protected.
"""

from __future__ import annotations

import fitz

from app.documents.pipeline import (
    _clip_candidate_regions,
    _exclude_table_art,
    analyze_document,
    reconstruct_document,
)


def _grid(path):
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=200)
        for row in range(2):
            for col in range(2):
                rect = fitz.Rect(30 + col * 120, 40 + row * 55, 150 + col * 120, 95 + row * 55)
                page.draw_rect(rect, color=(0, 0, 1), fill=(0.9, 0.9, 0.9), width=1.2)
                page.insert_text((rect.x0 + 8, rect.y0 + 25), f"Cell {row}{col}", fontsize=11)
        doc.save(path)


def test_table_frame_candidate_is_traced_and_does_not_block_cell_rendering(tmp_path):
    source, candidate = tmp_path / "source.pdf", tmp_path / "candidate.pdf"
    _grid(source)
    ir = analyze_document(str(source), str(tmp_path / "analysis"))
    codes = [w.get("code") for w in ir["warnings"]]
    assert "PROTECTED_CANDIDATE_TABLE_ART" in codes
    for region in ir.get("protected_visual_regions", []):
        assert region["provenance"] != "user_annotation_unvalidated"
        assert region["authenticity_verified"] is False
        # Schema required by the specification (§18) and the Angular model.
        assert region["type"] == "protected_visual_region"
    block = ir["pages"][0]["blocks"][0]
    render = reconstruct_document(ir, {block["id"]: "Texte cellule traduit"}, str(candidate))
    assert render["changed_blocks"] == 1
    assert render["table_render_trace"][0]["status"] == "ready"


def test_visual_partially_overlapping_a_table_keeps_its_protection():
    warnings: list[dict] = []
    table = {"bbox": [30.0, 40.0, 270.0, 150.0]}
    stamp = {"page": 1, "bbox": [220.0, 120.0, 290.0, 190.0], "subtype": "stamp_or_logo_candidate"}
    kept = _exclude_table_art([stamp], [table], warnings, 1)
    assert kept == [stamp]
    assert warnings == []


def test_candidate_equal_to_table_frame_is_excluded_with_its_bbox():
    warnings: list[dict] = []
    table = {"bbox": [30.0, 40.0, 270.0, 150.0]}
    frame = {"page": 1, "bbox": [28.0, 38.0, 272.0, 152.0]}
    assert _exclude_table_art([frame], [table], warnings, 1) == []
    assert warnings[0]["code"] == "PROTECTED_CANDIDATE_TABLE_ART"
    assert warnings[0]["bbox"] == [28.0, 38.0, 272.0, 152.0]


def test_automatic_candidates_are_clipped_and_labelled_automatic():
    warnings: list[dict] = []
    pages = [{"number": 1, "width": 100.0, "height": 50.0}]
    regions = [
        {"page": 1, "bbox": [-0.0001, 10.0, 100.00001, 40.0]},
        {"page": 1, "bbox": [10.0, 10.0, 10.2, 40.0]},
        {"page": 2, "bbox": [0.0, 0.0, 5.0, 5.0]},
    ]
    kept = _clip_candidate_regions(regions, pages, warnings)
    assert kept == [
        {"page": 1, "bbox": [0.0, 10.0, 100.0, 40.0], "provenance": "automatic_candidate:preprocessing"}
    ]
    assert {w["code"] for w in warnings} == {
        "PROTECTED_CANDIDATE_DEGENERATE",
        "PROTECTED_CANDIDATE_INVALID",
    }
