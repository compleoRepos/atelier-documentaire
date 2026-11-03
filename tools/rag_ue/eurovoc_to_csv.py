#!/usr/bin/env python3
"""EuroVoc (archive XML officielle) -> fichiers CSV d'import des référentiels RAG.

Source : Office des publications de l'Union européenne, EuroVoc, archive ``eurovoc_xml.zip``
(descripteurs ``desc_XX.xml``, non-descripteurs ``uf_XX.xml``, notes ``sn_XX.xml``, rattachement
``desc_thes.xml``). Licence déclarée par les métadonnées officielles du jeu de données
(``eurovoc_metadata.ttl``, ``dcterms:license``) : CC BY 4.0 ; attribution et indication des
modifications portées sur chaque ligne (colonne ``provenance``).

Modifications apportées (à déclarer, CC BY 4.0) : sélection de microthésaurus, mise en paires
« langue -> français », rattachement aux domaines du produit, synonymes tronqués à 500 caractères.
Aucun texte n'est réécrit ni traduit : chaque terme est le libellé officiel de sa langue.

Usage :
    python tools/rag_ue/eurovoc_to_csv.py --zip eurovoc_xml.zip --out data/rag-ue/eurovoc
Sortie : un CSV par paire ``xx-fr`` (séparateur « ; », UTF-8), plus ``manifest.json``.
Les fichiers sont importés en BROUILLON ; la publication exige la validation à quatre yeux.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

EU_LANGUAGES = (
    "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "ga", "hr",
    "hu", "it", "lt", "lv", "mt", "nl", "pl", "pt", "ro", "sk", "sl", "sv",
)  # fmt: skip
TARGET = "fr"

# Microthésaurus retenus -> domaine du produit (ordre = priorité si un descripteur est rattaché
# à plusieurs microthésaurus retenus).
MICROTHESAURI = {
    "4426": "HR",  # relation et droit du travail
    "4421": "PAYROLL",  # administration et rémunération du personnel
    "4416": "HR",  # conditions et organisation du travail
    "4406": "HR",  # emploi
    "4411": "HR",  # marché du travail
    "2836": "HR",  # protection sociale
    "2416": "BANKING",  # institutions financières et crédit
    "2426": "FINANCE",  # investissement et financement
    "2421": "FINANCE",  # libre circulation des capitaux
    "2411": "FINANCE",  # économie monétaire
    "2406": "FINANCE",  # relations monétaires
    "2451": "FINANCE",  # prix
    "4026": "FINANCE",  # gestion comptable
    "2446": "TAX",  # fiscalité
    "2431": "INSURANCE",  # assurance
    "1211": "LEGAL",  # droit civil
    "4016": "LEGAL",  # forme juridique de société
    "2811": "ADMINISTRATION",  # migration
}
VERSION_RE = re.compile(rb'VERSION="([^"]+)"')
SYN_LIMIT = 500
PROVENANCE_LIMIT = 200
TEXT_LIMIT = 4000
COLUMNS = (
    "source_language",
    "source_term",
    "target_language",
    "target_term",
    "synonyms",
    "definition",
    "usage_context",
    "domain",
    "jurisdiction",
    "provenance",
)


def _parse(data: bytes) -> ET.Element:
    # Archive officielle de confiance, mais aucune entité n'est admise (pas d'expansion).
    if b"<!ENTITY" in data:
        raise ValueError("entité XML refusée")
    return ET.fromstring(data)


def _text(node: ET.Element | None) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def _formula_safe(value: str) -> bool:
    return not value.startswith(("=", "+", "@", "\t", "\r", "-"))


def load(zf: zipfile.ZipFile) -> dict:
    names = set(zf.namelist())
    version = VERSION_RE.search(zf.read("desc_thes.xml")[:400])
    data: dict = {"version": version.group(1).decode() if version else "?", "langs": {}}
    links: dict[str, list[str]] = {}
    for record in _parse(zf.read("desc_thes.xml")).iter("RECORD"):
        desc = record.find("DESCRIPTEUR_ID")
        if desc is None or (desc.get("COUNTRY") or "no") != "no":
            continue  # noms de pays : hors périmètre terminologique
        links.setdefault(_text(desc), []).append(_text(record.find("THESAURUS_ID")))
    data["links"] = links
    for lang in EU_LANGUAGES:
        labels, definitions, synonyms, notes = {}, {}, {}, {}
        for record in _parse(zf.read(f"desc_{lang}.xml")).iter("RECORD"):
            key = _text(record.find("DESCRIPTEUR_ID"))
            labels[key] = _text(record.find("LIBELLE"))
            if record.find("DEF") is not None:
                definitions[key] = _text(record.find("DEF"))
        if f"uf_{lang}.xml" in names:
            for record in _parse(zf.read(f"uf_{lang}.xml")).iter("RECORD"):
                key = _text(record.find("DESCRIPTEUR_ID"))
                synonyms[key] = [_text(el) for el in record.iter("UF_EL") if _text(el)]
        if f"sn_{lang}.xml" in names:
            for record in _parse(zf.read(f"sn_{lang}.xml")).iter("RECORD"):
                notes[_text(record.find("DESCRIPTEUR_ID"))] = _text(record.find("SN"))
        data["langs"][lang] = {
            "labels": labels,
            "definitions": definitions,
            "synonyms": synonyms,
            "notes": notes,
        }
    return data


def _synonyms(values: list[str], label: str) -> tuple[str, int]:
    kept, dropped, seen = [], 0, {label.casefold()}
    for value in values:
        value = value.replace("|", "/")
        if value.casefold() in seen or not _formula_safe(value):
            dropped += value.casefold() not in seen
            continue
        candidate = "|".join([*kept, value])
        if len(candidate) > SYN_LIMIT:
            dropped += 1
            continue
        kept.append(value)
        seen.add(value.casefold())
    return "|".join(kept), dropped


def build_rows(data: dict, lang: str) -> tuple[list[dict], dict]:
    src, tgt = data["langs"][lang], data["langs"][TARGET]
    rows, stats = [], {"selected": 0, "missing_label": 0, "unsafe": 0, "synonyms_dropped": 0}
    order = list(MICROTHESAURI)
    for desc in sorted(data["links"], key=lambda d: (len(d), d)):
        retained = [mt for mt in data["links"][desc] if mt in MICROTHESAURI]
        if not retained:
            continue
        stats["selected"] += 1
        retained.sort(key=order.index)
        source, target = src["labels"].get(desc, ""), tgt["labels"].get(desc, "")
        if not source or not target:
            stats["missing_label"] += 1
            continue
        if not (_formula_safe(source) and _formula_safe(target)):
            stats["unsafe"] += 1
            continue
        synonyms, dropped = _synonyms(src["synonyms"].get(desc, []), source)
        stats["synonyms_dropped"] += dropped
        note = tgt["notes"].get(desc, "")
        context = f"EuroVoc (UE), microthésaurus {', '.join(retained)}"
        if note:
            context += f". Note d'application (fr) : {note}"
        provenance = (
            f"EuroVoc {data['version']}, Office des publications de l'UE, CC BY 4.0 ; "
            f"descripteur {desc} ; modifié : sélection, paire {lang}-{TARGET}"
        )
        rows.append(
            {
                "source_language": lang,
                "source_term": source,
                "target_language": TARGET,
                "target_term": target,
                "synonyms": synonyms,
                "definition": tgt["definitions"].get(desc, "")[:TEXT_LIMIT],
                "usage_context": context[:TEXT_LIMIT],
                "domain": MICROTHESAURI[retained[0]],
                # Équivalents linguistiques généraux, non liés à une juridiction : une entrée
                # portant une juridiction est écartée (JURISDICTION_UNKNOWN) tant que le document
                # n'en déclare pas une identique. Réservé aux définitions juridiques des actes.
                "jurisdiction": "",
                "provenance": provenance[:PROVENANCE_LIMIT],
            }
        )
    return rows, stats


def write_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, delimiter=";", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    archive = args.zip.read_bytes()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        data = load(zf)
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "EuroVoc, Office des publications de l'Union européenne",
        "version": data["version"],
        "licence": "CC BY 4.0 (dcterms:license, eurovoc_metadata.ttl)",
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "microthesauri": MICROTHESAURI,
        "modifications": "sélection de microthésaurus ; paires langue->fr ; domaines du produit ; "
        "synonymes tronqués à 500 caractères",
        "files": {},
    }
    for lang in EU_LANGUAGES:
        if lang == TARGET:
            continue
        rows, stats = build_rows(data, lang)
        payload = write_csv(rows)
        name = f"eurovoc-{lang}-{TARGET}.csv"
        (args.out / name).write_bytes(payload)
        manifest["files"][name] = {
            "rows": len(rows),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            **stats,
        }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    total = sum(item["rows"] for item in manifest["files"].values())
    print(f"EuroVoc {data['version']} : {len(manifest['files'])} fichiers, {total} lignes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
