"""Génère ``backend/app/domain/eu_lang_markers.py`` (marqueurs irlandais et maltais).

``langdetect`` n'a pas de profil irlandais et confond souvent le maltais court
avec l'italien. Ce générateur extrait, des textes officiels EUR-Lex versionnés
dans ``data/rag-ue/eurlex/eurlex``, des mots distinctifs :

* seuls les actes de la moitié de mise au point (DEV) sont lus : un acte est en
  DEV si l'entier SHA-256 de son numéro CELEX est pair ; l'autre moitié (TEST)
  et les actes de contrôle supplémentaires ne servent qu'à la mesure ;
* un mot (plié en minuscules, sans diacritiques combinants) est retenu pour la
  langue L s'il apparaît au moins ``MIN_COUNT`` fois dans les articles DEV de L
  et JAMAIS dans les articles DEV des autres langues ;
* un mot attesté dans une autre langue, d'après les fréquences ``wordfreq``
  (fréquence zipf >= ``MAX_FOREIGN_ZIPF`` dans l'une des langues couvertes, hors
  L), est écarté : « car », « fil » ou « pointe » ne peuvent pas désigner le
  maltais ou l'irlandais dans un texte français ;
* les mots sont classés par nombre d'articles de L qui les contiennent, puis
  par ordre alphabétique ; les ``TOP`` premiers sont gardés.

Le résultat est déterministe pour un même contenu de ``data/rag-ue/eurlex``.

Usage :
    python tools/rag_ue/lang_markers_build.py --eurlex data/rag-ue/eurlex/eurlex \\
        --out backend/app/domain/eu_lang_markers.py
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import re
import unicodedata
from pathlib import Path

LANGUAGES = {"ga": "gle", "mt": "mlt"}
MIN_COUNT = 5
MIN_LEN = 3
TOP = 400
MAX_FOREIGN_ZIPF = 1.0
# Langues ``wordfreq`` utilisées pour écarter les mots attestés ailleurs (UE,
# serbo-croate pour le croate, catalan et arabe) ; l'irlandais et le maltais
# n'y figurent pas.
FOREIGN_LANGUAGES = (
    "ar", "bg", "ca", "cs", "da", "de", "el", "en", "es", "fi", "fr", "hu",
    "it", "lt", "lv", "nl", "pl", "pt", "ro", "sh", "sk", "sl", "sv",
)  # fmt: skip
WORD = re.compile(r"\w+")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").casefold()
    return "".join(c for c in text if not unicodedata.combining(c))


def words(text: str) -> list[str]:
    return [w for w in WORD.findall(fold(text)) if not w.isdigit()]


def is_dev(celex: str) -> bool:
    return int(hashlib.sha256(celex.encode()).hexdigest(), 16) % 2 == 0


def attested_elsewhere(word: str) -> bool:
    import wordfreq

    return any(
        wordfreq.zipf_frequency(word, lang) >= MAX_FOREIGN_ZIPF for lang in FOREIGN_LANGUAGES
    )


def build(eurlex: Path) -> tuple[dict[str, list[str]], list[str], str]:
    count: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    docfreq: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    acts = []
    digest = hashlib.sha256()
    for path in sorted(eurlex.glob("*.jsonl.gz")):
        celex = path.name.split(".")[0]
        if not is_dev(celex):
            continue
        acts.append(celex)
        digest.update(path.read_bytes())
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                ws = words(row["text"])
                count[row["language"]].update(ws)
                docfreq[row["language"]].update(set(ws))
    result = {}
    for lang in LANGUAGES:
        others: set[str] = set()
        for other, counter in count.items():
            if other != lang:
                others.update(counter)
        candidates = [
            w
            for w, n in count[lang].items()
            if n >= MIN_COUNT
            and len(w) >= MIN_LEN
            and w not in others
            and not attested_elsewhere(w)
        ]
        candidates.sort(key=lambda w: (-docfreq[lang][w], w))
        result[lang] = candidates[:TOP]
    return result, acts, digest.hexdigest()


def render(result: dict[str, list[str]], acts: list[str], digest: str) -> str:
    from importlib.metadata import version as package_version

    version = package_version("wordfreq")
    lines = [
        '"""Marqueurs distinctifs de l\'irlandais et du maltais (FICHIER GÉNÉRÉ).',
        "",
        "Généré par ``tools/rag_ue/lang_markers_build.py`` à partir des textes officiels",
        "EUR-Lex (© Union européenne, réutilisation autorisée, décision 2011/833/UE) :",
        f"actes de mise au point {', '.join(acts)}.",
        f"Empreinte SHA-256 des fichiers lus : {digest}.",
        f"Règle : >= {MIN_COUNT} occurrences dans la langue, 0 dans les autres langues,",
        f"longueur >= {MIN_LEN}, absent de wordfreq {version} (zipf < {MAX_FOREIGN_ZIPF}) dans",
        f"{', '.join(FOREIGN_LANGUAGES)} ;",
        f"{TOP} premiers par fréquence documentaire. Ne pas éditer à la main.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "EU_LANGUAGE_MARKERS: dict[str, frozenset[str]] = {",
    ]
    for lang, iso3 in LANGUAGES.items():
        lines.append(f'    "{iso3}": frozenset(')
        lines.append("        {")
        for word in sorted(result[lang]):
            lines.append(f"            {json.dumps(word, ensure_ascii=False)},")
        lines.append("        }")
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--eurlex", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result, acts, digest = build(args.eurlex)
    args.out.write_text(render(result, acts, digest), encoding="utf-8")
    print(json.dumps({lang: len(v) for lang, v in result.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
