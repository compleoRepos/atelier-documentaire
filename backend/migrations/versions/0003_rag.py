"""DICE (RAG) : tables rag_* indépendantes. Aucune table métier existante n'est modifiée.

Le downgrade supprime uniquement les onze tables créées ici, dans l'ordre inverse
des dépendances.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_rag"
down_revision = "0002_industrial"
branch_labels = None
depends_on = None

RAG_TABLES = (
    "rag_referentials",
    "rag_referential_versions",
    "rag_term_entries",
    "rag_legal_texts",
    "rag_legal_passages",
    "rag_notion_equivalences",
    "rag_validation_events",
    "rag_document_contexts",
    "rag_tenant_settings",
    "rag_role_assignments",
    "rag_search_log",
)


def _tenant(nullable=True, primary_key=False):
    return sa.Column(
        "tenant_id",
        sa.String(36),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=nullable,
        primary_key=primary_key,
    )


def _tz(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade():
    op.create_table(
        "rag_referentials",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(40)),
        sa.Column("country", sa.String(2)),
        sa.Column("jurisdiction", sa.String(80)),
        sa.Column("languages", sa.JSON()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        _tz("created_at", False),
        _tz("updated_at", False),
    )
    op.create_index("ix_rag_referentials_tenant", "rag_referentials", ["tenant_id"])
    op.create_index(
        "uq_rag_referentials_tenant_name", "rag_referentials", ["tenant_id", "name"], unique=True
    )
    op.create_table(
        "rag_referential_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "referential_id",
            sa.String(36),
            sa.ForeignKey("rag_referentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _tenant(),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("content_sha256", sa.String(64)),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("submitted_by", sa.String(36)),
        sa.Column("validated_by", sa.String(36)),
        sa.Column("published_by", sa.String(36)),
        _tz("created_at", False),
        _tz("submitted_at"),
        _tz("validated_at"),
        _tz("published_at"),
        _tz("retired_at"),
        sa.Column("note", sa.Text()),
    )
    op.create_index(
        "uq_rag_versions_ref_number",
        "rag_referential_versions",
        ["referential_id", "number"],
        unique=True,
    )
    op.create_index("ix_rag_versions_tenant", "rag_referential_versions", ["tenant_id"])
    op.create_table(
        "rag_term_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("rag_referential_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referential_id",
            sa.String(36),
            sa.ForeignKey("rag_referentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _tenant(),
        sa.Column("source_language", sa.String(12), nullable=False),
        sa.Column("source_term", sa.String(500), nullable=False),
        sa.Column("normalized_source", sa.String(500), nullable=False),
        sa.Column("target_language", sa.String(12), nullable=False),
        sa.Column("target_term", sa.String(500), nullable=False),
        sa.Column("synonyms", sa.JSON()),
        sa.Column("regional_variants", sa.JSON()),
        sa.Column("definition", sa.Text()),
        sa.Column("usage_context", sa.Text()),
        sa.Column("register", sa.String(40)),
        sa.Column("domain", sa.String(40)),
        sa.Column("country", sa.String(2)),
        sa.Column("jurisdiction", sa.String(80)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provenance", sa.String(200)),
        sa.Column("validated_by", sa.String(36)),
        _tz("validated_at"),
        _tz("created_at", False),
    )
    op.create_index("ix_rag_terms_version", "rag_term_entries", ["version_id"])
    op.create_index(
        "ix_rag_terms_lookup",
        "rag_term_entries",
        ["tenant_id", "source_language", "normalized_source"],
    )
    op.create_table(
        "rag_legal_texts",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column(
            "referential_id",
            sa.String(36),
            sa.ForeignKey("rag_referentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("rag_referential_versions.id", ondelete="CASCADE"),
        ),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("jurisdiction", sa.String(80)),
        sa.Column("legal_domain", sa.String(80)),
        sa.Column("text_type", sa.String(60)),
        sa.Column("official_reference", sa.String(300), nullable=False),
        sa.Column("publication_date", sa.Date()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("end_of_validity_date", sa.Date()),
        sa.Column("text_version", sa.String(60)),
        sa.Column("official_source", sa.String(500)),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("language", sa.String(12)),
        _tz("created_at", False),
    )
    op.create_index(
        "ix_rag_legal_texts_tenant_country", "rag_legal_texts", ["tenant_id", "country"]
    )
    op.create_table(
        "rag_legal_passages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "legal_text_id",
            sa.String(36),
            sa.ForeignKey("rag_legal_texts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _tenant(),
        sa.Column("article_ref", sa.String(120)),
        sa.Column("language", sa.String(12)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False),
        _tz("created_at", False),
    )
    op.create_index("ix_rag_legal_passages_text", "rag_legal_passages", ["legal_text_id"])
    op.create_table(
        "rag_notion_equivalences",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column(
            "referential_id",
            sa.String(36),
            sa.ForeignKey("rag_referentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("rag_referential_versions.id", ondelete="CASCADE"),
        ),
        sa.Column("notion", sa.String(500), nullable=False),
        sa.Column("source_country", sa.String(2)),
        sa.Column("target_country", sa.String(2)),
        sa.Column("source_language", sa.String(12)),
        sa.Column("target_language", sa.String(12)),
        sa.Column("equivalence_type", sa.String(20), nullable=False),
        sa.Column("guidance", sa.Text()),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("validated_by", sa.String(36)),
        _tz("validated_at"),
        sa.Column("provenance", sa.String(200)),
        _tz("created_at", False),
    )
    op.create_index("ix_rag_notions_tenant", "rag_notion_equivalences", ["tenant_id"])
    op.create_table(
        "rag_validation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(36)),
        sa.Column("actor_role", sa.String(40)),
        sa.Column("comment", sa.String(500)),
        _tz("created_at", False),
    )
    op.create_index(
        "ix_rag_validation_object",
        "rag_validation_events",
        ["tenant_id", "object_type", "object_id"],
    )
    op.create_table(
        "rag_document_contexts",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(nullable=False),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_language", sa.String(12)),
        sa.Column("target_language", sa.String(12)),
        sa.Column("source_country", sa.String(2)),
        sa.Column("target_country", sa.String(2)),
        sa.Column("jurisdiction", sa.String(80)),
        sa.Column("document_date", sa.Date()),
        sa.Column("legal_reference_date", sa.Date()),
        sa.Column("origins", sa.JSON()),
        sa.Column("declared_by", sa.String(36)),
        _tz("declared_at", False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("validated_by", sa.String(36)),
        _tz("validated_at"),
    )
    op.create_index(
        "uq_rag_document_contexts_doc",
        "rag_document_contexts",
        ["tenant_id", "document_id"],
        unique=True,
    )
    op.create_table(
        "rag_tenant_settings",
        _tenant(nullable=False, primary_key=True),
        sa.Column("max_mode", sa.String(10), nullable=False),
        sa.Column("updated_by", sa.String(36)),
        _tz("updated_at", False),
    )
    op.create_table(
        "rag_role_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(nullable=False),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("granted_by", sa.String(36)),
        _tz("granted_at", False),
    )
    op.create_index(
        "uq_rag_roles_tenant_user_role",
        "rag_role_assignments",
        ["tenant_id", "user_id", "role"],
        unique=True,
    )
    op.create_table(
        "rag_search_log",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(nullable=False),
        sa.Column("document_id", sa.String(36)),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("query_sha256", sa.String(64), nullable=False),
        sa.Column("filters", sa.JSON()),
        sa.Column("result_ids", sa.JSON()),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("referential_versions", sa.JSON()),
        sa.Column("latency_ms", sa.Float()),
        sa.Column("outcome", sa.JSON()),
        _tz("created_at", False),
    )
    op.create_index(
        "ix_rag_search_log_tenant_created", "rag_search_log", ["tenant_id", "created_at"]
    )


def downgrade():
    for table in reversed(RAG_TABLES):
        op.drop_table(table)
