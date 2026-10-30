"""Tables du module RAG (préfixe ``rag_``), créées par la migration ``0003_rag``.

Isolation : chaque ligne porte ``tenant_id``. ``tenant_id`` NULL désigne la
bibliothèque commune, en lecture seule pour les tenants (écriture réservée à
l'outillage plateforme). Aucune table métier existante n'est modifiée.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core import models as _core_models  # noqa: F401  (cibles des clés étrangères)
from ..core.db import Base
from ..core.models import now_utc, uid

TENANT_FK = "tenants.id"


class RagReferential(Base):
    __tablename__ = "rag_referentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    scope: Mapped[str] = mapped_column(String(10), nullable=False)  # tenant | common
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # linguistic|business|regulatory
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(2))
    jurisdiction: Mapped[str | None] = mapped_column(String(80))
    languages: Mapped[list | None] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (
        Index("ix_rag_referentials_tenant", "tenant_id"),
        Index("uq_rag_referentials_tenant_name", "tenant_id", "name", unique=True),
    )


class RagReferentialVersion(Base):
    __tablename__ = "rag_referential_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    referential_id: Mapped[str] = mapped_column(
        ForeignKey("rag_referentials.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    # draft -> in_review -> validated -> published -> retired (jamais automatique)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36))
    submitted_by: Mapped[str | None] = mapped_column(String(36))
    validated_by: Mapped[str | None] = mapped_column(String(36))
    published_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        Index("uq_rag_versions_ref_number", "referential_id", "number", unique=True),
        Index("ix_rag_versions_tenant", "tenant_id"),
    )


class RagTermEntry(Base):
    __tablename__ = "rag_term_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("rag_referential_versions.id", ondelete="CASCADE"), nullable=False
    )
    referential_id: Mapped[str] = mapped_column(
        ForeignKey("rag_referentials.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    source_language: Mapped[str] = mapped_column(String(12), nullable=False)
    source_term: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_source: Mapped[str] = mapped_column(String(500), nullable=False)
    target_language: Mapped[str] = mapped_column(String(12), nullable=False)
    target_term: Mapped[str] = mapped_column(String(500), nullable=False)
    synonyms: Mapped[list | None] = mapped_column(JSON)
    regional_variants: Mapped[list | None] = mapped_column(JSON)
    definition: Mapped[str | None] = mapped_column(Text)
    usage_context: Mapped[str | None] = mapped_column(Text)
    register: Mapped[str | None] = mapped_column(String(40))
    domain: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(2))
    jurisdiction: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="candidate", nullable=False)
    provenance: Mapped[str | None] = mapped_column(String(200))
    validated_by: Mapped[str | None] = mapped_column(String(36))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (
        Index("ix_rag_terms_version", "version_id"),
        Index("ix_rag_terms_lookup", "tenant_id", "source_language", "normalized_source"),
    )


class RagLegalText(Base):
    """Texte réglementaire (préparé pour le LOT 3, aucune donnée au LOT 1)."""

    __tablename__ = "rag_legal_texts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    referential_id: Mapped[str] = mapped_column(
        ForeignKey("rag_referentials.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rag_referential_versions.id", ondelete="CASCADE"), nullable=True
    )
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(80))
    legal_domain: Mapped[str | None] = mapped_column(String(80))
    text_type: Mapped[str | None] = mapped_column(String(60))
    official_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    end_of_validity_date: Mapped[date | None] = mapped_column(Date)
    text_version: Mapped[str | None] = mapped_column(String(60))
    official_source: Mapped[str | None] = mapped_column(String(500))
    validation_status: Mapped[str] = mapped_column(String(20), default="candidate", nullable=False)
    language: Mapped[str | None] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (Index("ix_rag_legal_texts_tenant_country", "tenant_id", "country"),)


class RagLegalPassage(Base):
    __tablename__ = "rag_legal_passages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    legal_text_id: Mapped[str] = mapped_column(
        ForeignKey("rag_legal_texts.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    article_ref: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str | None] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (Index("ix_rag_legal_passages_text", "legal_text_id"),)


class RagNotionEquivalence(Base):
    """Fiche de notion : jamais créée ni validée automatiquement."""

    __tablename__ = "rag_notion_equivalences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    referential_id: Mapped[str] = mapped_column(
        ForeignKey("rag_referentials.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rag_referential_versions.id", ondelete="CASCADE"), nullable=True
    )
    notion: Mapped[str] = mapped_column(String(500), nullable=False)
    source_country: Mapped[str | None] = mapped_column(String(2))
    target_country: Mapped[str | None] = mapped_column(String(2))
    source_language: Mapped[str | None] = mapped_column(String(12))
    target_language: Mapped[str | None] = mapped_column(String(12))
    equivalence_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # exact|approximate|none
    guidance: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(20), default="candidate", nullable=False)
    validated_by: Mapped[str | None] = mapped_column(String(36))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (Index("ix_rag_notions_tenant", "tenant_id"),)


class RagValidationEvent(Base):
    __tablename__ = "rag_validation_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    actor_role: Mapped[str | None] = mapped_column(String(40))
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (Index("ix_rag_validation_object", "tenant_id", "object_type", "object_id"),)


class RagDocumentContext(Base):
    """Contexte déclaré d'un document (langues, pays, juridiction, dates)."""

    __tablename__ = "rag_document_contexts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    source_language: Mapped[str | None] = mapped_column(String(12))
    target_language: Mapped[str | None] = mapped_column(String(12))
    source_country: Mapped[str | None] = mapped_column(String(2))
    target_country: Mapped[str | None] = mapped_column(String(2))
    jurisdiction: Mapped[str | None] = mapped_column(String(80))
    document_date: Mapped[date | None] = mapped_column(Date)
    legal_reference_date: Mapped[date | None] = mapped_column(Date)
    origins: Mapped[dict | None] = mapped_column(JSON)
    declared_by: Mapped[str | None] = mapped_column(String(36))
    declared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    # declared -> validated (par un autre utilisateur habilité). Seul un contexte
    # validé peut alimenter country_context (mode ACTIVE).
    status: Mapped[str] = mapped_column(String(20), default="declared", nullable=False)
    validated_by: Mapped[str | None] = mapped_column(String(36))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("uq_rag_document_contexts_doc", "tenant_id", "document_id", unique=True),
    )


class RagTenantSettings(Base):
    __tablename__ = "rag_tenant_settings"
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), primary_key=True
    )
    max_mode: Mapped[str] = mapped_column(String(10), default="DISABLED", nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class RagRoleAssignment(Base):
    __tablename__ = "rag_role_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    granted_by: Mapped[str | None] = mapped_column(String(36))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (
        Index("uq_rag_roles_tenant_user_role", "tenant_id", "user_id", "role", unique=True),
    )


class RagSearchLog(Base):
    """Journal d'audit des recherches : empreinte de requête, jamais le texte."""

    __tablename__ = "rag_search_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str | None] = mapped_column(String(36))
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    query_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSON)
    result_ids: Mapped[list | None] = mapped_column(JSON)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    referential_versions: Mapped[list | None] = mapped_column(JSON)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    # Décisions d'injection (identifiants, motifs, jetons) ; jamais de texte.
    outcome: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (Index("ix_rag_search_log_tenant_created", "tenant_id", "created_at"),)


# --- LOT 2 (migration ``0004_rag_lot2``) : index lexical BM25 et imports. -----------------


class RagLexicalIndex(Base):
    """État de l'index lexical d'une version (idempotence, version du normaliseur)."""

    __tablename__ = "rag_lexical_indexes"
    version_id: Mapped[str] = mapped_column(
        ForeignKey("rag_referential_versions.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    normalizer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posting_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # {"en>fr": [nombre d'entrées, somme des longueurs]} : statistiques BM25 précalculées.
    pair_stats: Mapped[dict | None] = mapped_column(JSON)
    built_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class RagTermPosting(Base):
    """Posting BM25 : un jeton normalisé d'une entrée publiée (terme, synonymes, variantes)."""

    __tablename__ = "rag_term_postings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("rag_referential_versions.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[str] = mapped_column(
        ForeignKey("rag_term_entries.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=True
    )
    source_language: Mapped[str] = mapped_column(String(12), nullable=False)
    target_language: Mapped[str] = mapped_column(String(12), nullable=False)
    token: Mapped[str] = mapped_column(String(200), nullable=False)
    tf: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_len: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        Index(
            "ix_rag_postings_lookup", "version_id", "source_language", "target_language", "token"
        ),
        Index("ix_rag_postings_entry", "entry_id"),
    )


class RagImportBatch(Base):
    """Trace d'un import CSV/XLSX : empreinte du fichier, compteurs, codes par ligne, sans texte."""

    __tablename__ = "rag_import_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE"), nullable=False
    )
    referential_id: Mapped[str] = mapped_column(
        ForeignKey("rag_referentials.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rag_referential_versions.id", ondelete="SET NULL"), nullable=True
    )
    actor_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # dry_run|applied|rejected
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)  # csv | xlsx
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Numéros de ligne et codes uniquement ; jamais le contenu des cellules.
    report: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    __table_args__ = (Index("ix_rag_import_batches_tenant_created", "tenant_id", "created_at"),)


# Les onze tables du LOT 1 (0003_rag) restent listées à part : leur contrat est figé.
RAG_TABLES: tuple[str, ...] = (
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
RAG_LOT2_TABLES: tuple[str, ...] = (
    "rag_lexical_indexes",
    "rag_term_postings",
    "rag_import_batches",
)
RAG_ALL_TABLES: tuple[str, ...] = RAG_TABLES + RAG_LOT2_TABLES


def rag_table_objects():
    return [Base.metadata.tables[name] for name in RAG_ALL_TABLES]
