"""LOT 2.3 Phase B — D-DET-02 : un bloc étiqueté français n'est plus retiré en silence.

Avant correction, la finalisation retirait l'alerte « non traduit » de **tout** bloc
étiqueté français et le statut de bloc le déclarait « déjà français » : un bloc
anglais mal étiqueté n'était ni traduit ni signalé. Les tests vérifient aussi que du
vrai français (y compris avec des emprunts) ne déclenche aucune alerte nouvelle.
"""

from __future__ import annotations

import pytest

from app.application import jobs
from app.documents import language_evidence
from app.documents.block_status import classify_blocks

FRENCH_LABEL_ISSUE = "FRENCH_LABEL_UNVERIFIED"


def french_label_unverified(text, languages):
    # Import différé : sur le code d'origine, seul le test concerné échoue.
    return language_evidence.french_label_unverified(text, languages)


def _reconcile_french_alerts(ir, result):
    return jobs._reconcile_french_alerts(ir, result)


needs_lexicon = pytest.mark.skipif(
    not language_evidence.available(), reason="lexique hors ligne (wordfreq) absent"
)

ENGLISH = "Gross salary and notice period of the employee"
FRENCH = "Le salaire brut et la période de préavis du salarié"


@needs_lexicon
@pytest.mark.parametrize(
    "text",
    [
        ENGLISH,
        "Please sign and return the attached employment contract",
    ],
)
def test_english_text_labelled_french_is_unverified(text):
    assert french_label_unverified(text, ["fra", "eng"]) is True


@needs_lexicon
@pytest.mark.parametrize(
    "text",
    [
        FRENCH,
        "Total",
        "Date de naissance",
        "Merci de confirmer votre rendez-vous par email avant le week-end",
        "Contrat de travail à durée indéterminée",
    ],
)
def test_real_french_raises_no_new_alert(text):
    assert french_label_unverified(text, ["fra", "eng"]) is False


@pytest.mark.parametrize("text", ["الأجر الإجمالي للموظف", "Ακαθάριστος μισθός", "Брутна заплата"])
def test_non_latin_script_cannot_be_french(text):
    # Règle d'écriture : indépendante du lexique hors ligne.
    assert french_label_unverified(text, ["fra"]) is True


def test_short_or_empty_text_is_not_flagged():
    assert french_label_unverified("", ["fra"]) is False
    assert french_label_unverified("5 €", ["fra"]) is False


def _ir(*blocks):
    return {
        "language": "fra",
        "languages": [{"code": "fra"}, {"code": "eng"}],
        "pages": [{"number": 1, "blocks": list(blocks)}],
    }


@needs_lexicon
def test_block_status_keeps_mislabelled_block_for_review():
    ir = _ir(
        {"id": "b1", "text": ENGLISH, "language": "fra"},
        {"id": "b2", "text": FRENCH, "language": "fra"},
    )
    status = classify_blocks(ir, {"b1": ENGLISH, "b2": FRENCH}, [])
    assert status["blocks"]["b1"]["status"] == "UNCERTAIN"
    assert status["blocks"]["b1"]["reason"] == "french_label_unverified"
    assert status["blocks"]["b2"]["status"] == "PRESERVED_INTENTIONALLY"
    assert status["blocks"]["b2"]["reason"] == "already_french"


@needs_lexicon
def test_finalisation_signals_mislabelled_block_and_still_clears_real_french():
    ir = _ir(
        {"id": "b1", "text": ENGLISH, "language": "fra"},
        {"id": "b2", "text": FRENCH, "language": "fra"},
    )
    # Formats réels : le moteur écrit ``block_id`` ; l'évaluation qualité ``block_ids``.
    result = {
        "translations": {"b1": ENGLISH, "b2": FRENCH},
        "untranslated_blocks": ["b1", "b2"],
        "issues": [
            {"code": "UNTRANSLATED", "severity": "error", "block_id": "b1"},
            {"code": "UNTRANSLATED", "severity": "error", "block_id": "b2"},
        ],
        "quality": {
            "untranslated_blocks": ["b1", "b2"],
            "issues": [
                {"code": "UNTRANSLATED", "severity": "error", "block_ids": ["b1"]},
                {"code": "UNTRANSLATED", "severity": "error", "block_ids": ["b2"]},
            ],
        },
    }
    flagged = _reconcile_french_alerts(ir, result)
    assert flagged == ["b1"]
    for holder in (result, result["quality"]):
        codes = {
            (i["code"], block_id)
            for i in holder["issues"]
            for block_id in ([i["block_id"]] if "block_id" in i else []) + i.get("block_ids", [])
        }
        assert ("UNTRANSLATED", "b2") not in codes  # fausse alerte retirée, comme avant
        assert ("UNTRANSLATED", "b1") in codes  # alerte d'origine conservée
        assert (FRENCH_LABEL_ISSUE, "b1") in codes  # signalement explicite
        assert holder["untranslated_blocks"] == ["b1"]


def test_finalisation_is_unchanged_without_french_labelled_block():
    ir = _ir({"id": "b1", "text": ENGLISH, "language": "eng"})
    result = {
        "translations": {"b1": "Salaire brut"},
        "untranslated_blocks": [],
        "issues": [],
    }
    assert _reconcile_french_alerts(ir, result) == []
    assert result["issues"] == [] and result["untranslated_blocks"] == []


@needs_lexicon
def test_translated_or_protected_french_labelled_blocks_are_not_flagged():
    ir = _ir(
        {"id": "b1", "text": ENGLISH, "language": "fra"},
        {"id": "b2", "text": ENGLISH, "language": "fra", "protected": True},
    )
    result = {"translations": {"b1": "Salaire brut et préavis", "b2": ENGLISH}, "issues": []}
    assert _reconcile_french_alerts(ir, result) == []
