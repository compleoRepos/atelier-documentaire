from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.ocr import PaddleAssetsError, PaddleOCRLocal, detect_script, select_languages


def test_script_and_language_selection_are_local_and_explicit():
    assert detect_script("شهادة عمل") == "arabic"
    used, warnings, script = select_languages(None, {"ara", "eng"}, "شهادة عمل")
    assert used == ["ara"]
    assert script == "arabic"
    assert warnings == []


def test_missing_traineddata_is_warning_not_download():
    used, warnings, _ = select_languages(["fra", "deu"], {"fra"}, "")
    assert used == ["fra"]
    assert warnings and warnings[0]["code"] == "OCR_LANGUAGE_UNAVAILABLE"
    assert "download" in warnings[0]["message"] or "télécharg" in warnings[0]["message"]


def test_paddle_requires_existing_private_assets(tmp_path: Path):
    with pytest.raises(PaddleAssetsError):
        PaddleOCRLocal(assets={})
    with pytest.raises(PaddleAssetsError):
        PaddleOCRLocal(
            assets={"det_model_dir": str(tmp_path / "det"), "rec_model_dir": str(tmp_path / "rec")}
        )
