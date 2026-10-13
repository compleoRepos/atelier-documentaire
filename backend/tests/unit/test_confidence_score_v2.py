"""RUN27: documentary confidence v2 + independent verifier (synthetic data only)."""

import random
import sys
from pathlib import Path

import pytest

from app.documents import confidence_score as cs1
from app.documents import confidence_score_v2 as cs

TOOLS = str(Path(__file__).resolve().parents[3] / "tools" / "recette")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import score_verify  # noqa: E402

EVIDENCE = {k: True for k in cs.EVIDENCE_REQUIREMENTS}


def _perfect(value=1.0) -> dict:
    return {
        name: {key: value for key in spec["components"]} for name, spec in cs.DIMENSIONS.items()
    }


def _verify(result: dict) -> dict:
    """Independent recomputation (Fractions, own weight table) of a v2 result."""
    checked = score_verify.verify_document_v2(result)
    assert checked["deviation_lower"] < 1e-9 and checked["deviation_upper"] < 1e-9
    assert checked["deviation_ceiling"] < 1e-9
    return checked


def test_evidence_is_a_gate_and_quality_weights_keep_v1_proportions():
    assert cs.TOTAL_WEIGHT == 90
    for name, spec in cs.DIMENSIONS.items():
        assert spec["weight"] == cs1.DIMENSIONS[name]["weight"]  # relative weights unchanged
    assert "evidence" not in cs.DIMENSIONS
    assert set(cs.EVIDENCE_REQUIREMENTS) == set(cs1.DIMENSIONS["evidence"]["components"])


def test_all_measured_and_perfect():
    result = cs.score_document(_perfect(), EVIDENCE)
    assert (result["score_min"], result["score_max"], result["ceiling"]) == (100.0, 100.0, 100.0)
    assert result["threshold_met"] is True and result["unknowns"] == []
    assert result["status"] == "REVIEW_REQUIRED"  # no authorised human validation
    assert cs.score_document(_perfect(), EVIDENCE, human_validated=True)["status"] == "VALIDATED"
    _verify(result)


def test_all_measured_with_zero_values():
    result = cs.score_document(_perfect(0.0), EVIDENCE, human_validated=True)
    assert (result["score_min"], result["score_max"]) == (0.0, 0.0)
    assert result["ceiling"] == 100.0  # nothing unknown: a perfect measure would reach 100
    assert result["threshold_met"] is False and result["status"] == "VALIDATED"  # validated as bad
    _verify(result)


def test_unknowns_are_never_positive_and_are_qualified():
    comps = _perfect()
    comps["translation"]["semantic_accuracy"] = None  # human reference missing
    comps["coverage"]["written_share"] = None  # a tool did not produce its measure
    result = cs.score_document(comps, EVIDENCE, human_validated=True)
    reasons = {(u["dimension"], u["component"]): u["reason"] for u in result["unknowns"]}
    assert reasons == {
        ("translation", "semantic_accuracy"): cs.HUMAN_REFERENCE_MISSING,
        ("coverage", "written_share"): cs.MEASUREMENT_MISSING,
    }
    # lower bound: unknown = 0 ; upper bound: unknown = 1
    assert result["exact"]["lower"] == pytest.approx(100 * (90 - 20 - 7.5) / 90)
    assert result["exact"]["upper"] == pytest.approx(100.0)
    assert result["unknown_points_human"] == pytest.approx(100 * 7.5 / 90, abs=1e-3)
    assert result["unknown_points_measurement"] == pytest.approx(100 * 20 / 90, abs=1e-3)
    assert result["measurement_gaps"] == ["coverage.written_share"]
    assert result["status"] == "REVIEW_REQUIRED"  # even with a human validation flag
    assert result["threshold_met"] is False
    _verify(result)


def test_entirely_not_applicable_dimension_is_renormalised():
    comps = _perfect()
    comps["ocr"] = {k: cs.NOT_APPLICABLE for k in cs.DIMENSIONS["ocr"]["components"]}
    comps["coverage"]["written_share"] = 0.5
    result = cs.score_document(comps, EVIDENCE)
    assert result["dimensions"]["ocr"]["applicable"] is False
    assert result["applicable_weight"] == 80
    assert result["exact"]["lower"] == pytest.approx(100 * (80 - 10) / 80)
    assert result["dimensions"]["coverage"]["effective_weight"] == pytest.approx(25.0)
    _verify(result)


def test_partially_unknown_dimension_and_partially_validated_interval():
    comps = _perfect()
    comps["ocr"]["character_accuracy"] = None
    result = cs.score_document(comps, EVIDENCE)
    dim = result["dimensions"]["ocr"]
    assert (dim["min"], dim["max"]) == (0.5, 1.0)
    # 40 % of the scanned text validated with an accuracy of 0.98
    comps["ocr"]["character_accuracy"] = {
        "lower": 0.4 * 0.98,
        "upper": 0.4 * 0.98 + 0.6,
        "validated_share": 0.4,
    }
    result = cs.score_document(comps, EVIDENCE)
    assert result["partial_components"][0]["component"] == "character_accuracy"
    assert result["dimensions"]["ocr"]["min"] == pytest.approx((1 + 0.392) / 2)
    assert result["dimensions"]["ocr"]["max"] == pytest.approx((1 + 0.992) / 2)
    assert result["unknown_points_human"] == pytest.approx(100 * 10 * 0.3 / 90, abs=1e-3)
    _verify(result)
    with pytest.raises(ValueError):
        comps["ocr"]["character_accuracy"] = {"lower": 0.9, "upper": 0.5}
        cs.score_document(comps, EVIDENCE)


def test_critical_defect_with_high_numeric_score_never_passes():
    defect = [{"code": "PROTECTED_ENTITY_CHANGED", "count": 1, "source": "product"}]
    result = cs.score_document(_perfect(), EVIDENCE, defect, human_validated=True)
    assert result["score_min"] == 100.0
    assert result["threshold_met"] is False and result["status"] == "REVIEW_REQUIRED"


def test_missing_evidence_blocks_without_adding_or_removing_points():
    evidence = dict(EVIDENCE, block_provenance=False)
    evidence.pop("execution_journal")  # not provided at all = not proven
    result = cs.score_document(_perfect(), evidence, human_validated=True)
    assert result["status"] == "BLOCKED" and result["threshold_met"] is False
    assert result["blocking"] == [
        "EVIDENCE_MISSING:block_provenance",
        "EVIDENCE_MISSING:execution_journal",
    ]
    assert result["score_min"] == 100.0  # evidence is a gate, not points
    _verify(result)
    with pytest.raises(KeyError):
        cs.score_document(_perfect(), dict(EVIDENCE, invented=True))


def test_absent_or_unreadable_document_is_counted_never_dropped():
    good = cs.score_document(_perfect(), EVIDENCE)
    corpus = cs.score_corpus({"A": good, "B": None}, expected=["A", "B"])
    assert corpus["missing_documents"] == ["B"]
    assert corpus["exact"]["lower"] == pytest.approx(50.0) and corpus["exact"][
        "upper"
    ] == pytest.approx(100.0)
    assert corpus["statuses"]["B"] == "BLOCKED" and corpus["threshold_met"] is False
    assert cs.score_corpus({"A": good}, expected=["A", "C"])["missing_documents"] == ["C"]
    with pytest.raises(KeyError):
        cs.score_corpus({"A": good, "Z": good}, expected=["A"])


def test_documents_of_different_sizes_have_equal_weight():
    # a 1-block document fully missed and a 1000-block document fully written:
    # the corpus is the mean of the documents (50), not the pooled ratio (99.9)
    small, large = _perfect(), _perfect()
    small["coverage"]["written_share"] = 0 / 1
    large["coverage"]["written_share"] = 1000 / 1000
    a = cs.score_document(small, EVIDENCE)
    b = cs.score_document(large, EVIDENCE)
    corpus = cs.score_corpus({"small": a, "large": b}, expected=["small", "large"])
    assert corpus["exact"]["lower"] == pytest.approx(
        (a["exact"]["lower"] + b["exact"]["lower"]) / 2
    )
    assert corpus["exact"]["lower"] == pytest.approx(100 * (1 - 20 / 90 / 2))


def test_bounds_identities_hold_on_random_documents():
    rng = random.Random(27)
    choices = [None, cs.NOT_APPLICABLE, 0.0, 1.0, 0.37, {"lower": 0.2, "upper": 0.7}]
    for _ in range(300):
        comps = {
            name: {key: rng.choice(choices) for key in spec["components"]}
            for name, spec in cs.DIMENSIONS.items()
        }
        comps["coverage"]["written_share"] = rng.random()  # at least one applicable dimension
        r = cs.score_document(comps, EVIDENCE)
        e = r["exact"]
        assert 0.0 <= e["lower"] <= e["ceiling"] + 1e-9 and e["lower"] <= e["upper"] <= 100.0 + 1e-9
        assert e["upper"] - e["lower"] == pytest.approx(100.0 - e["ceiling"])
        assert r["score_min"] <= e["lower"] + 1e-9 and r["score_max"] >= e["upper"] - 1e-9
        _verify(r)


def test_conservative_display_never_shows_a_threshold_that_is_not_met():
    comps = _perfect()
    comps["coverage"]["written_share"] = 1 - (6.04 / 100) * 90 / 20  # exact lower = 93.96
    r = cs.score_document(comps, EVIDENCE)
    assert r["exact"]["lower"] == pytest.approx(93.96)
    assert r["score_min"] == 93.9 and r["threshold_met"] is False  # round() would display 94.0
    assert cs.floor1(84.16666) == 84.1 and cs.ceil1(90.5662) == 90.6 and cs.floor1(100.0) == 100.0


def test_structural_ceiling_is_reached_and_derived_from_applicability():
    comps = _perfect()
    for dim, key in cs.HUMAN_COMPONENTS:
        comps[dim][key] = None
    r = cs.score_document(comps, EVIDENCE)
    assert r["exact"]["lower"] == pytest.approx(r["exact"]["ceiling"])  # ceiling reached
    lost = 15 / 2 + 15 / 3 + 10 / 2 + 10 / 3
    assert r["exact"]["ceiling"] == pytest.approx(100 * (90 - lost) / 90)
    assert cs.ceiling_without_human_references(_perfect()) == pytest.approx(r["exact"]["ceiling"])
    # French source: target language not applicable -> translation fully unknown -> lower ceiling
    french = _perfect()
    french["translation"]["target_language"] = cs.NOT_APPLICABLE
    lost_fr = 15 + 15 / 3 + 10 / 2 + 10 / 3
    assert cs.ceiling_without_human_references(french) == pytest.approx(100 * (90 - lost_fr) / 90)
    assert cs.ceiling_without_human_references(french) < r["exact"]["ceiling"]


def test_v1_ceiling_function_ignored_applicability_documented_regression():
    """RUN27 audit: v1's helper assumed every sub-component applicable (84.2 for all)."""
    comps = {
        name: {key: 1.0 for key in spec["components"]} for name, spec in cs1.DIMENSIONS.items()
    }
    comps["translation"] = {"target_language": cs1.NOT_APPLICABLE, "semantic_accuracy": None}
    comps["ocr"]["character_accuracy"] = None
    comps["hallucination"]["proven_by_reference"] = None
    real = cs1.score_document(comps)["score"]
    assert real == pytest.approx(76.7, abs=0.05)  # true v1 ceiling of such a document
    assert cs1.structural_ceiling(
        {
            "translation": ["semantic_accuracy"],
            "ocr": ["character_accuracy"],
            "hallucination": ["proven_by_reference"],
        }
    ) == pytest.approx(84.2, abs=0.05)  # what RUN26 announced for every document


def test_verifier_detects_a_tampered_score():
    r = cs.score_document(_perfect(), EVIDENCE)
    r["exact"]["lower"] = 99.0
    assert score_verify.verify_document_v2(r)["deviation_lower"] == pytest.approx(1.0)
    r = cs.score_document(_perfect(), dict(EVIDENCE, original_unchanged=False))
    r["status"] = "REVIEW_REQUIRED"
    with pytest.raises(ValueError):
        score_verify.verify_document_v2(r)


def test_v1_verifier_identities_on_a_v1_result():
    comps = {
        name: {key: 1.0 for key in spec["components"]} for name, spec in cs1.DIMENSIONS.items()
    }
    comps["translation"]["semantic_accuracy"] = None
    stored = cs1.score_document(comps)
    v = score_verify.verify_document(stored["dimensions"])
    assert float(v["lower"]) == pytest.approx(92.5) and float(v["upper"]) == pytest.approx(100.0)
    assert float(v["ceiling"]) == pytest.approx(92.5)


def test_layout_alert_families_are_deduplicated():
    import scorecard_v2

    issues = [
        {"code": "LAYOUT_OVERFLOW", "severity": "critical", "block_id": "b1"},
        {"code": "LAYOUT_OVERFLOW", "severity": "critical", "block_id": "b1"},  # written twice
        {"code": "LAYOUT_OVERFLOW", "severity": "critical", "block_id": "b2"},
        {"code": "RENDER_SOURCE_TEXT_MISSING", "severity": "critical", "count": 3},
        {"code": "RENDER_TRANSLATED_TEXT_MISSING", "severity": "critical", "count": 3},
        {"code": "RENDER_TEXT_CLIPPED_OR_MISSING", "severity": "critical", "count": 4},
        {"code": "RENDER_TEXT_CLIPPED_OR_MISSING", "severity": "critical", "count": 4},  # duplicate
        {"code": "RENDER_TEXT_MASK_TOO_LARGE", "severity": "critical", "page": 2},
        {"code": "VISUAL_MASK_TOO_LARGE", "severity": "critical", "page": 2},  # same page
        {"code": "LAYOUT_OVERFLOW", "severity": "warning", "block_id": "b9"},  # not critical
    ]
    occ = scorecard_v2.layout_occurrences(issues)
    assert occ["overflow"] == 2 and occ["missing_text"] == 4 and occ["oversized_mask"] == 1
    assert sum(occ.values()) == 7
