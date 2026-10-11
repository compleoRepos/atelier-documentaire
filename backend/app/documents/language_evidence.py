"""Block-level language evidence from an offline word-frequency lexicon.

Run18 audit: short OCR blocks of a French document were detected as Dutch,
Spanish or Italian by n-gram/stop-word evidence (labels and field values are
too short for it). Such blocks were sent for "translation" and reported as
untranslated when the engine rightly returned them unchanged, while a short
foreign label detected as French was never sent at all.

This module only re-labels a block when the lexical evidence is strong:

* ``fra`` when nearly every word is a common French word and clearly less
  common in the detected language (the block is then preserved as already
  French, never rewritten);
* the detected document language when a block labelled French is made of
  words that are common in that language and rare in French (the block is
  then translated instead of silently kept).

Without the ``wordfreq`` package the function returns ``None`` everywhere:
the previous behaviour (translate) is kept, nothing is silently preserved.
The lexicon code is Apache-2.0; its frequency data is CC-BY-SA 4.0 (licence to
be validated for production redistribution, see run18 reports).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

VERSION = "language-evidence-1"
COMMON_ZIPF = 3.0
RARE_ZIPF = 2.0
MIN_COVERAGE = 0.85
MIN_MARGIN = 0.30
SINGLE_WORD_COMMON_ZIPF = 3.5
_WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
_ISO = {
    "fra": "fr",
    "eng": "en",
    "spa": "es",
    "deu": "de",
    "ita": "it",
    "nld": "nl",
    "por": "pt",
    "fin": "fi",
    "swe": "sv",
    "dan": "da",
    "nor": "nb",
    "pol": "pl",
    "ron": "ro",
    "tur": "tr",
}


@lru_cache(maxsize=1)
def _lexicon() -> Any:
    try:
        from wordfreq import zipf_frequency
    except Exception:  # pragma: no cover - optional dependency
        return None
    return zipf_frequency


@lru_cache(maxsize=65536)
def _zipf(word: str, iso: str) -> float:
    lexicon = _lexicon()
    if lexicon is None:
        return 0.0
    return float(lexicon(word, iso))


def available() -> bool:
    return _lexicon() is not None


def _latin_words(text: str) -> list[str]:
    words = [w.lower() for w in _WORD.findall(text or "")]
    return [w for w in words if all("a" <= c <= "z" or "\u00c0" <= c <= "\u024f" for c in w)]


_ANY_WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


def has_linguistic_content(text: str) -> bool:
    """At least one run of two letters (any script). Blocks without it ("|",
    "i", ":", "5 €") are OCR fragments or symbols: nothing to translate, and a
    model could only invent text for them."""
    return bool(_ANY_WORD.search(text or ""))


def coverage(words: list[str], iso: str) -> float:
    if not words:
        return 0.0
    return sum(_zipf(w, iso) >= COMMON_ZIPF for w in words) / len(words)


def refine_language(
    text: str, detected: Any, document_languages: list[Any] | None = None
) -> dict[str, Any] | None:
    """Return ``{"language", "rule", ...}`` when the block must be re-labelled,
    else ``None`` (keep the detected language)."""
    if not available():
        return None
    detected_code = str(detected or "").lower()
    words = _latin_words(text)
    letters = sum(c.isalpha() for c in text or "")
    if not words or sum(len(w) for w in words) < 0.8 * letters:
        return None  # non-Latin or mixed script: script evidence decides
    others = []
    for code in [detected_code, *[str(c).lower() for c in document_languages or []]]:
        if code in _ISO and code != "fra" and code not in others:
            others.append(code)
    # Words rare in every candidate language are proper names, places or OCR
    # fragments ("Nom: <surname>", "Ville: <town>"): they carry no language
    # evidence and are excluded from both coverages.
    words = [w for w in words if max(_zipf(w, _ISO[c]) for c in ["fra", *others]) >= RARE_ZIPF]
    if not words:
        return None
    fr = coverage(words, "fr")
    best_other = max(others, key=lambda c: coverage(words, _ISO[c]), default=None)
    other = coverage(words, _ISO[best_other]) if best_other else 0.0
    if detected_code != "fra":
        if len(words) == 1:
            word = words[0]
            french_word = len(word) >= 3 and _zipf(word, "fr") >= SINGLE_WORD_COMMON_ZIPF
            rare_elsewhere = all(_zipf(word, _ISO[c]) < RARE_ZIPF for c in others)
            if french_word and rare_elsewhere and others:
                return {
                    "language": "fra",
                    "rule": "single_common_french_word",
                    "detected": detected_code or None,
                }
            return None
        if fr >= MIN_COVERAGE and fr - other >= MIN_MARGIN:
            return {
                "language": "fra",
                "rule": "lexical_french",
                "detected": detected_code or None,
                "fr_coverage": round(fr, 3),
                "other": best_other,
                "other_coverage": round(other, 3),
            }
        return None
    if best_other and len(words) >= 2 and other >= MIN_COVERAGE and other - fr >= MIN_MARGIN:
        return {
            "language": best_other,
            "rule": "lexical_foreign_detected_as_french",
            "detected": "fra",
            "fr_coverage": round(fr, 3),
            "other": best_other,
            "other_coverage": round(other, 3),
        }
    return None


def refine_block_languages(ir: dict[str, Any]) -> dict[str, Any]:
    """Apply :func:`refine_language` and :func:`has_linguistic_content` to every
    block of every page. Idempotent; the first detection is kept in
    ``language_detected`` and the evidence in ``language_evidence``."""
    stats: dict[str, Any] = {"version": VERSION, "lexicon": available(), "refined": {}}
    languages = [
        item.get("code") if isinstance(item, dict) else item for item in ir.get("languages") or []
    ]
    refined: dict[str, int] = {}
    no_content = 0
    for page in ir.get("pages", []):
        for block in page.get("blocks", []):
            text = str(block.get("text") or "")
            if not has_linguistic_content(text):
                block["no_linguistic_content"] = True
                no_content += 1
                continue
            block.pop("no_linguistic_content", None)
            original = block.get("language_detected", block.get("language"))
            result = refine_language(text, original, languages)
            if result is None:
                if "language_detected" in block:
                    block["language"] = block.pop("language_detected")
                    block.pop("language_evidence", None)
                continue
            block["language_detected"] = original
            block["language"] = result["language"]
            block["language_evidence"] = {"version": VERSION, **result}
            key = f"{result['rule']}:{result.get('detected')}->{result['language']}"
            refined[key] = refined.get(key, 0) + 1
    stats["refined"] = refined
    stats["no_linguistic_content"] = no_content
    ir["language_evidence"] = stats
    return stats


IDENTICAL_MARGIN = 0.5
FOREIGN_MARGIN = 1.0


def _other_isos(languages: list[Any] | None) -> list[str]:
    isos = []
    for code in languages or []:
        iso = _ISO.get(str(code or "").lower())
        if iso and iso != "fr" and iso not in isos:
            isos.append(iso)
    return isos or ["en"]


def identical_in_french(text: str, languages: list[Any] | None = None) -> bool:
    """Every Latin word is common in French (zipf >= 3) and not markedly more
    common in another document language (margin 0.5): "Date", "Total",
    "Contact" are the French text too. English function words that the
    French corpus also contains ("the": fr 3.6, en 7.7) fail the margin."""
    if not available():
        return False
    words = _latin_words(text)
    letters = sum(c.isalpha() for c in text or "")
    if not words or sum(len(w) for w in words) < 0.8 * letters:
        return False
    isos = _other_isos(languages)
    for word in words:
        fr = _zipf(word, "fr")
        if fr < COMMON_ZIPF or fr < max(_zipf(word, iso) for iso in isos) - IDENTICAL_MARGIN:
            return False
    return True


def foreign_word_evidence(text: str, languages: list[Any] | None = None) -> bool:
    """At least one Latin word that is common in a document language (zipf
    >= 3) and clearly more common there than in French (margin 1.0): a block
    returned verbatim with such a word is not French ("Name:", "Datum")."""
    if not available():
        return False
    isos = _other_isos(languages)
    for word in _latin_words(text):
        if len(word) < 3:
            continue
        best = max(_zipf(word, iso) for iso in isos)
        if best >= COMMON_ZIPF and best >= _zipf(word, "fr") + FOREIGN_MARGIN:
            return True
    return False
