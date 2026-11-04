"""Charger la base RAG UE dans la bibliothèque commune de DICE, en une commande.

Le script enchaîne, avec l'outil d'exploitation existant (``app.rag.common_library_cli``) et
sans le modifier :

1. le contrôle d'intégrité de chaque fichier (SHA-256 des manifestes ``data/rag-ue/*/manifest.json``) ;
2. l'import en brouillon : EuroVoc (23 paires vers le français), définitions EUR-Lex du droit du
   travail (22 paires), paire arabe-français alignée sur EuroVoc (la liste de revue n'est jamais
   importée), et les textes du droit du travail de l'UE article par article (25 actes, toutes
   langues disponibles ; référentiel ``regulatory``, empreinte de chaque fichier vérifiée) ;
3. le circuit à quatre yeux : soumission par l'auteur, validation par une **autre** personne,
   publication, puis activation.

Il est idempotent : un référentiel déjà présent n'est pas réimporté, une version déjà publiée
n'est pas retouchée. Il n'affiche que des comptes et des codes, jamais de contenu terminologique.
Les textes juridiques sont consultables (lecture seule) par ``common_library_cli legal-search`` ;
ils ne sont jamais injectés dans la traduction. ``--sans-textes-juridiques`` les exclut.
Chaque étape est une transaction : en cas d'erreur, l'étape en cours n'écrit rien et le script
s'arrête (code de retour 1).

Usage (racine du dépôt, ou conteneur ``api`` : voir VERSION-FINALE-DICE.md) :

    python tools/rag_ue/charger_dice_ue.py --author admin --validator relecteur
    python tools/rag_ue/charger_dice_ue.py --status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.rag.common_library_cli import LEGAL_CHECKSUMS, LEGAL_NAME, run  # noqa: E402

WIKIDATA_NAME = "Wikidata EuroVoc ar-fr"


class LoadError(RuntimeError):
    def __init__(self, step: str, **detail) -> None:
        super().__init__(step)
        self.payload = {"ok": False, "step": step, **detail}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check(path: Path, expected: str) -> None:
    if not path.is_file():
        raise LoadError("FILE_MISSING", file=path.name)
    if _sha256(path) != expected:
        raise LoadError("MANIFEST_MISMATCH", file=path.name)


def plan(data_dir: Path) -> dict:
    """Référentiels attendus, fichiers à importer et contrôle d'intégrité préalable."""
    eurovoc_dir = data_dir / "eurovoc"
    eurovoc = json.loads((eurovoc_dir / "manifest.json").read_text(encoding="utf-8"))
    eurovoc_names = []
    for name, meta in sorted(eurovoc["files"].items()):
        _check(eurovoc_dir / name, meta["sha256"])
        pair = name.removeprefix("eurovoc-").removesuffix(".csv")
        eurovoc_names.append(f"EuroVoc {eurovoc['version']} {pair}")

    eurlex_dir = data_dir / "eurlex"
    eurlex = json.loads((eurlex_dir / "manifest.json").read_text(encoding="utf-8"))
    definitions = []
    for source, meta in sorted(eurlex["definitions"].items()):
        if not meta.get("file") or not meta.get("rows"):
            continue
        path = eurlex_dir / "definitions" / meta["file"]
        _check(path, meta["sha256"])
        definitions.append((f"EUR-Lex définitions {source}-fr", f"{source},fr", path))

    wikidata_dir = data_dir / "wikidata"
    wikidata = json.loads((wikidata_dir / "manifest.json").read_text(encoding="utf-8"))
    arabic_meta = wikidata["files"]["wikidata-ar-fr.csv"]
    arabic = wikidata_dir / "wikidata-ar-fr.csv"
    _check(arabic, arabic_meta["sha256"])
    legal = json.loads((eurlex_dir / LEGAL_CHECKSUMS).read_text(encoding="utf-8"))
    for name, meta in sorted(legal["files"].items()):
        _check(eurlex_dir / "eurlex" / name, meta["sha256"])
    return {
        "eurovoc_dir": eurovoc_dir,
        "eurovoc_names": eurovoc_names,
        "definitions": definitions,
        "arabic": (WIKIDATA_NAME, "ar,fr", arabic),
        "legal": (LEGAL_NAME, eurlex_dir),
    }


def expected_names(todo: dict, *, legal: bool = True) -> list[str]:
    names = [*todo["eurovoc_names"], *(name for name, _, _ in todo["definitions"])]
    names.append(todo["arabic"][0])
    if legal:
        names.append(todo["legal"][0])
    return names


def _call(argv: list[str], *, settings=None) -> dict:
    outcome = run(argv, settings=settings)
    if not outcome.get("ok"):
        name = argv[argv.index("--name") + 1] if "--name" in argv else None
        raise LoadError(argv[0], name=name, code=outcome.get("code"), detail=outcome.get("detail"))
    return outcome


def _status(settings=None) -> dict[str, dict]:
    return {item["name"]: item for item in _call(["status"], settings=settings)["referentials"]}


def summary(expected: list[str], settings=None) -> dict:
    current = _status(settings)
    published = active = entries = 0
    legal = {"legal_texts": 0, "legal_passages": 0, "legal_acts": 0, "legal_languages": 0}
    missing = []
    for name in expected:
        item = current.get(name)
        if item is None:
            missing.append(name)
            continue
        latest = max(item["versions"], key=lambda v: v["number"]) if item["versions"] else None
        if latest and latest["status"] == "published":
            published += 1
            entries += int(latest["entries"] or 0)
            for key in legal:
                legal[key] += int(latest.get(key) or 0)
        active += int(bool(item["active"]))
    return {
        "expected": len(expected),
        "present": len(expected) - len(missing),
        "published": published,
        "active": active,
        "published_entries": entries,
        "published_legal": legal,
        "missing": missing,
    }


def load(data_dir: Path, author: str, validator: str, *, settings=None, legal: bool = True) -> dict:
    if author.strip().lower() == validator.strip().lower():
        raise LoadError("FOUR_EYES_REQUIRED", detail="--author et --validator doivent différer")
    todo = plan(data_dir)
    expected = expected_names(todo, legal=legal)

    imported = 0
    current = _status(settings)
    present = [name for name in todo["eurovoc_names"] if name in current]
    if not present:
        _call(
            ["import-eurovoc", "--dir", str(todo["eurovoc_dir"]), "--actor", author],
            settings=settings,
        )
        imported += len(todo["eurovoc_names"])
    elif len(present) != len(todo["eurovoc_names"]):
        raise LoadError(
            "EUROVOC_PARTIAL", present=len(present), expected=len(todo["eurovoc_names"])
        )
    for name, languages, path in [*todo["definitions"], todo["arabic"]]:
        if name in current:
            continue
        _call(
            ["import", "--name", name, "--languages", languages, "--actor", author, str(path)],
            settings=settings,
        )
        imported += 1
    legal_name, legal_dir = todo["legal"]
    if legal and legal_name not in current:
        _call(
            ["import-legal", "--dir", str(legal_dir), "--name", legal_name, "--actor", author],
            settings=settings,
        )
        imported += 1

    moves = {"draft": ("submit", "validate", "publish"), "in_review": ("validate", "publish"),
             "validated": ("publish",)}  # fmt: skip
    transitions = activations = 0
    current = _status(settings)
    for name in expected:
        item = current[name]
        latest = max(item["versions"], key=lambda v: v["number"])
        for action in moves.get(latest["status"], ()):
            actor = validator if action == "validate" else author
            _call(
                ["transition", "--name", name, "--version", str(latest["number"]),
                 "--action", action, "--actor", actor],
                settings=settings,
            )  # fmt: skip
            transitions += 1
        if not item["active"]:
            _call(["activate", "--name", name, "--actor", author], settings=settings)
            activations += 1
    return {
        "ok": True,
        "imported_referentials": imported,
        "transitions": transitions,
        "activations": activations,
        **summary(expected, settings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Charger la base RAG UE dans DICE.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "rag-ue")
    parser.add_argument("--author", help="utilisateur actif qui importe, soumet et publie")
    parser.add_argument("--validator", help="autre utilisateur actif qui valide (quatre yeux)")
    parser.add_argument("--status", action="store_true", help="afficher l'état sans rien écrire")
    parser.add_argument(
        "--sans-textes-juridiques",
        action="store_true",
        help="ne pas charger les textes EUR-Lex article par article (référentiel regulatory)",
    )
    args = parser.parse_args(argv)
    legal = not args.sans_textes_juridiques
    try:
        if args.status:
            result = {"ok": True, **summary(expected_names(plan(args.data_dir), legal=legal))}
        else:
            if not args.author or not args.validator:
                parser.error("--author et --validator sont requis (sauf avec --status)")
            result = load(args.data_dir, args.author, args.validator, legal=legal)
    except LoadError as exc:
        print(json.dumps(exc.payload, ensure_ascii=False, indent=2, default=str))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
