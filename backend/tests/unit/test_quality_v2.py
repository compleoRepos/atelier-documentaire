import hashlib
import json

from app.ai.quality.engine import evaluate_quality


def sha(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def approved_reference(**extra):
    return {
        "approved": True,
        "reviewer_id": "reviewer-1",
        "validated_at": "2026-10-07T12:00:00Z",
        "version": 2,
        "schema_version": "1.0",
        **extra,
    }


def complete_render():
    return {
        "source_page_count": 1,
        "translated_page_count": 1,
        "geometry_metrics": {"blocks": 1.0, "clipping": 1.0},
        "structure_metrics": {"tables": 1.0, "reading_order": 1.0},
        "protected_region_results": [{"id": "stamp", "preserved": True}],
    }


def test_missing_evidence_is_none_and_review_required():
    result = evaluate_quality(
        {"pages": [{"number": 1, "blocks": [{"id": "b1", "text": "Date 12/03/2024"}]}]},
        {"b1": "Date 12/03/2024"},
    )
    assert result["ocr_score"] is None
    assert result["semantic_score"] is None
    assert result["visual_score"] is None
    assert result["status"] == "REVIEW_REQUIRED"


def test_ocr_requires_human_scoped_reference_not_ir_flag():
    source = "Amount 1234"
    result = evaluate_quality(
        {"ocr_text": source, "ocr_validated": True, "source_text": source},
        {},
        reference=approved_reference(
            target_text="Montant 1234",
            ocr_text=source,
            ocr_validated=True,
            ocr_human_annotated=True,
            ocr_scope_sha256=sha(source),
        ),
    )
    assert result["ocr_score"] == 1.0
    assert result["semantic_score"] is None
    assert result["translation_score"] is None


def test_reference_agreement_is_lexical_only_and_nonidentical_semantics_unknown():
    ir = {
        "source_text": "Employment Certificate",
        "entities": [],
        "blocks": [{"id": "b1", "text": "Employment Certificate"}],
    }
    result = evaluate_quality(
        ir,
        {"b1": "Certificat de travail"},
        reference=approved_reference(target_text="Attestation de travail"),
    )
    assert result["translation_score"] is None
    assert 0.0 < result["quality"]["translation"]["reference_agreement"] < 1.0
    assert result["semantic_score"] is None
    assert result["provenance"]["semantic"] == "semantic_measurement_unavailable"


def test_signed_rubric_requires_all_dimensions_and_candidate_binding():
    source = "Gross Salary"
    ir = {
        "source_text": source,
        "review_version": 3,
        "entities": [],
        "blocks": [{"id": "b1", "text": source}],
    }
    translations = {"b1": "Salaire brut"}
    source_sha = sha(source)
    rubric = {
        "scores": {
            "fidelity": 0.9,
            "coherence": 0.8,
            "terminology": 1.0,
            "context": 0.8,
            "style": 0.7,
        },
        "signed": True,
        "translation_sha256": sha(translations),
        "source_sha256": source_sha,
        "review_version": 3,
    }
    result = evaluate_quality(
        ir,
        translations,
        reference=approved_reference(target_text="Salaire brut", rubric=rubric),
        render_result=complete_render(),
        options={"review_version": 3},
    )
    assert result["translation_score"] == 0.84
    assert result["coverage"]["translation_rubric"] is True

    partial = {
        **rubric,
        "scores": {"fidelity": 0.9, "coherence": 0.8, "terminology": 1.0, "style": 0.7},
    }
    untrusted = evaluate_quality(
        ir,
        translations,
        reference=approved_reference(target_text="Different", rubric=partial),
        options={"review_version": 3},
    )
    assert untrusted["translation_score"] is None
    assert untrusted["coverage"]["translation_rubric"] is False


def test_bool_rubric_score_is_not_numeric():
    source = "Gross Salary"
    translations = {"b1": "Salaire brut"}
    rubric = {
        "scores": {
            "fidelity": True,
            "coherence": 0.8,
            "terminology": 0.8,
            "context": 0.8,
            "style": 0.8,
        },
        "signed": True,
        "translation_sha256": sha(translations),
        "source_sha256": sha(source),
        "review_version": 1,
    }
    result = evaluate_quality(
        {"source_text": source, "review_version": 1, "blocks": [{"id": "b1", "text": source}]},
        translations,
        reference=approved_reference(target_text="Different", rubric=rubric),
        options={"review_version": 1},
    )
    assert result["translation_score"] is None


def test_changed_assertion_and_entity_fail_closed():
    result = evaluate_quality(
        {"source_text": "Date: 12/03/2024", "entities": [{"type": "date", "value": "12/03/2024"}]},
        {},
        reference=approved_reference(
            target_text="Date: 12/03/2024", assertions=[{"id": "date", "target": "12/03/2024"}]
        ),
    )
    assert result["status"] in {"FAIL", "REVIEW_REQUIRED"}
    assert result["untranslated_blocks"] == []
    assert result["coverage"]["hallucinations"]["assertions_semantic_coverage_explicit"] is False
