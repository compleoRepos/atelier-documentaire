"""Convertit un export IATE (TBX) en CSV d'import du RAG, une paire xx -> fr par fichier.

Aucun téléchargement : l'export ciblé TBX s'obtient sur https://iate.europa.eu/download-iate
avec un compte EU Login ; il est fourni ici par l'exploitant. Règles conservatrices :

* variantes TBX acceptées : ``termEntry``/``langSet``/``tig``|``ntig`` et TBX v3
  ``conceptEntry``/``langSec``/``termSec`` (espaces de noms ignorés) ;
* un terme est retenu seulement si sa fiabilité IATE (1 à 4) atteint ``--min-reliability``
  (3 par défaut) et s'il n'est ni déprécié, ni remplacé, ni obsolète ;
* une fiche sans terme français retenu est écartée ; le terme français cible est le terme
  privilégié (« preferred ») sinon le plus fiable ; les autres termes retenus de la langue
  source deviennent des synonymes de recherche ;
* chaque ligne trace la fiche IATE, sa fiabilité et la date de l'export (``--export-date``) ;
* entités XML refusées ; aucune valeur pouvant être lue comme une formule de tableur.

Les lignes produites restent des brouillons : validation à quatre yeux obligatoire.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eurovoc_to_csv import PROVENANCE_LIMIT, SYN_LIMIT, _formula_safe, write_csv  # noqa: E402

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
EU_LANGUAGES = (
    "bg cs da de el en es et fi ga hr hu it lt lv mt nl pl pt ro sk sl sv".split()
)  # le français est la cible
EXCLUDED_STATUS = ("deprecat", "supersed", "obsolete")
STATUS_FIELDS = ("administrativeStatus", "normativeAuthorization", "evaluation", "termStatus")
TERM_LIMIT = 500


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse(data: bytes) -> ET.Element:
    if b"<!ENTITY" in data:
        raise ValueError("entité XML refusée")
    return ET.fromstring(data)


def _children(node: ET.Element, *names: str) -> list[ET.Element]:
    return [child for child in node if _local(child.tag) in names]


def _notes(node: ET.Element) -> dict[str, str]:
    """``termNote``/``descrip`` par type, sans descendre dans les sous-sections de langue."""
    found: dict[str, str] = {}
    for child in node.iter():
        if _local(child.tag) in ("termNote", "descrip") and child.get("type"):
            found.setdefault(child.get("type"), " ".join("".join(child.itertext()).split()))
    return found


def _reliability(*sources: dict[str, str]) -> int | None:
    for notes in sources:
        value = notes.get("reliabilityCode", "").strip()
        if value[:1].isdigit():
            return int(value[:1])
    return None


def _terms(lang_section: ET.Element, min_reliability: int) -> list[dict]:
    section_notes = {
        key: value
        for child in lang_section
        if _local(child.tag) in ("descrip", "descripGrp", "termNote")
        for key, value in _notes(child).items()
    }
    out = []
    for group in _children(lang_section, "tig", "ntig", "termSec"):
        term_node = next((n for n in group.iter() if _local(n.tag) == "term"), None)
        term = " ".join("".join(term_node.itertext()).split()) if term_node is not None else ""
        notes = _notes(group)
        status = " ".join(notes.get(key, "") for key in STATUS_FIELDS).casefold()
        reliability = _reliability(notes, section_notes)
        if (
            not term
            or len(term) > TERM_LIMIT
            or not _formula_safe(term)
            or any(word in status for word in EXCLUDED_STATUS)
            or reliability is None
            or reliability < min_reliability
        ):
            continue
        preferred = "preferred" in notes.get("administrativeStatus", "").casefold()
        out.append({"term": term, "reliability": reliability, "preferred": preferred})
    # privilégié d'abord, puis le plus fiable, ordre de l'export conservé sinon
    return sorted(out, key=lambda item: (not item["preferred"], -item["reliability"]))


def _synonyms(terms: list[dict]) -> str:
    kept: list[str] = []
    for item in terms[1:]:
        value = item["term"].replace("|", "/")
        if value.casefold() in {k.casefold() for k in kept} or value == terms[0]["term"]:
            continue
        if len("|".join([*kept, value])) > SYN_LIMIT:
            break
        kept.append(value)
    return "|".join(kept)


def convert(data: bytes, *, min_reliability: int, export_date: str, domain: str) -> dict:
    rows: dict[str, list[dict]] = {lang: [] for lang in EU_LANGUAGES}
    stats = {"concepts": 0, "without_french": 0}
    for concept in _parse(data).iter():
        if _local(concept.tag) not in ("termEntry", "conceptEntry"):
            continue
        stats["concepts"] += 1
        sections = {
            (section.get(XML_LANG) or section.get("lang") or "").lower()[:2]: section
            for section in _children(concept, "langSet", "langSec")
        }
        french = _terms(sections["fr"], min_reliability) if "fr" in sections else []
        if not french:
            stats["without_french"] += 1
            continue
        concept_id = concept.get("id") or "?"
        subject = " ".join(
            value
            for child in _children(concept, "descrip", "descripGrp")
            for key, value in _notes(child).items()
            if key == "subjectField"
        )
        for lang in EU_LANGUAGES:
            source = _terms(sections[lang], min_reliability) if lang in sections else []
            if not source:
                continue
            reliability = min(source[0]["reliability"], french[0]["reliability"])
            provenance = (
                f"IATE, Union européenne, fiche {concept_id}, fiabilité {reliability}, "
                f"export du {export_date}"
            )[:PROVENANCE_LIMIT]
            rows[lang].append(
                {
                    "source_language": lang,
                    "source_term": source[0]["term"],
                    "target_language": "fr",
                    "target_term": french[0]["term"],
                    "synonyms": _synonyms(source),
                    "definition": "",
                    "usage_context": f"IATE, domaine {subject}"[:500] if subject else "IATE",
                    "domain": domain,
                    "jurisdiction": "",
                    "provenance": provenance,
                }
            )
    return {"rows": rows, "stats": stats}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--tbx", required=True, type=Path, help="export IATE (TBX)")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--export-date", required=True, help="date de l'export, AAAA-MM-JJ")
    parser.add_argument("--domain", default="HR", help="domaine du produit (HR, LEGAL, ...)")
    parser.add_argument("--min-reliability", type=int, default=3, choices=(1, 2, 3, 4))
    args = parser.parse_args(argv)
    data = args.tbx.read_bytes()
    result = convert(
        data,
        min_reliability=args.min_reliability,
        export_date=args.export_date,
        domain=args.domain,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    files = {}
    for lang, rows in result["rows"].items():
        if not rows:
            continue
        blob = write_csv(rows)
        name = f"iate-{lang}-fr.csv"
        (args.out / name).write_bytes(blob)
        files[lang] = {
            "file": name,
            "rows": len(rows),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }
    manifest = {
        "source": "IATE (https://iate.europa.eu), export fourni par l'exploitant",
        "export_sha256": hashlib.sha256(data).hexdigest(),
        "export_date": args.export_date,
        "min_reliability": args.min_reliability,
        "domain": args.domain,
        "stats": result["stats"],
        "files": files,
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(
        f"{result['stats']['concepts']} fiches, {result['stats']['without_french']} sans "
        f"français retenu, {sum(f['rows'] for f in files.values())} lignes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
