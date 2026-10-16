"""Typography-only differences are not a translation (final audit D27).

Observed on the real corpus (run16, DOC-008 and DOC-003): for non-French
blocks the model returned the source with only French typographic spacing
changes (no-break space before ":", space inserted before ";"). A strict
``target == source`` comparison then saw a "translation", no UNTRANSLATED
issue was raised and the renderer re-wrote the same foreign text over the
original. This key ignores Unicode compatibility forms, space variants,
spacing around punctuation, quote/dash variants and case, and nothing else.

F33 (run27): a doubled punctuation mark read by the OCR ("Fixe//Fax") that the
model "corrects" ("Fixe/Fax") is typography too: runs of the SAME punctuation
mark collapse to one in the key. Words and digits are still never touched, and
an equivalent answer is replaced by the exact source, so nothing is lost; the
original line is no longer re-typeset over itself.
F40 (run28): invisible bidirectional formatting controls (LRM/RLM, ALM,
embeddings, overrides and isolates) are not text either. The OCR attaches them
to right-to-left lines; a model answer that only drops or adds such a mark is the
source returned unchanged and must not be re-typeset over the original pixels.
"""

from __future__ import annotations

import re
import unicodedata

_BIDI_CONTROLS = re.compile(r"[\u200e\u200f\u061c\u202a-\u202e\u2066-\u2069]")
_SPACES = re.compile(r"[\s\u00a0\u202f\u2007\u2009\u200a\u200b\u2060\ufeff]+")
_AROUND_PUNCT = re.compile(r"\s*([:;!?,.()\[\]\"'/\-])\s*")
_REPEATED_PUNCT = re.compile(r"([:;!?,.()\[\]\"'/\-])\1+")
_VARIANTS = str.maketrans(
    {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00ab": '"',
        "\u00bb": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
)


def typography_key(text: str | None) -> str:
    value = _BIDI_CONTROLS.sub("", unicodedata.normalize("NFKC", text or "")).translate(_VARIANTS)
    value = _SPACES.sub(" ", value)
    value = _AROUND_PUNCT.sub(r"\1", value)
    value = _REPEATED_PUNCT.sub(r"\1", value)
    return value.strip().casefold()


def typography_equivalent(left: str | None, right: str | None) -> bool:
    """True when two texts differ only by typography (never by words or digits)."""
    return typography_key(left) == typography_key(right)
