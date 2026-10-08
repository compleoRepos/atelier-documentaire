from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from app.documents.pipeline import analyze_document, translate_document

ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = ROOT / "dataset" / "metadata" / "catalog.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8")) if CATALOG_PATH.is_file() else {}


def _approved_reference(source_sha: str):
    sys.path.insert(0, str(ROOT / "tools"))
    from golden_references import load_reference

    return load_reference(
        ROOT / "dataset/expected", source_sha, os.getenv("TRANSLATOR_GOLDEN_TENANT_ID")
    )


@pytest.mark.parametrize(
    "entry", CATALOG.get("documents", []), ids=lambda item: item.get("document_id", "document")
)
def test_golden_document_technical_pipeline(entry, tmp_path):
    source = ROOT / "dataset" / "input" / entry["filename"]
    if not source.exists():
        pytest.skip("Golden Input privé absent : ce cas n'est pas un PASS de recette")
    work = tmp_path / entry["document_id"]
    ir = analyze_document(str(source), str(work))
    assert len(ir["pages"]) == entry["pages"]
    assert [page["number"] for page in ir["pages"]] == list(range(1, entry["pages"] + 1))
    source_sha = ir["versions"]["source_sha256"]
    reference = _approved_reference(source_sha)
    result = asyncio.run(
        translate_document(ir, str(work), {"engine": "offline", "reference": reference})
    )
    assert Path(result["versions"]["candidate"]).exists()
    assert result["quality"]["status"] == "REVIEW_REQUIRED"
    assert result["quality"]["translation_score"] is None
    # Technical processing cannot fabricate an approved human linguistic reference.
    assert result["quality"]["reference_status"] in {"not_evaluated", "not_available", "validated"}
    if reference is None:
        assert result["quality"]["reference_status"] in {"not_evaluated", "not_available"}
    else:
        assert result["quality"]["reference_status"] == "validated"
