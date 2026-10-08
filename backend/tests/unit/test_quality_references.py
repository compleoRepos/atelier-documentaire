import hashlib

from app.ai.quality.metrics import reference_metrics


def approved_reference(**extra):
    return {
        "approved": True,
        "reviewer_id": "synthetic-reviewer",
        "validated_at": "2026-10-07T12:00:00Z",
        "version": 1,
        "schema_version": "1.0",
        **extra,
    }


def test_translation_reference_is_not_an_ocr_ground_truth():
    metrics = reference_metrics(
        "Employment Certificate",
        "Attestation de travail",
        approved_reference(target_text="Attestation de travail", ocr_validated=False),
    )
    assert metrics["translation_cer"] == 0.0
    assert metrics["translation_wer"] == 0.0
    assert metrics["cer"] is None and metrics["wer"] is None


def test_ocr_error_rate_requires_an_explicitly_validated_source_transcript():
    metrics = reference_metrics(
        "Amount 1235",
        "Montant 1235",
        approved_reference(
            ocr_validated=True,
            ocr_text="Amount 1234",
            ocr_annotated_by="synthetic-reviewer",
            ocr_scope_sha256=hashlib.sha256(b"Amount 1235").hexdigest(),
        ),
    )
    assert metrics["cer"] > 0 and metrics["wer"] > 0
    assert metrics["translation_cer"] is None


def test_unscoped_ocr_attestation_is_not_measured():
    metrics = reference_metrics(
        "Amount 1235",
        "Montant 1235",
        approved_reference(ocr_validated=True, ocr_text="Amount 1234"),
    )
    assert metrics["cer"] is None and metrics["wer"] is None
