"""Entity comparison false positives found on real multilingual originals.

Texts are synthetic paraphrases: no original document content.
"""

from __future__ import annotations

import pytest

from app.ai.quality.entities import compare_entities, extract_entities


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("Signed in Rotterdam d.d. 18 juni 2021", "Signé à Rotterdam le 18 juin 2021"),
        ("موقع في المدينة بتاريخ 18 يونيو 2021", "Fait en ville le 18 juin 2021"),
        ("Valid until 3 December 2026", "Valable jusqu'au 3 décembre 2026"),
        ("Firmato il 5 giugno 2024", "Signé le 5 juin 2024"),
        ("Fecha 7 marzo 2023", "Date 7 mars 2023"),
        ("Datum 16.09.2021", "Date 16.09.2021"),
        (
            "should be used before 31 December each year",
            "à solder au 31 décembre chaque année",
        ),
    ],
)
def test_localised_dates_keep_their_invariant(source, target):
    assert compare_entities(source, target)["errors"] == []


def test_changed_localised_date_is_still_critical():
    errors = compare_entities("Signed 12 June 2024", "Signé le 12 juillet 2024")["errors"]
    assert [e["code"] for e in errors] == ["CRITICAL_ENTITY_MODIFIED"]
    assert errors[0]["entity_type"] == "date"


@pytest.mark.parametrize(
    "prose",
    [
        "Date de reprise te 25 jours sans compter les ponts",
        "used before 31 December of the year it relates to",
        "de 12 mois au moins pour tous les salariés",
    ],
)
def test_prose_is_never_an_iban(prose):
    assert not [e for e in extract_entities(prose) if e["type"] == "iban"]


def test_real_iban_formats_detected_without_phone_or_name_duplicates():
    found = extract_entities("IBAN FR76 3000 6000 0112 3456 7890 189 et NL91ABNA0417164300")
    assert [e["value"] for e in found if e["type"] == "iban"] == [
        "FR76 3000 6000 0112 3456 7890 189",
        "NL91ABNA0417164300",
    ]
    assert not [e for e in found if e["type"] in {"phone", "name"}]


def test_changed_iban_digit_is_critical():
    errors = compare_entities("IBAN NL91ABNA0417164300", "IBAN NL91ABNA0417164301")["errors"]
    assert any(
        e["code"] == "CRITICAL_ENTITY_MODIFIED" and e["entity_type"] == "iban" for e in errors
    )


def test_spanish_date_with_connectors():
    assert (
        compare_entities("En la ciudad a 13 de enero de 2021", "Dans la ville, le 13 janvier 2021")[
            "errors"
        ]
        == []
    )


def test_french_possessive_is_not_a_company_suffix():
    found = extract_entities("dans les 10 jours après sa signature")
    assert not [e for e in found if e["type"] == "company"]
    assert [e["value"] for e in found if e["type"] == "number"] == ["10"]


def test_company_keeps_only_its_name_tokens():
    found = extract_entities("employé par Acme Holding B.V. depuis 2020")
    assert [e["value"] for e in found if e["type"] == "company"] == ["Acme Holding B.V."]


def test_single_omission_does_not_cascade_into_modifications():
    source = "Articles 10, 27, 2018, 5, 12 et 7."
    target = "Articles 27, 2018, 5, 12 et 7."
    errors = compare_entities(source, target)["errors"]
    assert [(e["code"], e["expected"]) for e in errors] == [("CRITICAL_ENTITY_MISSING", "10")]


def test_real_modification_still_reported():
    errors = compare_entities("Montant 1250 et délai 30", "Montant 1260 et délai 30")["errors"]
    assert [(e["code"], e["expected"], e["actual"]) for e in errors] == [
        ("CRITICAL_ENTITY_MODIFIED", "1250", "1260")
    ]
