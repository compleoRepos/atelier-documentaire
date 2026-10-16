from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routes import _content_disposition, _validate_regions
from app.core.settings import Settings


def test_private_settings_forward_all_budgets_and_secret():
    settings = Settings(
        jwt_secret="x" * 32,
        engine="private",
        private_ai_base_url="http://private.local",
        private_ai_allowed_hosts="private.local",
        private_ai_model="model-a",
        private_ai_api_key="secret",
        tokenizer_path="/models/tokenizer",
        max_context=30000,
        target_input=18000,
        max_output=9000,
        safety_margin=2000,
    )
    assert settings.translation_budgets == {
        "max_context": 30000,
        "target_input": 18000,
        "max_output": 9000,
        "safety_margin": 2000,
    }
    assert settings.private_hosts == ["private.local"]
    assert "secret" not in repr(settings.translation_budgets)


def test_filename_header_strips_crlf_and_supports_rfc5987():
    value = _content_disposition("rapport é\r\n.pdf")
    assert "\r" not in value and "\n" not in value
    assert "filename*=UTF-8''" in value


def test_protected_regions_require_finite_in_bounds_geometry():
    ir = {"pages": [{"number": 1, "width": 100, "height": 100}]}
    _validate_regions([{"page": 1, "bbox": [1, 1, 10, 10]}], ir)
    with pytest.raises(HTTPException):
        _validate_regions([{"page": 1, "bbox": [1, 1, float("nan"), 10]}], ir)
    with pytest.raises(HTTPException):
        _validate_regions([{"page": 1, "bbox": [1, 1, 101, 10]}], ir)
