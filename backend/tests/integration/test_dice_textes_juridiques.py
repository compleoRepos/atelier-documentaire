"""Version finale DICE : textes du droit du travail de l'UE article par article (25 actes).

Vraies données versionnées (data/rag-ue/eurlex), base SQLite de test, outil d'exploitation
réel (``common_library_cli``). Vérifie : fidélité exacte au texte source, double contrôle
d'intégrité, quatre yeux, empreinte du contenu, invisibilité tant que la version n'est pas
publiée et le référentiel activé, recherche dans chacune des langues, et absence de tout effet
sur la traduction (aucune entrée terminologique, aucun index BM25).
"""

from __future__ import annotations

import collections
import gzip
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.models import User
from app.rag.common_library_cli import LEGAL_NAME, run
from app.rag.models import (
    RagLegalPassage,
    RagLegalText,
    RagLexicalIndex,
    RagReferential,
    RagReferentialVersion,
    RagTermEntry,
)
from app.rag.storage import versioning
from app.rag.storage.legal_library import counts
from app.rag.storage.repository import TERMINOLOGY_KINDS, RagAccessError
from app.rag.terminology.linguistic import folded_tokens

from .rag_support import make_rag_client

ROOT = Path(__file__).resolve().parents[3]
EURLEX = ROOT / "data" / "rag-ue" / "eurlex"


def _cli(settings, *argv: str) -> dict:
    return run(list(argv), settings=settings)


def _source_rows() -> list[dict]:
    rows = []
    for path in sorted((EURLEX / "eurlex").glob("*.jsonl.gz")):
        rows += [json.loads(line) for line in gzip.open(path, "rt", encoding="utf-8")]
    return rows


def _move(settings, action: str, actor: str) -> dict:
    return _cli(
        settings, "transition", "--name", LEGAL_NAME, "--version", "1", "--action", action,
        "--actor", actor,
    )  # fmt: skip


def test_legal_texts_fidelity_four_eyes_fingerprint_search_and_isolation(app_env, monkeypatch):
    _client, app, _ids = make_rag_client(monkeypatch, mode="SHADOW")
    settings = app.state.settings
    factory = app.state.session_factory
    sums = json.loads((EURLEX / "textes-sha256.json").read_text(encoding="utf-8"))
    assert (sums["acts"], sums["act_language_pairs"], sums["articles_language"]) == (25, 571, 11208)

    imported = _cli(settings, "import-legal", "--dir", str(EURLEX), "--actor", "admin-a")
    assert imported["ok"], imported
    result = imported["result"]
    assert (result["texts"], result["passages"], result["status"]) == (571, 11208, "draft")

    # Fidélité : chaque passage = intitulé de l'article puis corps, octet pour octet.
    source = {
        (row["celex"], row["language"], row["article"]): (
            f"{row['title']}\n{row['text']}" if row.get("title") else row["text"]
        )
        for row in _source_rows()
    }
    assert len(source) == 11208
    with factory() as db:
        stored = {}
        for passage, text in db.execute(
            select(RagLegalPassage, RagLegalText).join(
                RagLegalText, RagLegalPassage.legal_text_id == RagLegalText.id
            )
        ).all():
            celex = text.official_reference.rsplit("CELEX ", 1)[1].rstrip(")")
            stored[(celex, passage.language, passage.article_ref)] = passage.text
            assert passage.language == text.language
        assert stored == source
        languages = {key[1] for key in source}
        assert len(languages) == 24
        assert db.scalar(select(func.count(RagTermEntry.id))) == 0

    # Brouillon : invisible.
    hidden = _cli(settings, "legal-search", "--query", "Arbeitszeit", "--language", "de")
    assert hidden["ok"] and hidden["matches"] == 0

    # Quatre yeux.
    assert _move(settings, "submit", "admin-a")["ok"]
    same = _move(settings, "validate", "admin-a")
    assert (same["ok"], same["code"]) == (False, "RAG_FOUR_EYES_REQUIRED")

    # Un passage modifié après soumission bloque la validation (empreinte du contenu juridique).
    with factory() as db:
        passage = db.scalars(select(RagLegalPassage).order_by(RagLegalPassage.id)).first()
        original = passage.text
        passage.text = original + " "
        db.commit()
    changed = _move(settings, "validate", "admin-b")
    assert (changed["ok"], changed["code"]) == (False, "RAG_CONTENT_CHANGED")
    with factory() as db:
        version = db.scalars(select(RagReferentialVersion)).one()
        # Le circuit générique (entrées terminologiques) ne contourne pas l'empreinte juridique.
        referential = db.get(RagReferential, version.referential_id)
        validator = db.scalar(select(User.id).where(User.username == "admin-b"))
        with pytest.raises(RagAccessError) as bypass:
            versioning.transition(
                db, referential, version, "validate", validator, {"legal_manager"}
            )
        assert bypass.value.code == "RAG_CONTENT_CHANGED"
        db.rollback()
        db.get(RagLegalPassage, passage.id).text = original
        db.commit()

    assert _move(settings, "validate", "admin-b")["ok"]
    assert _move(settings, "publish", "admin-a")["ok"]
    inactive = _cli(settings, "legal-search", "--query", "Arbeitszeit", "--language", "de")
    assert inactive["matches"] == 0
    assert _cli(settings, "activate", "--name", LEGAL_NAME, "--actor", "admin-a")["ok"]

    status = _cli(settings, "status")
    (item,) = [r for r in status["referentials"] if r["name"] == LEGAL_NAME]
    assert item["kind"] == "regulatory" and item["active"] is True
    assert item["versions"] == [
        {
            "number": 1,
            "status": "published",
            "entries": 0,
            "legal_texts": 571,
            "legal_passages": 11208,
            "legal_acts": 25,
            "legal_languages": 24,
        }
    ]

    # Recherche : article 6 de la directive 2003/88/CE (durée maximale hebdomadaire).
    found = _cli(
        settings, "legal-search", "--query", "durée maximale hebdomadaire de travail",
        "--language", "fr", "--reference", "2003/88",
    )  # fmt: skip
    assert found["ok"] and found["results"], found
    first = found["results"][0]
    assert (first["article"], first["language"]) == ("6", "fr")
    assert first["reference"] == "Directive 2003/88/CE (CELEX 32003L0088)"
    assert first["excerpt"].startswith("Durée maximale hebdomadaire de travail\n")
    assert first["source"].endswith("CELEX:32003L0088")
    greek = _cli(
        settings, "legal-search", "--query", "ΜΈΓΙΣΤΗ εβδομαδιαια διαρκεια", "--language", "el",
        "--reference", "2003/88",
    )  # fmt: skip
    assert [r["article"] for r in greek["results"]][:1] == ["6"]

    # Le JO allemand de 2003/88/CE écrit « Hoechstarbeitszeit » : les deux graphies trouvent l'art. 6,
    # et le texte officiel renvoyé n'est pas modifié.
    assert source[("32003L0088", "de", "6")].startswith("Wöchentliche Hoechstarbeitszeit\n")
    german_matches = set()
    for query, variants in (
        ("Höchstarbeitszeit", {"hochstarbeitszeit": ["hoechstarbeitszeit"]}),
        ("Hoechstarbeitszeit", {"hoechstarbeitszeit": ["hochstarbeitszeit"]}),
    ):
        german = _cli(settings, "legal-search", "--query", query, "--language", "de")
        assert german["ok"] and german["spelling_variants"] == variants, german
        top = german["results"][0]
        assert (top["reference"], top["article"], top["language"]) == (
            "Directive 2003/88/CE (CELEX 32003L0088)", "6", "de",
        )  # fmt: skip
        assert top["excerpt"].startswith("Wöchentliche Hoechstarbeitszeit\n")
        assert all(r["language"] == "de" for r in german["results"])
        german_matches.add(german["matches"])
    assert len(german_matches) == 1
    # Sans langue, seule la graphie transcrite d'un mot à tréma est ajoutée ; la graphie inverse
    # reste réservée à l'allemand (« oeuvre » en français ne devient jamais « ouvre »).
    unlabeled = _cli(settings, "legal-search", "--query", "Höchstarbeitszeit")
    assert unlabeled["spelling_variants"] == {"hochstarbeitszeit": ["hoechstarbeitszeit"]}
    assert unlabeled["results"][0]["article"] == "6"
    french = _cli(settings, "legal-search", "--query", "oeuvre", "--language", "fr")
    assert (french["query_words"], french["spelling_variants"]) == (["oeuvre"], {})
    expected = sum(
        1
        for (_c, lang, _a), text in source.items()
        if lang == "fr" and "oeuvre" in folded_tokens(text)
    )
    assert french["matches"] == expected > 0
    assert _cli(settings, "legal-search", "--query", "oeuvre")["spelling_variants"] == {}

    # Chaque langue est interrogeable : un mot de son premier passage retrouve ce passage.
    by_language = collections.defaultdict(list)
    for (celex, language, article), text in sorted(source.items()):
        by_language[language].append((celex, article, text))
    for language, items in sorted(by_language.items()):
        celex, article, text = items[0]
        word = max(folded_tokens(text), key=len)
        hit = _cli(settings, "legal-search", "--query", word, "--language", language,
                   "--limit", "50")  # fmt: skip
        assert hit["ok"], (language, hit)
        assert all(r["language"] == language for r in hit["results"]), language
        assert hit["matches"] >= 1, language

    # Isolement : rien pour la traduction (ni entrée terminologique, ni index BM25).
    assert "regulatory" not in TERMINOLOGY_KINDS
    with factory() as db:
        version = db.scalars(select(RagReferentialVersion)).one()
        assert db.scalar(select(func.count(RagTermEntry.id))) == 0
        assert db.get(RagLexicalIndex, version.id) is None
        assert counts(db, version)["legal_passages"] == 11208
        statuses = set(db.scalars(select(RagLegalText.validation_status)).all())
        assert statuses == {"validated"}

    # Requêtes refusées proprement.
    assert _cli(settings, "legal-search", "--query", " , ; ")["code"] == "QUERY_EMPTY"
    assert _cli(settings, "legal-search", "--query", "x", "--language", "zz")["code"] == (
        "LANGUAGE_INVALID"
    )


def _copy(tmp_path: Path) -> Path:
    copy = tmp_path / "eurlex"
    shutil.copytree(EURLEX, copy)
    return copy


def test_altered_text_file_or_manifest_stops_before_any_write(app_env, monkeypatch, tmp_path):
    _client, app, _ids = make_rag_client(monkeypatch, mode="SHADOW")
    settings = app.state.settings
    copy = _copy(tmp_path)
    target = copy / "eurlex" / "32003L0088.jsonl.gz"
    target.write_bytes(target.read_bytes() + b"\0")
    altered = _cli(settings, "import-legal", "--dir", str(copy), "--actor", "admin-a")
    assert (altered["ok"], altered["code"]) == (False, "MANIFEST_MISMATCH")
    assert altered["detail"] == {"file": "32003L0088.jsonl.gz"}

    copy2 = _copy(tmp_path / "b")
    manifest = json.loads((copy2 / "manifest.json").read_text(encoding="utf-8"))
    manifest["acts"]["32003L0088"]["languages"]["fr"]["articles"] += 1
    (copy2 / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    mismatch = _cli(settings, "import-legal", "--dir", str(copy2), "--actor", "admin-a")
    assert (mismatch["ok"], mismatch["code"]) == (False, "MANIFEST_MISMATCH")
    assert mismatch["detail"] == {"file": "32003L0088.jsonl.gz", "language": "fr"}

    assert _cli(settings, "status")["referentials"] == []
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count(RagLegalText.id))) == 0
        assert db.scalar(select(func.count(RagLegalPassage.id))) == 0
