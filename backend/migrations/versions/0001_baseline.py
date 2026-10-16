"""Schéma initial figé, sans import du modèle applicatif futur."""

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, primary_key=False),
        sa.Column("action", sa.String(80), nullable=False, primary_key=False),
        sa.Column("document_id", sa.String(36), nullable=True, primary_key=False),
        sa.Column("user_id", sa.String(36), nullable=True, primary_key=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("details", sa.JSON(), nullable=True, primary_key=False),
    )
    op.create_index("ix_audit_events_document_id", "audit_events", ["document_id"], unique=False)
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"], unique=False)
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, primary_key=False),
        sa.Column("filename", sa.String(255), nullable=False, primary_key=False),
        sa.Column("media_type", sa.String(100), nullable=False, primary_key=False),
        sa.Column("format", sa.String(12), nullable=False, primary_key=False),
        sa.Column("original_key", sa.String(700), nullable=False, primary_key=False),
        sa.Column("status", sa.String(32), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("language", sa.String(20), nullable=True, primary_key=False),
        sa.Column("document_type", sa.String(100), nullable=True, primary_key=False),
        sa.Column("domain", sa.String(100), nullable=True, primary_key=False),
        sa.Column("page_count", sa.Integer(), nullable=True, primary_key=False),
        sa.Column("analysis_json", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("translation_json", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("quality_json", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("issues_json", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("review_version", sa.Integer(), nullable=True, primary_key=False),
        sa.Column("active_version_id", sa.String(36), nullable=True, primary_key=False),
    )
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"], unique=False)
    op.create_table(
        "glossary",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, primary_key=False),
        sa.Column("source", sa.String(500), nullable=False, primary_key=False),
        sa.Column("target", sa.String(500), nullable=False, primary_key=False),
        sa.Column("domain", sa.String(100), nullable=True, primary_key=False),
        sa.Column("version", sa.Integer(), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index("ix_glossary_tenant_id", "glossary", ["tenant_id"], unique=False)
    op.create_table(
        "golden_references",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, primary_key=False),
        sa.Column("document_id", sa.String(36), nullable=False, primary_key=False),
        sa.Column("version", sa.Integer(), nullable=False, primary_key=False),
        sa.Column("expected_key", sa.String(700), nullable=False, primary_key=False),
        sa.Column("sha256", sa.String(64), nullable=False, primary_key=False),
        sa.Column("approved", sa.Boolean(), nullable=False, primary_key=False),
        sa.Column("reviewer_id", sa.String(36), nullable=False, primary_key=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index(
        "ix_golden_references_tenant_id", "golden_references", ["tenant_id"], unique=False
    )
    op.create_table(
        "memory",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, primary_key=False),
        sa.Column("source", sa.Text(), nullable=False, primary_key=False),
        sa.Column("target", sa.Text(), nullable=False, primary_key=False),
        sa.Column("validated", sa.Boolean(), nullable=False, primary_key=False),
        sa.Column("version", sa.Integer(), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index("ix_memory_tenant_id", "memory", ["tenant_id"], unique=False)
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, primary_key=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, primary_key=False),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("tenant_id", sa.String(36), nullable=False, primary_key=False),
        sa.Column("version", sa.Integer(), nullable=False, primary_key=False),
        sa.Column("candidate_key", sa.String(700), nullable=True, primary_key=False),
        sa.Column("final_key", sa.String(700), nullable=True, primary_key=False),
        sa.Column("analysis_key", sa.String(700), nullable=True, primary_key=False),
        sa.Column("translation_key", sa.String(700), nullable=True, primary_key=False),
        sa.Column("previews_prefix", sa.String(700), nullable=True, primary_key=False),
        sa.Column("translations", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("quality", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("issues", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("protected_entities", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("protected_regions", sa.JSON(), nullable=True, primary_key=False),
        sa.Column("is_final", sa.Boolean(), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index(
        "ix_document_versions_document_id", "document_versions", ["document_id"], unique=False
    )
    op.create_index(
        "ix_document_versions_tenant_id", "document_versions", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_version_doc_num", "document_versions", ["document_id", "version"], unique=True
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("username", sa.String(190), nullable=False, primary_key=False),
        sa.Column("password_hash", sa.String(512), nullable=False, primary_key=False),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("role", sa.String(20), nullable=False, primary_key=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, primary_key=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade():
    op.drop_table("users")
    op.drop_table("document_versions")
    op.drop_table("tenants")
    op.drop_table("memory")
    op.drop_table("golden_references")
    op.drop_table("glossary")
    op.drop_table("documents")
    op.drop_table("audit_events")
