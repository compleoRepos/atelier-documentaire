"""RUN26 regressions - synthetic data only (no corpus content).

F25: recovery of low-confidence OCR lines on a preprocessed working copy, and
review gate for blocks that stay unreliable.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.documents import ocr_recovery as rec
from app.documents.language_evidence import available as lexicon_available

LINE_BOX = [100.0, 100.0, 220.0, 110.0]  # 120 x 10 pt -> ~20 characters expected


def _block(text: str, conf: float, *, language: str = "nld", box=LINE_BOX) -> dict:
    return {
        "id": "p001-b0001",
        "provenance": "ocr:tesseract",
        "language": language,
        "text": text,
        "confidence": conf,
        "bbox": list(box),
        "source_lines": [{"text": text, "confidence": conf, "bbox": list(box)}],
    }


def _page_rgb() -> np.ndarray:
    rgb = np.full((900, 700, 3), 255, dtype=np.uint8)
    rgb[205:215, 205:420] = 0  # some ink inside the line box (scale 2)
    return rgb


class _Reader:
    def __init__(self, text: str, conf: float):
        self.result = (text, conf)
        self.calls = 0

    def __call__(self, image, lang):
        self.calls += 1
        assert lang == "nld"
        return self.result


# --- pure acceptance rules -------------------------------------------------


def test_accepts_clearly_better_reading_of_noise():
    assert rec.accept_reading("q zrvo", 0.14, "Naam van de aanvrager", 0.93, LINE_BOX) == ""


def test_refuses_reading_not_clearly_more_reliable():
    assert (
        rec.accept_reading("q zrvo", 0.50, "Naam van de aanvrager", 0.60, LINE_BOX)
        == "not_more_reliable"
    )
    assert (
        rec.accept_reading("q zrvo", 0.70, "Naam van de aanvrager", 0.82, LINE_BOX)
        == "not_more_reliable"
    )


def test_refuses_confident_truncated_reading():
    # Box implies ~20 characters: a 4-letter reading is a truncation.
    assert rec.accept_reading("xq", 0.20, "Naam", 0.95, LINE_BOX) == "shorter_than_line"
    small = [100.0, 100.0, 130.0, 110.0]
    assert (
        rec.accept_reading("Bijvoorbeeld", 0.54, "Bijv", 0.91, small)
        == "shorter_than_first_reading"
    )


def test_numbers_must_agree_when_first_reading_is_plausible():
    assert (
        rec.accept_reading("EUR 1.234,56 bruto", 0.53, "EUR 1 234.56 bruto", 0.92, LINE_BOX)
        == "numbers_disagree"
    )
    # A first reading that is noise carries no numeric information.
    assert rec.accept_reading("zq 2 xx", 0.14, "geboren 01-01-2000", 0.95, LINE_BOX) == ""


def test_same_reading_and_glyph_only_readings_are_not_replacements():
    assert rec.accept_reading("CLÁUSULAS EXTRA", 0.23, "CLAUSULAS extra", 0.92, LINE_BOX) == (
        "same_reading"
    )
    assert rec.accept_reading("i", 0.30, "|", 0.95, LINE_BOX) == "no_alphanumeric"
    assert rec.accept_reading("x", 0.30, "   ", 0.95, LINE_BOX) == "empty_reading"


def test_right_to_left_lines_are_never_rewritten():
    assert rec.accept_reading(
        "ao", 0.20, "\u0645\u062b\u0627\u0644 \u0646\u0635", 0.95, LINE_BOX
    ) == ("right_to_left_script")


def test_unknown_words_need_a_very_confident_reading():
    assert (
        rec.accept_reading("qq", 0.20, "zzkra vlomp drastig", 0.85, LINE_BOX, known_share=0.0)
        == "not_lexically_supported"
    )
    assert (
        rec.accept_reading("qq", 0.20, "zzkra vlomp drastig", 0.95, LINE_BOX, known_share=0.0) == ""
    )


# --- block recovery with an injected reader ---------------------------------


def test_recover_block_replaces_line_and_records_provenance():
    block = _block("aan vqrtnelm x", 0.29)
    reader = _Reader("Naam van de aanvrager", 0.93)
    stats: dict = {}
    replaced = rec.recover_block(
        block, [block], _page_rgb(), 2.0, ["nld"], stats, reader=reader, available={"nld"}
    )
    assert replaced == 1
    line = block["source_lines"][0]
    assert line["text"] == "Naam van de aanvrager"
    assert line["ocr_text_initial"] == "aan vqrtnelm x"
    assert line["provenance"] == "ocr:tesseract:recovered"
    assert line["ocr_recovery"]["accepted"] is True
    assert block["text"] == "Naam van de aanvrager"
    assert block["ocr_text_initial"] == "aan vqrtnelm x"
    assert block["confidence"] == pytest.approx(0.93)
    assert stats["ocr_recovery_lines_recovered"] == 1
    # Two preprocessed variants (binarised + grey) are read.
    assert reader.calls == 2


def test_recover_block_is_idempotent_on_reused_analysis():
    block = _block("aan vqrtnelm x", 0.29)
    reader = _Reader("Naam van de aanvrager", 0.93)
    rec.recover_block(
        block, [block], _page_rgb(), 2.0, ["nld"], {}, reader=reader, available={"nld"}
    )
    calls = reader.calls
    rec.recover_block(
        block, [block], _page_rgb(), 2.0, ["nld"], {}, reader=reader, available={"nld"}
    )
    assert reader.calls == calls


def test_recover_block_refuses_ambiguous_zone_without_reading():
    block = _block("aan vqrtnelm x", 0.29)
    other = {"id": "p001-b0002", "bbox": [90.0, 95.0, 230.0, 112.0], "text": "overlap"}
    reader = _Reader("Naam van de aanvrager", 0.93)
    stats: dict = {}
    assert (
        rec.recover_block(
            block,
            [block, other],
            _page_rgb(),
            2.0,
            ["nld"],
            stats,
            reader=reader,
            available={"nld"},
        )
        == 0
    )
    assert reader.calls == 0
    assert block["source_lines"][0]["ocr_recovery"]["reason"] == "ambiguous_zone"
    assert block["text"] == "aan vqrtnelm x"
    assert stats["ocr_recovery_refused_ambiguous_zone"] == 1


def test_confirmation_keeps_text_and_raises_confidence():
    block = _block("CLÁUSULAS ADICIONALES", 0.23, language="spa")
    reader = _Reader("CLAUSULAS ADICIONALES", 0.92)
    reader.result = ("CLAUSULAS ADICIONALES", 0.92)
    stats: dict = {}

    def spa_reader(image, lang):
        assert lang == "spa"
        return reader.result

    assert (
        rec.recover_block(
            block, [block], _page_rgb(), 2.0, ["spa"], stats, reader=spa_reader, available={"spa"}
        )
        == 0
    )
    line = block["source_lines"][0]
    assert line["text"] == "CLÁUSULAS ADICIONALES"
    assert line["confidence"] == pytest.approx(0.92)
    assert line["ocr_recovery"]["reason"] == "confirmed"
    assert block["confidence"] == pytest.approx(0.92)
    assert block["ocr_confirmed_lines"] == 1
    assert stats["ocr_recovery_lines_confirmed"] == 1


def test_lines_rewritten_by_checkbox_rules_and_reliable_blocks_are_skipped():
    block = _block("aan vqrtnelm x", 0.29)
    block["source_lines"][0]["ocr_text_raw"] = "[] aan vqrtnelm x"
    reader = _Reader("Naam van de aanvrager", 0.93)
    assert (
        rec.recover_block(
            block, [block], _page_rgb(), 2.0, ["nld"], {}, reader=reader, available={"nld"}
        )
        == 0
    )
    reliable = _block("Naam van de aanvrager", 0.91)
    assert (
        rec.recover_block(
            reliable, [reliable], _page_rgb(), 2.0, ["nld"], {}, reader=reader, available={"nld"}
        )
        == 0
    )
    assert reader.calls == 0


def test_no_language_model_means_no_recovery():
    block = _block("aan vqrtnelm x", 0.29, language="fin")
    stats: dict = {}
    reader = _Reader("Naam van de aanvrager", 0.93)
    assert (
        rec.recover_block(
            block, [block], _page_rgb(), 2.0, ["fin"], stats, reader=reader, available={"nld"}
        )
        == 0
    )
    assert stats["ocr_recovery_no_language_model"] == 1
    assert reader.calls == 0


def test_preprocess_returns_binarised_and_grey_variants():
    images = rec.preprocess_line(_page_rgb(), LINE_BOX, 2.0)
    assert len(images) == 2
    for image in images:
        assert image.height == rec.TARGET_HEIGHT_PX + 2 * rec.BORDER_PX
    assert set(np.unique(np.asarray(images[0]))) <= {0, 255}


# --- review gate --------------------------------------------------------------


@pytest.mark.skipif(not lexicon_available(), reason="wordfreq lexicon not installed")
def test_review_gate_marks_unrecovered_noise_but_not_low_confidence_words():
    noise = _block("ores rain deed xq", 0.33)
    assert rec.needs_review(noise, ["nld"]) is True
    words = _block("Naam van de aanvrager", 0.52)
    assert rec.needs_review(words, ["nld"]) is False
    numbers = _block("1.234,56", 0.53)
    assert rec.needs_review(numbers, ["nld"]) is True
    reliable = _block("ores rain deed xq", 0.75)
    assert rec.needs_review(reliable, ["nld"]) is False


def test_amount_with_other_separators_is_never_a_confirmation():
    # Same digits, different separators: a numeric conflict, not a confirmation.
    assert rec.accept_reading("1.234,56", 0.30, "1 234.56", 0.95, [100.0, 100.0, 130.0, 110.0]) == (
        "numbers_disagree"
    )
    block = _block("1.234,56", 0.30, box=[100.0, 100.0, 130.0, 110.0])
    reader = _Reader("1 234.56", 0.95)
    rec.recover_block(
        block, [block], _page_rgb(), 2.0, ["nld"], {}, reader=reader, available={"nld"}
    )
    line = block["source_lines"][0]
    assert line["text"] == "1.234,56"
    assert line["confidence"] == pytest.approx(0.30)
    assert line["ocr_recovery"]["reason"] == "numbers_disagree"


# --- F26: post-render verification of inserted translations -----------------

import fitz  # noqa: E402

from app.documents import render_verification as rv  # noqa: E402
from app.documents.block_status import classify_blocks  # noqa: E402

FRAME = [72.0, 72.0, 300.0, 100.0]


def _candidate(tmp_path, text: str | None, rect=FRAME):
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    if text is not None:
        assert page.insert_textbox(fitz.Rect(*rect), text, fontsize=10) >= 0
    out = tmp_path / "candidate.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _placement(text: str, block_id: str = "p001-b0001") -> dict:
    return {"page": 1, "inner": list(FRAME), "block_ids": [block_id], "text": text}


def test_token_recall_is_case_and_accent_insensitive():
    assert (
        rv.token_recall(
            "Rapport de contrôle du rendu synthétique", "RAPPORT DE CONTROLE DU RENDU SYNTHETIQUE"
        )
        == 1.0
    )
    assert rv.token_recall("Rapport de contrôle", "Rapport") == pytest.approx(1 / 3)
    assert rv.token_recall("—", "anything") is None


def test_complete_target_in_engine_frame_is_verified(tmp_path):
    out = _candidate(tmp_path, "Rapport de contrôle du rendu synthétique")
    issues, summary = rv.verify_placements(
        out, [_placement("Rapport de contrôle du rendu synthétique")]
    )
    assert issues == []
    assert summary["verified"] == 1 and summary["not_verified"] == 0


def test_truncated_target_is_not_verified(tmp_path):
    out = _candidate(tmp_path, "Rapport de contrôle")
    issues, summary = rv.verify_placements(
        out, [_placement("Rapport de contrôle du rendu synthétique")]
    )
    assert summary["not_verified"] == 1
    assert [i["code"] for i in issues] == ["RENDER_TARGET_NOT_VERIFIED"]
    assert issues[0]["severity"] == "critical"
    assert issues[0]["block_id"] == "p001-b0001"
    assert issues[0]["recall"] < rv.MIN_RECALL


def test_target_written_outside_its_frame_is_not_verified(tmp_path):
    out = _candidate(tmp_path, "Rapport de contrôle", rect=[72.0, 200.0, 300.0, 230.0])
    issues, summary = rv.verify_placements(out, [_placement("Rapport de contrôle")])
    assert summary["not_verified"] == 1 and len(issues) == 1


def test_target_without_alphanumeric_is_not_measurable_not_verified(tmp_path):
    out = _candidate(tmp_path, None)
    issues, summary = rv.verify_placements(out, [_placement("— / —")])
    assert issues == []
    assert summary["not_measurable"] == 1 and summary["verified"] == 0


def test_unverified_render_makes_block_failed_not_translated():
    ir = {
        "languages": ["eng"],
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {
                        "id": "p001-b0001",
                        "text": "Fixed-term employment contract",
                        "language": "eng",
                        "bbox": list(FRAME),
                        "confidence": 0.95,
                    }
                ],
            }
        ],
    }
    translations = {"p001-b0001": "Rapport de contrôle du rendu synthétique"}
    ok = classify_blocks(ir, translations, [])
    assert ok["blocks"]["p001-b0001"]["status"] == "TRANSLATED"
    issue = {"code": "RENDER_TARGET_NOT_VERIFIED", "severity": "critical", "block_id": "p001-b0001"}
    bad = classify_blocks(ir, translations, [issue])
    assert bad["blocks"]["p001-b0001"]["status"] == "FAILED"
    assert bad["blocks"]["p001-b0001"]["reason"] == "render_target_incomplete"


# --- F27: render_metrics reconciled with the post-render proof (F26) ---------

from app.documents import render_metrics as rm  # noqa: E402


def _geometry_inputs(*, protected: bool = False):
    source = {
        "pages": [{"number": 1, "width": 400.0, "height": 300.0, "scanned": True, "blocks": []}]
    }
    # The engine wrapped the target over two lines; the PDF text extractor
    # returns them as two separate text blocks.
    candidate = {
        "pages": [
            {
                "number": 1,
                "width": 400.0,
                "height": 300.0,
                "blocks": [
                    {
                        "id": "c1",
                        "page": 1,
                        "text": "Rapport de contrôle",
                        "bbox": [72, 72, 300, 84],
                    },
                    {
                        "id": "c2",
                        "page": 1,
                        "text": "à durée déterminée",
                        "bbox": [72, 86, 300, 98],
                    },
                ],
            }
        ]
    }
    block = {
        "id": "p001-b0001",
        "page": 1,
        "text": "Fixed-term employment contract",
        "bbox": list(FRAME),
    }
    if protected:
        block["protected"] = True
    ir = {"pages": [{"number": 1, "blocks": [block]}]}
    translations = {"p001-b0001": "Rapport de contrôle du rendu synthétique"}
    return source, candidate, ir, translations


def _codes(issues):
    return {i["code"] for i in issues}


def test_split_target_verified_in_engine_frame_is_not_missing():
    source, candidate, ir, translations = _geometry_inputs()
    _geometry, before = rm._geometry(source, candidate, ir, translations)
    assert "RENDER_TRANSLATED_TEXT_MISSING" in _codes(before)  # contiguous match fails
    geometry, after = rm._geometry(
        source, candidate, ir, translations, verified_block_ids={"p001-b0001"}
    )
    assert not _codes(after) & {
        "RENDER_TRANSLATED_TEXT_MISSING",
        "RENDER_SOURCE_TEXT_MISSING",
        "RENDER_TEXT_CLIPPED_OR_MISSING",
    }
    assert "matched_by_placement_verification" in str(geometry)


def test_unverified_split_target_stays_missing():
    source, candidate, ir, translations = _geometry_inputs()
    _geometry, issues = rm._geometry(
        source, candidate, ir, translations, verified_block_ids={"another-block"}
    )
    assert "RENDER_TRANSLATED_TEXT_MISSING" in _codes(issues)


def test_protected_block_translation_is_not_counted_as_missing_text():
    source, candidate, ir, translations = _geometry_inputs(protected=True)
    candidate["pages"][0]["blocks"] = []  # nothing written: the zone is protected
    _geometry, issues = rm._geometry(source, candidate, ir, translations)
    assert "RENDER_TRANSLATED_TEXT_MISSING" not in _codes(issues)


def test_verification_exposes_only_verified_block_ids(tmp_path):
    out = _candidate(tmp_path, "Rapport de contrôle")
    _issues, summary = rv.verify_placements(
        out,
        [
            _placement("Rapport de contrôle", "p001-b0001"),
            _placement("Rapport de contrôle du rendu synthétique et suite", "p001-b0002"),
        ],
    )
    assert summary["verified_block_ids"] == ["p001-b0001"]


# --- F28: a rewritten identifier is not "preserved" --------------------------


def _identifier_ir() -> dict:
    return {
        "languages": ["eng"],
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {
                        "id": "p001-b0001",
                        "text": "3.SALARY",
                        "language": "eng",
                        "bbox": list(FRAME),
                        "confidence": 0.95,
                        "identifier_only": True,
                    }
                ],
            }
        ],
    }


def test_rewritten_identifier_block_is_reported_as_translated():
    ir = _identifier_ir()
    kept = classify_blocks(ir, {"p001-b0001": "3.SALARY"}, [])
    assert kept["blocks"]["p001-b0001"]["status"] == "PRESERVED_INTENTIONALLY"
    assert kept["blocks"]["p001-b0001"]["reason"] == "identifier_or_number"
    rewritten = classify_blocks(ir, {"p001-b0001": "3. SALAIRE"}, [])
    assert rewritten["blocks"]["p001-b0001"]["status"] == "TRANSLATED"
