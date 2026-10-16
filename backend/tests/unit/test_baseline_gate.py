from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "baseline_gate", Path(__file__).resolve().parents[3] / "tools/compare_baseline.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def synthetic_report():
    return {
        "technical": [
            {
                "document_id": "SYNTHETIC",
                "source_sha256": "a" * 64,
                "metrics": {metric: 0.99 for metric in MODULE.METRICS},
            }
        ]
    }


def test_unchanged_synthetic_measures_are_not_a_regression():
    report = synthetic_report()
    assert MODULE.compare(report, report)["status"] == "PASS"


def test_decline_is_detected_even_when_above_absolute_threshold():
    baseline = synthetic_report()
    current = copy.deepcopy(baseline)
    current["technical"][0]["metrics"]["ocr_score"] = 0.98
    assert MODULE.compare(current, baseline)["status"] == "REGRESSION_DETECTED"


def test_missing_metrics_never_count_as_a_pass():
    baseline = synthetic_report()
    current = copy.deepcopy(baseline)
    current["technical"][0]["metrics"]["semantic_score"] = None
    assert MODULE.compare(current, baseline)["status"] == "NOT_EVALUATED"


def test_changed_input_requires_a_new_approved_baseline():
    baseline = synthetic_report()
    current = copy.deepcopy(baseline)
    current["technical"][0]["source_sha256"] = "b" * 64
    assert MODULE.compare(current, baseline)["status"] == "NOT_EVALUATED"
