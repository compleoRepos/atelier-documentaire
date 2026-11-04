"""LOT 2.3 — détection des 24 langues de l'UE (et de l'arabe), sans dégrader l'existant.

Mesures complètes (EUR-Lex, jeux DEV/TEST, corpus bancaire) dans le rapport de
Phase B ; ces tests figent les comportements essentiels et les gardes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain import classification as c

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "rag_ue_languages.json").read_text(
        encoding="utf-8"
    )
)
ISO3 = {
    "ar": "ara", "bg": "bul", "cs": "ces", "da": "dan", "de": "deu", "el": "ell", "en": "eng",
    "es": "spa", "et": "est", "fi": "fin", "ga": "gle", "hr": "hrv", "hu": "hun", "it": "ita",
    "lt": "lit", "lv": "lav", "mt": "mlt", "nl": "nld", "pl": "pol", "pt": "por", "ro": "ron",
    "sk": "slk", "sl": "slv", "sv": "swe",
}  # fmt: skip


@pytest.mark.parametrize(
    "item", FIXTURE["entries"], ids=[e["language"] for e in FIXTURE["entries"]]
)
def test_official_paragraph_is_detected_in_its_language(item):
    primary, languages, confidence = c.detect_language(item["text"])
    assert primary == ISO3[item["language"]]
    assert languages[0] == primary and 0 < confidence <= 1


def test_french_control_stays_french():
    assert c.detect_language(FIXTURE["french_control"]["text"])[0] == "fra"


def test_added_languages_are_exactly_the_18_other_eu_languages():
    assert len(c.ADDED_LANGUAGES) == 18
    historic = {"fra", "eng", "deu", "ita", "spa", "nld", "ara"}
    assert not c.ADDED_LANGUAGES & historic
    assert set(c._LANG_MAP.values()) == historic  # table historique inchangée


def test_uppercase_title_is_not_moved_to_an_added_language():
    # Le détecteur voit du portugais dans ce titre en capitales ; la confirmation
    # en minuscules l'empêche (résultat d'origine conservé).
    primary, languages, _ = c.detect_language("LAVORO NOTTURNO - LAVORO A TURNI - RITMO DI LAVORO")
    assert primary == "ita" and "por" not in languages


def test_long_document_of_another_language_does_not_trigger_irish_or_maltese():
    # Quelques faux indices (in-house, it-...) dans un long texte : densité trop faible.
    text = (
        "The in-house team reviewed the t-shirt order and the it-department budget. "
        * 3
        + "The employer confirms the salary, the employment start date and the notice period "
        "for the employee under the terms of the signed contract of employment. " * 6
    )
    primary, languages, _ = c.detect_language(text)
    assert primary == "eng"
    assert "gle" not in languages and "mlt" not in languages


@pytest.mark.parametrize("text", ["", "   ", "12/03/2026", "IBAN"])
def test_short_or_empty_text_stays_unknown(text):
    assert c.detect_language(text)[0] == "unknown"


def test_added_language_document_uses_whole_words_only():
    # « iva » (TVA it/es) ne doit pas compter dans des mots suédois.
    text = "Arbetsgivare · Lön\nEffektiva och positiva åtgärder för aktiva arbetstagare i Sverige."
    result = c.classify_document(text)
    assert result["languages"][0] == "swe"
    assert not any(hit["phrase"] == "iva" for hit in result["evidence"]["invoice"])
    assert result["domain"] == "HR"


def test_historic_documents_keep_the_original_substring_counting():
    # Comportement d'origine conservé à l'identique pour les langues historiques.
    text = "Private employment record. The employer confirms the salary of the employee."
    result = c.classify_document(text)
    assert result["languages"][0] == "eng"
    assert any(hit["phrase"] == "iva" for hit in result["evidence"]["invoice"])


def test_added_language_lexicons_are_ignored_when_the_language_is_not_detected():
    from app.domain.eu_type_lexicons import EU_TYPE_LEXICONS

    words = EU_TYPE_LEXICONS["contract"]["pol"]
    text = "Contrat de travail entre l'employeur et le salarié. " + " ".join(words)
    result = c.classify_document(text, ["fra"])
    assert not any(hit["language"] == "pol" for hit in result["evidence"]["contract"])
    assert any(
        hit["language"] == "pol"
        for hit in c.classify_document(text, ["fra", "pol"])["evidence"]["contract"]
    )


# --- Marqueurs distinctifs irlandais / maltais (``app.domain.eu_lang_markers``) ---

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Fragments officiels EUR-Lex que langdetect (sans profil irlandais) prenait
        # pour de l'anglais ou de l'espagnol, et le maltais court pour de l'italien.
        ("maidir le córais faireacháin uathoibrithe:", "gle"),
        ("dáta tosaithe an chaidrimh fostaíochta;", "gle"),
        ("tráth ar bith arna iarraidh sin dóibh.", "gle"),
        ("Din id-Direttiva hija indirizzata lill-Istati Membri.", "mlt"),
        ("Paragrafi 1, 2 u 3 għandhom japplikaw ukoll għal:", "mlt"),
    ],
)
def test_short_irish_and_maltese_fragments_are_recognised(text, expected):
    assert c.detect_language(text)[0] == expected


def test_markers_exclude_words_attested_in_other_languages():
    from app.domain.eu_lang_markers import EU_LANGUAGE_MARKERS

    assert set(EU_LANGUAGE_MARKERS) == {"gle", "mlt"}
    for word in ("car", "fil", "meta", "pointe", "fail", "min", "don", "sort", "mix", "fit"):
        assert all(word not in markers for markers in EU_LANGUAGE_MARKERS.values()), word


@pytest.mark.parametrize(
    "text",
    [
        (
            "Au fil des ans, la banque a renforcé le suivi des crédits. Le client déclare que "
            "les informations fournies sont exactes. Au fil du temps, la méta analyse des "
            "dossiers montre une amélioration. "
        )
        * 4,
        "car le client a fourni un mix de pièces",
        "Don de sang, sort du fil",
    ],
)
def test_french_text_with_lookalike_words_never_gets_irish_or_maltese(text):
    primary, languages, _confidence = c.detect_language(text)
    assert primary == "fra"
    assert "gle" not in languages and "mlt" not in languages


def test_generated_markers_module_is_reproducible_from_versioned_data():
    import importlib.util

    tool = REPO / "tools" / "rag_ue" / "lang_markers_build.py"
    spec = importlib.util.spec_from_file_location("lang_markers_build", tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result, acts, digest = module.build(REPO / "data" / "rag-ue" / "eurlex" / "eurlex")
    generated = module.render(result, acts, digest)
    current = (REPO / "backend" / "app" / "domain" / "eu_lang_markers.py").read_text(
        encoding="utf-8"
    )
    assert generated == current


@pytest.mark.parametrize(
    "text",
    [
        # Lignes officielles que le détecteur d'origine laissait « inconnu » et que la seule
        # voie statistique attribuait à une langue ajoutée (estonien, danois).
        "minimum paid annual leave;",
        "geldmarktinstrumenten,",
    ],
)
def test_statistical_path_keeps_original_behaviour_on_historic_lookalikes(text):
    assert c.detect_language(text) == ("unknown", [], 0.0)


def test_statistical_path_still_detects_an_added_language_phrase():
    assert c.detect_language("Työntekijöiden vähimmäisvuosiloma;")[0] == "fin"
