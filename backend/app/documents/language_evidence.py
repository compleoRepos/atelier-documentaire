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

VERSION = "language-evidence-2"  # RUN28 F35: reference_line
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
    # RUN28 F35: reference lines (addresses, legal identifiers, company names)
    # are flagged here, on the final language, and never sent to a model.
    references = 0
    for page in ir.get("pages", []):
        for block in page.get("blocks", []):
            reference = None
            if (
                not block.get("no_linguistic_content")
                and not block.get("protected")
                and str(block.get("language") or "").lower() not in {"fra", "fr"}
            ):
                reference = reference_line(
                    str(block.get("text") or ""), block.get("language"), languages, "pre_send"
                )
            if reference:
                block["reference_line"] = reference
                references += 1
            else:
                block.pop("reference_line", None)
    stats["reference_lines"] = references
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


# --- RUN28 F35: reference lines (addresses, legal identifiers, names) -------
#
# RUN27 MV-01: an address line and a line of legal identifiers of a French
# letterhead were detected as Spanish/English, sent "FR->FR" to the model and
# re-rendered from a faulty OCR (digit read as letter): an identifier became wrong in
# the PDF. Run27b also counted as ``model_returned_source`` failures many
# company names, addresses, post codes and URLs that the model rightly kept.
#
# Two levels, both conservative and explicit (never a silent omission):
# * ``pre_send``: the line is not sent to a model and keeps its original
#   pixels (status PRESERVED_INTENTIONALLY / reference_line). Strong anchors
#   only: a registry label with digits (RC, IF, CNSS, TVA, IBAN...), a street
#   word with an identifier token, or a legal form as the last word.
# * ``returned_unchanged``: only re-labels a block the model already returned
#   verbatim (status, not rendering); also accepts post codes / identifier
#   tokens, URLs and capitalised names that are rare in every language.
# Both refuse: any non-Latin word, any lowercase word other than a name
# particle, and any capitalised word common in a foreign language and clearly
# less common in French ("Employment", "September", "Box", "Telefon").
# Without the offline lexicon the function returns None (translate, as before).

REFERENCE_VERSION = "reference-line-1"
_PARTICLES = frozenset(
    "de du des la le el et en y e d l da di del della dos das do van von der den".split()
)
_REGISTRY = frozenset(
    "rc if ice cnss tva vat siret siren rcs naf ape iban bic swift patente ust hrb kvk btw nif cif".split()
)
_CONTACT = frozenset("fax fixe gsm tel tél email mail www bp cp cedex imm".split())
_LEGAL_FORMS = frozenset(
    "GmbH AG KG OHG UG SA SAS SASU SARL EURL SCI SNC Ltd LTD LLC LLP PLC plc Inc INC Corp BV NV SL SLU SAU SpA Srl SRL".split()
)
_STREET = frozenset(
    "road street lane avenue av ave avda bd blvd boulevard rue strasse straße weg platz allee gasse "
    "calle carrer via viale piazza plaza paseo laan straat gracht résidence residence lotissement immeuble".split()
)
_URL = re.compile(
    r"(?:https?://|www\.)\S+|\b[\w.-]+\.(?:com|net|org|info|fr|ma|uk|de|es|it|nl|eu|fi|be|ch)\b"
    r"|[\w.+-]+@[\w-]+\.[\w.-]+",
    re.IGNORECASE,
)
_LEGAL_DOTTED_END = re.compile(r"\b(?:S\.\s?L|S\.\s?A|B\.\s?V|N\.\s?V|S\.\s?R\.\s?L)\.?\W*$")
_IDENTIFIER = re.compile(r"\b(?=\w*\d)(?:\d{3,}|[A-Za-z]+\d+\w*|\d+[A-Za-z]+\w*)\b")
FOREIGN_COMMON_MARGIN = 0.5
NAME_RARE_ZIPF = 3.0


def _foreign_common(word: str, isos: list[str]) -> bool:
    best = max(_zipf(word, iso) for iso in isos)
    return best >= COMMON_ZIPF and best >= _zipf(word, "fr") + FOREIGN_COMMON_MARGIN


def reference_line(
    text: str,
    detected: Any = None,
    document_languages: list[Any] | None = None,
    mode: str = "pre_send",
) -> dict[str, Any] | None:
    """Return ``{"rule", "version", "mode", "anchors"}`` when ``text`` is a
    reference line that must not be translated (``pre_send``) or that the
    model rightly returned verbatim (``returned_unchanged``), else ``None``.
    Pure; see the comment above (RUN28 F35)."""
    if mode not in {"pre_send", "returned_unchanged"} or not available():
        return None
    value = str(text or "").strip()
    if not value or not has_linguistic_content(value):
        return None
    without_urls = _URL.sub(" ", value)
    anchors: set[str] = set()
    if without_urls != value:
        anchors.add("url_or_email")
    if _LEGAL_DOTTED_END.search(without_urls):
        anchors.add("legal_form")
        without_urls = _LEGAL_DOTTED_END.sub(" ", without_urls)
    raw_words = re.findall(r"[^\W\d_]{2,}", without_urls, flags=re.UNICODE)
    if any(
        not all("a" <= c.lower() <= "z" or "\u00c0" <= c <= "\u024f" for c in w) for w in raw_words
    ):
        return None  # non-Latin script: a transliteration/translation decision is needed
    if raw_words and raw_words[-1] in _LEGAL_FORMS:
        anchors.add("legal_form")
    if _IDENTIFIER.search(without_urls):
        anchors.add("identifier")
    isos = _other_isos([detected, *(document_languages or [])])
    registry = street = False
    names = []
    for raw in raw_words:
        low = raw.lower()
        if raw in _LEGAL_FORMS or low in _PARTICLES:
            continue
        if low in _REGISTRY:
            registry = True
            continue
        if low in _CONTACT:
            continue
        if low in _STREET:
            street = True
            continue
        if raw[0].islower():
            return None  # a lowercase word: phrase evidence (or OCR noise), translate
        if len(raw) <= 3 and raw.isupper():
            continue  # acronym / post-code part (e.g. "AB1 2CD", "1234 AB")
        if "legal_form" not in anchors and _foreign_common(low, isos):
            # a translatable foreign word ("Employment", "Box"); a company name
            # closed by its legal form is kept whole ("... Germany GmbH")
            return None
        names.append(low)
    if registry and "identifier" in anchors:
        anchors.add("registry_identifiers")
    if street and "identifier" in anchors:
        anchors.add("street_address")
    result = {"version": REFERENCE_VERSION, "mode": mode, "anchors": sorted(anchors)}
    strong = anchors & {"registry_identifiers", "street_address", "legal_form"}
    if strong:
        return {**result, "rule": "reference_line"}
    if mode == "pre_send":
        return None
    if anchors & {"identifier", "url_or_email"}:
        return {**result, "rule": "returned_unchanged_reference"}
    if (
        names
        and all(max(_zipf(w, iso) for iso in ["fr", *isos]) < NAME_RARE_ZIPF for w in names)
        and (len(names) >= 2 or len(names[0]) >= 4)
    ):
        return {**result, "rule": "returned_unchanged_proper_name"}
    return None


# --- RUN28 F39: incomplete translations (source segment copied verbatim) ----
#
# DOC-008 (run27b): a bilingual footer "Arabic — German" came back as
# "French — German": the Arabic half was translated, the German half copied
# verbatim, and the block counted as TRANSLATED. A target is incomplete when
# it contains, verbatim and in order, a run of source words holding at least
# PARTIAL_MIN_FOREIGN words that are common in a document language and
# clearly less common in French. Words shared with French, words in capitals
# (titles, acronyms: "CONVENIO ESTATAL", "GmbH") and capitalised words
# (proper names: "Connectivity Germany") never count, except in a German
# source where every noun is capitalised. Without the lexicon: None.
PARTIAL_VERSION = "partial-copy-1"
PARTIAL_MIN_RUN = 4
PARTIAL_MIN_FOREIGN = 3


def _cased_latin_words(text: str) -> list[str]:
    words = _WORD.findall(text or "")
    return [
        w for w in words if all("a" <= c <= "z" or "\u00c0" <= c <= "\u024f" for c in w.lower())
    ]


def copied_source_words(
    source: str,
    target: str,
    languages: list[Any] | None = None,
    source_language: Any = None,
) -> int | None:
    """Foreign common words in the longest run of >= PARTIAL_MIN_RUN source
    words copied verbatim into ``target`` (0 when there is none)."""
    if not available():
        return None
    cased = _cased_latin_words(source)
    src, tgt = [w.lower() for w in cased], _latin_words(target)
    if len(src) < PARTIAL_MIN_RUN or len(tgt) < PARTIAL_MIN_RUN:
        return 0
    best_len, best_end = 0, 0
    previous = [0] * (len(tgt) + 1)
    for i in range(1, len(src) + 1):
        current = [0] * (len(tgt) + 1)
        for j in range(1, len(tgt) + 1):
            if src[i - 1] == tgt[j - 1]:
                current[j] = previous[j - 1] + 1
                if current[j] > best_len:
                    best_len, best_end = current[j], i
        previous = current
    if best_len < PARTIAL_MIN_RUN:
        return 0
    isos = _other_isos([source_language, *(languages or [])])
    german = _ISO.get(str(source_language or "").lower()) == "de"
    count = 0
    for word in cased[best_end - best_len : best_end]:
        if len(word) < 3 or word.isupper() or (word[0].isupper() and not german):
            continue
        best = max(_zipf(word.lower(), iso) for iso in isos)
        if best >= COMMON_ZIPF and best >= _zipf(word.lower(), "fr") + FOREIGN_MARGIN:
            count += 1
    return count


def partial_source_copy(
    source: str,
    target: str,
    languages: list[Any] | None = None,
    source_language: Any = None,
) -> bool:
    """True when a changed target still holds an untranslated source segment."""
    if not target or target.split() == (source or "").split():
        return False
    found = copied_source_words(source, target, languages, source_language)
    return bool(found is not None and found >= PARTIAL_MIN_FOREIGN)
