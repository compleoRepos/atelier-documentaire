"""Snapshots immuables, mesures et révocations des sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0002_industrial"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("source_sha256", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column("analysis_revision", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("timings_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("uploaded_by", sa.String(36), nullable=True))
        batch.create_index("ix_documents_uploaded_by", ["uploaded_by"])
    with op.batch_alter_table("document_versions") as batch:
        batch.add_column(sa.Column("analysis_snapshot", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("source_sha256", sa.String(64), nullable=True))
        batch.add_column(sa.Column("provenance", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("timings_json", sa.JSON(), nullable=True))
    op.create_table(
        "revoked_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_sessions_user_id", "revoked_sessions", ["user_id"])
    op.create_index("ix_revoked_sessions_expires_at", "revoked_sessions", ["expires_at"])


def downgrade():
    op.drop_table("revoked_sessions")
    with op.batch_alter_table("document_versions") as batch:
        for name in ["timings_json", "provenance", "source_sha256", "analysis_snapshot"]:
            batch.drop_column(name)
    with op.batch_alter_table("documents") as batch:
        batch.drop_index("ix_documents_uploaded_by")
        for name in ["uploaded_by", "timings_json", "analysis_revision", "source_sha256"]:
            batch.drop_column(name)
