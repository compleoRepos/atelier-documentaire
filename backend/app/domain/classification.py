"""Classification explicable du type et du domaine des documents.

Le classifieur est volontairement lexical et déterministe : il fournit une
orientation auditable, jamais une validation sémantique ou une traduction.
"""

from __future__ import annotations

import unicodedata
from collections import Counter

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
    if detect_langs:
        try:
            for guess in detect_langs(text[:12000]):
                code = _LANG_MAP.get(guess.lang)
                if code:
                    detector_scores[code] = max(detector_scores.get(code, 0.0), float(guess.prob))
                    scores[code] += float(guess.prob) * 0.75
        except Exception:
            detector_scores = {}
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


def _score(text: str, spec: dict, languages: list[str]) -> tuple[float, list[dict[str, object]]]:
    low = _fold(text)
    score = 0.0
    hits: list[dict[str, object]] = []
    for lang, words in spec["lexicons"].items():
        language_factor = 1.15 if not languages or lang in languages else 0.9
        for word in words:
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
    scored = {name: _score(text, spec, languages) for name, spec in _TYPE_SPECS.items()}
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
