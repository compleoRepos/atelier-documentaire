"""Normalisation linguistique du LOT 2 (recherche uniquement, jamais d'écriture).

Trois formes sont dérivées d'un texte ; aucune ne remplace le texte du document
ni le terme conservé dans le référentiel :

``search_key`` (clé exacte)
    Normalisation LOT 1 (NFKC, casse, apostrophes, tirets, espaces, ponctuation
    de bord), plus des corrections qui ne changent jamais le sens :

    * retrait des caractères de contrôle de direction et des liants de largeur
      nulle (fréquents dans les PDF et l'OCR) ;
    * chiffres arabes-indiens et persans convertis en chiffres ASCII ;
    * arabe : retrait du tatweel et des signes de vocalisation (harakat),
      unification des alifs porteurs de hamza (أ إ آ ٱ -> ا) ;
    * français : l'élision est séparée du mot (``l'employeur`` -> ``l'`` +
      ``employeur``), afin qu'un terme ``employeur`` soit reconnu.

``folded_key`` (clé pliée, appariement de repli)
    Clé exacte sans diacritiques latins (sauf ``ñ``, qui distingue des mots en
    espagnol), ``ß`` -> ``ss``, et en arabe ى -> ي, ة -> ه, ؤ -> و, ئ -> ي.
    Ces confusions sont typiques de l'OCR et de la saisie, mais peuvent porter
    une différence de sens : une correspondance pliée n'est acceptée que si
    elle désigne une seule clé exacte (sinon FOLDED_AMBIGUOUS).

``bm25_tokens`` (recherche lexicale)
    Mots de la clé pliée ; en arabe, les proclitiques courants (و ف ب ك ل et
    l'article ال) sont détachés quand il reste au moins trois lettres. Ces
    jetons servent au classement BM25 et aux suggestions, jamais à l'injection.
"""

from __future__ import annotations

import re
import unicodedata

from .normalizer import tokens as base_tokens

VERSION = "rag-normalizer-2"
SUPPORTED_LANGUAGES = ("fr", "ar", "en", "es", "de")

# Contrôles de direction (LRM, RLM, ALM, incorporations, isolats) et liants.
_INVISIBLE = dict.fromkeys(
    [0x061C, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF]
    + list(range(0x202A, 0x202F))
    + list(range(0x2066, 0x206A)),
    None,
)
_DIGITS = {0x0660 + i: str(i) for i in range(10)} | {0x06F0 + i: str(i) for i in range(10)}
_TATWEEL = "\u0640"
_HAMZA_ALEF = str.maketrans(
    {"\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627", "\u0671": "\u0627"}
)
_ARABIC_FOLD = str.maketrans(
    {"\u0649": "\u064a", "\u0629": "\u0647", "\u0624": "\u0648", "\u0626": "\u064a"}
)
_ELISION = re.compile(r"^(lorsqu|puisqu|jusqu|quoiqu|qu|l|d|j|n|s|c|m|t)'(?=\w)", re.IGNORECASE)
_GERMAN_ALIAS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"})
_ARABIC_PREFIXES = ("وال", "فال", "بال", "كال", "لل", "ال", "و", "ف", "ب", "ك", "ل")


def _is_arabic_mark(char: str) -> bool:
    code = ord(char)
    return 0x064B <= code <= 0x065F or code == 0x0670 or 0x06D6 <= code <= 0x06ED


def _clean(text: object) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.translate(_INVISIBLE).translate(_DIGITS)
    if any("\u0600" <= ch <= "\u06ff" for ch in value):
        value = "".join(ch for ch in value if ch != _TATWEEL and not _is_arabic_mark(ch))
        value = value.translate(_HAMZA_ALEF)
    return value


def _split_elisions(words: list[str]) -> list[str]:
    out: list[str] = []
    for word in words:
        found = _ELISION.match(word)
        if found and len(word) > found.end():
            out.extend((word[: found.end()], word[found.end() :]))
        else:
            out.append(word)
    return out


def search_tokens(text: object) -> list[str]:
    """Mots de la clé exacte."""
    return _split_elisions(base_tokens(_clean(text)))


def search_key(text: object) -> str:
    return " ".join(search_tokens(text))


def _fold_word(word: str) -> str:
    word = word.replace("ß", "ss").translate(_ARABIC_FOLD)
    decomposed = unicodedata.normalize("NFD", word)
    kept = []
    for index, char in enumerate(decomposed):
        if unicodedata.category(char) == "Mn":
            # « ñ » = n + tilde combinant : la distinction est conservée.
            if char == "\u0303" and index and decomposed[index - 1] in "nN":
                kept.append(char)
            continue
        kept.append(char)
    return unicodedata.normalize("NFC", "".join(kept))


def folded_tokens(text: object) -> list[str]:
    return [_fold_word(word) for word in search_tokens(text)]


def folded_key(text: object) -> str:
    return " ".join(folded_tokens(text))


def fold_key(key: str) -> str:
    """Plie une clé exacte déjà calculée, mot à mot, sans la renormaliser.

    ``search_key`` n'est pas idempotente (``l'`` isolé perdrait son apostrophe) :
    une clé ne doit jamais repasser par ``search_key``.
    """
    return " ".join(_fold_word(word) for word in str(key).split(" ") if word)


def alias_keys(text: object, language: str | None) -> set[str]:
    """Clés pliées supplémentaires d'une entrée (translittération allemande)."""
    keys = set()
    if language == "de":
        alias = " ".join(_fold_word(word.translate(_GERMAN_ALIAS)) for word in search_tokens(text))
        keys.add(alias)
    return {key for key in keys if key}


def _arabic_stem(word: str) -> str:
    if not any("\u0600" <= ch <= "\u06ff" for ch in word):
        return word
    for prefix in _ARABIC_PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            return word[len(prefix) :]
    return word


def bm25_tokens(text: object) -> list[str]:
    """Jetons BM25 : clé pliée, clitiques arabes légers, sans articles élidés (« l' »)."""
    return [_arabic_stem(word) for word in folded_tokens(text) if not word.endswith("'")]
