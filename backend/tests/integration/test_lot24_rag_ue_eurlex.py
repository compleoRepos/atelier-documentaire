"""LOT 2.4 — textes du droit du travail de l'UE (EUR-Lex) et définitions légales alignées.

1. Manifeste : empreintes, comptes, licence ; anomalies des textes officiels déclarées à l'identique.
2. Chaque article a un texte, une source EUR-Lex et l'empreinte du HTML d'origine.
3. Les 22 fichiers de définitions passent l'importeur du produit (API, simulation) sans erreur.
4. Filtre de juridiction : une définition (juridiction EU) n'est injectée que si le document
   déclare la juridiction EU ; sans déclaration, elle est écartée (JURISDICTION_UNKNOWN).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

from app.application import rag_bridge
from app.rag.common_library_cli import run

from .rag_support import grant, headers, make_rag_client
from .test_rag_lot1_shadow import upload_pdf

DATA = Path(__file__).resolve().parents[3] / "data" / "rag-ue" / "eurlex"
# Anomalies des textes officiels eux-mêmes (numérotation), extraction arrêtée et signalée.
KNOWN_ANOMALIES = {("32000L0043", "it"), ("32000L0078", "es"), ("32002L0014", "ro")}
DE_TEXT = "Die Arbeitszeit wird erfasst."


def _manifest() -> dict:
    return json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_texts_sources_and_declared_anomalies():
    manifest = _manifest()
    assert "2011/833/UE" in manifest["licence"] and "font foi" in manifest["licence"]
    assert len(manifest["acts"]) == 25
    anomalies, couples = set(), 0
    for celex, act in manifest["acts"].items():
        blob = (DATA / "eurlex" / f"{celex}.jsonl.gz").read_bytes()
        assert hashlib.sha256(blob).hexdigest() == act["file_sha256"], celex
        records = [json.loads(line) for line in gzip.decompress(blob).decode().splitlines()]
        assert len(records) == act["records"] and act["title"]
        for record in records:
            meta = act["languages"][record["language"]]
            assert record["celex"] == celex and record["text"].strip()
            assert record["source"].endswith(f"CELEX:{celex}")
            assert record["html_sha256"] == meta["html_sha256"]
        for lang, meta in act["languages"].items():
            couples += 1
            if not meta["same_articles_as_fr"]:
                anomalies.add((celex, lang))
                assert "rupture" in meta["layout"]
    assert anomalies == KNOWN_ANOMALIES
    assert couples == 571


def test_every_definition_file_passes_the_product_importer(app_env, monkeypatch):
    client, _app, ids = make_rag_client(monkeypatch, mode="SHADOW")
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    grant(client, "admin-a", ids["admin-a"], "terminology_manager")
    h = headers(client, "admin-a")
    referential = client.post(
        "/api/rag-admin/referentials", headers=h, json={"kind": "linguistic", "name": "EUR-Lex"}
    )
    assert referential.status_code in (200, 201), referential.text
    draft = client.post(
        f"/api/rag-admin/referentials/{referential.json()['id']}/versions", headers=h, json={}
    ).json()
    definitions = _manifest()["definitions"]
    files = {lang: meta for lang, meta in definitions.items() if meta.get("rows")}
    assert len(files) == 22 and "fr" not in files
    total = 0
    for lang, meta in sorted(files.items()):
        data = (DATA / "definitions" / meta["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], lang
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8")), delimiter=";"))
        assert len(rows) == meta["rows"]
        for row in rows:
            assert row["source_language"] == lang and row["target_language"] == "fr"
            assert row["jurisdiction"] == "EU" and row["domain"] == "HR"
            assert "CELEX" in row["provenance"] and "2011/833/UE" in row["provenance"]
        response = client.post(
            f"/api/rag-admin/versions/{draft['id']}/import",
            params={"format": "csv", "dry_run": "true"},
            content=data,
            headers={**h, "Content-Type": "application/octet-stream"},
        )
        assert response.status_code == 200, (lang, response.text[:300])
        body = response.json()
        assert body["error_count"] == 0, (lang, body["report"][:3])
        assert body["accepted_count"] + body["skipped_count"] == meta["rows"], lang
        total += meta["rows"]
    assert total == 1654


def _targets(app, tenant_id: str, document_id: str | None) -> list[str]:
    ir = {
        "language": "de",
        "domain": "HR",
        "pages": [{"number": 1, "blocks": [{"id": "b1", "text": DE_TEXT, "language": "de"}]}],
    }
    options = {"engine": "private", "target_language": "fr", "glossary": [], "memory": {}}
    result = rag_bridge.augment_translation_options(
        app.state.settings, app.state.session_factory, tenant_id, document_id, ir, options
    )
    terminology = (result.get("document_memory") or {}).get("terminology") or []
    return [item["target"] for item in terminology]


def test_legal_definitions_are_injected_only_for_a_document_declaring_eu_jurisdiction(
    app_env, monkeypatch
):
    client, app, ids = make_rag_client(monkeypatch, mode="ACTIVE")
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    h = headers(client, "admin-a")
    assert client.post("/api/rag-admin/tenant", headers=h, json={"max_mode": "ACTIVE"}).is_success
    name = "EUR-Lex définitions de-fr"
    path = DATA / "definitions" / "eurlex-de-fr.csv"
    settings = app.state.settings
    imported = run(
        ["import", "--name", name, "--languages", "de,fr", "--actor", "admin-a", str(path)],
        settings=settings,
    )
    assert imported["ok"], imported
    step = ["transition", "--name", name, "--version", "1", "--action"]
    assert run([*step, "submit", "--actor", "admin-a"], settings=settings)["ok"]
    assert run([*step, "validate", "--actor", "reviewer-a"], settings=settings)["ok"]
    assert run([*step, "publish", "--actor", "admin-a"], settings=settings)["ok"]
    assert run(["activate", "--name", name, "--actor", "admin-a"], settings=settings)["ok"]

    doc_id = upload_pdf(client, "admin-a", "Synthetic employment record 2026.")
    assert "temps de travail" not in _targets(app, ids["tenant-a"], doc_id)  # rien de déclaré
    declared = client.post(
        f"/api/rag/documents/{doc_id}/context", headers=h, json={"jurisdiction": "EU"}
    )
    assert declared.status_code == 200, declared.text
    assert "temps de travail" in _targets(app, ids["tenant-a"], doc_id)
    other = upload_pdf(client, "admin-a", "Synthetic employment record 2027.")
    client.post(f"/api/rag/documents/{other}/context", headers=h, json={"jurisdiction": "FR"})
    assert "temps de travail" not in _targets(app, ids["tenant-a"], other)  # autre juridiction
