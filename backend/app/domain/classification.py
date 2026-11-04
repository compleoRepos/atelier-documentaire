"""Classification explicable du type et du domaine des documents.

Le classifieur est volontairement lexical et déterministe : il fournit une
orientation auditable, jamais une validation sémantique ou une traduction.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from app.domain.eu_lang_markers import EU_LANGUAGE_MARKERS
from app.domain.eu_type_lexicons import EU_TYPE_LEXICONS

try:
    from langdetect import DetectorFactory, detect_langs

    DetectorFactory.seed = 0
except Exception:  # pragma: no cover
    detect_langs = None

_LANG_MAP = {
    "en": "eng",
    "fr": "fra",
    "de": "deu",
    "it": "ita",
    "es": "spa",
    "nl": "nld",
    "ar": "ara",
}

# LOT 2.3 : les 18 autres langues officielles de l'UE (24 au total, plus l'arabe).
# Les 7 langues historiques ci-dessus gardent exactement leur traitement : une
# langue ajoutée n'est retenue que sur preuve forte (probabilité du détecteur
# élevée sur un texte assez long, écriture grecque, ou indices lexicaux pour
# l'irlandais et le maltais, absents des profils de langdetect). Sans preuve
# forte, le résultat reste celui d'origine (souvent "unknown").
EU_LANGUAGE_VERSION = "eu-languages-1"
_EU_LANG_MAP = {
    "bg": "bul",
    "cs": "ces",
    "da": "dan",
    "el": "ell",
    "et": "est",
    "fi": "fin",
    "hr": "hrv",
    "hu": "hun",
    "lt": "lit",
    "lv": "lav",
    "pl": "pol",
    "pt": "por",
    "ro": "ron",
    "sk": "slk",
    "sl": "slv",
    "sv": "swe",
}
# Codes ISO 639-3 des 18 langues ajoutées (16 via langdetect, irlandais et maltais).
ADDED_LANGUAGES = frozenset(_EU_LANG_MAP.values()) | {"gle", "mlt"}
EU_MIN_PROB = 0.90
EU_MIN_LETTERS = 20
EU_WEIGHT = 0.75
# Indices pliés (sans diacritiques) ; il en faut au moins deux occurrences.
_EU_HINTS = {
    "gle": (
        " agus ",
        " bhfuil ",
        " chun ",
        " faoi ",
        " leis ",
        " gach ",
        " airteagal ",
        " beidh ",
        " mbeidh ",
        " ata ",
        " sna ",
        " seo ",
        " ar an ",
        " maidir ",
        " le haghaidh ",
        " ballstait ",
        " treoir ",
    ),
    "mlt": (
        " il-",
        " tal-",
        " ta' ",
        " fil-",
        " mill-",
        " ghall-",
        " li ",
        " jew ",
        " huwa ",
        " minn ",
        " biex ",
        " skont ",
        " ghandu ",
        " ghandhom ",
        " ikun ",
        " tkun ",
    ),
}
EU_MIN_HINTS = 2
EU_HINT_WEIGHT = 0.35
# Densité minimale d'indices (part des mots) : un document long d'une autre langue
# accumule quelques faux indices, jamais une telle densité (mesure LOT 2.3 :
# irlandais p10 = 0,095, maltais p10 = 0,286, autres langues p95 = 0).
EU_MIN_HINT_DENSITY = {"gle": 0.05, "mlt": 0.10}
# Marqueurs distinctifs générés depuis EUR-Lex (voir ``eu_lang_markers``) : au moins
# deux marqueurs et une densité minimale, ou un seul dans un fragment très court.
# Une collision isolée dans un long document d'une autre langue reste sans effet.
EU_MARKER_MIN_DENSITY = 0.05
EU_MARKER_STRONG = 1.2
EU_MARKER_SINGLE = 0.9
EU_MARKER_SHORT_WORDS = 12
# Gardes de non-régression de la voie statistique (langdetect) des langues ajoutées :
# un fragment d'un seul mot, ou dont tous les mots sont des mots courants d'une langue
# historique (fréquence zipf >= EU_COMMON_ZIPF dans wordfreq), garde le comportement
# d'origine. Exemples mesurés : « minimum paid annual leave; » n'est plus estonien,
# « geldmarktinstrumenten, » n'est plus danois.
EU_STAT_MIN_WORDS = 2
EU_COMMON_ZIPF = 3.0
_HISTORIC_WORDFREQ = ("en", "fr", "de", "it", "es", "nl")
_WORD = re.compile(r"\w+")
_MALTESE_LETTERS = frozenset("ħĦġĠċĊ")
# Mutations initiales de l'irlandais (lénition, éclipse) : rares en début de mot
# dans les autres langues de l'UE.
_IRISH_MUTATION = re.compile(
    r"(?<![\w'-])(?:bh|mh|dh|fh|gh|gc|bp|dt|n-|t-)[aeiouáéíóú]", re.IGNORECASE
)
# Article défini maltais soudé au nom (il-, tal-, tax-, fl-...).
_MALTESE_ARTICLE = re.compile(
    r"(?<![\w'-])(?:il|l|tal|fil|fl|mill|bil|lill|sal|mal|għall|ghall|ix|is|it|id|in|ir|iż|iċ|"
    r"tad|tat|tas|tar|tax|taż|taċ|tan|fid|fit|fis|fix|bid|bit|bis|bix|mid|mit|mis|mix)-\w",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").casefold()
    return "".join(c for c in text if not unicodedata.combining(c))


_LANGUAGE_HINTS = {
    "fra": (
        " le ",
        " la ",
        " les ",
        " des ",
        " une ",
        " un ",
        " et ",
        " pour ",
        " dans ",
        " avec ",
        " attestation ",
        " salarié ",
    ),
    "eng": (
        " the ",
        " and ",
        " of ",
        " to ",
        " is ",
        " for ",
        " with ",
        " employment ",
        " employee ",
        " statement ",
        " invoice ",
    ),
    "deu": (
        " der ",
        " die ",
        " das ",
        " und ",
        " von ",
        " ist ",
        " für ",
        " in ",
        " mit ",
        " arbeitgeber ",
        " vertrag ",
    ),
    "ita": (
        " il ",
        " lo ",
        " la ",
        " gli ",
        " le ",
        " e ",
        " di ",
        " del ",
        " per ",
        " con ",
        " lavoro ",
        " contratto ",
    ),
    "spa": (
        " el ",
        " la ",
        " los ",
        " las ",
        " y ",
        " de ",
        " del ",
        " para ",
        " con ",
        " trabajo ",
        " contrato ",
    ),
    "nld": (
        " de ",
        " het ",
        " een ",
        " en ",
        " van ",
        " voor ",
        " met ",
        " werk ",
        " werknemer ",
        " werkgever ",
        " inkomen ",
        " verklaring ",
        " contract ",
    ),
}


def _script_evidence(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for char in text:
        code = ord(char)
        if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F:
            counts["ara"] += 1
        elif char.isalpha():
            counts["latin"] += 1
    return counts


def _greek_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    greek = sum(1 for c in letters if 0x0370 <= ord(c) <= 0x03FF or 0x1F00 <= ord(c) <= 0x1FFF)
    return greek / len(letters)


def _historic_lookalike(text: str) -> bool:
    """Vrai si la voie statistique ne doit pas attribuer une langue ajoutée."""
    words = [w for w in _WORD.findall(text.lower()) if not w.isdigit()]
    if len(words) < EU_STAT_MIN_WORDS:
        return True
    try:
        from wordfreq import zipf_frequency
    except Exception:  # pragma: no cover - dépendance épinglée du backend
        return False
    return any(
        all(zipf_frequency(w, lang) >= EU_COMMON_ZIPF for w in words) for lang in _HISTORIC_WORDFREQ
    )


def _eu_evidence(
    text: str,
    folded: str,
    eu_guesses: list[tuple[str, float]],
    scores: Counter[str],
    detector_scores: dict[str, float],
) -> None:
    """Preuves fortes des langues de l'UE ajoutées (voir ``_EU_LANG_MAP``)."""
    letters = sum(c.isalpha() for c in text)
    if letters < EU_MIN_LETTERS:
        return
    strong = [(code, prob) for code, prob in eu_guesses if prob >= EU_MIN_PROB]
    if strong and detect_langs and not _historic_lookalike(text):
        # Un titre en capitales trompe le détecteur : la langue ajoutée doit être
        # confirmée par la détection du même texte en minuscules.
        try:
            lowered = {
                _EU_LANG_MAP.get(g.lang): float(g.prob) for g in detect_langs(text[:12000].lower())
            }
        except Exception:
            lowered = {}
        for code, prob in strong:
            if lowered.get(code, 0.0) >= EU_MIN_PROB:
                detector_scores[code] = max(detector_scores.get(code, 0.0), prob)
                scores[code] += prob * EU_WEIGHT
    greek = _greek_ratio(text)
    if greek >= 0.5:
        scores["ell"] += min(0.85, 0.45 + greek * 0.5)
    for code, hints in _EU_HINTS.items():
        count = sum(folded.count(hint) for hint in hints)
        if code == "gle":
            count += len(_IRISH_MUTATION.findall(text))
        if code == "mlt":
            count += sum(1 for c in text if c in _MALTESE_LETTERS)
            count += len(_MALTESE_ARTICLE.findall(text))
        words = max(1, len(_WORD.findall(text)))
        if count >= EU_MIN_HINTS and count / words >= EU_MIN_HINT_DENSITY[code]:
            scores[code] += min(1.2, count * EU_HINT_WEIGHT)
    tokens = [w for w in _WORD.findall(folded) if not w.isdigit()]
    for code, markers in EU_LANGUAGE_MARKERS.items():
        hits = sum(1 for w in tokens if w in markers)
        if hits >= 2 and hits / max(1, len(tokens)) >= EU_MARKER_MIN_DENSITY:
            scores[code] += EU_MARKER_STRONG
        elif hits == 1 and len(tokens) <= EU_MARKER_SHORT_WORDS:
            scores[code] += EU_MARKER_SINGLE


def detect_language(text: str) -> tuple[str, list[str], float]:
    """Return primary language, detected languages and evidence confidence.

    Detector output is combined with script and language-specific word evidence.
    This avoids trusting a single short-sample guess and makes mixed-language
    documents explicit.  The confidence describes detector evidence only.
    """
    text = (text or "").strip()
    if not text:
        return "unknown", [], 0.0
    folded = f" {_fold(text)} "
    scores: Counter[str] = Counter()
    script = _script_evidence(text)
    # Arabic stamps/seals are often a small secondary region on a Latin page.
    # Script evidence is strong only when Arabic is dominant.
    arabic_ratio = script["ara"] / max(1, script.total())
    if script["ara"]:
        scores["ara"] += (
            min(0.85, 0.45 + arabic_ratio * 0.5) if arabic_ratio >= 0.35 else arabic_ratio * 0.35
        )
    lexical_counts: Counter[str] = Counter()
    for code, hints in _LANGUAGE_HINTS.items():
        lexical_counts[code] = sum(folded.count(_fold(hint)) for hint in hints)
        if lexical_counts[code]:
            scores[code] += min(0.7, lexical_counts[code] / 10)
    detector_scores: dict[str, float] = {}
    eu_guesses: list[tuple[str, float]] = []
    if detect_langs:
        try:
            for guess in detect_langs(text[:12000]):
                code = _LANG_MAP.get(guess.lang)
                if code:
                    detector_scores[code] = max(detector_scores.get(code, 0.0), float(guess.prob))
                    scores[code] += float(guess.prob) * 0.75
                elif guess.lang in _EU_LANG_MAP:
                    eu_guesses.append((_EU_LANG_MAP[guess.lang], float(guess.prob)))
        except Exception:
            detector_scores = {}
            eu_guesses = []
    _eu_evidence(text, folded, eu_guesses, scores, detector_scores)
    if not scores:
        return "unknown", [], 0.0
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_code, best_score = ordered[0]
    # A second language is retained only when it has independent evidence; this
    # is useful for headers/forms and avoids emitting every langdetect candidate.
    threshold = max(0.18, best_score * 0.34)
    languages = [code for code, score in ordered if score >= threshold]
    # A small Arabic stamp remains secondary evidence and cannot hide a Latin
    # page's lexical language.
    if arabic_ratio < 0.35 or script["latin"] > script["ara"]:
        latin_codes = [code for code, _score in ordered if code != "ara"]
        if latin_codes:
            best_code = latin_codes[0]
    if best_code not in languages:
        languages.insert(0, best_code)
    confidence = min(0.99, max(detector_scores.get(best_code, 0.0), best_score / 1.6))
    if script["ara"] and best_code == "ara":
        confidence = max(confidence, min(0.95, script["ara"] / max(1, script.total())))
    return best_code, languages, round(confidence, 3)


# Type names are stable API values. Domain values deliberately match the
# controlled vocabulary used in the IR and review UI.
_TYPE_SPECS = {
    "employment_certificate": {
        "domain": "HR",
        "lexicons": {
            "fra": (
                "attestation de travail",
                "certificat de travail",
                "certificat d emploi",
                "emploi",
                "salarié",
                "employeur",
                "rémunération",
            ),
            "eng": (
                "employment certificate",
                "certificate of employment",
                "work certificate",
                "employee certificate",
                "employer",
                "salary",
            ),
            "deu": (
                "arbeitsbescheinigung",
                "bescheinigung arbeit",
                "beschäftigungsnachweis",
                "bescheinigung des arbeitgebers",
                "beschäftigungsbescheinigung",
                "arbeitgeber",
                "arbeitnehmer",
                "gehalt",
            ),
            "ita": (
                "certificato di lavoro",
                "certificato di impiego",
                "attestazione di lavoro",
                "datore di lavoro",
                "dichiarazione del datore di lavoro",
                "dichiarazione di lavoro",
                "dichiarazione del reddito",
                "reddito da lavoro",
                "stipendio",
            ),
            "spa": (
                "certificado de trabajo",
                "certificado laboral",
                "constancia de empleo",
                "empleador",
                "salario",
            ),
            "nld": (
                "werkgeversverklaring",
                "arbeidsverklaring",
                "verklaring dienstverband",
                "inkomensverklaring",
                "verklaring van inkomen",
                "werkgever",
                "salaris",
            ),
            "ara": ("شهادة عمل", "شهادة توظيف", "صاحب العمل", "راتب", "دخل", "بيان دخل"),
        },
    },
    "contract": {
        "domain": "LEGAL",
        "lexicons": {
            "fra": (
                "contrat de travail",
                "contrat de prestation",
                "contrat",
                "accord",
                "parties",
                "clause",
                "signataire",
            ),
            "eng": (
                "employment contract",
                "service agreement",
                "contract",
                "agreement",
                "parties",
                "clause",
                "signatory",
            ),
            "deu": (
                "arbeitsvertrag",
                "dienstvertrag",
                "vertrag",
                "vereinbarung",
                "parteien",
                "klausel",
            ),
            "ita": ("contratto di lavoro", "contratto", "accordo", "parti", "clausola"),
            "spa": ("contrato de trabajo", "contrato", "acuerdo", "partes", "cláusula"),
            "nld": ("arbeidsovereenkomst", "contract", "overeenkomst", "partijen", "clausule"),
            "ara": ("عقد عمل", "عقد", "اتفاقية", "الأطراف", "بند"),
        },
    },
    "bank_statement": {
        "domain": "BANKING",
        "lexicons": {
            "fra": (
                "relevé bancaire",
                "releve de compte",
                "extrait de compte",
                "solde",
                "débit",
                "crédit",
                "iban",
            ),
            "eng": (
                "bank statement",
                "account statement",
                "balance",
                "debit",
                "credit",
                "iban",
                "transaction",
            ),
            "deu": ("kontoauszug", "bankauszug", "kontostand", "lastschrift", "gutschrift", "iban"),
            "ita": ("estratto conto", "saldo", "addebito", "accredito", "iban"),
            "spa": ("extracto bancario", "estado de cuenta", "saldo", "débito", "crédito", "iban"),
            "nld": ("bankafschrift", "rekeningafschrift", "saldo", "debet", "credit", "iban"),
            "ara": ("كشف حساب", "رصيد", "مدين", "دائن", "ايبان"),
        },
    },
    "invoice": {
        "domain": "FINANCE",
        "lexicons": {
            "fra": (
                "facture",
                "facturé",
                "montant dû",
                "total ttc",
                "tva",
                "échéance",
                "fournisseur",
            ),
            "eng": ("invoice", "amount due", "total due", "tax", "vat", "due date", "supplier"),
            "deu": (
                "rechnung",
                "rechnungsbetrag",
                "gesamtbetrag",
                "mehrwertsteuer",
                "fällig",
                "lieferant",
            ),
            "ita": ("fattura", "importo dovuto", "totale", "iva", "scadenza", "fornitore"),
            "spa": ("factura", "importe adeudado", "total", "iva", "vencimiento", "proveedor"),
            "nld": (
                "factuur",
                "verschuldigd bedrag",
                "totaal",
                "btw",
                "vervaldatum",
                "leverancier",
            ),
            "ara": ("فاتورة", "المبلغ المستحق", "ضريبة", "الإجمالي", "المورد"),
        },
    },
    "diploma": {
        "domain": "ACADEMIC",
        "lexicons": {
            "fra": (
                "diplôme",
                "diplome",
                "certificat de réussite",
                "université",
                "licence",
                "master",
                "formation",
            ),
            "eng": (
                "diploma",
                "degree certificate",
                "certificate of completion",
                "university",
                "bachelor",
                "master degree",
            ),
            "deu": ("diplom", "zeugnis", "hochschule", "universität", "abschluss"),
            "ita": ("diploma", "laurea", "certificato di laurea", "università"),
            "spa": (
                "diploma",
                "título universitario",
                "certificado de estudios",
                "universidad",
                "licenciatura",
            ),
            "nld": ("diploma", "getuigschrift", "universiteit", "opleiding"),
            "ara": ("شهادة جامعية", "دبلوم", "جامعة", "شهادة تخرج"),
        },
    },
    "administrative_form": {
        "domain": "ADMINISTRATION",
        "lexicons": {
            "fra": (
                "formulaire administratif",
                "formulaire",
                "cerfa",
                "déclaration administrative",
                "demande",
                "préfecture",
                "administration",
            ),
            "eng": (
                "administrative form",
                "application form",
                "declaration form",
                "government form",
                "authority",
            ),
            "deu": ("verwaltungsformular", "antragsformular", "formular", "behörde", "erklärung"),
            "ita": (
                "modulo amministrativo",
                "modulo",
                "dichiarazione amministrativa",
                "amministrazione",
            ),
            "spa": (
                "formulario administrativo",
                "formulario",
                "declaración administrativa",
                "administración",
            ),
            "nld": ("administratief formulier", "aanvraagformulier", "formulier", "overheid"),
            "ara": ("نموذج إداري", "استمارة إدارية", "إقرار إداري", "إدارة"),
        },
    },
}


def _score(
    text: str,
    spec: dict,
    languages: list[str],
    eu_lexicons: dict[str, tuple[str, ...]] | None = None,
) -> tuple[float, list[dict[str, object]]]:
    low = _fold(text)
    score = 0.0
    hits: list[dict[str, object]] = []
    lexicons = dict(spec["lexicons"])
    # LOT 2.3 : lexiques EuroVoc des langues ajoutées, seulement si la langue est
    # détectée dans le document (aucun effet sur les documents historiques).
    for lang, words in (eu_lexicons or {}).items():
        if lang in (languages or ()):
            lexicons[lang] = words
    added = set(lexicons) - set(spec["lexicons"])
    # Document dont la langue principale est une langue ajoutée : toutes les
    # expressions en mot entier (« iva » ne doit pas compter dans « effektiva »).
    # Les documents en langues historiques gardent le comptage d'origine.
    strict = bool(languages) and languages[0] in ADDED_LANGUAGES
    for lang, words in lexicons.items():
        language_factor = 1.15 if not languages or lang in languages else 0.9
        for word in words:
            if strict or lang in added:
                # Langues ajoutées : mot entier uniquement (pas de sous-chaîne).
                pattern = r"(?<!\w)" + re.escape(_fold(word)) + r"(?!\w)"
                hit = len(re.findall(pattern, low))
            else:
                hit = low.count(_fold(word))
            if hit:
                # Multi-word titles are strong evidence; isolated generic flags
                # are deliberately weak so ``contract`` cannot beat an employer
                # certificate phrase in a mixed-language form.
                parts = len(word.split())
                weight = 4.5 if parts >= 3 else 3.0 if parts == 2 else 0.65
                contribution = hit * weight * language_factor
                score += contribution
                hits.append(
                    {
                        "language": lang,
                        "phrase": word,
                        "count": hit,
                        "weight": round(contribution, 3),
                    }
                )
    return score, hits


def classify_document(text: str, languages: list[str] | None = None) -> dict[str, object]:
    languages = list(languages or detect_language(text)[1])
    scored = {
        name: _score(text, spec, languages, EU_TYPE_LEXICONS.get(name))
        for name, spec in _TYPE_SPECS.items()
    }
    scores = {name: value[0] for name, value in scored.items()}
    evidence = {name: value[1] for name, value in scored.items()}
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_name, best_score = ordered[0]
    second_name, second_score = ordered[1]
    warnings: list[dict[str, object]] = []
    if best_score <= 0:
        document_type = "unknown"
        confidence = 0.0
        warnings.append(
            {
                "code": "UNKNOWN_DOCUMENT_TYPE",
                "severity": "warning",
                "message": "Aucun lexique documentaire suffisamment explicable n'a été trouvé; revue humaine requise.",
            }
        )
        domain = "unknown"
    else:
        best_strong = any(item["weight"] >= 3.0 for item in evidence[best_name])
        second_strong = any(item["weight"] >= 3.0 for item in evidence[second_name])
        ambiguous = second_score > 0 and best_score < second_score * 1.35
        if best_strong and not second_strong and best_score >= second_score * 0.85:
            ambiguous = False
        if ambiguous:
            warnings.append(
                {
                    "code": "AMBIGUOUS_DOCUMENT_TYPE",
                    "severity": "warning",
                    "message": "Plusieurs types documentaires ont des indices proches; revue humaine requise.",
                }
            )
        document_type = best_name
        confidence = min(
            0.99, 0.42 + 0.08 * best_score + (0.12 if best_score > second_score * 1.8 else 0.0)
        )
        if ambiguous:
            confidence = min(confidence, 0.62)
        domain = _TYPE_SPECS[best_name]["domain"]
    return {
        "document_type": document_type,
        "domain": domain,
        "confidence": round(confidence, 3),
        "type_confidence": round(confidence, 3),
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "evidence": evidence,
        "domain_flags": {
            _TYPE_SPECS[name]["domain"]: [item["phrase"] for item in evidence[name]]
            for name in _TYPE_SPECS
            if evidence[name]
        },
        "ambiguous": any(w["code"] == "AMBIGUOUS_DOCUMENT_TYPE" for w in warnings),
        "warnings": warnings,
        "languages": languages,
    }


def classify_hr(text: str, languages: list[str] | None = None) -> dict[str, object]:
    """Compatibility wrapper retaining the historical classifier entry point."""
    result = classify_document(text, languages)
    hr_score = result["scores"].get("employment_certificate", 0) + result["scores"].get(
        "contract", 0
    )
    result["hr_relevance"] = round(float(hr_score), 3)
    return result
