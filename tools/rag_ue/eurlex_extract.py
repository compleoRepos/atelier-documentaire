#!/usr/bin/env python3
"""EUR-Lex / CELLAR (HTML du Journal officiel) -> articles par langue et définitions alignées.

Entrée : fichiers ``<CELEX>_<langue>.html.gz`` (téléchargés depuis CELLAR, langue vérifiée).
Sorties :
* ``eurlex/<CELEX>.jsonl.gz`` : un enregistrement par (langue, article) : numéro, titre, texte ;
* ``definitions/eurlex-<langue>-fr.csv`` : définitions légales alignées vers le français, au
  format d'import des référentiels (juridiction ``EU``) ;
* ``manifest.json`` : empreintes, comptes et écarts par acte et par langue.

Source : © Union européenne, https://eur-lex.europa.eu/ ; réutilisation autorisée avec mention
de la source (avis juridique EUR-Lex, décision 2011/833/UE). Seuls les textes publiés au Journal
officiel font foi. Aucun texte n'est réécrit : extraction et découpage uniquement.

Règles prudentes : un article n'est retenu que si son numéro est reconnu dans la langue ; une
définition n'est alignée que si l'article a exactement les mêmes points, chacun avec un terme
entre guillemets, dans la langue source et en français ; sinon l'article est écarté et compté.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sys
from pathlib import Path

from lxml import html as lxml_html

TARGET = "fr"
NUM = r"(\d+[a-z]?)"
HEADINGS = {
    "bg": rf"Член\s+{NUM}",
    "cs": rf"Článek\s+{NUM}",
    "da": rf"Artikel\s+{NUM}",
    "de": rf"Artikel\s+{NUM}",
    "el": rf"Άρθρο\s+{NUM}",
    "en": rf"Article\s+{NUM}",
    "es": rf"Artículo\s+{NUM}",
    "et": rf"Artikkel\s+{NUM}",
    "fi": rf"{NUM}\s+artikla",
    "fr": rf"Article\s+({NUM[1:-1]}|premier)",
    "ga": rf"Airteagal\s+{NUM}",
    "hr": rf"Članak\s+{NUM}\.?",
    "hu": rf"{NUM}\.?\s*cikk",  # « 4 cikk » sans point : coquille du texte officiel
    "it": rf"Articolo\s+{NUM}",
    "lt": rf"{NUM}\s+straipsnis?",  # « 27 straipsni » : coquille du texte officiel
    "lv": rf"{NUM}\.\s*pants",
    "mt": rf"(?:L-)?Artikolu\s+{NUM}",
    "nl": rf"Artikel\s+{NUM}",
    "pl": rf"Artykuł\s+{NUM}",
    "pt": r"Artigo\s+(\d+)(?:\.?\s*[oº°])?",  # « 1.o », « 1.º », « 1o »
    "ro": rf"Articolul\s+{NUM}",
    "sk": rf"Článok\s+{NUM}",
    "sl": rf"Člen\s+{NUM}",
    "sv": rf"Artikel\s+{NUM}",
}
COMPILED = {lang: re.compile(rf"^{rx}\.?$", re.IGNORECASE) for lang, rx in HEADINGS.items()}
# Fin du dispositif dans le format hérité (lieu et date de signature, annexes).
PLACES = re.compile(
    r"(brux|bruss|brüss|brys|brisel|bruksel|brüssz|briuse|luxem|lussem|luksem|strasb|straßb|"
    r"strazb|štrasb|estrasb|strasbur|страсбург|брюксел|люксембург|στρασβο|βρυξέλλ|λουξεμβο)",
    re.IGNORECASE,
)
YEAR = re.compile(r"\b(19|20)\d{2}\b")
# Intitulé d'annexe dans les 24 langues (fin du dispositif dans le format hérité).
ANNEX = re.compile(
    r"^(ANNEXE?|ANHANG|ALLEGATO|ANEXO|BIJLAGE|BILAG|BILAGA|LIITE|LISA|MELLÉKLET|PRIEDAS|"
    r"PIELIKUMS|ZAŁĄCZNIK|PŘÍLOHA|PRÍLOHA|PRILOGA|PRILOG|ANEXA|ПРИЛОЖЕНИЕ|ΠΑΡΑΡΤΗΜΑ|ANNESS|"
    r"IARSCRÍBHINN)\b",
    re.IGNORECASE,
)
POINT = re.compile(r"^\(?([0-9]{1,2}|[a-z]{1,2}|[а-я]{1,2}|[α-ω]{1,3})[\.\)]\s*(.*)$", re.DOTALL)
LABEL_ONLY = re.compile(r"^\(?([0-9]{1,2}|[a-z]{1,2}|[а-я]{1,2}|[α-ω]{1,3})[\.\)]$")
# Énumérations cyrillique (bg) et grecque (el) : correspondance par rang avec a), b), c)...
_LATIN = "abcdefghijklmnopqrstuvwxyz"
_CYRILLIC = "абвгдежзийклмнопрстуфхцчшщ"
_GREEK = "α β γ δ ε στ ζ η θ ι ια ιβ ιγ ιδ ιε ιστ ιζ ιη ιθ κ".split()
LABELS = {
    **dict(zip(_CYRILLIC, _LATIN, strict=True)),
    **dict(zip(_GREEK, _LATIN[: len(_GREEK)], strict=True)),
}
# Forme sans guillemets (« a) arbetsschema: ... ») : terme court suivi de deux-points.
TERM_COLON = re.compile(r"^([^:;«»„“”\"]{2,80}?)\s*:\s+(.+)$", re.DOTALL)
# Guillemets par paires ouvrant/fermant : l'apostrophe typographique (« groupe d’entreprises »)
# n'est jamais un guillemet fermant.
_PAIRS = (
    ("«", "»"),
    ("„", "“”"),
    ("“", "”"),
    ('"', '"'),
    ("”", "”"),
    ("‘", "’"),
    ("‚", "‘’"),
    ("»", "«"),
)
QUOTED = re.compile(
    "^(?:"
    + "|".join(
        f"{re.escape(o)}\\s*(?P<t{k}>[^{re.escape(c)}]{{1,160}}?)\\s*[{re.escape(c)}]"
        for k, (o, c) in enumerate(_PAIRS)
    )
    + ")\\s*[:,–-]?\\s*(?P<rest>.*)$",
    re.DOTALL,
)
TITLE_EXCLUDED = re.compile(r"([.;:,]$|^\(?[0-9a-z]{1,3}[.)])")
EUR_LEX = "https://eur-lex.europa.eu/legal-content/{lang}/TXT/?uri=CELEX:{celex}"


def _norm(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _own_text(p) -> str:
    """Texte propre d'un paragraphe : le HTML hérité imbrique des ``<p>`` mal fermés."""
    parts = [p.text or ""]
    for child in p:
        if child.tag != "p":
            parts.append(child.text_content())
        parts.append(child.tail or "")
    return _norm("".join(parts))


def _paragraphs(root) -> list[str]:
    return [t for t in (_own_text(p) for p in root.iter("p")) if t]


def _end_of_enacting_terms(text: str) -> bool:
    words = text.split()
    if len(words) < 25 and YEAR.search(text) and PLACES.search(text):
        return True
    return len(words) <= 4 and bool(ANNEX.match(text))


def _number(match: re.Match) -> str:
    value = match.group(1).lower()
    return "1" if value == "premier" else value


def _follows(previous: str | None, number: str) -> bool:
    if previous is None:
        return number == "1"
    base = int(re.match(r"\d+", previous).group())
    digits = int(re.match(r"\d+", number).group())
    return digits == base + 1 or (digits == base and number > previous)


def articles(data: bytes, lang: str) -> tuple[list[dict], str]:
    # Décodage UTF-8 explicite : sans déclaration, lxml lirait le HTML hérité en latin-1.
    root = lxml_html.fromstring(data, parser=lxml_html.HTMLParser(encoding="utf-8"))
    out: list[dict] = []
    subdivisions = root.xpath('//div[@class="eli-subdivision"][starts-with(@id,"art_")]')
    if subdivisions:
        for div in subdivisions:
            if "." in div.get("id", ""):
                continue  # sous-subdivisions (titres) : déjà incluses
            paragraphs = _paragraphs(div)
            if not paragraphs or not COMPILED[lang].match(paragraphs[0]):
                continue
            number = _number(COMPILED[lang].match(paragraphs[0]))
            out.append({"article": number, "paragraphs": paragraphs[1:]})
        layout = "eli"
    else:
        # Format hérité : 1) intitulés retenus seulement en séquence (1, 2, 2a, 3...) ; un
        # « Article 118 » cité isolément reste du texte ; 2) la fin du dispositif (lieu et date,
        # annexe) n'est cherchée qu'après le dernier article.
        # 3) rupture de numérotation dans le texte (doublon, saut) : arrêt net ; la suite est
        # écartée plutôt qu'attribuée à tort, et l'anomalie est signalée dans le manifeste.
        # Un intitulé hors séquence suivi plus loin de l'article attendu est une citation (texte).
        paragraphs = _paragraphs(root)
        found = [
            (index, _number(match))
            for index, text in enumerate(paragraphs)
            if (match := COMPILED[lang].match(text))
        ]
        heads: list[tuple[int, str]] = []
        limit = len(paragraphs)
        for position, (index, number) in enumerate(found):
            previous = heads[-1][1] if heads else None
            if _follows(previous, number):
                heads.append((index, number))
            elif heads and not any(_follows(previous, later) for _, later in found[position:]):
                limit, layout_break = index, f"rupture après l'article {previous} : {number}"
                break
        for position, (index, number) in enumerate(heads):
            stop = heads[position + 1][0] if position + 1 < len(heads) else limit
            body = paragraphs[index + 1 : stop]
            if position + 1 == len(heads):
                for cut, text in enumerate(body):
                    if _end_of_enacting_terms(text):
                        body = body[:cut]
                        break
            out.append({"article": number, "paragraphs": body})
        layout = "legacy" if limit == len(paragraphs) else f"legacy ({layout_break})"
    for item in out:
        paragraphs = item.pop("paragraphs")
        # Le texte garde tout le corps ; le titre n'est qu'une étiquette (beaucoup d'actes anciens
        # n'en ont pas : un premier alinéa court ne doit pas être retiré du texte).
        first = paragraphs[0] if paragraphs else ""
        titled = 0 < len(first) < 150 and not TITLE_EXCLUDED.search(first)
        item["title"] = first if titled else ""
        item["text"] = "\n".join(paragraphs[1:] if titled else paragraphs)
    seen, unique = set(), []
    for item in out:
        if item["article"] not in seen:  # articles modificatifs citant d'autres actes : 1er gardé
            seen.add(item["article"])
            unique.append(item)
    return unique, layout


def _lines(text: str) -> list[str]:
    merged: list[str] = []
    for line in text.split("\n"):
        if merged and LABEL_ONLY.match(merged[-1]):
            merged[-1] = f"{merged[-1]} {line}"  # étiquette seule sur sa ligne (bg, hr, ro)
        else:
            merged.append(line)
    return merged


def definitions(article: dict) -> dict[str, tuple[str, str]] | None:
    candidates = []
    for line in _lines(article["text"]):
        point = POINT.match(line)
        if point:
            label = point.group(1).lower()
            candidates.append((LABELS.get(label, label), point.group(2).strip()))
    quoted_form = any(QUOTED.match(body) for _, body in candidates)
    points: dict[str, tuple[str, str]] = {}
    for label, body in candidates:
        found = QUOTED.match(body)
        if not found and not quoted_form:
            found = TERM_COLON.match(body)
            if found and len(found.group(1).split()) > 8:
                found = None
        if not found:
            continue
        if label in points:
            return None  # numérotation ambiguë : écarté
        if found.re is QUOTED:
            term = next(v for k, v in found.groupdict().items() if k != "rest" and v)
            points[label] = (_norm(term), _norm(found.group("rest")))
        else:
            points[label] = (_norm(found.group(1)), _norm(found.group(2)))
    return points or None


def _formula_safe(value: str) -> bool:
    return not value.startswith(("=", "+", "@", "-", "\t", "\r"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--html", required=True, type=Path, nargs="+", help="répertoires source")
    parser.add_argument("--acts", required=True, type=Path, help="JSON : CELEX -> intitulé")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    titles = json.loads(args.acts.read_text(encoding="utf-8"))
    sources: dict[str, dict[str, Path]] = {}
    for directory in args.html:
        for path in sorted(directory.glob("*.html.gz")):
            celex, lang = path.name.removesuffix(".html.gz").rsplit("_", 1)
            sources.setdefault(celex, {})[lang] = path
    (args.out / "eurlex").mkdir(parents=True, exist_ok=True)
    (args.out / "definitions").mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "source": "EUR-Lex / CELLAR, Office des publications de l'Union européenne",
        "licence": "© Union européenne ; réutilisation avec mention de la source "
        "(avis juridique EUR-Lex, décision 2011/833/UE) ; seuls les textes du JO font foi",
        "acts": {},
        "definitions": {},
    }
    rows_by_lang: dict[str, list[dict]] = {}
    for celex in sorted(sources):
        if celex not in titles:
            continue
        records, act = [], {"title": titles[celex], "languages": {}}
        parsed = {}
        for lang, path in sorted(sources[celex].items()):
            raw = gzip.decompress(path.read_bytes())
            items, layout = articles(raw, lang)
            parsed[lang] = items
            act["languages"][lang] = {
                "articles": len(items),
                "layout": layout,
                "html_sha256": hashlib.sha256(raw).hexdigest(),
            }
            for item in items:
                records.append(
                    {
                        "celex": celex,
                        "language": lang,
                        "article": item["article"],
                        "title": item["title"],
                        "text": item["text"],
                        "source": EUR_LEX.format(lang=lang.upper(), celex=celex),
                        "html_sha256": act["languages"][lang]["html_sha256"],
                    }
                )
        reference = [a["article"] for a in parsed.get(TARGET, [])]
        for lang, items in parsed.items():
            act["languages"][lang]["same_articles_as_fr"] = [
                a["article"] for a in items
            ] == reference
        payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode()
        blob = gzip.compress(payload, mtime=0)
        (args.out / "eurlex" / f"{celex}.jsonl.gz").write_bytes(blob)
        act["records"] = len(records)
        act["file_sha256"] = hashlib.sha256(blob).hexdigest()
        # Définitions : alignement strict point à point avec le français.
        french = {a["article"]: definitions(a) for a in parsed.get(TARGET, [])}
        for lang, items in parsed.items():
            if lang == TARGET:
                continue
            stats = manifest["definitions"].setdefault(lang, {"aligned": 0, "rejected_articles": 0})
            for item in items:
                fr_points = french.get(item["article"])
                points = definitions(item)
                if not fr_points or not points:
                    continue
                if set(points) != set(fr_points) or len(points) < 2:
                    stats["rejected_articles"] += 1
                    continue
                for label in sorted(points, key=lambda x: (len(x), x)):
                    term, _ = points[label]
                    fr_term, fr_text = fr_points[label]
                    if not (term and fr_term and _formula_safe(term) and _formula_safe(fr_term)):
                        continue
                    rows_by_lang.setdefault(lang, []).append(
                        {
                            "source_language": lang,
                            "source_term": term[:500],
                            "target_language": TARGET,
                            "target_term": fr_term[:500],
                            "definition": fr_text[:4000],
                            "usage_context": (
                                f"Définition légale au sens de : {titles[celex]}, article "
                                f"{item['article']}, point {label} (uniquement dans ce cadre)."
                            )[:4000],
                            # Droit du travail : compatible documents RH et paie (LEGAL ne l'est pas).
                            "domain": "HR",
                            "jurisdiction": "EU",
                            "provenance": (
                                f"EUR-Lex CELEX {celex} art. {item['article']} pt {label} ; "
                                "© Union européenne, réutilisation décision 2011/833/UE ; "
                                "extrait non modifié"
                            )[:200],
                        }
                    )
                    stats["aligned"] += 1
        manifest["acts"][celex] = act
    columns = (
        "source_language",
        "source_term",
        "target_language",
        "target_term",
        "definition",
        "usage_context",
        "domain",
        "jurisdiction",
        "provenance",
    )
    for lang, rows in sorted(rows_by_lang.items()):
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        data = buffer.getvalue().encode("utf-8")
        name = f"eurlex-{lang}-{TARGET}.csv"
        (args.out / "definitions" / name).write_bytes(data)
        manifest["definitions"][lang].update(
            {"file": name, "rows": len(rows), "sha256": hashlib.sha256(data).hexdigest()}
        )
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    records = sum(a["records"] for a in manifest["acts"].values())
    aligned = sum(d.get("rows", 0) for d in manifest["definitions"].values())
    print(f"{len(manifest['acts'])} actes, {records} articles-langues, {aligned} définitions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
