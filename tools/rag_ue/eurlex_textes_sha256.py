"""Fichier d'empreintes des textes EUR-Lex article par article (``textes-sha256.json``).

Les fichiers ``data/rag-ue/eurlex/eurlex/<CELEX>.jsonl.gz`` sont produits par
``eurlex_extract.py`` ; ``manifest.json`` décrit leur contenu (articles par langue, empreinte du
HTML source) mais pas l'empreinte des fichiers eux-mêmes. Ce fichier la fixe, pour que le
chargement dans DICE refuse tout fichier modifié (``common_library_cli import-legal``).

Sortie déterministe (clés triées, aucune date) ; ``--check`` vérifie sans écrire.

    python tools/rag_ue/eurlex_textes_sha256.py
    python tools/rag_ue/eurlex_textes_sha256.py --check
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "data" / "rag-ue" / "eurlex"
NAME = "textes-sha256.json"


def build(directory: Path = DIRECTORY) -> dict:
    files = {}
    pairs = rows_total = 0
    for path in sorted((directory / "eurlex").glob("*.jsonl.gz")):
        data = path.read_bytes()
        rows = [json.loads(line) for line in gzip.decompress(data).decode("utf-8").splitlines()]
        languages = sorted({row["language"] for row in rows})
        files[path.name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "rows": len(rows),
            "languages": len(languages),
        }
        pairs += len(languages)
        rows_total += len(rows)
    return {
        "format": 1,
        "description": "Empreintes des textes EUR-Lex article par article (un fichier par acte)",
        "acts": len(files),
        "act_language_pairs": pairs,
        "articles_language": rows_total,
        "files": files,
    }


def render(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=DIRECTORY)
    parser.add_argument("--check", action="store_true", help="vérifier sans écrire")
    args = parser.parse_args(argv)
    expected = render(build(args.dir))
    target = args.dir / NAME
    if args.check:
        same = target.is_file() and target.read_text(encoding="utf-8") == expected
        print("OK" if same else "ÉCART")
        return 0 if same else 1
    target.write_text(expected, encoding="utf-8")
    print(f"{target.name} : {json.loads(expected)['articles_language']} articles-langues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
