"""DICE (RAG) LOT 2 — BM25 sur PostgreSQL 16 réel (schéma migré par Alembic).

Exécuté quand ``RAG_TEST_POSTGRES_URL`` désigne une base dédiée (CI et local) ;
la base est remise à zéro. Termes fabriqués pour les tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .test_rag_lot1_migration import _run

ROOT = Path(__file__).resolve().parents[2]
URL = os.environ.get("RAG_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="RAG_TEST_POSTGRES_URL non défini")

ROLES = {"rag_admin", "terminology_manager"}
ENTRIES = [
    ("en", "gross salary", "fr", "salaire brut", ["gross pay"], "HR"),
    ("en", "net salary", "fr", "salaire net", None, "PAYROLL"),
    ("en", "notice period", "fr", "préavis", None, "HR"),
    ("ar", "الراتب الأساسي", "fr", "salaire de base", None, "PAYROLL"),
    ("de", "Kündigung", "fr", "licenciement", ["Entlassung"], "HR"),
]


def _publish(db, referential, rows, author="u-author", checker="u-checker"):
    from app.rag.storage import versioning

    version = versioning.create_draft(db, referential, author, ROLES)
    versioning.add_entries(
        db,
        referential,
        version,
        [
            {
                "source_language": sl,
                "source_term": term,
                "target_language": tl,
                "target_term": target,
                "synonyms": synonyms,
                "domain": domain,
            }
            for sl, term, tl, target, synonyms, domain in rows
        ],
        author,
        ROLES,
    )
    versioning.transition(db, referential, version, "submit", author, ROLES)
    versioning.transition(db, referential, version, "validate", checker, ROLES)
    versioning.transition(db, referential, version, "publish", author, ROLES)
    return version


def test_bm25_publication_search_rollback_and_isolation_on_postgresql():
    from app.core.models import Tenant
    from app.rag.core import lexical
    from app.rag.models import RagLexicalIndex, RagTermPosting
    from app.rag.storage import versioning

    engine = create_engine(URL)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    _run(engine, Config(str(ROOT / "alembic.ini")), "upgrade", "head")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        tenant_a, tenant_b = Tenant(name="pg-a"), Tenant(name="pg-b")
        db.add_all([tenant_a, tenant_b])
        db.flush()
        referential = versioning.create_referential(
            db, tenant_a.id, {"kind": "linguistic", "name": "PG"}, "u-author", ROLES
        )
        versioning.set_referential_active(db, referential, True, "u-author", ROLES)
        v1 = _publish(db, referential, ENTRIES)
        db.commit()
        a, b = tenant_a.id, tenant_b.id

    with factory() as db:
        result = lexical.search(db, a, "monthly salary", "en", "fr")
        assert [r["source_term"] for r in result["results"]][:2] in (
            ["gross salary", "net salary"],
            ["net salary", "gross salary"],
        )
        assert result["documents"] == 3 and result["authority"] == "suggestion_non_injectable"
        assert [r["source_term"] for r in lexical.search(db, a, "راتب", "ar", "fr")["results"]] == [
            "الراتب الأساسي"
        ]
        assert [
            r["source_term"] for r in lexical.search(db, a, "kuendigung", "de", "fr")["results"]
        ] == ["Kündigung"]
        assert lexical.search(db, b, "monthly salary", "en", "fr")["results"] == []
        # Filtre de domaine : PAYROLL compatible HR ; LEGAL exclut tout.
        assert lexical.search(db, a, "salary", "en", "fr", domain="LEGAL")["results"] == []
        postings = db.query(RagTermPosting).filter_by(version_id=v1.id).count()
        assert postings > 0
        plan = db.execute(
            text(
                "EXPLAIN SELECT entry_id FROM rag_term_postings WHERE version_id = :v "
                "AND source_language = 'en' AND target_language = 'fr' AND token = 'salary'"
            ),
            {"v": v1.id},
        ).all()
        assert plan  # requête valide sur PostgreSQL (le choix d'index dépend du volume)

    with factory() as db:
        referential = db.get(type(referential), referential.id)
        changed = [
            row if row[1] != "notice period" else (*row[:3], "délai de préavis", None, "HR")
            for row in ENTRIES
        ]
        v2 = _publish(db, referential, changed)
        db.commit()
        assert [
            r["target_term"] for r in lexical.search(db, a, "notice", "en", "fr")["results"]
        ] == ["délai de préavis"]
        v1 = db.get(type(v1), v1.id)
        versioning.transition(db, referential, v1, "restore", "u-author", ROLES)
        db.commit()
        assert [
            r["target_term"] for r in lexical.search(db, a, "notice", "en", "fr")["results"]
        ] == ["préavis"]
        assert db.query(RagTermPosting).filter_by(version_id=v1.id).count() == postings
        assert {row.version_id for row in db.query(RagLexicalIndex)} == {v1.id, v2.id}
    engine.dispose()
