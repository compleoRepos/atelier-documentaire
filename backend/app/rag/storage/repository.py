"""Accès aux tables rag_* ; chaque requête est filtrée par tenant.

Règle d'isolation : un tenant lit ses propres lignes et la bibliothèque commune
(``tenant_id`` NULL) ; il n'écrit que ses propres lignes. Aucune fonction de ce
module n'accepte une lecture sans ``tenant_id``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...core.models import Document, User, now_utc
from ..config import mode_rank, normalize_mode
from ..models import (
    RagDocumentContext,
    RagNotionEquivalence,
    RagReferential,
    RagReferentialVersion,
    RagRoleAssignment,
    RagSearchLog,
    RagTenantSettings,
    RagTermEntry,
)

RAG_ROLES = ("rag_admin", "terminology_manager", "legal_manager", "reader")
REFERENTIAL_KINDS = ("linguistic", "business", "regulatory")
# Les référentiels réglementaires (LOT 3) ne sont jamais lus par la recherche
# terminologique des LOTS 1 et 2.
TERMINOLOGY_KINDS = ("linguistic", "business")


class RagAccessError(PermissionError):
    """Refus d'accès ; ``code`` est stable et sans donnée sensible."""

    def __init__(self, code: str, status: int = 403) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def _visible(column, tenant_id: str):
    return or_(column == tenant_id, column.is_(None))


# ---------------------------------------------------------------- paramètres
def tenant_max_mode(db: Session, tenant_id: str) -> str:
    row = db.get(RagTenantSettings, tenant_id)
    return normalize_mode(row.max_mode) if row else "DISABLED"


def set_tenant_max_mode(
    db: Session, tenant_id: str, mode: str, actor_id: str | None, global_mode: str
) -> RagTenantSettings:
    mode = normalize_mode(mode)
    if mode_rank(mode) > mode_rank(global_mode):
        raise RagAccessError("RAG_MODE_ABOVE_GLOBAL", 409)
    row = db.get(RagTenantSettings, tenant_id)
    if row is None:
        row = RagTenantSettings(tenant_id=tenant_id)
        db.add(row)
    row.max_mode = mode
    row.updated_by = actor_id
    row.updated_at = now_utc()
    return row


# --------------------------------------------------------------------- rôles
def user_roles(db: Session, tenant_id: str, user_id: str) -> set[str]:
    rows = db.scalars(
        select(RagRoleAssignment.role).where(
            RagRoleAssignment.tenant_id == tenant_id, RagRoleAssignment.user_id == user_id
        )
    )
    return set(rows)


def list_roles(db: Session, tenant_id: str) -> list[RagRoleAssignment]:
    return list(
        db.scalars(
            select(RagRoleAssignment)
            .where(RagRoleAssignment.tenant_id == tenant_id)
            .order_by(RagRoleAssignment.granted_at, RagRoleAssignment.id)
        )
    )


def tenant_user(db: Session, tenant_id: str, user_id: str) -> User | None:
    user = db.get(User, user_id)
    return user if user is not None and user.tenant_id == tenant_id else None


def grant_role(
    db: Session, tenant_id: str, user_id: str, role: str, actor_id: str | None
) -> RagRoleAssignment:
    if role not in RAG_ROLES:
        raise RagAccessError("RAG_ROLE_UNKNOWN", 422)
    if tenant_user(db, tenant_id, user_id) is None:
        raise RagAccessError("RAG_USER_NOT_FOUND", 404)
    existing = db.scalar(
        select(RagRoleAssignment).where(
            RagRoleAssignment.tenant_id == tenant_id,
            RagRoleAssignment.user_id == user_id,
            RagRoleAssignment.role == role,
        )
    )
    if existing is not None:
        return existing
    row = RagRoleAssignment(tenant_id=tenant_id, user_id=user_id, role=role, granted_by=actor_id)
    db.add(row)
    return row


def revoke_role(db: Session, tenant_id: str, user_id: str, role: str) -> bool:
    row = db.scalar(
        select(RagRoleAssignment).where(
            RagRoleAssignment.tenant_id == tenant_id,
            RagRoleAssignment.user_id == user_id,
            RagRoleAssignment.role == role,
        )
    )
    if row is None:
        return False
    db.delete(row)
    return True


# --------------------------------------------------------------- référentiels
def list_referentials(db: Session, tenant_id: str) -> list[RagReferential]:
    return list(
        db.scalars(
            select(RagReferential)
            .where(_visible(RagReferential.tenant_id, tenant_id))
            .order_by(RagReferential.name, RagReferential.id)
        )
    )


def visible_referential(db: Session, tenant_id: str, referential_id: str) -> RagReferential:
    row = db.get(RagReferential, referential_id)
    if row is None or row.tenant_id not in (tenant_id, None):
        raise RagAccessError("RAG_REFERENTIAL_NOT_FOUND", 404)
    return row


def writable_referential(db: Session, tenant_id: str, referential_id: str) -> RagReferential:
    row = visible_referential(db, tenant_id, referential_id)
    if row.tenant_id is None:
        raise RagAccessError("RAG_COMMON_REFERENTIAL_READ_ONLY", 403)
    return row


def visible_version(db: Session, tenant_id: str, version_id: str) -> RagReferentialVersion:
    row = db.get(RagReferentialVersion, version_id)
    if row is None or row.tenant_id not in (tenant_id, None):
        raise RagAccessError("RAG_VERSION_NOT_FOUND", 404)
    return row


def writable_version(db: Session, tenant_id: str, version_id: str) -> RagReferentialVersion:
    row = visible_version(db, tenant_id, version_id)
    if row.tenant_id is None:
        raise RagAccessError("RAG_COMMON_REFERENTIAL_READ_ONLY", 403)
    return row


def versions_of(db: Session, referential: RagReferential) -> list[RagReferentialVersion]:
    return list(
        db.scalars(
            select(RagReferentialVersion)
            .where(RagReferentialVersion.referential_id == referential.id)
            .order_by(RagReferentialVersion.number)
        )
    )


def version_entries(db: Session, version: RagReferentialVersion) -> list[RagTermEntry]:
    return list(
        db.scalars(
            select(RagTermEntry)
            .where(
                RagTermEntry.version_id == version.id,
                # défense en profondeur : une entrée appartient au tenant de sa version
                (RagTermEntry.tenant_id == version.tenant_id)
                if version.tenant_id is not None
                else RagTermEntry.tenant_id.is_(None),
            )
            .order_by(RagTermEntry.normalized_source, RagTermEntry.id)
        )
    )


def published_scope(db: Session, tenant_id: str) -> list[dict]:
    """Versions publiées lisibles par le tenant (référentiels actifs, terminologie)."""
    rows = db.execute(
        select(
            RagReferentialVersion.id,
            RagReferentialVersion.content_sha256,
            RagReferentialVersion.number,
            RagReferential.id,
            RagReferential.tenant_id,
            RagReferential.kind,
        )
        .join(RagReferential, RagReferential.id == RagReferentialVersion.referential_id)
        .where(
            RagReferentialVersion.status == "published",
            RagReferential.active.is_(True),
            RagReferential.kind.in_(TERMINOLOGY_KINDS),
            _visible(RagReferential.tenant_id, tenant_id),
        )
        .order_by(RagReferentialVersion.id)
    ).all()
    scope = []
    for version_id, sha, number, referential_id, owner, kind in rows:
        scope.append(
            {
                "version_id": version_id,
                "content_sha256": sha,
                "number": number,
                "referential_id": referential_id,
                "scope": "common" if owner is None else "tenant",
                "tenant_id": owner,
                "kind": kind,
            }
        )
    return scope


def published_entries(
    db: Session,
    tenant_id: str,
    scope: list[dict],
    source_languages: Iterable[str],
    target_language: str,
) -> list[RagTermEntry]:
    owners = {item["version_id"]: item["tenant_id"] for item in scope}
    languages = sorted({code for code in source_languages if code})
    if not owners or not languages:
        return []
    rows = db.scalars(
        select(RagTermEntry)
        .where(
            RagTermEntry.version_id.in_(sorted(owners)),
            RagTermEntry.status == "validated",
            RagTermEntry.target_language == target_language,
            RagTermEntry.source_language.in_(languages),
            _visible(RagTermEntry.tenant_id, tenant_id),
        )
        .order_by(RagTermEntry.id)
    )
    # Une entrée n'est retenue que si elle appartient au même tenant que sa version.
    return [row for row in rows if row.tenant_id == owners.get(row.version_id)]


def published_notions(
    db: Session, tenant_id: str, scope: list[dict], target_language: str
) -> list[RagNotionEquivalence]:
    owners = {item["version_id"]: item["tenant_id"] for item in scope}
    if not owners:
        return []
    rows = db.scalars(
        select(RagNotionEquivalence)
        .where(
            RagNotionEquivalence.version_id.in_(sorted(owners)),
            RagNotionEquivalence.validation_status == "validated",
            or_(
                RagNotionEquivalence.target_language == target_language,
                RagNotionEquivalence.target_language.is_(None),
            ),
            _visible(RagNotionEquivalence.tenant_id, tenant_id),
        )
        .order_by(RagNotionEquivalence.id)
    )
    return [row for row in rows if row.tenant_id == owners.get(row.version_id)]


# ------------------------------------------------------- documents et contexte
def tenant_document(db: Session, tenant_id: str, document_id: str) -> Document:
    doc = db.get(Document, document_id)
    if doc is None or doc.tenant_id != tenant_id:
        raise RagAccessError("RAG_DOCUMENT_NOT_FOUND", 404)
    return doc


def document_context(db: Session, tenant_id: str, document_id: str) -> RagDocumentContext | None:
    return db.scalar(
        select(RagDocumentContext).where(
            RagDocumentContext.tenant_id == tenant_id,
            RagDocumentContext.document_id == document_id,
        )
    )


CONTEXT_FIELDS = (
    "source_language",
    "target_language",
    "source_country",
    "target_country",
    "jurisdiction",
    "document_date",
    "legal_reference_date",
)


def declare_document_context(
    db: Session, tenant_id: str, document_id: str, values: dict, actor_id: str | None
) -> RagDocumentContext:
    """Déclaration humaine ; toute modification remet le statut à « declared »."""
    tenant_document(db, tenant_id, document_id)
    row = document_context(db, tenant_id, document_id)
    if row is None:
        row = RagDocumentContext(tenant_id=tenant_id, document_id=document_id)
        db.add(row)
    for name in CONTEXT_FIELDS:
        value = values.get(name)
        if isinstance(value, str) and name.endswith("_date"):
            value = date.fromisoformat(value)
        setattr(row, name, value)
    row.origins = {name: "declared" for name in CONTEXT_FIELDS if values.get(name) is not None}
    row.declared_by = actor_id
    row.declared_at = now_utc()
    row.status = "declared"
    row.validated_by = None
    row.validated_at = None
    return row


def validate_document_context(
    db: Session, tenant_id: str, document_id: str, actor_id: str
) -> RagDocumentContext:
    row = document_context(db, tenant_id, document_id)
    if row is None:
        raise RagAccessError("RAG_CONTEXT_NOT_FOUND", 404)
    if row.declared_by == actor_id:
        raise RagAccessError("RAG_FOUR_EYES_REQUIRED", 403)
    row.status = "validated"
    row.validated_by = actor_id
    row.validated_at = now_utc()
    return row


# ------------------------------------------------------------------- journal
def add_search_log(db: Session, **fields) -> RagSearchLog:
    row = RagSearchLog(**fields)
    db.add(row)
    return row


def search_logs(
    db: Session, tenant_id: str, document_id: str | None = None, limit: int = 50
) -> list[RagSearchLog]:
    query = select(RagSearchLog).where(RagSearchLog.tenant_id == tenant_id)
    if document_id is not None:
        query = query.where(RagSearchLog.document_id == document_id)
    query = query.order_by(RagSearchLog.created_at.desc(), RagSearchLog.id.desc()).limit(limit)
    return list(db.scalars(query))


def entries_by_ids(db: Session, tenant_id: str, ids: Iterable[str]) -> dict[str, RagTermEntry]:
    wanted = sorted({str(x) for x in ids if x})
    if not wanted:
        return {}
    rows = db.scalars(
        select(RagTermEntry).where(
            RagTermEntry.id.in_(wanted), _visible(RagTermEntry.tenant_id, tenant_id)
        )
    )
    return {row.id: row for row in rows}
