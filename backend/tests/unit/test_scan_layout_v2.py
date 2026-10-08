from __future__ import annotations

import time

import fitz
from PIL import Image, ImageDraw

from app.documents.layout import detect_layout
from app.domain.classification import classify_document, detect_language


def _grid_page() -> fitz.Page:
    document = fitz.open()
    page = document.new_page(width=300, height=220)
    for x in (20, 100, 180, 280):
        if x == 100:
            page.draw_line((x, 20), (x, 70), width=1)
            page.draw_line((x, 115), (x, 160), width=1)
        else:
            page.draw_line((x, 20), (x, 160), width=1)
    for y in (20, 70, 115, 160):
        page.draw_line((20, y), (280, y), width=1)
    return page


def test_vector_2x3_grid_links_existing_blocks_and_preserves_merged_cell():
    page = _grid_page()
    blocks = [
        {"id": "p001-b0000", "bbox": [26, 28, 80, 44], "text": "Name"},
        {"id": "p001-b0001", "bbox": [106, 28, 160, 44], "text": "Value"},
    ]
    result = detect_layout(page=page, blocks=blocks, page_number=1, width=300, height=220)
    table = result["tables"][0]
    assert (table["rows"], table["columns"]) == (3, 3)
    assert table["provenance"] == "candidate_unvalidated"
    assert any(cell["column_span"] == 2 for cell in table["cells"])
    linked = [block_id for cell in table["cells"] for block_id in cell["block_ids"]]
    assert sorted(linked) == ["p001-b0000", "p001-b0001"]
    assert len(linked) == len(set(linked))
    assert all(cell["text"] == "" for cell in table["cells"])


def test_raster_checkbox_is_candidate_with_human_state_uncertainty():
    image = Image.new("RGB", (300, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 45, 45), outline="black", width=2)
    result = detect_layout(image, page_number=1, width=300, height=180)
    assert result["checkboxes"]
    checkbox = result["checkboxes"][0]
    assert checkbox["provenance"] == "candidate_unvalidated"
    assert "CHECKBOX_STATE_REQUIRES_REVIEW" in checkbox["human_uncertainty"]


def test_large_raster_pseudotext_is_bounded_and_keeps_table_and_checkbox():
    image = Image.new("L", (800, 1200), 255)
    draw = ImageDraw.Draw(image)
    for x in (40, 180, 320, 500):
        draw.line((x, 40, x, 300), fill=0, width=2)
    for y in (40, 120, 210, 300):
        draw.line((40, y, 500, y), fill=0, width=2)
    draw.rectangle((600, 50, 620, 70), outline=0, width=2)
    for y in range(350, 1150, 12):
        for x in range(10, 790, 18):
            draw.line((x, y, x + 7, y), fill=0)
            if (x // 18 + y // 12) % 3 == 0:
                draw.line((x, y, x, y + 5), fill=0)

    started = time.perf_counter()
    result = detect_layout(image, page_number=1, width=800, height=1200)
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0
    assert [(table["rows"], table["columns"]) for table in result["tables"]] == [(3, 3)]
    assert result["checkboxes"]
    assert "CHECKBOX_STATE_REQUIRES_REVIEW" in result["checkboxes"][0]["human_uncertainty"]


def test_unruled_rows_are_review_candidates_not_asserted_tables():
    blocks = [
        {"id": "a", "bbox": [10, 10, 40, 20], "text": "A"},
        {"id": "b", "bbox": [80, 10, 110, 20], "text": "B"},
        {"id": "c", "bbox": [10, 35, 40, 45], "text": "C"},
        {"id": "d", "bbox": [80, 35, 110, 45], "text": "D"},
    ]
    result = detect_layout(blocks=blocks, page_number=1, width=150, height=80)
    assert result["tables"][0]["candidate_reason"] == "text_row_clustering_without_ruled_lines"
    assert result["tables"][0]["confidence"] < 0.5
    assert "UNRULED_TABLE_REQUIRES_REVIEW" in result["tables"][0]["human_uncertainty"]


def test_reported_multilingual_cases_do_not_use_ids_or_filenames():
    cases = {
        "Dichiarazione del datore di lavoro e reddito da lavoro": "employment_certificate",
        "Werkgeversverklaring inkomensverklaring werkgever دخل صاحب العمل": "employment_certificate",
        "Arbeitsbescheinigung des Arbeitgebers, attestation de travail, contrat": "employment_certificate",
    }
    for text, expected in cases.items():
        result = classify_document(text)
        assert result["document_type"] == expected
    assert detect_language("Werkgeversverklaring werkgever ختم صاحب العمل")[0] == "nld"
