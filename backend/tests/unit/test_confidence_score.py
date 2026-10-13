"""RUN26: documentary confidence score (pure function, no corpus data)."""

import pytest

from app.documents import confidence_score as cs


def _perfect() -> dict:
    return {name: {key: 1.0 for key in spec["components"]} for name, spec in cs.DIMENSIONS.items()}


def test_weights_sum_to_100_and_every_dimension_is_listed():
    assert sum(spec["weight"] for spec in cs.DIMENSIONS.values()) == 100
    assert set(cs.DIMENSIONS) == {
        "coverage",
        "translation",
        "source_fidelity",
        "entities",
        "layout",
        "ocr",
        "hallucination",
        "evidence",
    }


def test_all_measured_and_perfect_without_human_validation_stays_review_required():
    result = cs.score_document(_perfect())
    assert result["score"] == 100.0 and result["score_max"] == 100.0
    assert result["threshold_met"] is True
    assert result["status"] == "REVIEW_REQUIRED"  # no authorised human validation
    assert cs.score_document(_perfect(), human_validated=True)["status"] == "VALIDATED"


def test_unknown_is_never_scored_positive():
    comps = _perfect()
    comps["translation"]["semantic_accuracy"] = None
    result = cs.score_document(comps)
    dim = result["dimensions"]["translation"]
    assert dim["min"] == 0.5 and dim["max"] == 1.0 and dim["measured_share"] == 0.5
    assert result["score"] == 92.5  # 15 * 0.5 lost in the lower bound
    assert result["score_max"] == 100.0
    assert result["threshold_met"] is False


def test_not_applicable_component_is_left_out_but_unknown_is_not():
    comps = _perfect()
    comps["entities"]["digit_sequences"] = cs.NOT_APPLICABLE
    result = cs.score_document(comps)
    assert result["dimensions"]["entities"]["applicable"] is False
    assert result["score"] == 100.0
    comps["entities"]["digit_sequences"] = None
    assert cs.score_document(comps)["score"] == 85.0


def test_critical_defect_blocks_the_threshold_whatever_the_average():
    defect = [{"code": "ENTITY_DIGITS_MISMATCH", "count": 1, "source": "scorecard"}]
    result = cs.score_document(_perfect(), defect, human_validated=True)
    assert result["score"] == 100.0
    assert result["threshold_met"] is False
    assert result["status"] == "REVIEW_REQUIRED"


def test_evidence_failure_blocks_the_document():
    result = cs.score_document(_perfect(), blocking=["ORIGINAL_INTEGRITY_NOT_PROVEN"])
    assert result["status"] == "BLOCKED" and result["threshold_met"] is False


def test_out_of_range_or_unexpected_component_is_refused():
    comps = _perfect()
    comps["coverage"]["written_share"] = 1.2
    with pytest.raises(ValueError):
        cs.score_document(comps)
    comps = _perfect()
    comps["coverage"]["invented"] = 1.0
    with pytest.raises(KeyError):
        cs.score_document(comps)


def test_corpus_is_an_unweighted_mean_and_lists_documents_with_defects():
    good = cs.score_document(_perfect())
    comps = _perfect()
    comps["coverage"]["written_share"] = 0.5
    weak = cs.score_document(comps, [{"code": "X", "count": 1}])
    corpus = cs.score_corpus({"A": good, "B": weak})
    assert corpus["score"] == 95.0
    assert corpus["documents_with_critical_defects"] == ["B"]
    assert corpus["threshold_met"] is False


def test_structural_ceiling_without_human_references():
    ceiling = cs.structural_ceiling(
        {
            "translation": ["semantic_accuracy"],
            "ocr": ["character_accuracy"],
            "hallucination": ["proven_by_reference"],
        }
    )
    assert ceiling == pytest.approx(84.2, abs=0.05)
