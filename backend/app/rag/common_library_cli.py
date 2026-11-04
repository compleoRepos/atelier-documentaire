"""Ligne de commande d'exploitation de la bibliothèque commune du RAG (hors API).

Exemples (depuis ``backend/``, base désignée par la configuration habituelle) :

    python -m app.rag.common_library_cli import-eurovoc --dir ../data/rag-ue/eurovoc --actor alice
    python -m app.rag.common_library_cli status
    python -m app.rag.common_library_cli transition --name "EuroVoc 4.24 de-fr" --version 1 \
        --action submit --actor alice
    python -m app.rag.common_library_cli transition ... --action validate --actor bob  # autre personne
    python -m app.rag.common_library_cli transition ... --action publish --actor alice
    python -m app.rag.common_library_cli activate --name "EuroVoc 4.24 de-fr" --actor alice
    python -m app.rag.common_library_cli import-legal --dir ../data/rag-ue/eurlex --actor alice
    python -m app.rag.common_library_cli legal-search --query "durée maximale hebdomadaire" \
        --language fr

Un import laisse toujours la version en brouillon. Chaque commande est une transaction :
en cas d'erreur, rien n'est écrit. La sortie est un JSON sans contenu terminologique ; seule
``legal-search`` (lecture seule) renvoie des extraits de textes publics du Journal officiel.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path

from ..core.db import init_db, make_engine, make_session_factory
from ..core.settings import get_settings
from .models import RagReferential
from .storage import common_library as lib
from .storage import legal_library as legal
from .storage.repository import versions_of


def _eurovoc_files(directory: Path) -> list[tuple[str, str, bytes]]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for name, meta in sorted(manifest["files"].items()):
        data = (directory / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise lib.CommonLibraryError("MANIFEST_MISMATCH", {"file": name})
        pair = name.removeprefix("eurovoc-").removesuffix(".csv")
        out.append((f"EuroVoc {manifest['version']} {pair}", name, data))
    return out


LEGAL_NAME = "EUR-Lex droit du travail UE textes"
LEGAL_CHECKSUMS = "textes-sha256.json"


def _legal_texts(directory: Path) -> list[dict]:
    """Textes EUR-Lex article par article, après double contrôle d'intégrité.

    1. empreinte SHA-256 et nombre de lignes de chaque fichier (``textes-sha256.json``) ;
    2. recoupement avec ``manifest.json`` : actes attendus, nombre d'articles par langue et
       empreinte du HTML source de chaque ligne. Un seul écart arrête tout, avant écriture.
    """
    checksums = json.loads((directory / LEGAL_CHECKSUMS).read_text(encoding="utf-8"))
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    acts = manifest["acts"]
    files = checksums["files"]
    if sorted(name.removesuffix(".jsonl.gz") for name in files) != sorted(acts):
        raise lib.CommonLibraryError("MANIFEST_MISMATCH", {"file": LEGAL_CHECKSUMS})
    texts: list[dict] = []
    for name, meta in sorted(files.items()):
        data = (directory / "eurlex" / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise lib.CommonLibraryError("MANIFEST_MISMATCH", {"file": name})
        rows = [json.loads(line) for line in gzip.decompress(data).decode("utf-8").splitlines()]
        celex = name.removesuffix(".jsonl.gz")
        if len(rows) != meta["rows"] or any(row.get("celex") != celex for row in rows):
            raise lib.CommonLibraryError("MANIFEST_MISMATCH", {"file": name})
        title = acts[celex]["title"]
        grouped: OrderedDict[str, list[dict]] = OrderedDict()
        for row in rows:
            grouped.setdefault(row["language"], []).append(row)
        for language, items in grouped.items():
            expected = acts[celex]["languages"].get(language) or {}
            if expected.get("articles") != len(items) or any(
                row.get("html_sha256") != expected.get("html_sha256") for row in items
            ):
                raise lib.CommonLibraryError(
                    "MANIFEST_MISMATCH", {"file": name, "language": language}
                )
            texts.append(
                {
                    "official_reference": f"{title} (CELEX {celex})",
                    "language": language,
                    "country": "EU",
                    "jurisdiction": "EU",
                    "legal_domain": "HR",
                    "text_type": "regulation" if title.startswith("Règlement") else "directive",
                    "text_version": f"JO texte initial html:{expected['html_sha256'][:16]}",
                    "official_source": items[0].get("source"),
                    "passages": [
                        {
                            "article_ref": row["article"],
                            "text": f"{row['title']}\n{row['text']}"
                            if row.get("title")
                            else row["text"],
                        }
                        for row in items
                    ],
                }
            )
    return texts


def _status(db) -> list[dict]:
    rows = db.query(RagReferential).filter(RagReferential.tenant_id.is_(None)).all()
    out = []
    for referential in sorted(rows, key=lambda r: r.name):
        versions = [
            {"number": v.number, "status": v.status, "entries": v.entry_count}
            for v in versions_of(db, referential)
        ]
        if referential.kind == legal.LEGAL_KIND:
            for item, version in zip(versions, versions_of(db, referential), strict=True):
                item.update(legal.counts(db, version))
        out.append(
            {
                "name": referential.name,
                "kind": referential.kind,
                "active": referential.active,
                "versions": versions,
            }
        )
    return out


def run(argv: list[str] | None = None, *, settings=None) -> dict:
    parser = argparse.ArgumentParser(prog="common_library_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("import")
    one.add_argument("--name", required=True)
    one.add_argument("--kind", default="linguistic")
    one.add_argument("--languages", required=True, help="codes séparés par des virgules")
    one.add_argument("--domain")
    one.add_argument("--jurisdiction")
    one.add_argument("--actor", required=True)
    one.add_argument("files", nargs="+", type=Path)
    eurovoc = sub.add_parser("import-eurovoc")
    eurovoc.add_argument("--dir", required=True, type=Path)
    eurovoc.add_argument("--actor", required=True)
    move = sub.add_parser("transition")
    move.add_argument("--name", required=True)
    move.add_argument("--version", required=True, type=int)
    move.add_argument(
        "--action", required=True, choices=("submit", "reject", "validate", "publish", "retire")
    )
    move.add_argument("--actor", required=True)
    move.add_argument("--comment")
    for command in ("activate", "deactivate"):
        toggle = sub.add_parser(command)
        toggle.add_argument("--name", required=True)
        toggle.add_argument("--actor", required=True)
    sub.add_parser("status")
    texts = sub.add_parser("import-legal")
    texts.add_argument("--dir", required=True, type=Path)
    texts.add_argument("--name", default=LEGAL_NAME)
    texts.add_argument("--actor", required=True)
    find = sub.add_parser("legal-search")
    find.add_argument("--query", required=True)
    find.add_argument("--language")
    find.add_argument("--reference", help="filtre sur la référence officielle (ex. 2003/88)")
    find.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    settings = settings or get_settings()
    engine = make_engine(settings)
    init_db(engine, settings)
    factory = make_session_factory(engine)
    with factory() as db:
        try:
            if args.command == "status":
                return {"ok": True, "referentials": _status(db)}
            if args.command == "legal-search":
                found = legal.search(
                    db, args.query, language=args.language, reference=args.reference,
                    limit=args.limit,
                )  # fmt: skip
                return {"ok": True, **found}
            actor = lib.resolve_actor(db, args.actor)
            if args.command == "import":
                referential = lib.get_or_create(
                    db,
                    name=args.name,
                    kind=args.kind,
                    languages=args.languages.split(","),
                    actor_id=actor,
                    domain=args.domain,
                    jurisdiction=args.jurisdiction,
                )
                files = [(path.name, path.read_bytes()) for path in args.files]
                result = [lib.import_draft(db, settings, referential=referential, files=files,
                                           actor_id=actor).__dict__]  # fmt: skip
            elif args.command == "import-eurovoc":
                result = []
                for name, filename, data in _eurovoc_files(args.dir):
                    source = filename.split("-")[1]
                    referential = lib.get_or_create(
                        db,
                        name=name,
                        kind="linguistic",
                        languages=[source, "fr"],
                        actor_id=actor,
                        jurisdiction="EU",
                    )
                    outcome = lib.import_draft(
                        db, settings, referential=referential, files=[(filename, data)],
                        actor_id=actor,
                    )  # fmt: skip
                    result.append({"name": name, **outcome.__dict__})
            elif args.command == "import-legal":
                items = _legal_texts(args.dir)
                languages = sorted({item["language"] for item in items})
                referential = lib.get_or_create(
                    db,
                    name=args.name,
                    kind=legal.LEGAL_KIND,
                    languages=languages,
                    actor_id=actor,
                    domain="HR",
                    jurisdiction="EU",
                )
                outcome = legal.import_legal_draft(
                    db, referential=referential, texts=items, actor_id=actor
                )
                result = {"name": referential.name, **outcome.__dict__}
            elif args.command == "transition":
                referential = lib.common_referential(db, args.name)
                if referential is None:
                    raise lib.CommonLibraryError("REFERENTIAL_NOT_FOUND")
                version = lib.apply_transition(
                    db,
                    referential=referential,
                    number=args.version,
                    action=args.action,
                    actor_id=actor,
                    comment=args.comment,
                )
                result = {"name": referential.name, "number": version.number,
                          "status": version.status}  # fmt: skip
            else:
                referential = lib.common_referential(db, args.name)
                if referential is None:
                    raise lib.CommonLibraryError("REFERENTIAL_NOT_FOUND")
                lib.set_active(
                    db, referential=referential, active=args.command == "activate", actor_id=actor
                )
                result = {"name": referential.name, "active": referential.active}
            db.commit()
            return {"ok": True, "result": result}
        except (lib.CommonLibraryError, legal.LegalLibraryError) as exc:
            db.rollback()
            return {"ok": False, "code": exc.code, "detail": exc.detail}


def main(argv: list[str] | None = None) -> int:
    outcome = run(argv)
    print(json.dumps(outcome, ensure_ascii=False, indent=2, default=str))
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
