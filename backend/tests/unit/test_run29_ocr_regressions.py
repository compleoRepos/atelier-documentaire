"""RUN29 F51: a single short known word is no lexical evidence at a very low
OCR confidence (synthetic texts only, no corpus content)."""

from __future__ import annotations

import pytest

from app.documents import ocr_recovery as orr
from app.documents.language_evidence import available


def _block(text: str, confidence: float, language: str = "nld") -> dict:
    return {
        "text": text,
        "confidence": confidence,
        "language": language,
        "source_lines": [{"bbox": [0, 0, 10, 10], "confidence": confidence}],
    }


def test_f51_weak_lexical_evidence_is_one_word_of_at_most_five_letters():
    assert orr.weak_lexical_evidence("7 Hond : ")
    assert orr.weak_lexical_evidence("12 / 05")  # no word of 3+ letters
    assert not orr.weak_lexical_evidence("Voorwaarden")  # one long word
    assert not orr.weak_lexical_evidence("Hond kat")  # two words


def test_f51_single_short_word_at_very_low_confidence_needs_review():
    assert orr.needs_review(_block("7 Hond : ", 0.21), ["ita", "spa"])


@pytest.mark.skipif(not available(), reason="lexicon unavailable")
def test_f51_counter_proof_the_previous_rule_called_it_lexically_supported(monkeypatch):
    assert orr.lexically_supported("7 Hond : ", "nld", ["ita", "spa"])
    monkeypatch.setattr(orr, "WEAK_SUPPORT_BELOW", 0.0)
    assert not orr.needs_review(_block("7 Hond : ", 0.21), ["ita", "spa"])


@pytest.mark.skipif(not available(), reason="lexicon unavailable")
def test_f51_does_not_touch_a_long_title_or_a_moderate_confidence():
    # A real low-confidence title stays translatable (historical rule).
    assert not orr.needs_review(_block("Voorwaarden", 0.21), ["nld"])
    # Above the F51 bound the historical lexical rule alone decides.
    assert not orr.needs_review(_block("7 Hond : ", 0.40), ["nld"])
    # A reliable reading is never reviewed.
    assert not orr.needs_review(_block("7 Hond : ", 0.90), ["nld"])
