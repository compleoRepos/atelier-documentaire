"""Version finale DICE — textes du droit du travail de l'UE sur PostgreSQL 16 réel.

Exécuté quand ``RAG_TEST_POSTGRES_URL`` désigne une base dédiée (CI et local) ; la base est
remise à zéro puis migrée par Alembic. Données réelles versionnées (data/rag-ue/eurlex) :
import complet des 25 actes, quatre yeux, empreinte, recherche par mots entiers dans des
écritures latine, grecque et cyrillique, et annulation complète d'un import refusé.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from .test_rag_lot1_migration import _run

ROOT = Path(__file__).resolve().parents[2]
EURLEX = ROOT.parent / "data" / "rag-ue" / "eurlex"
URL = os.environ.get("RAG_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="RAG_TEST_POSTGRES_URL non défini")
ROLES = {"legal_manager"}


def test_legal_texts_import_four_eyes_search_and_rollback_on_postgresql():
    from app.rag.common_library_cli import LEGAL_NAME, _legal_texts
    from app.rag.models import RagLegalPassage, RagLegalText, RagLexicalIndex, RagTermEntry
    from app.rag.storage import common_library, legal_library
    from app.rag.storage.repository import RagAccessError

    engine = create_engine(URL)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    _run(engine, Config(str(ROOT / "alembic.ini")), "upgrade", "head")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    items = _legal_texts(EURLEX)
    assert (len(items), sum(len(item["passages"]) for item in items)) == (571, 11208)

    # Un import refusé (doublon d'article) n'écrit rien : la transaction est annulée.
    broken = [dict(item) for item in items[:2]]
    broken[1]["passages"] = [*broken[1]["passages"], broken[1]["passages"][0]]
    with factory() as db:
        referential = common_library.get_or_create(
            db, name=LEGAL_NAME, kind="regulatory", languages=["fr"], actor_id="u-author",
            domain="HR", jurisdiction="EU",
        )  # fmt: skip
        with pytest.raises(legal_library.LegalLibraryError) as duplicate:
            legal_library.import_legal_draft(
                db, referential=referential, texts=broken, actor_id="u-author"
            )
        assert duplicate.value.code == "PASSAGE_DUPLICATE"
        db.rollback()
    with factory() as db:
        assert db.scalar(select(func.count(RagLegalText.id))) == 0
        assert db.scalar(select(func.count(RagLegalPassage.id))) == 0

    with factory() as db:
        languages = sorted({item["language"] for item in items})
        referential = common_library.get_or_create(
            db, name=LEGAL_NAME, kind="regulatory", languages=languages, actor_id="u-author",
            domain="HR", jurisdiction="EU",
        )  # fmt: skip
        outcome = legal_library.import_legal_draft(
            db, referential=referential, texts=items, actor_id="u-author"
        )
        db.commit()
        assert (outcome.texts, outcome.passages) == (571, 11208)
        version = common_library.version_by_number(db, referential, 1)
        legal_library.transition(db, referential, version, "submit", "u-author", ROLES)
        with pytest.raises(RagAccessError) as same:
            legal_library.transition(db, referential, version, "validate", "u-author", ROLES)
        assert same.value.code == "RAG_FOUR_EYES_REQUIRED"
        legal_library.transition(db, referential, version, "validate", "u-checker", ROLES)
        legal_library.transition(db, referential, version, "publish", "u-author", ROLES)
        common_library.set_active(db, referential=referential, active=True, actor_id="u-author")
        db.commit()
        assert version.content_sha256 == outcome.content_sha256

    with factory() as db:
        fr = legal_library.search(
            db, "durée maximale hebdomadaire de travail", language="fr", reference="2003/88"
        )
        assert (fr["results"][0]["article"], fr["results"][0]["language"]) == ("6", "fr")
        el = legal_library.search(db, "μεγιστη εβδομαδιαια διαρκεια", language="el",
                                  reference="2003/88")  # fmt: skip
        assert el["results"][0]["article"] == "6"
        bg = legal_library.search(db, "работно време", language="bg", reference="2003/88")
        assert bg["matches"] >= 1 and all(r["language"] == "bg" for r in bg["results"])
        # La ponctuation (dont « % ») est ignorée : aucun joker LIKE implicite.
        assert (
            legal_library.search(db, "travail%")["matches"]
            == legal_library.search(db, "travail")["matches"]
        )
        assert db.scalar(select(func.count(RagTermEntry.id))) == 0
        assert db.scalar(select(func.count(RagLexicalIndex.version_id))) == 0
        assert legal_library.counts(db, version)["legal_passages"] == 11208
    engine.dispose()
