"""DICE (RAG) LOT 2 — migration Alembic 0004_rag_lot2 (SQLite ; PostgreSQL 16 en CI)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.core.db import Base
from app.rag import models as rag_models

from .test_rag_lot1_migration import _run, _schema

ROOT = Path(__file__).resolve().parents[2]


def _engines(tmp_path):
    yield "sqlite", create_engine(f"sqlite:///{tmp_path / 'rag2.db'}")
    url = os.environ.get("RAG_TEST_POSTGRES_URL")
    if url:
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        yield "postgresql", engine


@pytest.mark.parametrize("backend", ["sqlite", "postgresql"])
def test_0004_adds_only_lot2_tables_and_downgrades_to_exact_0003(tmp_path, backend):
    engines = dict(_engines(tmp_path))
    if backend not in engines:
        pytest.skip("PostgreSQL : définir RAG_TEST_POSTGRES_URL (exécuté en CI et en local)")
    engine = engines[backend]
    config = Config(str(ROOT / "alembic.ini"))
    _run(engine, config, "upgrade", "0003_rag")
    lot1 = sorted(t for t in inspect(engine).get_table_names() if t != "alembic_version")
    before = _schema(engine, lot1)

    _run(engine, config, "upgrade", "head")
    tables = set(inspect(engine).get_table_names())
    assert tables - set(lot1) - {"alembic_version"} == set(rag_models.RAG_LOT2_TABLES)
    assert _schema(engine, lot1) == before  # LOT 1 et tables métier strictement identiques
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0004_rag_lot2"
        )
    inspector = inspect(engine)
    for table in rag_models.RAG_LOT2_TABLES:
        assert "tenant_id" in {c["name"] for c in inspector.get_columns(table)}, table
    lookup = {i["name"]: i["column_names"] for i in inspector.get_indexes("rag_term_postings")}
    assert lookup["ix_rag_postings_lookup"] == [
        "version_id",
        "source_language",
        "target_language",
        "token",
    ]

    _run(engine, config, "downgrade", "0003_rag")
    assert sorted(t for t in inspect(engine).get_table_names() if t != "alembic_version") == lot1
    assert _schema(engine, lot1) == before
    _run(engine, config, "upgrade", "head")
    assert set(rag_models.RAG_ALL_TABLES) <= set(inspect(engine).get_table_names())
    for item in engines.values():
        item.dispose()
