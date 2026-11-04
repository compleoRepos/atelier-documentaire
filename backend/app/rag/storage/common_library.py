"""Bibliothèque commune du RAG (``tenant_id`` NULL) : outillage plateforme, hors API.

L'API ne crée jamais de référentiel commun et refuse toute écriture sur eux
(``RAG_COMMON_REFERENTIAL_READ_ONLY``). Ce module est l'outil réservé à l'exploitation :

* création d'un référentiel commun (inactif) et import de fichiers en BROUILLON uniquement,
  avec les briques de l'importeur de l'API (limites, validation ligne à ligne, doublons,
  formules, instructions) ; trace d'import = événement de validation (empreinte, comptes) ;
  un seul fichier rejeté annule tout l'import (aucune écriture partielle) ;
* transitions (soumission, validation, publication, retrait) déléguées à
  ``versioning.transition`` : quatre yeux, empreinte du contenu, index BM25 inchangés ;
* activation explicite par un administrateur ;
* chaque acteur doit être un utilisateur existant : aucune action anonyme.

Rien n'est publié automatiquement : un import laisse la version en brouillon.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...core.models import User
from ..models import RagReferential, RagReferentialVersion
from ..terminology.importer import (
    ImportFileError,
    detect_duplicates,
    detect_format,
    read_csv,
    read_xlsx,
    validate_rows,
)
from ..terminology.normalizer import normalize_language
from .repository import REFERENTIAL_KINDS, RagAccessError, versions_of
from .versioning import (
    _event,
    _referential_event,
    add_entries,
    allowed_roles,
    create_draft,
    set_referential_active,
    transition,
)


class CommonLibraryError(RuntimeError):
    def __init__(self, code: str, detail: object = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class ImportOutcome:
    referential_id: str
    version_id: str
    version_number: int
    status: str
    files: list[dict] = field(default_factory=list)


def resolve_actor(db: Session, actor: str) -> str:
    """Identifiant d'un utilisateur existant et actif (par identifiant ou nom d'utilisateur)."""
    value = str(actor or "").strip()
    if not value:
        raise CommonLibraryError("ACTOR_REQUIRED")
    user_id = db.scalar(
        select(User.id).where(or_(User.id == value, User.username == value), User.enabled.is_(True))
    )
    if user_id is None:
        raise CommonLibraryError("ACTOR_UNKNOWN")
    return user_id


def common_referential(db: Session, name: str) -> RagReferential | None:
    return db.scalar(
        select(RagReferential).where(
            RagReferential.tenant_id.is_(None), RagReferential.name == name
        )
    )


def get_or_create(
    db: Session,
    *,
    name: str,
    kind: str,
    languages: Iterable[str],
    actor_id: str,
    domain: str | None = None,
    jurisdiction: str | None = None,
) -> RagReferential:
    if kind not in REFERENTIAL_KINDS:
        raise CommonLibraryError("KIND_INVALID")
    clean = " ".join(str(name or "").split())
    if not clean or len(clean) > 200:
        raise CommonLibraryError("NAME_INVALID")
    existing = common_referential(db, clean)
    if existing is not None:
        if existing.kind != kind:
            raise CommonLibraryError("KIND_MISMATCH")
        return existing
    codes = [normalize_language(code) for code in languages]
    if any(not code for code in codes):
        raise CommonLibraryError("LANGUAGE_INVALID")
    row = RagReferential(
        tenant_id=None,
        scope="common",
        kind=kind,
        name=clean,
        domain=(domain or None),
        country=None,
        jurisdiction=(jurisdiction or None),
        languages=sorted(set(codes)) or None,
        active=False,
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    _referential_event(db, row, "create_referential", actor_id, allowed_roles(kind, "create"))
    return row


def _analyse(db: Session, settings, referential, version, data: bytes):
    """Même enchaînement que ``importer.import_file`` (limites, lecture, lignes, doublons).

    Seule différence : pas de ``RagImportBatch`` (table propre aux tenants, tenant obligatoire) ;
    la trace est un événement de validation de la version (empreinte et comptes, sans contenu).
    """
    if not data:
        raise CommonLibraryError("IMPORT_EMPTY")
    if len(data) > settings.rag_import_max_bytes:
        raise CommonLibraryError("IMPORT_TOO_LARGE")
    fmt = detect_format(data, "csv")
    reader = read_xlsx if fmt == "xlsx" else read_csv
    try:
        header, rows, formula_rows = reader(data, settings.rag_import_max_rows)
    except ImportFileError as exc:
        raise CommonLibraryError(exc.code) from exc
    if len(rows) > settings.rag_import_max_rows:
        raise CommonLibraryError("IMPORT_TOO_MANY_ROWS")
    items, ignored = validate_rows(header, rows, formula_rows)
    detect_duplicates(db, None, referential, version, items)
    return rows, items, ignored


def import_draft(
    db: Session,
    settings,
    *,
    referential: RagReferential,
    files: list[tuple[str, bytes]],
    actor_id: str,
) -> ImportOutcome:
    """Nouveau brouillon alimenté par les fichiers ; tout ou rien (l'appelant valide)."""
    if referential.tenant_id is not None:
        raise CommonLibraryError("NOT_COMMON")
    if not files:
        raise CommonLibraryError("NO_FILE")
    roles = set(allowed_roles(referential.kind, "edit"))
    version = create_draft(db, referential, actor_id, roles)
    outcome = ImportOutcome(referential.id, version.id, version.number, version.status)
    for name, data in files:
        rows, items, ignored = _analyse(db, settings, referential, version, data)
        outcomes = [result for result, _ in items]
        errors = sum(result.action == "rejected" for result in outcomes)
        if errors:
            report = [result.as_dict() for result in outcomes if result.action == "rejected"]
            raise CommonLibraryError("IMPORT_REJECTED", {"file": name, "report": report[:50]})
        accepted = [values for result, values in items if result.action == "accepted"]
        if accepted:
            add_entries(db, referential, version, accepted, actor_id, roles)
        sha256 = hashlib.sha256(data).hexdigest()
        item = {
            "file": name,
            "status": "applied",
            "rows": len(rows),
            "accepted": len(accepted),
            "skipped": sum(result.action == "skipped" for result in outcomes),
            "errors": 0,
            "warnings": sum(result.severity == "warning" for result in outcomes),
            "ignored_columns": len(ignored),
            "sha256": sha256,
        }
        outcome.files.append(item)
        comment = (
            f"import plateforme {name} sha256={sha256} lignes={item['rows']} "
            f"acceptées={item['accepted']} ignorées={item['skipped']} "
            f"avertissements={item['warnings']}"
        )
        _event(db, referential, version, "import", actor_id, roles, comment)
    outcome.status = version.status
    return outcome


def version_by_number(
    db: Session, referential: RagReferential, number: int
) -> RagReferentialVersion:
    for version in versions_of(db, referential):
        if version.number == number:
            return version
    raise CommonLibraryError("VERSION_NOT_FOUND")


def apply_transition(
    db: Session,
    *,
    referential: RagReferential,
    number: int,
    action: str,
    actor_id: str,
    comment: str | None = None,
) -> RagReferentialVersion:
    if referential.tenant_id is not None:
        raise CommonLibraryError("NOT_COMMON")
    version = version_by_number(db, referential, number)
    try:
        return transition(
            db,
            referential,
            version,
            action,
            actor_id,
            set(allowed_roles(referential.kind, action)),
            comment,
        )
    except RagAccessError as exc:  # quatre yeux, contenu modifié, transition invalide
        raise CommonLibraryError(exc.code) from exc


def set_active(
    db: Session, *, referential: RagReferential, active: bool, actor_id: str
) -> RagReferential:
    if referential.tenant_id is not None:
        raise CommonLibraryError("NOT_COMMON")
    return set_referential_active(db, referential, active, actor_id, {"rag_admin"})
