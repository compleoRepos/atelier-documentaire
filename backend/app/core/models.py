from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


def uid() -> str:
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    users: Mapped[list[User]] = relationship(back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(190), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    tenant: Mapped[Tenant] = relationship(back_populates="users")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    format: Mapped[str] = mapped_column(String(12), nullable=False)
    original_key: Mapped[str] = mapped_column(String(700), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="UPLOADED", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )
    language: Mapped[str | None] = mapped_column(String(20))
    document_type: Mapped[str | None] = mapped_column(String(100))
    domain: Mapped[str | None] = mapped_column(String(100))
    page_count: Mapped[int | None] = mapped_column(Integer)
    analysis_json: Mapped[dict | None] = mapped_column(JSON)
    translation_json: Mapped[dict | None] = mapped_column(JSON)
    quality_json: Mapped[dict | None] = mapped_column(JSON)
    issues_json: Mapped[list | None] = mapped_column(JSON)
    review_version: Mapped[int | None] = mapped_column(Integer)
    active_version_id: Mapped[str | None] = mapped_column(String(36))
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    analysis_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timings_json: Mapped[dict | None] = mapped_column(JSON)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), index=True)
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_key: Mapped[str | None] = mapped_column(String(700))
    final_key: Mapped[str | None] = mapped_column(String(700))
    analysis_key: Mapped[str | None] = mapped_column(String(700))
    translation_key: Mapped[str | None] = mapped_column(String(700))
    previews_prefix: Mapped[str | None] = mapped_column(String(700))
    translations: Mapped[dict | None] = mapped_column(JSON)
    quality: Mapped[dict | None] = mapped_column(JSON)
    issues: Mapped[list | None] = mapped_column(JSON)
    protected_entities: Mapped[list | None] = mapped_column(JSON)
    protected_regions: Mapped[list | None] = mapped_column(JSON)
    analysis_snapshot: Mapped[dict | None] = mapped_column(JSON)
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    provenance: Mapped[dict | None] = mapped_column(JSON)
    timings_json: Mapped[dict | None] = mapped_column(JSON)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    document: Mapped[Document] = relationship(back_populates="versions")
    __table_args__ = (Index("ix_version_doc_num", "document_id", "version", unique=True),)


class GlossaryEntry(Base):
    __tablename__ = "glossary"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    target: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class MemoryEntry(Base):
    __tablename__ = "memory"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    document_id: Mapped[str | None] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    details: Mapped[dict | None] = mapped_column(JSON)


class GoldenReference(Base):
    __tablename__ = "golden_references"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_key: Mapped[str] = mapped_column(String(700), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class RevokedSession(Base):
    __tablename__ = "revoked_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
