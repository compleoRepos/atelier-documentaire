from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "verify_acceptance.py"
SPEC = importlib.util.spec_from_file_location("acceptance_gate", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def proof(tmp_path):
    sha = "a" * 64
    references = tmp_path / "expected"
    folder = references / "tenant-fixture" / sha
    folder.mkdir(parents=True)
    reference = {
        "approved": True,
        "reviewer_id": "reviewer-fixture",
        "tenant_id": "tenant-fixture",
        "validated_at": "2026-10-07T12:00:00Z",
        "source_sha256": sha,
        "version": 1,
        "translations": {"block-1": "Texte synthétique validé"},
    }
    (folder / "v1.json").write_text(json.dumps(reference), encoding="utf-8")
    catalog = {"documents": [{"document_id": "SYNTHETIC", "sha256": sha}]}
    row = {
        "document_id": "SYNTHETIC",
        "source_sha256": sha,
        "technical": "PASS",
        "acceptance": "PASS",
        "metrics": {key: 1.0 for key in GATE.THRESHOLDS},
        "critical_entity_errors": 0,
        "hallucination_errors": 0,
        "context_overflow": 0,
        "untranslated_blocks": [],
    }
    report = {"technical_status": "PASS", "technical": [row]}
    return references, catalog, report, row


def test_empty_dataset_and_report_do_not_pass(tmp_path):
    failures, validated = GATE.collect_failures({}, {}, tmp_path, None, GATE.THRESHOLDS)
    assert failures and not validated


def test_synthetic_complete_evidence_is_accepted_by_evidence_checker(tmp_path):
    references, catalog, report, _ = proof(tmp_path)
    failures, validated = GATE.collect_failures(
        catalog, report, references, "tenant-fixture", GATE.THRESHOLDS
    )
    assert failures == [] and validated == ["SYNTHETIC"]


def test_missing_semantic_metric_never_becomes_zero_or_pass(tmp_path):
    references, catalog, report, row = proof(tmp_path)
    row["metrics"]["semantic_score"] = None
    failures, _ = GATE.collect_failures(
        catalog, report, references, "tenant-fixture", GATE.THRESHOLDS
    )
    assert any("semantic_score non mesuré" in message for message in failures)


def test_reference_cannot_cross_tenant(tmp_path):
    references, catalog, report, _ = proof(tmp_path)
    failures, validated = GATE.collect_failures(
        catalog, report, references, "other-tenant", GATE.THRESHOLDS
    )
    assert not validated and any("référence humaine" in message for message in failures)


def test_counter_proof_is_required_and_scores_use_declared_scale(tmp_path):
    references, catalog, report, row = proof(tmp_path)
    row["metrics"]["ocr_score"] = 99.0
    row.pop("hallucination_errors")
    row["context_overflow"] = 1
    failures, _ = GATE.collect_failures(
        catalog, report, references, "tenant-fixture", GATE.THRESHOLDS
    )
    assert any("ocr_score" in message for message in failures)
    assert any("hallucination_errors" in message for message in failures)
    assert any("context_overflow" in message for message in failures)
