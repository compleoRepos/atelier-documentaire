"""LOT 2.3 — paire arabe -> français (libellés Wikidata alignés sur EuroVoc).

EuroVoc, IATE et EUR-Lex ne couvrent pas l'arabe : la paire est construite par
``tools/rag_ue/wikidata_ar_to_csv.py`` (Wikidata CC0 pour l'arabe, terme
français officiel EuroVoc). On vérifie l'intégrité, l'alignement sur le
français officiel, l'importeur du produit et la publication à quatre yeux.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from app.application import rag_bridge
from app.rag.common_library_cli import run

from .rag_support import grant, headers, make_rag_client

DATA = Path(__file__).resolve().parents[3] / "data" / "rag-ue"
WIKIDATA = DATA / "wikidata"
ARABIC = re.compile(r"[\u0600-\u06FF]")


def _rows() -> list[dict]:
    data = (WIKIDATA / "wikidata-ar-fr.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(data), delimiter=";"))


def _eurovoc_french() -> dict[str, str]:
    labels: dict[str, str] = {}
    for path in sorted((DATA / "eurovoc").glob("eurovoc-*-fr.csv")):
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                match = re.search(r"descripteur (\d+)", row["provenance"])
                if match:
                    labels.setdefault(match.group(1), row["target_term"])
    return labels


def test_manifest_licence_and_file_integrity():
    manifest = json.loads((WIKIDATA / "manifest.json").read_text(encoding="utf-8"))
    assert "CC0" in manifest["licence"] and "CC BY 4.0" in manifest["licence"]
    meta = manifest["files"]["wikidata-ar-fr.csv"]
    blob = (WIKIDATA / "wikidata-ar-fr.csv").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == meta["sha256"]
    assert meta["rows"] == len(_rows()) == manifest["stats"]["lignes"] == 290
    # 70 descripteurs écartés par l'évaluation automatique (pas une revue humaine)
    review = manifest["review_list"]
    blob = (WIKIDATA / review["file"]).read_bytes()
    assert hashlib.sha256(blob).hexdigest() == review["sha256"]
    assert review["descriptors"] == manifest["stats"]["exclus_revue"] == 70


def test_review_list_is_disjoint_from_the_importable_file_and_motivated():
    with (WIKIDATA / "revue-evaluation-automatique.csv").open(encoding="utf-8", newline="") as fh:
        review = list(csv.DictReader(fh, delimiter=";"))
    assert len(review) == 70
    assert {r["evaluateur"] for r in review} <= {"gpt-6.1-sol", "gpt-5.5"}
    assert all(r["verdict"] == "incorrect" and r["motif"].strip() for r in review)
    imported = {re.search(r"descripteur (\d+)$", row["provenance"]).group(1) for row in _rows()}
    assert not imported & {r["descriptor"] for r in review}


def test_every_row_is_arabic_and_targets_the_official_eurovoc_french_label():
    french = _eurovoc_french()
    descriptors = set()
    for row in _rows():
        assert row["source_language"] == "ar" and row["target_language"] == "fr"
        assert ARABIC.search(row["source_term"]), row["source_term"]
        match = re.search(r"Wikidata Q\d+ \(CC0\).*descripteur (\d+)$", row["provenance"])
        assert match, row["provenance"]
        descriptor = match.group(1)
        assert french[descriptor] == row["target_term"], descriptor  # jamais le libellé Wikidata
        descriptors.add(descriptor)
        for synonym in filter(None, (s.strip() for s in row["synonyms"].split("|"))):
            assert ARABIC.search(synonym), synonym
    assert len(descriptors) == 290  # une ligne par descripteur


def test_arabic_file_passes_the_product_importer(app_env, monkeypatch):
    client, _app, ids = make_rag_client(monkeypatch, mode="SHADOW")
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    grant(client, "admin-a", ids["admin-a"], "terminology_manager")
    h = headers(client, "admin-a")
    referential = client.post(
        "/api/rag-admin/referentials", headers=h, json={"kind": "linguistic", "name": "Wikidata ar"}
    )
    assert referential.status_code in (200, 201), referential.text
    draft = client.post(
        f"/api/rag-admin/referentials/{referential.json()['id']}/versions", headers=h, json={}
    ).json()
    response = client.post(
        f"/api/rag-admin/versions/{draft['id']}/import",
        params={"format": "csv", "dry_run": "true"},
        content=(WIKIDATA / "wikidata-ar-fr.csv").read_bytes(),
        headers={**h, "Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200, response.text[:300]
    body = response.json()
    assert body["error_count"] == 0, body["report"][:3]
    assert body["accepted_count"] + body["skipped_count"] == 290


def test_arabic_entry_is_injected_after_four_eyes_publication_in_the_common_library(
    app_env, monkeypatch
):
    client, app, ids = make_rag_client(monkeypatch, mode="ACTIVE")
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    h = headers(client, "admin-a")
    assert client.post("/api/rag-admin/tenant", headers=h, json={"max_mode": "ACTIVE"}).is_success
    settings = app.state.settings
    name = "Wikidata ar-fr"
    imported = run(
        [
            "import",
            "--name",
            name,
            "--languages",
            "ar,fr",
            "--actor",
            "admin-a",
            str(WIKIDATA / "wikidata-ar-fr.csv"),
        ],
        settings=settings,
    )
    assert imported["ok"], imported
    step = ["transition", "--name", name, "--version", "1", "--action"]
    assert run([*step, "submit", "--actor", "admin-a"], settings=settings)["ok"]
    assert run([*step, "validate", "--actor", "reviewer-a"], settings=settings)["ok"]
    assert run([*step, "publish", "--actor", "admin-a"], settings=settings)["ok"]
    assert run(["activate", "--name", name, "--actor", "admin-a"], settings=settings)["ok"]
    text = "تلتزم الشركة بتحسين ظروف عمل الموظفين."
    ir = {
        "language": "ara",
        "domain": "HR",
        "pages": [{"number": 1, "blocks": [{"id": "b1", "text": text, "language": "ara"}]}],
    }
    options = {"engine": "private", "target_language": "fr", "glossary": [], "memory": {}}
    result = rag_bridge.augment_translation_options(
        settings, app.state.session_factory, ids["tenant-a"], None, ir, options
    )
    targets = [t["target"] for t in (result.get("document_memory") or {}).get("terminology") or []]
    assert "condition de travail" in targets
