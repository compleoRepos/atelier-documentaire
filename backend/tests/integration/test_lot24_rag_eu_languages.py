"""LOT 2.4 — RAG : les 24 langues officielles de l'UE sur le vrai chemin.

Import -> validation à quatre yeux -> publication -> injection dans le contexte de traduction.
Les clés de recherche ne changent pas : seules l'acceptation à l'import et les alias ISO 639-2
sont étendus. Données synthétiques uniquement.
"""

from __future__ import annotations

import pytest

from app.application import rag_bridge
from app.rag.terminology.linguistic import EU_OFFICIAL_LANGUAGES, SUPPORTED_LANGUAGES
from app.rag.terminology.normalizer import normalize_language

from .rag_support import make_rag_client, publish_referential

ISO_639_2 = {
    "bul": "bg", "ces": "cs", "cze": "cs", "dan": "da", "deu": "de", "ger": "de", "ell": "el",
    "gre": "el", "eng": "en", "spa": "es", "est": "et", "fin": "fi", "fra": "fr", "fre": "fr",
    "gle": "ga", "hrv": "hr", "hun": "hu", "ita": "it", "lit": "lt", "lav": "lv", "mlt": "mt",
    "nld": "nl", "dut": "nl", "pol": "pl", "por": "pt", "ron": "ro", "rum": "ro", "slk": "sk",
    "slo": "sk", "slv": "sl", "swe": "sv",
}  # fmt: skip


def test_all_24_official_languages_are_accepted_and_history_is_kept():
    assert len(EU_OFFICIAL_LANGUAGES) == len(set(EU_OFFICIAL_LANGUAGES)) == 24
    assert SUPPORTED_LANGUAGES[:5] == ("fr", "ar", "en", "es", "de")  # ordre historique
    assert set(EU_OFFICIAL_LANGUAGES) | {"ar"} == set(SUPPORTED_LANGUAGES)
    assert len(SUPPORTED_LANGUAGES) == 25


@pytest.mark.parametrize(("code", "expected"), sorted(ISO_639_2.items()))
def test_iso_639_2_codes_map_to_iso_639_1(code, expected):
    assert normalize_language(code) == expected
    assert normalize_language(code.upper()) == expected


def test_non_eu_language_stays_out_of_scope():
    assert normalize_language("ja") == "ja"
    assert "ja" not in SUPPORTED_LANGUAGES


ENTRIES = [
    {
        "source_language": "el",
        "source_term": "μισθός",
        "target_language": "fr",
        "target_term": "salaire",
        "domain": "hr",
        "provenance": "test-synthetique",
    },
    {
        "source_language": "bg",
        "source_term": "трудов договор",
        "target_language": "fr",
        "target_term": "contrat de travail",
        "domain": "hr",
        "provenance": "test-synthetique",
    },
    {
        "source_language": "pl",
        "source_term": "okres wypowiedzenia",
        "target_language": "fr",
        "target_term": "délai de préavis",
        "domain": "hr",
        "provenance": "test-synthetique",
    },
    {
        "source_language": "mt",
        "source_term": "ħlas",
        "target_language": "fr",
        "target_term": "paiement",
        "domain": "hr",
        "provenance": "test-synthetique",
    },
]


def _terminology(app, ids, language: str, text: str) -> list[dict]:
    ir = {
        "language": language,
        "domain": "HR",
        "pages": [{"number": 1, "blocks": [{"id": "b1", "text": text, "language": language}]}],
    }
    # L'injection ne concerne que le moteur privé (avec « offline », le RAG reste en ombre).
    options = {"engine": "private", "target_language": "fr", "glossary": [], "memory": {}}
    reports: list[dict] = []
    result = rag_bridge.augment_translation_options(
        app.state.settings,
        app.state.session_factory,
        ids["tenant-a"],
        None,
        ir,
        options,
        on_report=reports.append,
    )
    return (result.get("document_memory") or {}).get("terminology") or []


def _injected(app, ids, language: str, text: str) -> list[str]:
    terminology = _terminology(app, ids, language, text)
    # Sources : forme lue dans le document (avec l'article maltais le cas échéant).
    return [item["source"] for item in terminology]


def _targets(app, ids, language: str, text: str) -> list[str]:
    return [item["target"] for item in _terminology(app, ids, language, text)]


@pytest.mark.parametrize(
    ("language", "text", "expected"),
    [
        ("el", "Ο ΜΙΣΘΌΣ: καταβάλλεται μηνιαίως.", "μισθός"),  # majuscules, accent, ponctuation
        ("bg", "Трудов договор (срочен) — подписан.", "трудов договор"),
        ("pl", "Okres wypowiedzenia, zgodnie z umową.", "okres wypowiedzenia"),
        ("mt", "Il-ħlas isir kull xahar.", "Il-ħlas"),  # article attaché (règle maltaise)
    ],
)
def test_eu_language_entry_is_injected_after_four_eyes_publication(
    app_env, monkeypatch, language, text, expected
):
    client, app, ids = make_rag_client(monkeypatch, mode="ACTIVE")
    publish_referential(client, ids, entries=ENTRIES, name="UE test", max_mode="ACTIVE")
    assert expected in _injected(app, ids, language, text)


def test_entry_of_another_language_is_not_injected(app_env, monkeypatch):
    client, app, ids = make_rag_client(monkeypatch, mode="ACTIVE")
    publish_referential(client, ids, entries=ENTRIES, name="UE test", max_mode="ACTIVE")
    # Le texte polonais ne contient aucun terme grec ou bulgare publié.
    assert _injected(app, ids, "pl", "Wynagrodzenie zasadnicze.") == []


def test_maltese_article_aliases_follow_assimilation_and_touch_only_maltese():
    from app.rag.terminology.linguistic import alias_keys

    assert "il-ħlas" in alias_keys("ħlas", "mt")  # consonne « lunaire »
    assert "ix-xogħol" in alias_keys("xogħol", "mt")  # consonne solaire : assimilation
    assert "il-xogħol" not in alias_keys("xogħol", "mt")
    assert "l-impjegat" in alias_keys("impjegat", "mt")  # voyelle
    assert "tal-impjegat" in alias_keys("impjegat", "mt")
    assert "l-għalliem" in alias_keys("għalliem", "mt")  # « għ » se comporte comme une voyelle
    assert "il-hlas tas-salarju" not in alias_keys("ħlas tas-salarju", "mt")
    assert len(alias_keys("ħlas", "mt")) == 9
    assert alias_keys("il-ħlas", "mt") == set()  # article déjà présent : rien d'ajouté
    for language in ("en", "fr", "it", "el", "ar", None):
        assert alias_keys("ħlas", language) == set()  # aucune autre langue n'est touchée
    assert alias_keys("Kündigung", "de") == {"kuendigung"}  # règle allemande inchangée


@pytest.mark.parametrize(
    ("text", "entry", "expected"),
    [
        ("Ix-xogħol jibda fit-8.", "xogħol", True),
        ("Id-drittijiet tal-impjegat.", "impjegat", True),
        ("Il-ħlas isir kull xahar.", "ħlas", True),
        ("Ħlas ieħor.", "ħlas", True),  # sans article
        ("Il-ħlasijiet.", "ħlas", False),  # autre mot : jamais d'appariement partiel
    ],
)
def test_maltese_term_is_found_behind_the_attached_article(
    app_env, monkeypatch, text, entry, expected
):
    client, app, ids = make_rag_client(monkeypatch, mode="ACTIVE")
    entries = [
        {
            "source_language": "mt",
            "source_term": entry,
            "target_language": "fr",
            "target_term": "cible-mt",
            "domain": "hr",
            "provenance": "test-synthetique",
        }
    ]
    publish_referential(client, ids, entries=entries, name="MT", max_mode="ACTIVE")
    assert (_targets(app, ids, "mt", text) == ["cible-mt"]) is expected
