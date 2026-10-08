from __future__ import annotations

import asyncio
from pathlib import Path

import fitz

from app.documents.pipeline import analyze_document, translate_document


def _pdf(path: Path):
    d = fitz.open()
    for text in ("Page one 2024", "", "Page three"):
        p = d.new_page(width=300, height=200)
        if text:
            p.insert_text((20, 40), text)
    d.save(path)
    d.close()


def test_repeated_analysis_has_stable_ids_and_pages(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    a = analyze_document(str(source), str(tmp_path / "a"), {"ocr_languages": ["eng"]})
    b = analyze_document(str(source), str(tmp_path / "b"), {"ocr_languages": ["eng"]})
    ids_a = [x["id"] for p in a["pages"] for x in p["blocks"]]
    ids_b = [x["id"] for p in b["pages"] for x in p["blocks"]]
    assert ids_a == ids_b
    assert len(a["pages"]) == 3


def test_offline_candidate_is_review_only(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    ir = analyze_document(str(source), str(tmp_path / "work"), {"ocr_languages": ["eng"]})
    result = asyncio.run(translate_document(ir, str(tmp_path / "work"), {"engine": "offline"}))
    assert result["quality"]["status"] == "REVIEW_REQUIRED"
    assert result["quality"]["ocr_score"] is None
    assert result["quality"]["semantic_score"] is None
