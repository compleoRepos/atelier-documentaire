"""Ligne de commande d'exploitation de la bibliothèque commune du RAG (hors API).

Exemples (depuis ``backend/``, base désignée par la configuration habituelle) :

    python -m app.rag.common_library_cli import-eurovoc --dir ../data/rag-ue/eurovoc --actor alice
    python -m app.rag.common_library_cli status
    python -m app.rag.common_library_cli transition --name "EuroVoc 4.24 de-fr" --version 1 \
        --action submit --actor alice
    python -m app.rag.common_library_cli transition ... --action validate --actor bob  # autre personne
    python -m app.rag.common_library_cli transition ... --action publish --actor alice
    python -m app.rag.common_library_cli activate --name "EuroVoc 4.24 de-fr" --actor alice

Un import laisse toujours la version en brouillon. Chaque commande est une transaction :
en cas d'erreur, rien n'est écrit. La sortie est un JSON sans contenu terminologique.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from ..core.db import init_db, make_engine, make_session_factory
from ..core.settings import get_settings
from .models import RagReferential
from .storage import common_library as lib
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


def _status(db) -> list[dict]:
    rows = db.query(RagReferential).filter(RagReferential.tenant_id.is_(None)).all()
    out = []
    for referential in sorted(rows, key=lambda r: r.name):
        out.append(
            {
                "name": referential.name,
                "kind": referential.kind,
                "active": referential.active,
                "versions": [
                    {"number": v.number, "status": v.status, "entries": v.entry_count}
                    for v in versions_of(db, referential)
                ],
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
    args = parser.parse_args(argv)

    settings = settings or get_settings()
    engine = make_engine(settings)
    init_db(engine, settings)
    factory = make_session_factory(engine)
    with factory() as db:
        try:
            if args.command == "status":
                return {"ok": True, "referentials": _status(db)}
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
        except lib.CommonLibraryError as exc:
            db.rollback()
            return {"ok": False, "code": exc.code, "detail": exc.detail}


def main(argv: list[str] | None = None) -> int:
    outcome = run(argv)
    print(json.dumps(outcome, ensure_ascii=False, indent=2, default=str))
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
