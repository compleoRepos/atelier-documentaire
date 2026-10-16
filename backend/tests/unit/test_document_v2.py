from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from app.documents.pipeline import analyze_document, evaluate_document, translate_document


def test_docx_uses_real_libreoffice_pages_and_preserves_runs(tmp_path: Path):
    docx = pytest.importorskip("docx")
    source = tmp_path / "source.docx"
    document = docx.Document()
    document.sections[0].header.paragraphs[0].text = "Source header"
    paragraph = document.add_paragraph()
    paragraph.add_run("Employee ").bold = True
    paragraph.add_run("name")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Salary"
    table.cell(0, 1).text = "1234"
    document.sections[0].footer.paragraphs[0].text = "Source footer"
    document.save(source)

    work = tmp_path / "work"
    ir = analyze_document(str(source), str(work))
    assert ir["format"] == "docx"
    assert ir["versions"]["pagination"] in {"libreoffice-pdf", None}
    if ir["versions"]["pagination"] == "libreoffice-pdf":
        assert list((work / "previews").glob("original-*.png"))
    assert ir["tables"][0]["rows"] == 1 and ir["tables"][0]["columns"] == 2
    result = asyncio.run(
        translate_document(
            ir, str(work), {"engine": "offline", "memory": {"Employee name": "Nom salarié"}}
        )
    )
    assert Path(result["versions"]["candidate"]).is_file()
    candidate = docx.Document(result["versions"]["candidate"])
    assert len(candidate.paragraphs[0].runs) == 2
    assert candidate.sections[0].header.paragraphs[0].text == "Source header"


def test_quality_contract_absence_is_explicit(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.ai.quality.engine", None)
    result = evaluate_document(
        {"pages": [{"blocks": [{"id": "b", "text": "1234"}]}]}, {"b": "1234"}
    )
    assert result["provenance"]["quality_engine"] == "unavailable"
    assert result["coverage"]["quality_engine"] is False
    assert any(issue["code"] == "QUALITY_ENGINE_UNAVAILABLE" for issue in result["issues"])
