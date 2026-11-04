"""Textes juridiques de la bibliothèque commune (``rag_legal_texts`` / ``rag_legal_passages``).

Outillage plateforme, hors API, comme ``common_library`` :

* import en BROUILLON d'un référentiel commun de type ``regulatory`` : un texte par couple
  acte-langue, un passage par article (intitulé de l'article en première ligne, puis le corps,
  sans aucune modification du texte source) ;
* empreinte canonique du contenu juridique de la version (textes et passages) : elle est fixée
  à la soumission et revérifiée à la validation et à la publication ;
* circuit à quatre yeux identique à celui des terminologies (``versioning.TRANSITIONS``) :
  le validateur ne peut être ni l'auteur ni le soumetteur ;
* recherche lexicale en lecture seule (mots entiers, insensible à la casse et aux diacritiques)
  limitée aux versions publiées de référentiels communs actifs.

Ces textes ne sont jamais injectés dans la traduction : le moteur RAG ne lit que les
référentiels terminologiques (``repository.TERMINOLOGY_KINDS``). Leur exploitation dans le
pipeline relève du LOT 3 et d'une qualification dédiée.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.models import now_utc
from ..models import RagLegalPassage, RagLegalText, RagReferential, RagReferentialVersion
from ..terminology.linguistic import SUPPORTED_LANGUAGES, fold_key, folded_tokens, search_tokens
from ..terminology.normalizer import normalize_language
from .repository import RagAccessError, versions_of
from .versioning import TRANSITIONS, _event, allowed_roles, create_draft

LEGAL_KIND = "regulatory"
TEXT_FIELDS = (
    "country",
    "jurisdiction",
    "legal_domain",
    "text_type",
    "official_reference",
    "text_version",
    "official_source",
    "language",
)
_MAX_PASSAGE = 200_000
_MAX_RESULTS = 50
_LIKE_ESCAPE = "\\"


class LegalLibraryError(RuntimeError):
    def __init__(self, code: str, detail: object = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class LegalImportOutcome:
    referential_id: str
    version_id: str
    version_number: int
    status: str
    texts: int
    passages: int
    content_sha256: str


def normalized_passage(text: object) -> str:
    """Clé de recherche d'un passage : mots pliés, bornés par une espace (mots entiers)."""
    words = folded_tokens(text)
    return f" {' '.join(words)} " if words else ""


def _clean(value: object, limit: int, *, required: bool = False) -> str | None:
    text = " ".join(str(value or "").split())
    if not text:
        if required:
            raise LegalLibraryError("LEGAL_FIELD_REQUIRED")
        return None
    if len(text) > limit:
        raise LegalLibraryError("LEGAL_FIELD_TOO_LONG")
    return text


def _texts(db: Session, version: RagReferentialVersion) -> list[RagLegalText]:
    return list(db.scalars(select(RagLegalText).where(RagLegalText.version_id == version.id)).all())


def _passages(db: Session, text_ids: list[str]) -> dict[str, list[RagLegalPassage]]:
    out: dict[str, list[RagLegalPassage]] = {key: [] for key in text_ids}
    if not text_ids:
        return out
    rows = db.scalars(
        select(RagLegalPassage).where(RagLegalPassage.legal_text_id.in_(text_ids))
    ).all()
    for row in rows:
        out[row.legal_text_id].append(row)
    return out


def has_legal_content(db: Session, version: RagReferentialVersion) -> bool:
    return (
        db.scalar(select(func.count(RagLegalText.id)).where(RagLegalText.version_id == version.id))
        or 0
    ) > 0


def legal_content_sha256(db: Session, version: RagReferentialVersion) -> str:
    """Empreinte canonique des textes et passages d'une version (ordre indifférent)."""
    texts = _texts(db, version)
    passages = _passages(db, [text.id for text in texts])
    canonical = []
    for text in texts:
        body = [
            [passage.position, passage.article_ref, passage.language, passage.text]
            for passage in sorted(passages[text.id], key=lambda p: (p.position, p.id))
        ]
        head = {name: getattr(text, name) for name in TEXT_FIELDS}
        canonical.append(json.dumps({"text": head, "passages": body}, sort_keys=True))
    return hashlib.sha256("\n".join(sorted(canonical)).encode("utf-8")).hexdigest()


def counts(db: Session, version: RagReferentialVersion) -> dict:
    texts = _texts(db, version)
    passages = sum(len(rows) for rows in _passages(db, [text.id for text in texts]).values())
    return {
        "legal_texts": len(texts),
        "legal_passages": passages,
        "legal_acts": len({text.official_reference for text in texts}),
        "legal_languages": len({text.language for text in texts}),
    }


def import_legal_draft(
    db: Session,
    *,
    referential: RagReferential,
    texts: Iterable[Mapping],
    actor_id: str,
) -> LegalImportOutcome:
    """Nouveau brouillon de textes juridiques ; tout ou rien (l'appelant valide la transaction).

    Chaque élément de ``texts`` décrit un couple acte-langue : ``official_reference``,
    ``language``, ``country``, ``jurisdiction``, ``legal_domain``, ``text_type``,
    ``text_version``, ``official_source`` et ``passages`` (``article_ref``, ``text``).
    """
    if referential.tenant_id is not None:
        raise LegalLibraryError("NOT_COMMON")
    if referential.kind != LEGAL_KIND:
        raise LegalLibraryError("KIND_INVALID")
    items = list(texts)
    if not items:
        raise LegalLibraryError("NO_TEXT")
    roles = set(allowed_roles(referential.kind, "edit"))
    version = create_draft(db, referential, actor_id, roles)
    seen: set[tuple[str, str]] = set()
    n_passages = 0
    for item in items:
        language = normalize_language(item.get("language"))
        if language not in SUPPORTED_LANGUAGES:
            raise LegalLibraryError(
                "LANGUAGE_INVALID", {"reference": item.get("official_reference")}
            )
        reference = _clean(item.get("official_reference"), 300, required=True)
        key = (reference, language)
        if key in seen:
            raise LegalLibraryError(
                "LEGAL_TEXT_DUPLICATE", {"reference": reference, "language": language}
            )
        seen.add(key)
        country = str(item.get("country") or "").strip().upper()
        if len(country) != 2 or not country.isalpha():
            raise LegalLibraryError("COUNTRY_INVALID", {"reference": reference})
        passages = list(item.get("passages") or [])
        if not passages:
            raise LegalLibraryError("NO_PASSAGE", {"reference": reference, "language": language})
        row = RagLegalText(
            tenant_id=None,
            referential_id=referential.id,
            version_id=version.id,
            country=country,
            jurisdiction=_clean(item.get("jurisdiction"), 80),
            legal_domain=_clean(item.get("legal_domain"), 80),
            text_type=_clean(item.get("text_type"), 60),
            official_reference=reference,
            text_version=_clean(item.get("text_version"), 60),
            official_source=_clean(item.get("official_source"), 500),
            validation_status="candidate",
            language=language,
        )
        db.add(row)
        db.flush()
        refs: set[str] = set()
        for position, passage in enumerate(passages):
            article = _clean(passage.get("article_ref"), 120, required=True)
            if article in refs:
                raise LegalLibraryError(
                    "PASSAGE_DUPLICATE",
                    {"reference": reference, "language": language, "article": article},
                )
            refs.add(article)
            body = str(passage.get("text") or "")
            if not body.strip():
                raise LegalLibraryError(
                    "PASSAGE_EMPTY", {"reference": reference, "article": article}
                )
            if len(body) > _MAX_PASSAGE:
                raise LegalLibraryError(
                    "PASSAGE_TOO_LONG", {"reference": reference, "article": article}
                )
            db.add(
                RagLegalPassage(
                    legal_text_id=row.id,
                    tenant_id=None,
                    article_ref=article,
                    language=language,
                    text=body,
                    normalized_text=normalized_passage(body),
                    position=position,
                )
            )
            n_passages += 1
    db.flush()
    digest = legal_content_sha256(db, version)
    comment = (
        f"import plateforme textes juridiques sha256={digest} textes={len(items)} "
        f"passages={n_passages}"
    )
    _event(db, referential, version, "import", actor_id, roles, comment)
    return LegalImportOutcome(
        referential.id, version.id, version.number, version.status, len(items), n_passages, digest
    )


def transition(
    db: Session,
    referential: RagReferential,
    version: RagReferentialVersion,
    action: str,
    actor_id: str | None,
    roles: set[str],
    comment: str | None = None,
) -> RagReferentialVersion:
    """Même circuit que ``versioning.transition``, appliqué au contenu juridique.

    Aucun index BM25 n'est construit : il ne concerne que les entrées terminologiques.
    """
    if action not in TRANSITIONS:
        raise RagAccessError("RAG_ACTION_UNKNOWN", 422)
    if referential.kind != LEGAL_KIND:
        raise RagAccessError("RAG_REFERENTIAL_KIND_INVALID", 422)
    needed = allowed_roles(referential.kind, action)
    if not roles & needed:
        raise RagAccessError("RAG_ROLE_REQUIRED")
    source, target = TRANSITIONS[action]
    if version.status != source:
        raise RagAccessError("RAG_TRANSITION_INVALID", 409)
    now = now_utc()
    if action == "submit":
        if not has_legal_content(db, version):
            raise RagAccessError("RAG_VERSION_EMPTY", 409)
        version.content_sha256 = legal_content_sha256(db, version)
        version.submitted_by = actor_id
        version.submitted_at = now
    elif action == "reject":
        version.content_sha256 = None
        version.submitted_by = None
        version.submitted_at = None
    elif action == "validate":
        if actor_id is None or actor_id in {version.created_by, version.submitted_by}:
            raise RagAccessError("RAG_FOUR_EYES_REQUIRED", 403)
        if legal_content_sha256(db, version) != version.content_sha256:
            raise RagAccessError("RAG_CONTENT_CHANGED", 409)
        for text in _texts(db, version):
            if text.validation_status == "candidate":
                text.validation_status = "validated"
        version.validated_by = actor_id
        version.validated_at = now
    elif action in {"publish", "restore"}:
        if legal_content_sha256(db, version) != version.content_sha256:
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
    elif action == "retire":
        version.retired_at = now
    version.status = target
    referential.updated_at = now
    _event(db, referential, version, action, actor_id, roles & needed, comment)
    return version


def _like(token: str) -> str:
    escaped = token.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2).replace("%", "\\%").replace("_", "\\_")
    return f"% {escaped} %"


_SPACES = re.compile(r"\s+")

# Le Journal officiel écrit parfois l'allemand sans tréma (« Hoechstarbeitszeit » dans la directive
# 2003/88/CE, à côté de « Höchstarbeitszeit » ailleurs). Le texte officiel n'est jamais modifié :
# c'est la requête qui essaie aussi l'autre graphie.
_GERMAN_TRANSLIT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"})
_GERMAN_REVERSE = (("ae", "a"), ("oe", "o"), ("ue", "u"))


def _query_variants(query: str, language: str | None) -> list[tuple[str, tuple[str, ...]]]:
    """Mots pliés de la requête, chacun avec ses graphies admises (le mot plié en premier).

    - mot avec tréma : graphie transcrite ajoutée (ä -> ae, ö -> oe, ü -> ue), sans risque
      pour les autres langues puisqu'elle ne concerne que les mots qui portent un tréma ;
    - langue explicitement allemande : graphie inverse ajoutée (ae -> a, oe -> o, ue -> u),
      réservée à l'allemand (« oeuvre » en français ne doit pas devenir « ouvre »).
    """
    out: dict[str, list[str]] = {}
    for raw in search_tokens(query):
        word = fold_key(raw)
        if not word:
            continue
        variants = out.setdefault(word, [word])
        forward = fold_key(raw.translate(_GERMAN_TRANSLIT))
        if forward and forward not in variants:
            variants.append(forward)
        if language == "de":
            reverse = word
            for old, new in _GERMAN_REVERSE:
                reverse = reverse.replace(old, new)
            if reverse and reverse not in variants:
                variants.append(reverse)
    return [(word, tuple(variants)) for word, variants in out.items()]


def search(
    db: Session,
    query: str,
    *,
    language: str | None = None,
    reference: str | None = None,
    limit: int = 10,
) -> dict:
    """Passages publiés contenant tous les mots de la requête (lecture seule)."""
    words = list(dict.fromkeys(folded_tokens(query)))
    if not words:
        raise LegalLibraryError("QUERY_EMPTY")
    if len(words) > 12:
        raise LegalLibraryError("QUERY_TOO_LONG")
    code = None
    if language:
        code = normalize_language(language)
        if code not in SUPPORTED_LANGUAGES:
            raise LegalLibraryError("LANGUAGE_INVALID")
    variants = _query_variants(query, code)
    limit = max(1, min(int(limit), _MAX_RESULTS))
    statement = (
        select(RagLegalPassage, RagLegalText)
        .join(RagLegalText, RagLegalPassage.legal_text_id == RagLegalText.id)
        .join(RagReferentialVersion, RagLegalText.version_id == RagReferentialVersion.id)
        .join(RagReferential, RagLegalText.referential_id == RagReferential.id)
        .where(
            RagReferential.tenant_id.is_(None),
            RagReferential.kind == LEGAL_KIND,
            RagReferential.active.is_(True),
            RagReferentialVersion.status == "published",
        )
    )
    for _word, forms in variants:
        statement = statement.where(
            or_(
                *(
                    RagLegalPassage.normalized_text.like(_like(form), escape=_LIKE_ESCAPE)
                    for form in forms
                )
            )
        )
    if code:
        statement = statement.where(RagLegalPassage.language == code)
    if reference:
        needle = _SPACES.sub(" ", reference.strip())
        statement = statement.where(RagLegalText.official_reference.contains(needle))
    scored = []
    for passage, text in db.execute(statement).all():
        haystack = passage.normalized_text or ""
        occurrences = sum(
            haystack.count(f" {form} ") for _word, forms in variants for form in forms
        )
        # Pertinence : mots présents dans la première ligne (l'intitulé de l'article quand il
        # existe), puis densité d'occurrences ; l'ordre ne modifie aucun texte renvoyé.
        head = set(folded_tokens(passage.text.split("\n", 1)[0]))
        in_head = sum(any(form in head for form in forms) for _word, forms in variants)
        density = occurrences / max(1, len(haystack.split()))
        key = (-in_head, -density, text.official_reference, text.language, passage.position)
        scored.append((key, occurrences, passage, text))
    scored.sort(key=lambda item: item[0])
    results = []
    for _key, occurrences, passage, text in scored[:limit]:
        results.append(
            {
                "reference": text.official_reference,
                "language": text.language,
                "article": passage.article_ref,
                "occurrences": occurrences,
                "excerpt": passage.text[:400],
                "source": text.official_source,
            }
        )
    expanded = {word: list(forms[1:]) for word, forms in variants if len(forms) > 1}
    return {
        "query_words": words,
        "spelling_variants": expanded,
        "matches": len(scored),
        "results": results,
    }


def status(db: Session, referential: RagReferential) -> list[dict]:
    return [
        {"number": version.number, "status": version.status, **counts(db, version)}
        for version in versions_of(db, referential)
    ]
