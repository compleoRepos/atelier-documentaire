"""DICE (RAG) LOT 2 : index lexical BM25 et traçabilité des imports.

Trois tables nouvelles, préfixe ``rag_`` ; ni les tables métier ni les onze
tables de ``0003_rag`` ne sont modifiées. Le downgrade supprime uniquement ces
trois tables (données dérivées et traces d'import) et ramène exactement au
schéma ``0003_rag``.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_rag_lot2"
down_revision = "0003_rag"
branch_labels = None
depends_on = None

RAG_LOT2_TABLES = (
    "rag_lexical_indexes",
    "rag_term_postings",
    "rag_import_batches",
)


def _tenant(nullable=True):
    return sa.Column(
        "tenant_id",
        sa.String(36),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=nullable,
    )


def _version_fk(name, nullable=False, primary_key=False, ondelete="CASCADE"):
    return sa.Column(
        name,
        sa.String(36),
        sa.ForeignKey("rag_referential_versions.id", ondelete=ondelete),
        nullable=nullable,
        primary_key=primary_key,
    )


def upgrade():
    op.create_table(
        "rag_lexical_indexes",
        _version_fk("version_id", primary_key=True),
        _tenant(),
        sa.Column("normalizer_version", sa.String(40), nullable=False),
        sa.Column("content_sha256", sa.String(64)),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("posting_count", sa.Integer(), nullable=False),
        sa.Column("pair_stats", sa.JSON()),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rag_term_postings",
        sa.Column("id", sa.String(36), primary_key=True),
        _version_fk("version_id"),
        sa.Column(
            "entry_id",
            sa.String(36),
            sa.ForeignKey("rag_term_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _tenant(),
        sa.Column("source_language", sa.String(12), nullable=False),
        sa.Column("target_language", sa.String(12), nullable=False),
        sa.Column("token", sa.String(200), nullable=False),
        sa.Column("tf", sa.Integer(), nullable=False),
        sa.Column("doc_len", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_rag_postings_lookup",
        "rag_term_postings",
        ["version_id", "source_language", "target_language", "token"],
    )
    op.create_index("ix_rag_postings_entry", "rag_term_postings", ["entry_id"])
    op.create_table(
        "rag_import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(nullable=False),
        sa.Column(
            "referential_id",
            sa.String(36),
            sa.ForeignKey("rag_referentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _version_fk("version_id", nullable=True, ondelete="SET NULL"),
        sa.Column("actor_id", sa.String(36)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("file_format", sa.String(10), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("report", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_rag_import_batches_tenant_created", "rag_import_batches", ["tenant_id", "created_at"]
    )


def downgrade():
    for table in reversed(RAG_LOT2_TABLES):
        op.drop_table(table)
