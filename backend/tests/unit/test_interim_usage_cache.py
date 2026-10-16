"""Usage accounting when the proxy reports cached input outside prompt_tokens.

Observed on a live response: prompt_tokens=168, cached_tokens=1152,
completion_tokens=1117, total_tokens=2437 (= 168 + 1152 + 1117). The
validator must accept only that exact accounting and keep every 32K bound
on the effective input (prompt + cached).
"""

from __future__ import annotations

from app.ai.translation.interim import InterimTranslationEngine

validate = InterimTranslationEngine._validate_usage
BOUNDS = {"prompt_upper_bound": 22_000, "max_tokens": 8_000, "reserved_total": 32_768}
DETAILS = {"reasoning_tokens": 0, "accepted_prediction_tokens": 0, "rejected_prediction_tokens": 0}


def _usage(prompt, completion, total, cached=None, **extra):
    usage = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "completion_tokens_details": DETAILS,
    }
    if cached is not None:
        usage["prompt_tokens_details"] = {
            "cached_tokens": cached,
            "cache_read_input_tokens": cached,
        }
    usage["prompt_tokens_details"] = {**usage.get("prompt_tokens_details", {}), **extra}
    return usage


def test_standard_openai_accounting_is_unchanged():
    usage, error = validate(_usage(1338, 1103, 2441), **BOUNDS)
    assert error is None
    assert usage["prompt_tokens"] == 1338
    assert usage["usage_semantics"] == "openai_prompt_includes_cache"
    assert "provider_reported_prompt_tokens" not in usage


def test_cache_reported_outside_prompt_is_accepted_with_effective_input():
    usage, error = validate(_usage(168, 1117, 2437, cached=1152), **BOUNDS)
    assert error is None
    assert usage["prompt_tokens"] == 1320
    assert usage["provider_reported_prompt_tokens"] == 168
    assert usage["usage_semantics"] == "cache_reported_outside_prompt"


def test_inexact_accounting_is_still_refused():
    _, error = validate(_usage(168, 1117, 2438, cached=1152), **BOUNDS)
    assert error == "usage.total_tokens is inconsistent with prompt and completion tokens"
    _, error = validate(_usage(168, 1117, 2437), **BOUNDS)
    assert error == "usage.total_tokens is inconsistent with prompt and completion tokens"


def test_disagreeing_cache_counters_are_refused():
    usage = _usage(168, 1117, 2437, cached=1152)
    usage["prompt_tokens_details"]["cache_read_input_tokens"] = 1000
    _, error = validate(usage, **BOUNDS)
    assert error == "usage cached token counters disagree"


def test_effective_input_over_preflight_bound_is_refused():
    _, error = validate(_usage(1000, 500, 22_501, cached=21_001), **BOUNDS)
    assert error == "usage.prompt_tokens exceeds the conservative preflight bound"


def test_total_over_32k_is_refused_even_with_exact_cache_accounting():
    bounds = {**BOUNDS, "prompt_upper_bound": 40_000}
    _, error = validate(_usage(1000, 8000, 33_000, cached=24_000), **bounds)
    assert error == "usage.total_tokens exceeds 32768"
