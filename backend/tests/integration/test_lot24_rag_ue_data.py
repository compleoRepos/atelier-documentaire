"""LOT 2.4 — données RAG UE (EuroVoc 4.24) et bibliothèque commune, sur le vrai chemin.

1. Intégrité : empreintes du manifeste, licence et indication des modifications sur chaque ligne.
2. Les 23 fichiers passent l'importeur du produit (API, simulation) sans aucune erreur.
3. Outil de plateforme : import en brouillon (invisible), quatre yeux imposés, publication,
   activation, puis injection réelle chez deux tenants distincts (bibliothèque commune).
4. Tout ou rien : un fichier invalide ou un manifeste altéré n'écrit rien.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from pathlib import Path

from app.application import rag_bridge
from app.rag.common_library_cli import run
from app.rag.terminology.linguistic import EU_OFFICIAL_LANGUAGES

from .rag_support import grant, headers, make_rag_client

DATA = Path(__file__).resolve().parents[3] / "data" / "rag-ue" / "eurovoc"
REPORTS: list[dict] = []
DE_TEXT = "Der Arbeitsvertrag wurde unterschrieben; es gilt der Mindestlohn."


def _manifest() -> dict:
    return json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))


def _rows(name: str) -> list[dict]:
    text = (DATA / name).read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def test_manifest_matches_files_licence_and_modifications_on_every_row():
    manifest = _manifest()
    assert manifest["version"] == "4.24"
    assert "CC BY 4.0" in manifest["licence"]
    expected = {f"eurovoc-{code}-fr.csv" for code in EU_OFFICIAL_LANGUAGES if code != "fr"}
    assert set(manifest["files"]) == expected and len(expected) == 23
    total = 0
    for name, meta in manifest["files"].items():
        data = (DATA / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], name
        rows = _rows(name)
        assert len(rows) == meta["rows"]
        source = name.split("-")[1]
        for row in rows:
            assert row["source_language"] == source and row["target_language"] == "fr"
            assert row["source_term"] and row["target_term"]
            assert "CC BY 4.0" in row["provenance"] and "modifié" in row["provenance"]
            assert row["jurisdiction"] == ""  # sinon écartée sans juridiction déclarée
        total += len(rows)
    assert total == 20537


def test_every_eurovoc_file_passes_the_product_importer(app_env, monkeypatch):
    client, _app, ids = make_rag_client(monkeypatch, mode="SHADOW")
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    grant(client, "admin-a", ids["admin-a"], "terminology_manager")
    h = headers(client, "admin-a")
    referential = client.post(
        "/api/rag-admin/referentials",
        headers=h,
        # L'API plafonne à 20 langues déclarées (contrat inchangé) : aucune n'est déclarée ici.
        json={"kind": "linguistic", "name": "EuroVoc"},
    )
    assert referential.status_code in (200, 201), referential.text
    referential = referential.json()
    draft = client.post(
        f"/api/rag-admin/referentials/{referential['id']}/versions", headers=h, json={}
    ).json()
    for name, meta in sorted(_manifest()["files"].items()):
        response = client.post(
            f"/api/rag-admin/versions/{draft['id']}/import",
            params={"format": "csv", "dry_run": "true"},
            content=(DATA / name).read_bytes(),
            headers={**h, "Content-Type": "application/octet-stream"},
        )
        assert response.status_code == 200, (name, response.text[:300])
        body = response.json()
        assert body["status"] == "dry_run", (name, body["report"][:3])
        assert body["error_count"] == 0, name
        assert body["accepted_count"] == meta["rows"], name


def _targets(app, tenant_id: str, text: str) -> list[str]:
    ir = {
        "language": "de",
        "domain": "HR",
        "pages": [{"number": 1, "blocks": [{"id": "b1", "text": text, "language": "de"}]}],
    }
    options = {"engine": "private", "target_language": "fr", "glossary": [], "memory": {}}
    REPORTS.clear()
    result = rag_bridge.augment_translation_options(
        app.state.settings,
        app.state.session_factory,
        tenant_id,
        None,
        ir,
        options,
        on_report=REPORTS.append,
    )
    terminology = (result.get("document_memory") or {}).get("terminology") or []
    return [item["target"] for item in terminology]


def _cli(app, *argv: str) -> dict:
    return run(list(argv), settings=app.state.settings)


def test_common_library_import_four_eyes_publication_and_injection_in_two_tenants(
    app_env, monkeypatch
):
    client, app, ids = make_rag_client(monkeypatch, mode="ACTIVE")
    for author in ("admin-a", "admin-b"):
        grant(client, author, ids[author], "rag_admin")
        mode = client.post(
            "/api/rag-admin/tenant", headers=headers(client, author), json={"max_mode": "ACTIVE"}
        )
        assert mode.status_code == 200, mode.text

    imported = _cli(app, "import-eurovoc", "--dir", str(DATA), "--actor", "admin-a")
    assert imported["ok"], imported
    assert len(imported["result"]) == 23
    manifest = _manifest()["files"]
    for item in imported["result"]:
        (batch,) = item["files"]
        assert item["status"] == "draft" and batch["status"] == "applied"
        assert batch["errors"] == 0 and batch["accepted"] == manifest[batch["file"]]["rows"]

    name = "EuroVoc 4.24 de-fr"
    assert _targets(app, ids["tenant-a"], DE_TEXT) == []  # brouillon : invisible

    version = next(i for i in imported["result"] if i["name"] == name)["version_id"]
    refused = client.post(
        f"/api/rag-admin/versions/{version}/import",
        params={"format": "csv", "dry_run": "true"},
        content=(DATA / "eurovoc-de-fr.csv").read_bytes(),
        headers={**headers(client, "admin-a"), "Content-Type": "application/octet-stream"},
    )
    assert refused.status_code in (403, 404)  # un tenant n'écrit jamais la bibliothèque commune

    step = ("transition", "--name", name, "--version", "1", "--action")
    assert _cli(app, *step, "submit", "--actor", "admin-a")["ok"]
    same = _cli(app, *step, "validate", "--actor", "admin-a")
    assert same == {"ok": False, "code": "RAG_FOUR_EYES_REQUIRED", "detail": None}
    assert _cli(app, *step, "validate", "--actor", "reviewer-a")["ok"]
    assert _cli(app, *step, "publish", "--actor", "admin-a")["ok"]
    assert _targets(app, ids["tenant-a"], DE_TEXT) == []  # publié mais inactif : invisible
    assert _cli(app, "activate", "--name", name, "--actor", "admin-a")["ok"]

    for tenant in ("tenant-a", "tenant-b"):
        targets = _targets(app, ids[tenant], DE_TEXT)
        assert "contrat de travail" in targets and "salaire minimal" in targets, (
            tenant,
            repr(REPORTS)[:3000],
        )

    status = _cli(app, "status")["referentials"]
    published = [r for r in status if r["name"] == name][0]
    assert published["active"] and published["versions"][0]["status"] == "published"
    others = [r for r in status if r["name"] != name]
    assert len(others) == 22 and all(r["versions"][0]["status"] == "draft" for r in others)


def test_unknown_actor_altered_manifest_and_invalid_file_write_nothing(
    app_env, monkeypatch, tmp_path
):
    _client, app, _ids = make_rag_client(monkeypatch, mode="SHADOW")
    assert _cli(app, "import-eurovoc", "--dir", str(DATA), "--actor", "inconnu") == {
        "ok": False,
        "code": "ACTOR_UNKNOWN",
        "detail": None,
    }
    altered = tmp_path / "eurovoc"
    shutil.copytree(DATA, altered)
    with (altered / "eurovoc-sv-fr.csv").open("a", encoding="utf-8") as handle:
        handle.write("sv;tillägg;fr;ajout;;;;HR;EU;test\n")
    outcome = _cli(app, "import-eurovoc", "--dir", str(altered), "--actor", "admin-a")
    assert outcome["ok"] is False and outcome["code"] == "MANIFEST_MISMATCH"

    bad = tmp_path / "bad.csv"
    bad.write_text(
        "source_language;source_term;target_language;target_term\n"
        "de;Lohn;fr;salaire\nja;給料;fr;salaire\n",
        encoding="utf-8",
    )
    outcome = _cli(
        app, "import", "--name", "Essai", "--languages", "de,fr", "--actor", "admin-a", str(bad)
    )
    assert outcome["ok"] is False and outcome["code"] == "IMPORT_REJECTED"
    assert _cli(app, "status")["referentials"] == []  # aucune écriture partielle
