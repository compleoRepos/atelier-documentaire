"""Tesseract timeout under CPU load: one bounded retry, traced; never a loop."""

from __future__ import annotations

import pytest
from PIL import Image

from app.ai.ocr import tesseract as module


def _data():
    keys = ("text", "conf", "block_num", "par_num", "line_num", "left", "top", "width", "height")
    row = {
        "text": "Attestation",
        "conf": "91",
        "block_num": 1,
        "par_num": 1,
        "line_num": 1,
        "left": 10,
        "top": 10,
        "width": 80,
        "height": 12,
    }
    return {k: [row[k]] for k in keys}


def _engine(monkeypatch, outcomes, calls):
    import pytesseract

    def fake(image, lang, config, output_type, timeout):
        calls.append(timeout)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(pytesseract, "image_to_data", fake)
    monkeypatch.setattr(module.TesseractOCR, "available_languages", staticmethod(lambda: {"eng"}))
    return module.TesseractOCR(["eng"], timeout=90)


def test_timeout_is_retried_once_with_doubled_bounded_delay(monkeypatch):
    calls: list[float] = []
    engine = _engine(monkeypatch, [RuntimeError("Tesseract process timeout"), _data()], calls)
    result = engine.image_to_blocks(Image.new("RGB", (200, 60), "white"))
    assert calls == [90.0, 180.0]
    text = str(result)
    assert "OCR_TIMEOUT_RETRIED" in text and "Attestation" in text


def test_second_timeout_fails_closed(monkeypatch):
    calls: list[float] = []
    timeout = RuntimeError("Tesseract process timeout")
    engine = _engine(monkeypatch, [timeout, RuntimeError("Tesseract process timeout")], calls)
    with pytest.raises(RuntimeError):
        engine.image_to_blocks(Image.new("RGB", (200, 60), "white"))
    assert calls == [90.0, 180.0]


def test_other_errors_are_not_retried(monkeypatch):
    calls: list[float] = []
    engine = _engine(monkeypatch, [RuntimeError("invalid image")], calls)
    with pytest.raises(RuntimeError):
        engine.image_to_blocks(Image.new("RGB", (200, 60), "white"))
    assert calls == [90.0]
