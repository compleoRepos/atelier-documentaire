"""Version finale DICE : chargement de la base RAG UE en une commande (tools/rag_ue/charger_dice_ue.py).

Vraies données versionnées (data/rag-ue), base SQLite de test, API réelle (TestClient).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from .rag_support import headers, make_rag_client

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "rag-ue"
SCRIPT = ROOT / "tools" / "rag_ue" / "charger_dice_ue.py"


def _loader():
    spec = importlib.util.spec_from_file_location("charger_dice_ue", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest_rows() -> tuple[int, int]:
    eurovoc = json.loads((DATA / "eurovoc" / "manifest.json").read_text(encoding="utf-8"))
    eurlex = json.loads((DATA / "eurlex" / "manifest.json").read_text(encoding="utf-8"))
    wikidata = json.loads((DATA / "wikidata" / "manifest.json").read_text(encoding="utf-8"))
    definitions = [m for m in eurlex["definitions"].values() if m.get("file") and m.get("rows")]
    referentials = len(eurovoc["files"]) + len(definitions) + 1
    rows = sum(m["rows"] for m in eurovoc["files"].values())
    # Un même terme défini dans plusieurs directives n'est publié qu'une fois (DUPLICATE_IN_FILE).
    for meta in definitions:
        path = DATA / "eurlex" / "definitions" / meta["file"]
        lines = list(csv.DictReader(path.open(encoding="utf-8"), delimiter=";"))
        assert len(lines) == meta["rows"]
        rows += len({(x["source_term"].casefold().strip(), x["target_term"].casefold().strip())
                     for x in lines})  # fmt: skip
    rows += wikidata["files"]["wikidata-ar-fr.csv"]["rows"]
    return referentials, rows


def _probe(lang: str) -> dict:
    if lang == "ar":
        path = DATA / "wikidata" / "wikidata-ar-fr.csv"
    else:
        path = DATA / "eurovoc" / f"eurovoc-{lang}-fr.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8"), delimiter=";"))
    return rows[len(rows) // 2]


def test_full_load_four_eyes_idempotent_and_search_in_every_source_language(app_env, monkeypatch):
    loader = _loader()
    client, app, _ids = make_rag_client(monkeypatch, mode="SHADOW")
    settings = app.state.settings

    with pytest.raises(loader.LoadError) as refused:
        loader.load(DATA, "admin-a", "ADMIN-A", settings=settings)
    assert refused.value.payload["step"] == "FOUR_EYES_REQUIRED"

    referentials, rows = _manifest_rows()
    first = loader.load(DATA, "admin-a", "admin-b", settings=settings)
    assert first["ok"] and first["missing"] == []
    assert first["imported_referentials"] == referentials == 46
    assert first["transitions"] == 3 * referentials
    assert first["activations"] == referentials
    assert first["published"] == first["active"] == referentials
    assert first["published_entries"] == rows

    second = loader.load(DATA, "admin-a", "admin-b", settings=settings)
    assert (second["imported_referentials"], second["transitions"], second["activations"]) == (
        0,
        0,
        0,
    )
    assert second["published_entries"] == rows

    token = headers(client, "admin-a")
    mode = client.post("/api/rag-admin/tenant", headers=token, json={"max_mode": "SHADOW"})
    assert mode.status_code == 200, mode.text
    languages = sorted(p.name[8:10] for p in (DATA / "eurovoc").glob("eurovoc-*-fr.csv"))
    assert len(languages) == 23
    for lang in [*languages, "ar"]:
        row = _probe(lang)
        body = {
            "text": row["source_term"],
            "source_language": lang,
            "target_language": "fr",
            "domain": row["domain"],
            "limit": 10,
        }
        found = client.post("/api/rag/search", headers=token, json=body)
        assert found.status_code == 200, (lang, found.text)
        targets = [item.get("target_term") for item in found.json()["results"]]
        assert row["target_term"] in targets, lang

    # Exemple documenté dans VERSION-FINALE-DICE.md §5.
    example = client.post(
        "/api/rag/search",
        headers=token,
        json={
            "text": "Mindestlohn",
            "source_language": "de",
            "target_language": "fr",
            "domain": "PAYROLL",
        },
    )
    assert example.status_code == 200, example.text
    assert "salaire minimal" in [item.get("target_term") for item in example.json()["results"]]

    # Sans domaine, une entrée spécialisée n'est jamais proposée (règle produit).
    row = _probe("de")
    blind = client.post(
        "/api/rag/search",
        headers=token,
        json={"text": row["source_term"], "source_language": "de", "target_language": "fr"},
    )
    assert blind.status_code == 200
    assert blind.json()["results"] == []
    assert blind.json()["exclusion_reasons"].get("DOMAIN_UNKNOWN", 0) >= 1


def test_altered_file_stops_before_any_write(app_env, monkeypatch, tmp_path):
    loader = _loader()
    _client, app, _ids = make_rag_client(monkeypatch, mode="SHADOW")
    copy = tmp_path / "rag-ue"
    shutil.copytree(DATA / "eurovoc", copy / "eurovoc")
    shutil.copytree(DATA / "wikidata", copy / "wikidata")
    (copy / "eurlex").mkdir()
    shutil.copy2(DATA / "eurlex" / "manifest.json", copy / "eurlex" / "manifest.json")
    shutil.copytree(DATA / "eurlex" / "definitions", copy / "eurlex" / "definitions")
    target = copy / "wikidata" / "wikidata-ar-fr.csv"
    target.write_bytes(target.read_bytes() + b"\n")

    with pytest.raises(loader.LoadError) as altered:
        loader.load(copy, "admin-a", "admin-b", settings=app.state.settings)
    assert altered.value.payload == {
        "ok": False,
        "step": "MANIFEST_MISMATCH",
        "file": "wikidata-ar-fr.csv",
    }
    status = loader.summary(["EuroVoc 4.24 de-fr"], settings=app.state.settings)
    assert status["present"] == 0
