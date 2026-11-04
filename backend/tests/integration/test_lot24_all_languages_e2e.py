"""LOT 2.3 — toutes les langues de bout en bout : détection, analyse, RAG.

Pour chacune des 23 langues officielles de l'UE autres que le français, et pour
l'arabe, un DOCX contenant un texte officiel EUR-Lex (arabe : phrase
synthétique) est envoyé par l'API, puis analysé et traduit par le vrai pipeline.
On vérifie :

1. la langue et le domaine déterminés par le pipeline (IR « analysis »), sans
   rien poser à la main ;
2. que la recherche RAG a trouvé l'entrée publiée (journal de recherche) ;
3. que l'entrée est injectée dans le contexte du moteur privé à partir de cette
   IR réelle.

Seul l'appel au modèle de traduction est simulé (moteur hors ligne des tests).
Les entrées publiées sont des lignes réelles des données ``data/rag-ue``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from docx import Document

from app.application import rag_bridge

from .rag_support import headers, make_rag_client, publish_referential

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "rag_ue_languages.json").read_text(
        encoding="utf-8"
    )
)
ENTRIES = FIXTURE["entries"]
ISO3 = {
    "ar": "ara", "bg": "bul", "cs": "ces", "da": "dan", "de": "deu", "el": "ell", "en": "eng",
    "es": "spa", "et": "est", "fi": "fin", "ga": "gle", "hr": "hrv", "hu": "hun", "it": "ita",
    "lt": "lit", "lv": "lav", "mt": "mlt", "nl": "nld", "pl": "pol", "pt": "por", "ro": "ron",
    "sk": "slk", "sl": "slv", "sv": "swe", "fr": "fra",
}  # fmt: skip
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx(text: str) -> bytes:
    document = Document()
    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _published_rows() -> list[dict]:
    return [
        {
            "source_language": item["language"],
            "source_term": item["term"],
            "target_language": "fr",
            "target_term": item["target"],
            "domain": item["domain"],
            "provenance": item["entry_provenance"][:200],
        }
        for item in ENTRIES
    ]


def _run_document(client, app, ids, text: str) -> dict:
    from app.rag.workers.tasks import wait_for_shadow

    response = client.post(
        "/api/documents",
        headers=headers(client, "admin-a"),
        files={"file": ("synthetique.docx", _docx(text), DOCX)},
    )
    assert response.status_code == 200, response.text
    doc_id = response.json()["id"]
    response = client.post(f"/api/documents/{doc_id}/translate", headers=headers(client, "admin-a"))
    assert response.status_code == 200, response.text
    assert wait_for_shadow(30)
    response = client.get(
        f"/api/documents/{doc_id}/artifact/analysis", headers=headers(client, "admin-a")
    )
    assert response.status_code == 200, response.text
    return response.json()


def _injected_targets(app, ids, ir: dict) -> list[str]:
    options = {"engine": "private", "target_language": "fr", "glossary": [], "memory": {}}
    result = rag_bridge.augment_translation_options(
        app.state.settings, app.state.session_factory, ids["tenant-a"], None, ir, options
    )
    terminology = (result.get("document_memory") or {}).get("terminology") or []
    return [item["target"] for item in terminology]


def test_fixture_covers_every_supported_source_language():
    from app.rag.terminology.linguistic import SUPPORTED_LANGUAGES

    assert sorted(item["language"] for item in ENTRIES) == sorted(set(SUPPORTED_LANGUAGES) - {"fr"})


@pytest.mark.parametrize("item", ENTRIES, ids=[item["language"] for item in ENTRIES])
def test_language_is_detected_and_its_rag_entry_reaches_the_private_engine(
    app_env, monkeypatch, item
):
    client, app, ids = make_rag_client(monkeypatch, mode="ACTIVE")
    publish_referential(
        client, ids, entries=_published_rows(), name="RAG UE langues", max_mode="ACTIVE"
    )
    # Document réaliste : intitulé d'attestation d'emploi dans la langue + paragraphe.
    ir = _run_document(client, app, ids, item["title"] + "\n" + item["text"])
    # 1. Langue et domaine déterminés par le pipeline, rien n'est posé à la main.
    assert ir["language"] == ISO3[item["language"]], (item["language"], ir.get("language"))
    assert ir["domain"] == "HR", (item["language"], ir.get("domain"))
    # 2. La recherche du vrai parcours a trouvé l'entrée (moteur hors ligne : ombre).
    log = client.get("/api/rag-admin/search-log", headers=headers(client, "admin-a")).json()
    assert log and log[-1]["result_count"] >= 1, log
    # 3. Le contexte du moteur privé reçoit la traduction française publiée.
    assert item["target"] in _injected_targets(app, ids, ir)


def test_french_control_document_stays_french_and_gets_no_foreign_entry(app_env, monkeypatch):
    client, app, ids = make_rag_client(monkeypatch, mode="ACTIVE")
    publish_referential(
        client, ids, entries=_published_rows(), name="RAG UE langues", max_mode="ACTIVE"
    )
    ir = _run_document(client, app, ids, FIXTURE["french_control"]["text"])
    assert ir["language"] == "fra"
    assert _injected_targets(app, ids, ir) == []
