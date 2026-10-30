"""Cycle de vie des versions de référentiel ; aucune transition automatique.

    draft --submit--> in_review --validate--> validated --publish--> published
      ^                   |                                            |
      +------reject-------+                         retire  <----------+
                                     retired --restore--> published (retour arrière)

Règles :
* chaque transition est une action humaine explicite, journalisée dans
  ``rag_validation_events`` ;
* principe des quatre yeux : le valideur n'est ni l'auteur ni le soumetteur ;
* les entrées ne sont modifiables qu'en ``draft`` ; l'empreinte du contenu est
  figée à la soumission et revérifiée à la publication et à la restauration ;
* un référentiel réglementaire n'est soumis, validé, publié ou restauré que par
  le responsable juridique ;
* la bibliothèque commune n'est jamais modifiable par un tenant (contrôlé par
  ``repository.writable_*``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.models import now_utc
from ..models import RagReferential, RagReferentialVersion, RagTermEntry, RagValidationEvent
from ..terminology.normalizer import normalize_language, normalize_term
from .repository import REFERENTIAL_KINDS, RagAccessError, version_entries, versions_of

_TERMINOLOGY_ROLES = frozenset({"rag_admin", "terminology_manager"})
_LEGAL_ROLES = frozenset({"legal_manager"})
TRANSITIONS: dict[str, tuple[str, str]] = {
    "submit": ("draft", "in_review"),
    "reject": ("in_review", "draft"),
    "validate": ("in_review", "validated"),
    "publish": ("validated", "published"),
    "retire": ("published", "retired"),
    "restore": ("retired", "published"),
}
ENTRY_FIELDS = (
    "source_language",
    "source_term",
    "target_language",
    "target_term",
    "synonyms",
    "regional_variants",
    "definition",
    "usage_context",
    "register",
    "domain",
    "country",
    "jurisdiction",
    "provenance",
)
_MAX_TERM = 500


def allowed_roles(kind: str, action: str) -> frozenset[str]:
    if action not in TRANSITIONS and action not in {"edit", "create"}:
        raise RagAccessError("RAG_ACTION_UNKNOWN", 422)
    return _LEGAL_ROLES if kind == "regulatory" else _TERMINOLOGY_ROLES


def _event(
    db: Session,
    referential: RagReferential,
    version: RagReferentialVersion,
    action: str,
    actor_id: str | None,
    roles: Iterable[str],
    comment: str | None,
) -> None:
    db.add(
        RagValidationEvent(
            tenant_id=referential.tenant_id,
            object_type="referential_version",
            object_id=version.id,
            action=action,
            actor_id=actor_id,
            actor_role=",".join(sorted(roles)) or None,
            comment=(comment or "")[:500] or None,
        )
    )


def content_sha256(entries: Iterable[RagTermEntry]) -> str:
    """Empreinte canonique du contenu d'une version (ordre indifférent)."""
    canonical = sorted(
        json.dumps({name: getattr(entry, name) for name in ENTRY_FIELDS}, sort_keys=True)
        for entry in entries
    )
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def _clean_text(value: object, *, required: bool, limit: int = _MAX_TERM) -> str | None:
    text = " ".join(str(value or "").split())
    if not text:
        if required:
            raise RagAccessError("RAG_ENTRY_INVALID", 422)
        return None
    if len(text) > limit:
        raise RagAccessError("RAG_ENTRY_TOO_LONG", 422)
    return text


def _clean_list(value: object) -> list[str] | None:
    if value in (None, "", []):
        return None
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise RagAccessError("RAG_ENTRY_INVALID", 422)
    items = [_clean_text(item, required=True) for item in value]
    return [item for item in items if item] or None


def _clean_country(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if len(text) != 2 or not text.isalpha():
        raise RagAccessError("RAG_ENTRY_COUNTRY_INVALID", 422)
    return text


def create_referential(
    db: Session,
    tenant_id: str,
    values: Mapping,
    actor_id: str | None,
    roles: set[str],
) -> RagReferential:
    """Référentiel propre au tenant, inactif tant qu'un administrateur ne l'active pas.

    La bibliothèque commune (``tenant_id`` NULL) n'est jamais créée par l'API.
    """
    kind = str(values.get("kind") or "")
    if kind not in REFERENTIAL_KINDS:
        raise RagAccessError("RAG_REFERENTIAL_KIND_INVALID", 422)
    needed = allowed_roles(kind, "create")
    if not roles & needed:
        raise RagAccessError("RAG_ROLE_REQUIRED")
    name = _clean_text(values.get("name"), required=True, limit=200)
    exists = db.scalar(
        select(RagReferential.id).where(
            RagReferential.tenant_id == tenant_id, RagReferential.name == name
        )
    )
    if exists is not None:
        raise RagAccessError("RAG_REFERENTIAL_EXISTS", 409)
    languages = [normalize_language(x) for x in values.get("languages") or []]
    if any(not code for code in languages):
        raise RagAccessError("RAG_ENTRY_LANGUAGE_INVALID", 422)
    row = RagReferential(
        tenant_id=tenant_id,
        scope="tenant",
        kind=kind,
        name=name,
        domain=_clean_text(values.get("domain"), required=False, limit=40),
        country=_clean_country(values.get("country")),
        jurisdiction=_clean_text(values.get("jurisdiction"), required=False, limit=80),
        languages=sorted(set(languages)) or None,
        active=False,
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    _referential_event(db, row, "create_referential", actor_id, roles & needed)
    return row


def set_referential_active(
    db: Session, referential: RagReferential, active: bool, actor_id: str | None, roles: set[str]
) -> RagReferential:
    """Seul un administrateur RAG décide qu'un référentiel est lu par la recherche."""
    if "rag_admin" not in roles:
        raise RagAccessError("RAG_ROLE_REQUIRED")
    referential.active = bool(active)
    referential.updated_at = now_utc()
    _referential_event(
        db, referential, "activate" if active else "deactivate", actor_id, {"rag_admin"}
    )
    return referential


def _referential_event(
    db: Session,
    referential: RagReferential,
    action: str,
    actor_id: str | None,
    roles: Iterable[str],
) -> None:
    db.add(
        RagValidationEvent(
            tenant_id=referential.tenant_id,
            object_type="referential",
            object_id=referential.id,
            action=action,
            actor_id=actor_id,
            actor_role=",".join(sorted(roles)) or None,
        )
    )


def create_draft(
    db: Session,
    referential: RagReferential,
    actor_id: str | None,
    roles: set[str],
    copy_from: RagReferentialVersion | None = None,
) -> RagReferentialVersion:
    needed = allowed_roles(referential.kind, "create")
    if not roles & needed:
        raise RagAccessError("RAG_ROLE_REQUIRED")
    number = (
        db.scalar(
            select(func.max(RagReferentialVersion.number)).where(
                RagReferentialVersion.referential_id == referential.id
            )
        )
        or 0
    ) + 1
    version = RagReferentialVersion(
        referential_id=referential.id,
        tenant_id=referential.tenant_id,
        number=number,
        status="draft",
        created_by=actor_id,
    )
    db.add(version)
    db.flush()
    if copy_from is not None:
        if copy_from.referential_id != referential.id:
            raise RagAccessError("RAG_VERSION_NOT_FOUND", 404)
        for entry in version_entries(db, copy_from):
            db.add(
                RagTermEntry(
                    version_id=version.id,
                    referential_id=referential.id,
                    tenant_id=referential.tenant_id,
                    normalized_source=entry.normalized_source,
                    status="candidate",
                    **{name: getattr(entry, name) for name in ENTRY_FIELDS},
                )
            )
        version.entry_count = len(version_entries(db, copy_from))
    _event(db, referential, version, "create", actor_id, roles & needed, None)
    return version


def add_entries(
    db: Session,
    referential: RagReferential,
    version: RagReferentialVersion,
    entries: Iterable[Mapping],
    actor_id: str | None,
    roles: set[str],
) -> list[RagTermEntry]:
    needed = allowed_roles(referential.kind, "edit")
    if not roles & needed:
        raise RagAccessError("RAG_ROLE_REQUIRED")
    if version.status != "draft":
        raise RagAccessError("RAG_VERSION_NOT_EDITABLE", 409)
    created = []
    for raw in entries:
        source_language = normalize_language(raw.get("source_language"))
        target_language = normalize_language(raw.get("target_language"))
        if not source_language or not target_language:
            raise RagAccessError("RAG_ENTRY_LANGUAGE_INVALID", 422)
        source_term = _clean_text(raw.get("source_term"), required=True)
        normalized = normalize_term(source_term)
        if not normalized:
            raise RagAccessError("RAG_ENTRY_INVALID", 422)
        entry = RagTermEntry(
            version_id=version.id,
            referential_id=referential.id,
            tenant_id=referential.tenant_id,
            source_language=source_language,
            source_term=source_term,
            normalized_source=normalized,
            target_language=target_language,
            target_term=_clean_text(raw.get("target_term"), required=True),
            synonyms=_clean_list(raw.get("synonyms")),
            regional_variants=_clean_list(raw.get("regional_variants")),
            definition=_clean_text(raw.get("definition"), required=False, limit=4000),
            usage_context=_clean_text(raw.get("usage_context"), required=False, limit=4000),
            register=_clean_text(raw.get("register"), required=False, limit=40),
            domain=_clean_text(raw.get("domain"), required=False, limit=40),
            country=_clean_country(raw.get("country")),
            jurisdiction=_clean_text(raw.get("jurisdiction"), required=False, limit=80),
            provenance=_clean_text(raw.get("provenance"), required=False, limit=200),
            status="candidate",
        )
        db.add(entry)
        created.append(entry)
    db.flush()
    version.entry_count = len(version_entries(db, version))
    _event(db, referential, version, "edit", actor_id, roles & needed, f"{len(created)} entrées")
    return created


def transition(
    db: Session,
    referential: RagReferential,
    version: RagReferentialVersion,
    action: str,
    actor_id: str | None,
    roles: set[str],
    comment: str | None = None,
) -> RagReferentialVersion:
    if action not in TRANSITIONS:
        raise RagAccessError("RAG_ACTION_UNKNOWN", 422)
    needed = allowed_roles(referential.kind, action)
    if not roles & needed:
        raise RagAccessError("RAG_ROLE_REQUIRED")
    source, target = TRANSITIONS[action]
    if version.status != source:
        raise RagAccessError("RAG_TRANSITION_INVALID", 409)
    entries = version_entries(db, version)
    now = now_utc()
    if action == "submit":
        if not entries:
            raise RagAccessError("RAG_VERSION_EMPTY", 409)
        version.content_sha256 = content_sha256(entries)
        version.entry_count = len(entries)
        version.submitted_by = actor_id
        version.submitted_at = now
    elif action == "reject":
        version.content_sha256 = None
        version.submitted_by = None
        version.submitted_at = None
    elif action == "validate":
        if actor_id is None or actor_id in {version.created_by, version.submitted_by}:
            raise RagAccessError("RAG_FOUR_EYES_REQUIRED", 403)
        if content_sha256(entries) != version.content_sha256:
            raise RagAccessError("RAG_CONTENT_CHANGED", 409)
        for entry in entries:
            if entry.status == "candidate":
                entry.status = "validated"
                entry.validated_by = actor_id
                entry.validated_at = now
        version.validated_by = actor_id
        version.validated_at = now
    elif action in {"publish", "restore"}:
        if content_sha256(entries) != version.content_sha256:
            raise RagAccessError("RAG_CONTENT_CHANGED", 409)
        if action == "restore" and version.published_at is None:
            raise RagAccessError("RAG_TRANSITION_INVALID", 409)
        for other in versions_of(db, referential):
            if other.id != version.id and other.status == "published":
                other.status = "retired"
                other.retired_at = now
                _event(db, referential, other, "retire", actor_id, roles & needed, action)
        version.published_by = actor_id
        version.published_at = now
        version.retired_at = None
        # LOT 2 : index lexical BM25 de la version publiée, dans la même transaction
        # (idempotent : une restauration réutilise l'index si le contenu est inchangé).
        from ..core import lexical

        lexical.index_version(db, version, entries)
    elif action == "retire":
        version.retired_at = now
    version.status = target
    referential.updated_at = now
    _event(db, referential, version, action, actor_id, roles & needed, comment)
    return version


# --- LOT 2 : historique et comparaison de versions (lecture seule). ------------------------

DIFF_FIELDS = tuple(name for name in ENTRY_FIELDS if name not in {"source_language", "source_term"})


def entry_identity(entry: RagTermEntry) -> tuple:
    """Identité métier d'une entrée : paire de langues, clé source, contexte d'emploi."""
    return (
        entry.source_language,
        entry.target_language,
        entry.normalized_source,
        (entry.domain or "").upper(),
        entry.country or "",
        entry.jurisdiction or "",
    )


def diff_versions(db: Session, base: RagReferentialVersion, other: RagReferentialVersion) -> dict:
    """Différences ``base`` -> ``other`` d'un même référentiel (ajouts, retraits, champs modifiés)."""
    if base.referential_id != other.referential_id:
        raise RagAccessError("RAG_VERSION_NOT_FOUND", 404)

    def grouped(version):
        out: dict[tuple, list[RagTermEntry]] = {}
        for entry in version_entries(db, version):
            out.setdefault(entry_identity(entry), []).append(entry)
        return out

    before, after = grouped(base), grouped(other)
    added, removed, changed = [], [], []
    unchanged = 0
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key, []), after.get(key, [])
        if not old:
            added.extend(new)
            continue
        if not new:
            removed.extend(old)
            continue
        # Appariement déterministe dans l'ordre des cibles (une identité porte souvent 1 entrée).
        old_sorted = sorted(old, key=lambda e: (e.target_term, e.id))
        new_sorted = sorted(new, key=lambda e: (e.target_term, e.id))
        for left, right in zip(old_sorted, new_sorted, strict=False):
            fields = [n for n in DIFF_FIELDS if getattr(left, n) != getattr(right, n)]
            if fields:
                changed.append((left, right, fields))
            else:
                unchanged += 1
        added.extend(new_sorted[len(old_sorted) :])
        removed.extend(old_sorted[len(new_sorted) :])

    def view(entry):
        return {
            "entry_id": entry.id,
            "source_language": entry.source_language,
            "source_term": entry.source_term,
            "target_language": entry.target_language,
            "target_term": entry.target_term,
            "domain": entry.domain,
            "country": entry.country,
        }

    return {
        "base_version_id": base.id,
        "base_number": base.number,
        "other_version_id": other.id,
        "other_number": other.number,
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": unchanged,
        },
        "added": [view(e) for e in added],
        "removed": [view(e) for e in removed],
        "changed": [
            {"before": view(a), "after": view(b), "fields": fields} for a, b, fields in changed
        ],
    }


def history(db: Session, referential: RagReferential) -> dict:
    """Versions et événements de validation d'un référentiel, du plus ancien au plus récent."""
    versions = versions_of(db, referential)
    ids = [referential.id, *(v.id for v in versions)]
    events = db.scalars(
        select(RagValidationEvent)
        .where(
            RagValidationEvent.object_id.in_(ids),
            RagValidationEvent.object_type.in_(("referential", "referential_version")),
        )
        .order_by(RagValidationEvent.created_at, RagValidationEvent.id)
    ).all()
    return {
        "referential_id": referential.id,
        "versions": [
            {
                "version_id": v.id,
                "number": v.number,
                "status": v.status,
                "entry_count": v.entry_count,
                "content_sha256": v.content_sha256,
                "created_by": v.created_by,
                "submitted_by": v.submitted_by,
                "validated_by": v.validated_by,
                "published_by": v.published_by,
                "published_at": v.published_at.isoformat() if v.published_at else None,
                "retired_at": v.retired_at.isoformat() if v.retired_at else None,
            }
            for v in versions
        ],
        "events": [
            {
                "object_type": e.object_type,
                "object_id": e.object_id,
                "action": e.action,
                "actor_id": e.actor_id,
                "actor_role": e.actor_role,
                "comment": e.comment,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }
