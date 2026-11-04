"""Paire arabe -> français alignée sur EuroVoc, à partir des libellés Wikidata.

EuroVoc, IATE et EUR-Lex ne contiennent pas l'arabe. Wikidata (licence CC0)
relie des éléments aux descripteurs EuroVoc (propriété P5437, « EuroVoc ID »)
et porte souvent un libellé arabe. Ce convertisseur :

* ne garde que les descripteurs déjà retenus dans ``data/rag-ue/eurovoc`` ;
* prend le terme ARABE de Wikidata (libellé, puis libellés alternatifs comme
  synonymes) et le terme FRANÇAIS officiel d'EuroVoc (jamais celui de
  Wikidata) ;
* reprend le domaine et le microthésaurus de la ligne EuroVoc ;
* refuse les cellules qui ressemblent à une formule de tableur ;
* avec ``--review``, écarte les descripteurs listés (paires rejetées par une
  évaluation automatique) : ils ne sont PAS importables par défaut et restent
  dans la liste de revue humaine, avec leur motif.

Les deux exports Wikidata sont produits par les requêtes SPARQL ci-dessous, sur
https://query.wikidata.org/sparql (format CSV) :

    SELECT ?item ?ev ?ar ?fr WHERE { ?item wdt:P5437 ?ev .
      ?item rdfs:label ?ar . FILTER(LANG(?ar)="ar")
      ?item rdfs:label ?fr . FILTER(LANG(?fr)="fr") }

    SELECT ?ev ?alt WHERE { ?item wdt:P5437 ?ev .
      ?item skos:altLabel ?alt . FILTER(LANG(?alt)="ar") }

Usage :
    python tools/rag_ue/wikidata_ar_to_csv.py --labels wd-ar-fr.csv \\
        --alt wd-ar-alt.csv --retrieved-at 2026-11-03T23:57Z \\
        --eurovoc data/rag-ue/eurovoc --out data/rag-ue/wikidata \\
        --review data/rag-ue/wikidata/revue-evaluation-automatique.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eurovoc_to_csv import (  # noqa: E402
    COLUMNS,
    PROVENANCE_LIMIT,
    SYN_LIMIT,
    _formula_safe,
    write_csv,
)

DESCRIPTOR_RE = re.compile(r"descripteur (\d+)")
QID_RE = re.compile(r"Q(\d+)$")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
OUTPUT = "wikidata-ar-fr.csv"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_eurovoc(directory: Path) -> dict[str, dict]:
    """Descripteur EuroVoc -> terme français, domaine, contexte (lignes retenues)."""
    selection: dict[str, dict] = {}
    for path in sorted(directory.glob("eurovoc-*-fr.csv")):
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                match = DESCRIPTOR_RE.search(row["provenance"])
                if match:
                    selection.setdefault(
                        match.group(1),
                        {
                            "target_term": row["target_term"],
                            "domain": row["domain"],
                            "usage_context": row["usage_context"],
                        },
                    )
    return selection


def _qid(uri: str) -> int:
    match = QID_RE.search(uri or "")
    return int(match.group(1)) if match else sys.maxsize


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def load_review(path: Path | None) -> set[str]:
    """Descripteurs à écarter (colonne ``descriptor`` de la liste de revue)."""
    if path is None:
        return set()
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["descriptor"].strip() for row in csv.DictReader(fh, delimiter=";")}


def build_rows(
    labels: list[dict],
    alts: list[dict],
    selection: dict[str, dict],
    excluded: set[str] | frozenset[str] = frozenset(),
) -> tuple[list[dict], dict]:
    by_descriptor: dict[str, list[dict]] = collections.defaultdict(list)
    for row in labels:
        by_descriptor[row["ev"].strip()].append(row)
    alt_by_descriptor: dict[str, set[str]] = collections.defaultdict(set)
    for row in alts:
        alt_by_descriptor[row["ev"].strip()].add(_clean(row["alt"]))
    stats = collections.Counter()
    rows = []
    for descriptor in sorted(selection, key=int):
        items = by_descriptor.get(descriptor)
        if not items:
            stats["sans_libelle_arabe"] += 1
            continue
        if descriptor in excluded:
            stats["exclus_revue"] += 1
            continue
        concept = selection[descriptor]
        french = concept["target_term"].casefold()
        # Élément principal : celui dont le libellé français est celui d'EuroVoc,
        # sinon le plus ancien (QID le plus petit) ; ordre déterministe.
        items = sorted(items, key=lambda r: (r["fr"].casefold() != french, _qid(r["item"])))
        main = items[0]
        term = _clean(main["ar"])
        if not ARABIC_RE.search(term) or not _formula_safe(term):
            stats["libelle_rejete"] += 1
            continue
        if len(items) > 1:
            stats["plusieurs_elements"] += 1
        candidates = {_clean(r["ar"]) for r in items[1:]} | alt_by_descriptor.get(descriptor, set())
        synonyms, kept = [], 0
        for value in sorted(c for c in candidates if c and c != term):
            if not ARABIC_RE.search(value) or not _formula_safe(value) or "|" in value:
                stats["synonyme_rejete"] += 1
                continue
            if len(" | ".join([*synonyms, value])) > SYN_LIMIT:
                stats["synonyme_tronque"] += 1
                continue
            synonyms.append(value)
            kept += 1
        stats["synonymes"] += kept
        qid = main["item"].rsplit("/", 1)[-1]
        provenance = (
            f"Wikidata {qid} (CC0) pour l'arabe ; EuroVoc 4.24 (CC BY 4.0) pour le français ; "
            f"descripteur {descriptor}"
        )[:PROVENANCE_LIMIT]
        rows.append(
            {
                "source_language": "ar",
                "source_term": term,
                "target_language": "fr",
                "target_term": concept["target_term"],
                "synonyms": " | ".join(synonyms),
                "definition": "",
                "usage_context": concept["usage_context"],
                "domain": concept["domain"],
                "jurisdiction": "",
                "provenance": provenance,
            }
        )
    stats["lignes"] = len(rows)
    stats["descripteurs_retenus"] = len(selection)
    return rows, dict(stats)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--alt", type=Path, required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--eurovoc", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=None)
    args = parser.parse_args(argv)
    with args.labels.open(encoding="utf-8", newline="") as fh:
        labels = list(csv.DictReader(fh))
    with args.alt.open(encoding="utf-8", newline="") as fh:
        alts = list(csv.DictReader(fh))
    selection = load_eurovoc(args.eurovoc)
    excluded = load_review(args.review)
    rows, stats = build_rows(labels, alts, selection, excluded)
    args.out.mkdir(parents=True, exist_ok=True)
    data = write_csv(rows)
    (args.out / OUTPUT).write_bytes(data)
    manifest = {
        "source": "Wikidata (libellés arabes) aligné sur EuroVoc 4.24 (termes français)",
        "licence": "Wikidata : CC0 1.0 ; EuroVoc : CC BY 4.0 (Office des publications de l'UE)",
        "retrieved_at": args.retrieved_at,
        "sparql_endpoint": "https://query.wikidata.org/sparql",
        "inputs_sha256": {"labels": _sha256(args.labels), "alt_labels": _sha256(args.alt)},
        "modifications": (
            "jointure sur la propriété P5437 ; terme français officiel EuroVoc ; "
            "domaine EuroVoc ; synonymes arabes tronqués à 500 caractères ; "
            "descripteurs de la liste de revue écartés (évaluation automatique, "
            "pas une revue humaine)"
        ),
        "review_list": (
            {"file": args.review.name, "descriptors": len(excluded), "sha256": _sha256(args.review)}
            if args.review
            else None
        ),
        "columns": list(COLUMNS),
        "stats": stats,
        "files": {OUTPUT: {"rows": len(rows), "sha256": hashlib.sha256(data).hexdigest()}},
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
