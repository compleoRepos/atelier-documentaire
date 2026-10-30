"""Normalisation des termes pour la recherche uniquement.

La forme normalisée sert à apparier un terme du document avec une entrée de
référentiel. Elle ne remplace jamais le texte du document ni le terme source
conservé dans le référentiel.

LOT 1 : normalisation générique (Unicode NFKC, casse, apostrophes, tirets,
espaces, ponctuation en bordure). Les signes diacritiques combinants ne sont
pas retirés : en arabe comme dans les langues latines, ils peuvent porter une
distinction de sens. La normalisation propre à l'arabe arrive au LOT 2.
"""

from __future__ import annotations

import re
import unicodedata

VERSION = "rag-normalizer-1"

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "`": "'", "\u00b4": "'"})
_DASHES = str.maketrans(
    {"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"}
)
_SPACES = re.compile(r"\s+")
_LANGUAGE_ALIASES = {
    "eng": "en",
    "fra": "fr",
    "fre": "fr",
    "ara": "ar",
    "spa": "es",
    "deu": "de",
    "ger": "de",
    "french": "fr",
    "english": "en",
    "arabic": "ar",
    "spanish": "es",
    "german": "de",
}


def _is_edge_punctuation(char: str) -> bool:
    category = unicodedata.category(char)
    return category[0] in {"P", "S", "Z"} or char.isspace()


def _strip_edges(value: str) -> str:
    start, end = 0, len(value)
    while start < end and _is_edge_punctuation(value[start]):
        start += 1
    while end > start and _is_edge_punctuation(value[end - 1]):
        end -= 1
    return value[start:end]


def _base(text: object) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.translate(_APOSTROPHES).translate(_DASHES).casefold()
    return _SPACES.sub(" ", value).strip()


def tokens(text: object) -> list[str]:
    """Mots normalisés d'un texte (ponctuation de bord retirée, jamais interne)."""
    words = (_strip_edges(word) for word in _base(text).split(" "))
    return [word for word in words if word]


def normalize_term(text: object) -> str:
    """Forme de recherche d'un terme : ses mots normalisés séparés par une espace.

    La même fonction produit la clé d'une entrée et les n-grammes du document,
    ce qui garantit que la correspondance ne dépend que de la normalisation.
    """
    return " ".join(tokens(text))


def normalize_language(value: object) -> str | None:
    """Code de langue court (ISO 639-1) ou None si inconnu."""
    code = str(value or "").strip().lower().replace("_", "-")
    if not code or code in {"unknown", "und", "none", "mixed"}:
        return None
    code = code.split("-")[0]
    code = _LANGUAGE_ALIASES.get(code, code)
    return code if re.fullmatch(r"[a-z]{2,3}", code) else None
