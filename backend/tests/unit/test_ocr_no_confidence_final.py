"""D25 — an OCR fragment with a measured confidence of ~0 is never sent.

Final audit: a 0.00-confidence fragment read inside an overprinted footer
looked like a word, so the historical noise rule (no 4+ letter word) let it
through; the model changed its punctuation and the renderer wrote it over the
original. Synthetic data only.
"""

from __future__ import annotations

import numpy as np

from app.documents.line_verification import verify_lines
from app.documents.segmentation import OCR_NO_CONFIDENCE, is_unreliable_ocr


def test_measured_zero_confidence_word_is_unreliable() -> None:
    assert is_unreliable_ocr("Pesos:", 0.0)
    assert is_unreliable_ocr("Pesos:", OCR_NO_CONFIDENCE - 0.01)


def test_historical_rule_unchanged_above_threshold() -> None:
    # Real low-confidence titles stay translatable; pure noise does not.
    assert not is_unreliable_ocr("CLÁUSULAS", 0.30)
    assert not is_unreliable_ocr("Pesos:", OCR_NO_CONFIDENCE)
    assert is_unreliable_ocr("ak wg", 0.30)
    # No measurement: only the historical rule applies.
    assert not is_unreliable_ocr("Pesos:", None)  # type: ignore[arg-type]


def _ir(blocks: list[dict]) -> dict:
    return {
        "pages": [{"number": 1, "scanned": True, "width": 100, "height": 100, "blocks": blocks}]
    }


def _ocr_block(block_id: str, text: str, confidence: float | None, **extra) -> dict:
    box = [10.0, 10.0, 60.0, 20.0]
    return {
        "id": block_id,
        "text": text,
        "bbox": box,
        "confidence": confidence,
        "source_lines": [{"id": block_id, "text": text, "bbox": box, "confidence": confidence}],
        **extra,
    }


def test_reused_analysis_gets_the_current_rule() -> None:
    zero = _ocr_block("b0", "Pesos:", 0.0)
    clean = _ocr_block("b1", "Contrat de travail", 0.93)
    native = {"id": "b2", "text": "Texte natif", "bbox": [10.0, 30.0, 60.0, 40.0]}
    ir = _ir([zero, clean, native])
    white = np.full((400, 400, 3), 255, dtype=np.uint8)
    stats = verify_lines(ir, "unused.pdf", rasters={1: white}, reader=lambda _image: None)
    assert zero["ocr_unreliable"] is True
    assert not clean.get("ocr_unreliable")
    assert "ocr_unreliable" not in native  # no OCR lines, no measured confidence
    assert stats["blocks_ocr_unreliable_rechecked"] == 1


def test_flag_is_never_cleared() -> None:
    noisy = _ocr_block("b0", "Contrat de travail", 0.93, ocr_unreliable=True)
    ir = _ir([noisy])
    white = np.full((400, 400, 3), 255, dtype=np.uint8)
    stats = verify_lines(ir, "unused.pdf", rasters={1: white}, reader=lambda _image: None)
    assert noisy["ocr_unreliable"] is True
    assert stats["blocks_ocr_unreliable_rechecked"] == 0
