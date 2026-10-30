"""Import de référentiels terminologiques CSV/XLSX (LOT 2).

Garanties :
* **tout ou rien** : une seule erreur bloque l'import ; rien n'est écrit dans le
  brouillon (statut ``rejected``) ; l'essai à blanc (``dry_run``) n'écrit jamais ;
* import uniquement dans une version **brouillon** d'un référentiel du tenant,
  avec les rôles d'édition ; la suite du cycle (soumission, validation par une
  autre personne, publication) reste humaine et inchangée ;
* XLSX lu sans dépendance nouvelle (``zipfile`` + ``lxml``) : bornes de taille,
  de taux de compression et de nombre de membres (bombes zip), DTD/entités
  refusées (XXE), formules refusées ; CSV UTF-8 strict, NUL refusé ;
* cellules débutant par ``=``, ``+``, ``@``, tabulation ou retour chariot
  refusées (injection de formules), ainsi que les textes ressemblant à une
  instruction adressée au modèle (même filtre que le constructeur de contexte) ;
* le rapport persistant (``rag_import_batches``) ne contient que des numéros de
  ligne et des codes, jamais le contenu des cellules ; rien n'est journalisé.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from lxml import etree
from sqlalchemy.orm import Session

from ..core.context_builder import _UNSAFE
from ..models import RagImportBatch, RagReferential, RagReferentialVersion
from ..storage.repository import RagAccessError, published_scope, version_entries, versions_of
from ..storage.versioning import add_entries, allowed_roles
from . import domains
from .linguistic import SUPPORTED_LANGUAGES, fold_key, search_key
from .normalizer import normalize_language

COLUMNS = (
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
REQUIRED = ("source_language", "source_term", "target_language", "target_term")
ALIASES = {
    "langue_source": "source_language",
    "terme_source": "source_term",
    "langue_cible": "target_language",
    "terme_cible": "target_term",
    "synonymes": "synonyms",
    "variantes": "regional_variants",
    "variantes_regionales": "regional_variants",
    "contexte": "usage_context",
    "contexte_usage": "usage_context",
    "registre": "register",
    "domaine": "domain",
    "pays": "country",
    "juridiction": "jurisdiction",
    "provenance": "provenance",
}
LIMITS = {
    "source_term": 500,
    "target_term": 500,
    "synonyms": 500,
    "regional_variants": 500,
    "definition": 4000,
    "usage_context": 4000,
    "register": 40,
    "domain": 40,
    "country": 2,
    "jurisdiction": 80,
    "provenance": 200,
}
LIST_SEPARATOR = "|"
_FORMULA_PREFIX = ("=", "+", "@", "\t", "\r")
_FORMULA_DASH = re.compile(r"^-.*[(!|=]")
_XLSX_MAX_MEMBERS = 200
_XLSX_MAX_MEMBER_BYTES = 20_000_000
_XLSX_MAX_TOTAL_BYTES = 50_000_000
_XLSX_MAX_RATIO = 100
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ERRORS = frozenset(
    {
        "COUNTRY_INVALID",
        "DOMAIN_UNKNOWN",
        "FORMULA_REJECTED",
        "LANGUAGE_UNSUPPORTED",
        "MISSING_FIELD",
        "SAME_LANGUAGE",
        "TOO_LONG",
        "UNSAFE_INSTRUCTION",
    }
)


class ImportFileError(RagAccessError):
    """Fichier refusé dans son ensemble (format, taille, structure, sécurité)."""

    def __init__(self, code: str) -> None:
        super().__init__(code, 422)


@dataclass
class RowOutcome:
    row: int
    codes: list[str] = field(default_factory=list)
    action: str = "accepted"  # accepted | skipped | rejected

    @property
    def severity(self) -> str:
        if self.action == "rejected":
            return "error"
        return "warning" if self.codes else "info"

    def as_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "codes": sorted(set(self.codes)),
            "action": self.action,
            "severity": self.severity,
        }


# --- Lecture des fichiers ------------------------------------------------------------------


def _header(name: object) -> str:
    key = re.sub(r"[\s\-]+", "_", str(name or "").strip().lower())
    return ALIASES.get(key, key)


def read_csv(data: bytes, max_rows: int) -> tuple[list[str], list[tuple[int, list[str]]], set[int]]:
    if b"\x00" in data:
        raise ImportFileError("IMPORT_CSV_BINARY")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportFileError("IMPORT_CSV_NOT_UTF8") from exc
    first = text.split("\n", 1)[0]
    delimiter = max((";", ",", "\t"), key=first.count)
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        rows = []
        header: list[str] | None = None
        for line_number, record in enumerate(reader, start=1):
            if header is None:
                header = record
                continue
            rows.append((line_number, record))
            if len(rows) > max_rows:
                raise ImportFileError("IMPORT_TOO_MANY_ROWS")
    except csv.Error as exc:
        raise ImportFileError("IMPORT_CSV_MALFORMED") from exc
    if not header:
        raise ImportFileError("IMPORT_EMPTY")
    return header, rows, set()


def _safe_xml(data: bytes) -> etree._Element:
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ImportFileError("IMPORT_XLSX_DTD_REJECTED")
    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
    )
    try:
        return etree.fromstring(data, parser)
    except etree.XMLSyntaxError as exc:
        raise ImportFileError("IMPORT_XLSX_MALFORMED") from exc


def _column_index(reference: str) -> int:
    letters = "".join(ch for ch in reference if ch.isalpha()).upper()
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - 64)
    return index - 1


def read_xlsx(
    data: bytes, max_rows: int
) -> tuple[list[str], list[tuple[int, list[str]]], set[int]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ImportFileError("IMPORT_XLSX_NOT_ZIP") from exc
    members = archive.infolist()
    if len(members) > _XLSX_MAX_MEMBERS:
        raise ImportFileError("IMPORT_XLSX_TOO_MANY_MEMBERS")
    total = 0
    for info in members:
        total += info.file_size
        ratio = info.file_size / max(info.compress_size, 1)
        if info.file_size > _XLSX_MAX_MEMBER_BYTES or (
            info.file_size > 1_000_000 and ratio > _XLSX_MAX_RATIO
        ):
            raise ImportFileError("IMPORT_XLSX_BOMB_REJECTED")
    if total > _XLSX_MAX_TOTAL_BYTES:
        raise ImportFileError("IMPORT_XLSX_BOMB_REJECTED")
    names = {info.filename for info in members}

    def member(name: str) -> bytes:
        with archive.open(name) as handle:
            content = handle.read(_XLSX_MAX_MEMBER_BYTES + 1)
        if len(content) > _XLSX_MAX_MEMBER_BYTES:
            raise ImportFileError("IMPORT_XLSX_BOMB_REJECTED")
        return content

    if "xl/workbook.xml" not in names:
        raise ImportFileError("IMPORT_XLSX_MALFORMED")
    workbook = _safe_xml(member("xl/workbook.xml"))
    sheet = workbook.find("m:sheets/m:sheet", _NS)
    if sheet is None:
        raise ImportFileError("IMPORT_EMPTY")
    target = "xl/worksheets/sheet1.xml"
    rel_id = sheet.get(f"{{{_REL_NS}}}id")
    if rel_id and "xl/_rels/workbook.xml.rels" in names:
        rels = _safe_xml(member("xl/_rels/workbook.xml.rels"))
        for rel in rels:
            if rel.get("Id") == rel_id and rel.get("Target"):
                path = rel.get("Target").lstrip("/")
                target = path if path.startswith("xl/") else f"xl/{path}"
    if target not in names:
        raise ImportFileError("IMPORT_XLSX_MALFORMED")
    shared: list[str] = []
    if "xl/sharedStrings.xml" in names:
        for item in _safe_xml(member("xl/sharedStrings.xml")).findall("m:si", _NS):
            # Texte riche : runs <t>, sans les indications phonétiques <rPh>.
            shared.append(
                "".join(
                    t.text or ""
                    for t in item.iter(f"{{{_NS['m']}}}t")
                    if t.getparent().tag != f"{{{_NS['m']}}}rPh"
                )
            )
    rows: list[tuple[int, list[str]]] = []
    formulas: set[int] = set()
    for row in _safe_xml(member(target)).iterfind("m:sheetData/m:row", _NS):
        number = int(row.get("r") or len(rows) + 1)
        values: dict[int, str] = {}
        for position, cell in enumerate(row.findall("m:c", _NS)):
            column = _column_index(cell.get("r")) if cell.get("r") else position
            if cell.find("m:f", _NS) is not None:
                formulas.add(number)
            kind = cell.get("t")
            raw = cell.find("m:v", _NS)
            if kind == "s" and raw is not None:
                try:
                    value = shared[int(raw.text)]
                except (ValueError, IndexError) as exc:
                    raise ImportFileError("IMPORT_XLSX_MALFORMED") from exc
            elif kind == "inlineStr":
                inline = cell.find("m:is", _NS)
                value = "".join(inline.itertext()) if inline is not None else ""
            else:
                value = raw.text if raw is not None and raw.text is not None else ""
            if 0 <= column < 64:
                values[column] = value
        record = [values.get(i, "") for i in range(max(values) + 1)] if values else []
        rows.append((number, record))
        if len(rows) > max_rows + 1:
            raise ImportFileError("IMPORT_TOO_MANY_ROWS")
    if not rows:
        raise ImportFileError("IMPORT_EMPTY")
    return rows[0][1], rows[1:], formulas


# --- Validation et doublons ------------------------------------------------------------------


def _cell(value: object) -> str:
    return " ".join(str(value or "").split())


def _list(value: str) -> list[str]:
    return [part for part in (_cell(p) for p in value.split(LIST_SEPARATOR)) if part]


def _formula(raw: str) -> bool:
    return raw.startswith(_FORMULA_PREFIX) or bool(_FORMULA_DASH.match(raw))


def validate_rows(
    header: list[str], rows: list[tuple[int, list[str]]], formula_rows: set[int] | None = None
) -> tuple[list[tuple[RowOutcome, dict]], list[str]]:
    columns = [_header(name) for name in header]
    missing = [name for name in REQUIRED if name not in columns]
    if missing:
        raise ImportFileError("IMPORT_REQUIRED_COLUMN_MISSING")
    if len(set(columns)) != len(columns):
        raise ImportFileError("IMPORT_DUPLICATE_COLUMN")
    ignored = sorted({name for name in columns if name not in COLUMNS and name})
    out: list[tuple[RowOutcome, dict]] = []
    for number, record in rows:
        outcome = RowOutcome(number)
        raws = {columns[i]: str(v or "") for i, v in enumerate(record[: len(columns)])}
        extra = record[len(columns) :]
        if not any(_cell(v) for v in record):
            outcome.action = "skipped"
            outcome.codes.append("EMPTY_ROW")
            out.append((outcome, {}))
            continue
        if number in (formula_rows or set()):
            outcome.codes.append("FORMULA_REJECTED")
        if any(_cell(v) for v in extra):
            outcome.codes.append("EXTRA_CELLS")
        values: dict[str, Any] = {}
        for name in COLUMNS:
            raw = raws.get(name, "")
            if raw.strip() and _formula(raw.lstrip(" ")):
                outcome.codes.append("FORMULA_REJECTED")
            text = _cell(raw)
            if text and _UNSAFE.search(text):
                outcome.codes.append("UNSAFE_INSTRUCTION")
            if name in {"synonyms", "regional_variants"}:
                items = _list(raw)
                if any(len(item) > LIMITS[name] for item in items):
                    outcome.codes.append("TOO_LONG")
                values[name] = items or None
                continue
            if text and len(text) > LIMITS.get(name, 500) and name not in {"country"}:
                outcome.codes.append("TOO_LONG")
            values[name] = text or None
        for name in REQUIRED:
            if not values.get(name):
                outcome.codes.append("MISSING_FIELD")
        for name in ("source_language", "target_language"):
            code = normalize_language(values.get(name)) if values.get(name) else None
            if values.get(name) and code not in SUPPORTED_LANGUAGES:
                outcome.codes.append("LANGUAGE_UNSUPPORTED")
            values[name] = code
        if values["source_language"] and values["source_language"] == values["target_language"]:
            outcome.codes.append("SAME_LANGUAGE")
        if values.get("country"):
            country = values["country"].upper()
            if len(country) != 2 or not country.isalpha():
                outcome.codes.append("COUNTRY_INVALID")
            values["country"] = country
        if values.get("domain"):
            code = domains.canonical_domain(values["domain"])
            if code is None:
                outcome.codes.append("DOMAIN_UNKNOWN")
            values["domain"] = code
        term_key = search_key(values.get("source_term") or "")
        for name in ("synonyms", "regional_variants"):
            if values.get(name):
                kept = [v for v in values[name] if search_key(v) != term_key]
                values[name] = kept or None
        if set(outcome.codes) & ERRORS:
            outcome.action = "rejected"
        out.append((outcome, values))
    return out, ignored


def _identity(values: Mapping[str, Any], key: str) -> tuple:
    return (
        values.get("source_language"),
        values.get("target_language"),
        key,
        values.get("domain") or "",
        values.get("country") or "",
        values.get("jurisdiction") or "",
    )


def detect_duplicates(
    db: Session,
    tenant_id: str,
    referential: RagReferential,
    version: RagReferentialVersion,
    items: list[tuple[RowOutcome, dict]],
) -> None:
    """Annote les lignes valides : doublons, conflits, quasi-doublons, collisions."""
    exact: dict[tuple, str] = {}
    folded: dict[tuple, str] = {}
    forms: dict[tuple, str] = {}  # (sl, tl, clé de forme) -> cible
    for outcome, values in items:
        if outcome.action != "accepted":
            continue
        key = search_key(values["source_term"])
        target = search_key(values["target_term"])
        ident = _identity(values, key)
        fident = _identity(values, fold_key(key))
        if ident in exact:
            if exact[ident] == target:
                outcome.codes.append("DUPLICATE_IN_FILE")
                outcome.action = "skipped"
                continue
            outcome.codes.append("CONFLICTING_TARGETS")
        elif fident in folded:
            outcome.codes.append("NEAR_DUPLICATE")
        pair = (values["source_language"], values["target_language"])
        own = [key] + [search_key(v) for v in values.get("synonyms") or []]
        own += [search_key(v) for v in values.get("regional_variants") or []]
        for form in own[1:]:
            previous = forms.get((*pair, form))
            if previous is not None and previous != target:
                outcome.codes.append("SYNONYM_COLLISION")
        if forms.get((*pair, key)) not in (None, target) and ident not in exact:
            outcome.codes.append("SYNONYM_COLLISION")
        exact.setdefault(ident, target)
        folded.setdefault(fident, key)
        for form in own:
            forms.setdefault((*pair, form), target)

    def keyed(entries):
        out: dict[tuple, set[str]] = {}
        for entry in entries:
            ident = (
                entry.source_language,
                entry.target_language,
                search_key(entry.source_term),
                domains.canonical_domain(entry.domain) or (entry.domain or "").upper(),
                entry.country or "",
                entry.jurisdiction or "",
            )
            out.setdefault(ident, set()).add(search_key(entry.target_term))
        return out

    draft = keyed(version_entries(db, version))
    published = [v for v in versions_of(db, referential) if v.status == "published"]
    own_published = keyed(e for v in published for e in version_entries(db, v))
    other_versions = [
        db.get(RagReferentialVersion, item["version_id"])
        for item in published_scope(db, tenant_id)
        if item["referential_id"] != referential.id
    ]
    elsewhere = keyed(e for v in other_versions if v is not None for e in version_entries(db, v))
    for outcome, values in items:
        if outcome.action != "accepted":
            continue
        ident = _identity(values, search_key(values["source_term"]))
        target = search_key(values["target_term"])
        if target in draft.get(ident, set()):
            outcome.codes.append("ALREADY_IN_DRAFT")
            outcome.action = "skipped"
            continue
        if ident in own_published:
            known = own_published[ident]
            outcome.codes.append(
                "UNCHANGED_FROM_PUBLISHED" if target in known else "CHANGES_PUBLISHED_TARGET"
            )
        if ident in elsewhere and target not in elsewhere[ident]:
            outcome.codes.append("CONFLICT_WITH_OTHER_REFERENTIAL")


# --- Orchestration -----------------------------------------------------------------------------


def detect_format(data: bytes, declared: str | None) -> str:
    fmt = (declared or "").lower().lstrip(".")
    is_zip = data[:4] == b"PK\x03\x04"
    if fmt in {"", "auto"}:
        fmt = "xlsx" if is_zip else "csv"
    if fmt not in {"csv", "xlsx"}:
        raise ImportFileError("IMPORT_FORMAT_UNSUPPORTED")
    if (fmt == "xlsx") != is_zip:
        raise ImportFileError("IMPORT_FORMAT_MISMATCH")
    return fmt


def import_file(
    db: Session,
    *,
    settings: Any,
    tenant_id: str,
    referential: RagReferential,
    version: RagReferentialVersion,
    data: bytes,
    file_format: str | None,
    actor_id: str | None,
    roles: set[str],
    dry_run: bool = True,
) -> RagImportBatch:
    if referential.tenant_id != tenant_id or version.referential_id != referential.id:
        raise RagAccessError("RAG_VERSION_NOT_FOUND", 404)
    if not roles & allowed_roles(referential.kind, "edit"):
        raise RagAccessError("RAG_ROLE_REQUIRED")
    if version.status != "draft":
        raise RagAccessError("RAG_VERSION_NOT_EDITABLE", 409)
    if not data:
        raise ImportFileError("IMPORT_EMPTY")
    if len(data) > settings.rag_import_max_bytes:
        raise ImportFileError("IMPORT_TOO_LARGE")
    fmt = detect_format(data, file_format)
    reader = read_xlsx if fmt == "xlsx" else read_csv
    header, rows, formula_rows = reader(data, settings.rag_import_max_rows)
    if len(rows) > settings.rag_import_max_rows:
        raise ImportFileError("IMPORT_TOO_MANY_ROWS")
    items, ignored = validate_rows(header, rows, formula_rows)
    detect_duplicates(db, tenant_id, referential, version, items)
    outcomes = [outcome for outcome, _ in items]
    errors = sum(o.action == "rejected" for o in outcomes)
    accepted = [values for outcome, values in items if outcome.action == "accepted"]
    if errors:
        status = "rejected"
    elif dry_run:
        status = "dry_run"
    else:
        status = "applied"
    if status == "applied" and accepted:
        add_entries(db, referential, version, accepted, actor_id, roles)
    report = [o.as_dict() for o in outcomes if o.codes or o.action != "accepted"]
    if ignored:
        report.insert(
            0,
            {
                "row": 1,
                "codes": ["COLUMN_IGNORED"],
                "action": "ignored",
                "severity": "warning",
                "columns": len(ignored),
            },
        )
    batch = RagImportBatch(
        tenant_id=tenant_id,
        referential_id=referential.id,
        version_id=version.id,
        actor_id=actor_id,
        status=status,
        file_format=fmt,
        file_sha256=hashlib.sha256(data).hexdigest(),
        file_size=len(data),
        row_count=len(rows),
        accepted_count=len(accepted) if status != "rejected" else 0,
        skipped_count=sum(o.action == "skipped" for o in outcomes),
        error_count=errors,
        warning_count=sum(o.severity == "warning" for o in outcomes),
        report=report[:5000],
    )
    db.add(batch)
    db.flush()
    return batch


def batch_view(batch: RagImportBatch) -> dict[str, Any]:
    return {
        "import_id": batch.id,
        "referential_id": batch.referential_id,
        "version_id": batch.version_id,
        "status": batch.status,
        "file_format": batch.file_format,
        "file_size": batch.file_size,
        "row_count": batch.row_count,
        "accepted_count": batch.accepted_count,
        "skipped_count": batch.skipped_count,
        "error_count": batch.error_count,
        "warning_count": batch.warning_count,
        "report": batch.report or [],
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
    }
