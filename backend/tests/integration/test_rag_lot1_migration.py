"""DICE (RAG) LOT 1 — migration Alembic 0003_rag (SQLite ; PostgreSQL en CI)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.core.db import Base
from app.rag import models as rag_models

ROOT = Path(__file__).resolve().parents[2]


def _schema(engine, tables):
    inspector = inspect(engine)
    result = {}
    for table in tables:
        result[table] = {
            "columns": [
                (c["name"], str(c["type"]), c["nullable"]) for c in inspector.get_columns(table)
            ],
            "pk": inspector.get_pk_constraint(table)["constrained_columns"],
            "fks": sorted(
                (tuple(fk["constrained_columns"]), fk["referred_table"])
                for fk in inspector.get_foreign_keys(table)
            ),
            "indexes": sorted(
                (i["name"], tuple(i["column_names"]), bool(i["unique"]))
                for i in inspector.get_indexes(table)
            ),
        }
    return result


def _run(engine, config, action, revision):
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        getattr(command, action)(config, revision)


def test_0003_rag_creates_only_rag_tables_and_downgrades_cleanly(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rag.db'}")
    config = Config(str(ROOT / "alembic.ini"))
    _run(engine, config, "upgrade", "0002_industrial")
    business = sorted(inspect(engine).get_table_names())
    assert not any(name.startswith("rag_") for name in business)
    before = _schema(engine, [t for t in business if t != "alembic_version"])

    # Contrat LOT 1 vérifié sur sa propre révision (la tête porte aussi 0004_rag_lot2).
    _run(engine, config, "upgrade", "0003_rag")
    tables = set(inspect(engine).get_table_names())
    assert tables - set(business) == set(rag_models.RAG_TABLES)
    assert len(rag_models.RAG_TABLES) == 11
    # Les tables métier existantes sont strictement identiques.
    assert _schema(engine, list(before)) == before
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)

    # Seules les tables LOT 2, absentes à cette révision, peuvent différer.
    def lot2(item):
        table = item[1] if item[0] == "add_table" else getattr(item[1], "table", None)
        return (
            item[0] in {"add_table", "add_index"}
            and table is not None
            and (table.name in rag_models.RAG_LOT2_TABLES)
        )

    others = [d for d in diff if not lot2(d)]
    assert others == []
    added = sorted(d[1].name for d in diff if d[0] == "add_table")
    assert added == sorted(rag_models.RAG_LOT2_TABLES)
    # Toutes les tables RAG portent tenant_id (isolation).
    inspector = inspect(engine)
    for table in rag_models.RAG_TABLES:
        assert "tenant_id" in {c["name"] for c in inspector.get_columns(table)}, table

    _run(engine, config, "downgrade", "0002_industrial")
    assert sorted(inspect(engine).get_table_names()) == business
    assert _schema(engine, list(before)) == before

    _run(engine, config, "upgrade", "head")
    assert set(rag_models.RAG_ALL_TABLES) <= set(inspect(engine).get_table_names())
    engine.dispose()
