"""Run18 regression tests (synthetic data only).

Each test pins one confirmed root cause of the run17 regressions; the numbers
in the docstrings come from the private per-block diagnosis (no real text).
"""

from __future__ import annotations

import httpx
import numpy as np
import pytest
from test_interim_owner_authorization import options
from test_interim_unchanged_retry import _handler, _ir
from test_ocr_line_gap_split import _item

from app.ai.ocr.tesseract import split_line_at_gaps, vertical_rule_between
from app.ai.translation.service import translate_blocks
from app.documents.line_verification import verify_lines


def _page_with_rule(x: int | None) -> np.ndarray:
    gray = np.full((120, 400), 255, dtype=np.uint8)
    if x is not None:
        gray[:, x : x + 2] = 0  # cell rule crossing the whole line band
    return gray


def test_line_is_split_at_a_vertical_cell_rule_and_rule_glyph_dropped():
    """Run18 C3: "label | value" of two form cells read as one OCR line was
    kept in the source language as a whole by the form-structure guard."""
    item = _item(
        [
            ("Nombre", 100, 140, 50, 60, 0.9),
            ("|", 144, 147, 49, 61, 0.4),  # the rule read as a glyph
            ("Juan", 150, 175, 50, 60, 0.9),
            ("Perez", 178, 205, 50, 60, 0.9),
        ]
    )
    segments = split_line_at_gaps(item, gray=_page_with_rule(145))
    assert [s["text"] for s in segments] == ["Nombre", "Juan Perez"]
    assert all(s.get("split_at_rule") for s in segments)


def test_line_without_rule_is_not_split_and_letters_never_count_as_rule():
    item = _item(
        [
            ("Nombre", 100, 140, 50, 60, 0.9),
            ("del", 144, 160, 50, 60, 0.9),
            ("titular", 163, 200, 50, 60, 0.9),
        ]
    )
    gray = _page_with_rule(None)
    gray[50:60, 120:122] = 0  # a stem inside a word, not between words
    assert [s["text"] for s in split_line_at_gaps(item, gray=gray)] == ["Nombre del titular"]
    assert not vertical_rule_between(gray, 140, 144, 50, 60)


def _ruled_raster(rule_rows: list[int]) -> np.ndarray:
    rgb = np.full((800, 1800, 3), 255, dtype=np.uint8)
    for y in rule_rows:
        rgb[y : y + 3, 150:1700] = 0
    return rgb


def test_block_spanning_ruled_table_rows_is_split_and_table_refs_follow():
    """Run18 C3: 8 lines of 8 table rows merged into one paragraph were kept in
    the source language as a whole (1 197 characters never sent)."""
    lines = [
        {
            "id": f"l{i}",
            "text": f"Row {i} label text",
            "bbox": [50, 50 + 20 * i, 400, 60 + 20 * i],
            "confidence": 0.9,
        }
        for i in range(3)
    ]
    block = {
        "id": "p001-b0007",
        "text": "Row 0 label text Row 1 label text Row 2 label text",
        "bbox": [50, 50, 400, 100],
        "role": "paragraph",
        "line_count": 3,
        "line_heights": [10, 10, 10],
        "style": {"align": "right"},
        "source_lines": lines,
    }
    ir = {
        "pages": [
            {
                "number": 1,
                "scanned": True,
                "blocks": [block],
                "layout": {"tables": [{"cells": [{"block_ids": ["p001-b0007"]}]}]},
            }
        ],
        "tables": [{"cells": [{"block_ids": ["p001-b0007", "p001-b0009"]}]}],
        "warnings": [{"code": "X", "block_id": "p001-b0007"}],
    }
    # rules in the gaps between rows (page scale 4.0: gap 60-70 pt -> 240-280 px)
    stats = verify_lines(
        ir, "unused.pdf", reader=lambda _i: None, rasters={1: _ruled_raster([258, 338])}
    )
    parts = ir["pages"][0]["blocks"]
    assert [p["id"] for p in parts] == ["p001-b0007-r1", "p001-b0007-r2", "p001-b0007-r3"]
    assert [p["text"] for p in parts] == [
        "Row 0 label text",
        "Row 1 label text",
        "Row 2 label text",
    ]
    assert [p["role"] for p in parts] == ["line", "line", "line"]
    assert parts[1]["bbox"] == [50.0, 70.0, 400.0, 80.0] and parts[1]["line_heights"] == [10]
    assert parts[2]["split_from"] == {
        "id": "p001-b0007",
        "reason": "horizontal_rule_between_lines",
        "part": 3,
        "parts": 3,
    }
    assert [p["reading_order"] for p in parts] == [0, 1, 2]
    assert ir["tables"][0]["cells"][0]["block_ids"] == [
        "p001-b0007-r1",
        "p001-b0007-r2",
        "p001-b0007-r3",
        "p001-b0009",
    ]
    assert ir["pages"][0]["layout"]["tables"][0]["cells"][0]["block_ids"][0] == "p001-b0007-r1"
    assert ir["warnings"][0]["block_id"] == "p001-b0007-r1"
    assert stats["blocks_split_at_rules"] == 1 and stats["blocks_form_structure_risk"] == 0


def test_block_without_rule_between_lines_is_not_split():
    lines = [
        {"id": f"l{i}", "text": f"Sentence part {i}", "bbox": [50, 50 + 12 * i, 400, 60 + 12 * i]}
        for i in range(2)
    ]
    block = {"id": "p001-b0001", "text": "x", "style": {}, "source_lines": lines}
    ir = {"pages": [{"number": 1, "scanned": True, "blocks": [block]}]}
    stats = verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters={1: _ruled_raster([])})
    assert ir["pages"][0]["blocks"] == [block] and stats["blocks_split_at_rules"] == 0


# --- C4: short non-Latin labels returned verbatim are retried once ---------


@pytest.mark.asyncio
async def test_one_word_arabic_label_returned_verbatim_is_retried(tmp_path):
    """Run18 C4 (DOC-004): 18 one/two-word Arabic cell labels were returned
    unchanged by the model and never retried (the rule needed 2 words >= 4
    letters), so they stayed in Arabic in the French output."""
    seen: list[dict] = []
    blocks = [
        {"id": "a1", "text": "نعم", "language": "ara"},  # synthetic: "yes"
        {"id": "a2", "text": "الاسم", "language": "unknown"},  # "the name"
        {"id": "n1", "text": "PL 46", "language": "eng"},  # Latin code: not retried
    ]
    result = await translate_blocks(
        _ir(blocks), options(tmp_path, httpx.MockTransport(_handler(seen, translate_on_retry=True)))
    )
    assert [s["retry"] for s in seen] == [False, True]
    assert seen[1]["ids"] == ["a1", "a2"]
    assert result["translations"]["a1"] == "Traduction a-un."
    assert result["translations"]["n1"] == "PL 46"


# --- C6: symbols are never sent; lexical evidence relabels short blocks ----


@pytest.mark.asyncio
async def test_blocks_without_any_word_are_not_sent_and_are_traced(tmp_path):
    seen: list[dict] = []
    blocks = [
        {"id": "s1", "text": "|", "language": "unknown", "no_linguistic_content": True},
        {"id": "s2", "text": "5 €", "language": "unknown", "no_linguistic_content": True},
        {"id": "w1", "text": "Employment certificate", "language": "eng"},
    ]
    result = await translate_blocks(
        _ir(blocks), options(tmp_path, httpx.MockTransport(_handler(seen, translate_on_retry=True)))
    )
    assert all(ids == ["w1"] for ids in (s["ids"] for s in seen))
    kept = [i["block_id"] for i in result["issues"] if i["code"] == "NO_LINGUISTIC_CONTENT_KEPT"]
    assert sorted(kept) == ["s1", "s2"]
    assert result["translations"]["s1"] == "|" and result["translations"]["s2"] == "5 €"


def test_lexical_evidence_relabels_only_on_strong_evidence():
    from app.documents.language_evidence import (
        available,
        has_linguistic_content,
        refine_block_languages,
    )

    if not available():
        pytest.skip("wordfreq lexicon not installed")
    ir = {
        "languages": ["fra", "nld", "spa"],
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {"id": "f1", "text": "Renseignements personnels", "language": "nld"},
                    {"id": "f2", "text": "+ Ville: Smalltown", "language": "ita"},
                    {"id": "e1", "text": "SEGUNDA: La biblioteca abre mañana", "language": "fra"},
                    {"id": "n1", "text": "Nombre: Juan", "language": "spa"},
                    {"id": "x1", "text": "| 5 €", "language": "unknown"},
                ],
            }
        ],
    }
    stats = refine_block_languages(ir)
    blocks = {b["id"]: b for b in ir["pages"][0]["blocks"]}
    assert blocks["f1"]["language"] == "fra" and blocks["f1"]["language_detected"] == "nld"
    assert blocks["e1"]["language"] == "spa"  # foreign text labelled French gets translated
    assert blocks["n1"]["language"] == "spa"  # ambiguous word (fr/es): detection kept
    assert blocks["x1"]["no_linguistic_content"] is True
    assert not has_linguistic_content("3 ,417.") and has_linguistic_content("نعم")
    assert stats["no_linguistic_content"] == 1
    # idempotent
    again = refine_block_languages(ir)
    assert again["refined"] == stats["refined"]
    assert blocks["f1"]["language_detected"] == "nld"


# --- C1: right-anchored (RTL) cell labels grow left, not right -------------


def _rtl_label(box, align="left"):
    return {
        "id": "p001-b0040",
        "page": 1,
        "text": "العنوان",  # synthetic one-word Arabic label ("the address")
        "bbox": list(box),
        "confidence": 0.9,
        "role": "line",
        "line_count": 1,
        "line_heights": [box[3] - box[1]],
        "source_lines": [{"id": "l0", "text": "العنوان", "bbox": list(box), "confidence": 0.9}],
        "style": {"align": align, "bold": False, "color": None, "highlight": False},
    }


def test_rtl_label_translation_grows_left_into_free_cell_space():
    """Run18 C1 (DOC-004): French replacements of short right-aligned Arabic
    labels are ~2x longer; growth was only to the right, where the cell ends,
    so they overflowed and were not written."""
    from test_scan_render_plan_final import _plan

    label = _rtl_label([470, 300, 510, 310])
    item, _issues, overflow = _plan(label, "Adresse du domicile")
    assert item is not None and not overflow
    assert item["inner"][2] <= 510.0 + 0.5  # right anchor kept (never pushed right)
    assert item["inner"][0] < 470  # grew into the free space on the left
    assert item["size"] >= 0.97 * item["measured_size"]
    assert item.get("align") == 2


def test_rtl_dominance_is_measured_on_letters():
    from app.documents.pdf_fidelity import _rtl_dominant

    assert _rtl_dominant("العنوان")
    assert not _rtl_dominant("Adresse العنوان du domicile")
    assert not _rtl_dominant("12/05")


# --- §10: one explicit status + reason per block ---------------------------


def _status_ir():
    def blk(i, text, language, **extra):
        return {"id": f"p001-b{i:04d}", "text": text, "language": language, **extra}

    return {
        "language": "eng",
        "languages": ["eng"],
        "pages": [
            {
                "number": 1,
                "blocks": [
                    blk(0, "The employee works full time.", "eng"),
                    blk(1, "Le salarié travaille à temps plein.", "fra"),
                    blk(2, "12/05/2021", "unknown"),
                    blk(3, "|", "unknown"),
                    blk(4, "Name of the employer", "eng"),
                    blk(5, "Date:", "eng"),
                    blk(6, "Blurred line ofr text", "eng", ocr_unreliable=True),
                    blk(7, "The contract ends in March.", "eng"),
                    blk(8, "Signature of the manager", "eng"),
                ],
            }
        ],
    }


def test_every_block_gets_one_explicit_status_and_reason():
    from app.documents.block_status import classify_blocks

    ir = _status_ir()
    source = {b["id"]: b["text"] for b in ir["pages"][0]["blocks"]}
    translations = dict(source)
    translations["p001-b0000"] = "Le salarié travaille à temps plein."
    translations["p001-b0007"] = "Le contrat prend fin en mars."
    del translations["p001-b0008"]
    issues = [{"code": "LAYOUT_OVERFLOW", "severity": "critical", "block_id": "p001-b0007"}]
    out = classify_blocks(ir, translations, issues)["blocks"]
    got = {k[-4:]: (v["status"], v["reason"]) for k, v in out.items()}
    assert got["0000"] == ("TRANSLATED", "translated_and_placed")
    assert got["0001"] == ("PRESERVED_INTENTIONALLY", "already_french")
    assert got["0002"][0] == "NOT_TRANSLATABLE" or got["0002"][0] == "PRESERVED_INTENTIONALLY"
    assert got["0003"] == ("NOT_TRANSLATABLE", "no_linguistic_content")
    assert got["0004"] == ("FAILED", "model_returned_source")  # omission stays visible
    assert got["0006"] == ("UNCERTAIN", "ocr_unreliable")
    assert got["0007"] == ("FAILED", "render_overflow")  # translated but not written
    assert got["0008"] == ("NOT_PROCESSED", "absent_from_translation_result")


def test_lexical_evidence_identical_in_french_and_foreign_word():
    import pytest

    from app.documents import language_evidence as le

    if not le.available():
        pytest.skip("offline lexicon not installed")
    assert le.identical_in_french("Date:", ["eng"]) and le.identical_in_french("Total", ["eng"])
    assert not le.identical_in_french("the", ["eng"])  # fr corpus noise, margin rejects it
    assert not le.identical_in_french("Name:", ["eng"])
    assert le.foreign_word_evidence("Name:", ["eng"]) and le.foreign_word_evidence("Datum", ["deu"])
    assert not le.foreign_word_evidence("Date:", ["eng"])


def test_short_foreign_label_returned_unchanged_is_retried_even_if_language_unknown():
    import pytest

    from app.ai.translation.service import _retry_candidate
    from app.documents import language_evidence as le

    if not le.available():
        pytest.skip("offline lexicon not installed")
    assert _retry_candidate({"text": "Name:", "language": "unknown"}, "Name:", "eng")
    assert not _retry_candidate({"text": "Date:", "language": "unknown"}, "Date:", "eng")
    assert not _retry_candidate({"text": "Nom :", "language": "fra"}, "Nom :", "eng")


# --- F9: check-box glyphs are protected visual regions --------------------
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.documents.line_verification import (  # noqa: E402
    checkbox_glyphs,
    normalize_mirrored_brackets,
    split_block_at_enumerators,
)

_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_LINE_PT = [50.0, 50.0, 150.0, 62.0]  # one OCR line, 12 pt high (48 px at x4)


def _line_raster(mark: str | None, letters: str = "nee") -> np.ndarray:
    image = Image.new("RGB", (800, 400), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    if mark is not None:
        box = (204, 204, 242, 242)  # 38 px square, 0.8 x line height
        if mark == "filled":
            draw.rectangle(box, fill=(20, 20, 20))
        else:
            draw.rectangle(box, outline=(20, 20, 20), width=3)
        if mark == "marked":
            draw.line((212, 212, 234, 234), fill=(20, 20, 20), width=3)
            draw.line((212, 234, 234, 212), fill=(20, 20, 20), width=3)
    draw.text((262, 202), letters, font=ImageFont.truetype(_BOLD, 40), fill=(20, 20, 20))
    return np.asarray(image)


@pytest.mark.parametrize("state", ["empty", "marked", "filled"])
def test_checkbox_glyph_detected_with_its_state(state):
    """Run18 DOC-004: yes/no boxes of a form were masked with their label."""
    found = checkbox_glyphs(_line_raster(state), [v * 4 for v in _LINE_PT])
    assert [g["state"] for g in found] == [state]


def test_round_and_square_letters_are_not_checkboxes():
    found = checkbox_glyphs(_line_raster(None, "oDOae0Q"), [v * 4 for v in _LINE_PT])
    assert found == []


# --- F17: empty boxes on inflated (RTL) OCR line boxes ---------------------
_INFLATED_LINE_PT = [50.0, 50.0, 150.0, 66.0]  # 64 px at x4 (ascenders/diacritics)


def _inflated_raster(mark: str | None, letters: str = "nee nee", size: int = 20) -> np.ndarray:
    image = Image.new("RGB", (800, 400), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    box = (204, 218, 232, 246)  # 28 px box = 0.44 x the inflated line height
    if mark == "filled":
        draw.rectangle(box, fill=(20, 20, 20))
    elif mark == "empty":
        draw.rectangle(box, outline=(20, 20, 20), width=3)
    draw.text((262, 222), letters, font=ImageFont.truetype(_BOLD, size), fill=(20, 20, 20))
    return np.asarray(image)


def test_empty_box_on_inflated_line_box_is_detected():
    """Run18 final audit DOC-004: Arabic OCR line boxes 58-66 px high around
    27-29 px empty boxes; the 0.6 x line-height bound rejected them and the
    translation masks erased three option boxes of a form."""
    found = checkbox_glyphs(_inflated_raster("empty"), [v * 4 for v in _INFLATED_LINE_PT])
    assert [g["state"] for g in found] == ["empty"]
    assert found[0]["height_reference"] == "line_glyphs"


def test_filled_square_or_letters_on_inflated_line_stay_rejected():
    """Filled components below the line bound are bold dots / bullets in the
    corpus (0.6-0.9 x the median glyph): never relabelled as boxes."""
    line = [v * 4 for v in _INFLATED_LINE_PT]
    assert checkbox_glyphs(_inflated_raster("filled"), line) == []
    assert checkbox_glyphs(_inflated_raster(None, "oDOae0Q nee", 26), line) == []


# --- F18: degraded RTL option lines are not sent -----------------------------
def _f18_option_block(text: str) -> dict:
    return {
        "id": "p001-b0009",
        "text": text,
        "language": "ara",
        "source_lines": [{"text": text, "bbox": [50.0, 50.0, 150.0, 66.0]}],
    }


def _f18_strip(block: dict) -> dict:
    import collections

    from app.documents.line_verification import strip_checkbox_tokens

    stats: dict = collections.defaultdict(int)
    # RTL line: the box sits at the right edge, where the line starts to be read.
    strip_checkbox_tokens({"pages": []}, block, {0: [[143.0, 52.0, 150.0, 59.0]]}, stats)
    return stats


def test_mixed_script_noise_rule():
    from app.documents.line_verification import mixed_script_noise

    assert mixed_script_noise("نص تجريبي قصير ab")
    assert mixed_script_noise("نص de تجريبي")
    assert not mixed_script_noise("نص تجريبي قصير")
    assert not mixed_script_noise("نص تجريبي Example Holding")  # bilingual label
    assert not mixed_script_noise("ab cd")  # no RTL word


def test_option_line_with_mixed_script_noise_is_uncertain_not_sent():
    """Run18 final audit DOC-004: after the box token was removed, an option
    line still read "<ar> <ar> + short Latin token" (words missing); the model
    invented a label. The block must be UNCERTAIN with the source kept."""
    block = _f18_option_block("xy نص تجريبي قصير ab")
    stats = _f18_strip(block)
    assert block["source_lines"][0]["checkbox_token"] == "stripped"
    assert block["source_lines"][0]["ocr_noise"] == "mixed_script"
    assert block["ocr_unreliable"] is True
    assert block["ocr_unreliable_reason"] == "checkbox_line_mixed_script_noise"
    assert stats["checkbox_lines_mixed_script_noise"] == 1
    clean = _f18_option_block("xy نص تجريبي قصير")
    _f18_strip(clean)
    assert clean["text"] == "نص تجريبي قصير"
    assert not clean.get("ocr_unreliable")
    _f18_strip(block)  # idempotent on analysis reuse
    assert block["ocr_unreliable"] is True


def _checkbox_ir():
    block = {
        "id": "p001-b0003",
        "provenance": "ocr:tesseract",
        "text": "nee",
        "bbox": list(_LINE_PT),
        "style": {"align": "left"},
        "source_lines": [{"id": "l0", "text": "nee", "bbox": list(_LINE_PT), "confidence": 0.9}],
    }
    page = {"number": 1, "scanned": True, "width": 200, "height": 100, "blocks": [block]}
    return {"pages": [page], "protected_visual_regions": []}, block


def test_checkbox_declared_once_as_carving_region():
    ir, block = _checkbox_ir()
    rasters = {1: _line_raster("marked")}
    stats = verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters=rasters)
    verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters=rasters)  # reuse
    regions = ir["protected_visual_regions"]
    assert len(regions) == 1 and stats["checkbox_regions_added"] == 1
    region = regions[0]
    assert region["subtype"] == "checkbox_glyph" and region["state"] == "marked"
    assert region["provenance"] == "automatic_candidate:line_verification"
    assert block["checkbox_glyphs"] == ["marked"]
    x0, y0, x1, y1 = region["bbox"]
    assert 50 <= x0 < x1 <= 62 and 50 <= y0 < y1 <= 62  # the box only, not the label


def test_checkbox_region_carves_text_but_never_protects_whole_block(tmp_path):
    import fitz

    from app.documents.pdf_fidelity import _scan_region_protects
    from app.documents.protected_visuals import protect_ir

    block = {"bbox": list(_LINE_PT)}
    box = {"bbox": [51.0, 51.0, 60.5, 60.5]}
    checkbox = {
        **box,
        "subtype": "checkbox_glyph",
        "provenance": "automatic_candidate:line_verification",
    }
    stamp = {
        **box,
        "subtype": "monochrome_visual_candidate",
        "provenance": "automatic_candidate:preprocessing",
    }
    human = {**box, "subtype": "checkbox_glyph", "provenance": "user_annotation"}
    assert _scan_region_protects(block, checkbox) is False
    assert _scan_region_protects(block, stamp) is True
    assert _scan_region_protects(block, human) is True
    source = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page(width=200, height=100)
    doc.save(source)
    doc.close()
    ir, ocr_block = _checkbox_ir()
    ir["source_path"] = str(source)
    ir["format"] = "pdf"
    ir["protected_visual_regions"] = [{**checkbox, "page": 1}]
    protect_ir(ir)
    assert ocr_block["protected"] is False  # translatable, box avoided by the renderer


# --- F10: numbered list items are rendered in place ------------------------
def _list_block(texts):
    lines = [
        {"id": f"l{i}", "text": t, "bbox": [40, 50 + 14 * i, 300, 61 + 14 * i], "confidence": 0.9}
        for i, t in enumerate(texts)
    ]
    return {
        "id": "p001-b0010",
        "text": " ".join(texts),
        "bbox": [40, 50, 300, 61 + 14 * (len(texts) - 1)],
        "line_count": len(texts),
        "line_heights": [11] * len(texts),
        "style": {"align": "left"},
        "source_lines": lines,
    }


def test_consecutive_numbered_lines_become_one_block_per_item():
    """Run18 DOC-004: numbered list items merged into one reflowed
    paragraph no longer faced their amounts."""
    parts = split_block_at_enumerators(
        _list_block(["1. Base pay", "2. Bonus for", "night work", "3. Overtime", "4. Leave"])
    )
    assert [p["id"] for p in parts] == [f"p001-b0010-i{n}" for n in (1, 2, 3, 4)]
    assert parts[1]["text"] == "2. Bonus for night work"  # continuation kept with its item
    rtl = split_block_at_enumerators(
        _list_block(
            [
                "\u0627\u0644\u0623\u062c\u0631 1",
                "\u0645\u0646\u062d\u0629 2",
                "\u0639\u0637\u0644\u0629 3",
            ]
        )
    )
    assert rtl is not None and len(rtl) == 3


@pytest.mark.parametrize(
    "texts",
    [
        ["1. Base pay", "3. Overtime", "4. Leave"],  # not consecutive
        ["1. Base pay", "2. Bonus"],  # too short
        ["12/03/2021 start", "13/03/2021 end", "14/03/2021 stop"],  # dates
        ["Paid in 2021", "Due in 2022", "Closed in 2023"],  # years
    ],
)
def test_lines_without_a_consecutive_enumeration_are_not_split(texts):
    assert split_block_at_enumerators(_list_block(texts)) is None


# --- F11: mirrored parentheses of RTL OCR lines ------------------------------
def test_mirrored_parentheses_around_digits_fixed_only_in_rtl_lines():
    """Run18 DOC-004: a footer phone number kept mirrored parentheses in source and target."""
    fixed, count = normalize_mirrored_brackets("\u0647\u0627\u062a\u0641 )010( 123")
    assert fixed == "\u0647\u0627\u062a\u0641 (010) 123" and count == 1
    assert normalize_mirrored_brackets("Tel )010( 123") == ("Tel )010( 123", 0)
    assert normalize_mirrored_brackets("\u0647\u0627\u062a\u0641 (010)")[1] == 0


# --- F12: a word is never cut inside a narrow frame --------------------------
def test_fit_refuses_a_frame_narrower_than_a_word():
    """Run18 DOC-004: a single word was drawn as two fragments in a narrow cell."""
    import fitz

    from app.documents.pdf_fidelity import _fit_on_scratch

    doc = fitz.open()
    doc.new_page(width=300, height=200)
    data = doc.tobytes()
    doc.close()
    style = {"bold": False, "italic": False}
    narrow = fitz.Rect(20, 20, 60, 120)  # 40 pt: the word needs ~80 pt at 10 pt
    ok, _rest, _used = _fit_on_scratch(data, 1, narrow, "pourcentage", 10.0, style, 0, 0.72)
    assert ok is False
    wide = fitz.Rect(20, 20, 140, 120)
    ok, _rest, used = _fit_on_scratch(data, 1, wide, "pourcentage", 10.0, style, 0, 0.72)
    assert ok is True and used == 10.0


def test_square_glyph_squeezed_inside_a_word_is_not_a_checkbox():
    """Run18 DOC-007: a degraded bold letter inside a word had square corners;
    a real box is separated from its label by a space on at least one side."""
    image = Image.new("RGB", (800, 400), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    for x in (150, 170, 190):  # letter stems on the left (gap 8 px)
        draw.rectangle((x, 204, x + 5, 242), fill=(20, 20, 20))
    draw.rectangle((204, 204, 242, 242), outline=(20, 20, 20), width=3)
    for x in (250, 270, 290):  # letter stems on the right (gap 8 px)
        draw.rectangle((x, 204, x + 5, 242), fill=(20, 20, 20))
    assert checkbox_glyphs(np.asarray(image), [v * 4 for v in _LINE_PT]) == []


# --- F19: a translation never grows over the line of an overlapping neighbour
def test_slightly_overlapping_neighbour_line_stays_an_obstacle():
    """Run18 final audit DOC-007: OCR boxes of two consecutive lines overlapped
    by 2 pt, the upper line was dropped from the obstacles and the longer
    translation of the lower block grew over it (two lines printed on top of
    each other). The neighbour is kept, clipped to its part outside the box."""
    import fitz

    from app.documents.pdf_fidelity import _grow_vertical, _neighbour_obstacle

    box = [84.0, 575.0, 543.0, 599.0]
    upper = [83.0, 563.0, 542.0, 577.0]
    page = fitz.Rect(0, 0, 595, 842)
    clipped = _neighbour_obstacle(upper, box)
    assert clipped == [83.0, 563.0, 542.0, 575.0]
    grown = _grow_vertical(box, 40.0, [clipped, [0.0, 600.0, 595.0, 842.0]], page)
    assert grown[1] >= 575.0  # never over the upper line
    # Former behaviour (neighbour dropped): the box climbed over the upper line.
    assert _grow_vertical(box, 40.0, [[0.0, 600.0, 595.0, 842.0]], page)[1] < 563.0
    lower = [84.0, 597.0, 543.0, 611.0]
    assert _neighbour_obstacle(lower, box) == [84.0, 599.0, 543.0, 611.0]
    side = [30.0, 576.0, 90.0, 598.0]
    assert _neighbour_obstacle(side, box) == [30.0, 576.0, 84.0, 598.0]


def test_container_or_disjoint_neighbours_keep_former_behaviour():
    from app.documents.pdf_fidelity import _neighbour_obstacle

    box = [100.0, 100.0, 300.0, 130.0]
    assert _neighbour_obstacle([90.0, 95.0, 310.0, 140.0], box) is None  # container
    assert _neighbour_obstacle([120.0, 105.0, 200.0, 125.0], box) is None  # contained
    assert _neighbour_obstacle([100.0, 140.0, 300.0, 160.0], box) == [100.0, 140.0, 300.0, 160.0]


# --- F13 / F13b / F15: check-box options, box glyph read as letters, evaluation


def _option_block(text, language="nld", lines=None):
    lines = lines or [{"id": "l0", "text": text, "bbox": list(_LINE_PT), "confidence": 0.9}]
    block = {
        "id": "p001-b0007",
        "provenance": "ocr:tesseract",
        "language": language,
        "text": " ".join(line["text"] for line in lines),
        "bbox": [50.0, 50.0, 150.0, float(lines[-1]["bbox"][3])],
        "style": {"align": "left"},
        "source_lines": lines,
    }
    page = {"number": 1, "scanned": True, "width": 200, "height": 100, "blocks": [block]}
    return {"pages": [page], "protected_visual_regions": []}, page


def test_short_token_read_in_place_of_the_box_is_removed_and_kept_raw():
    """Run18 DOC-004: an option line whose box was read as a one-character token was
    sent to the model and reflowed with the label."""
    ir, page = _option_block("© ja voor altijd")
    rasters = {1: _line_raster("empty", "ja voor")}
    stats = verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters=rasters)
    verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters=rasters)  # idempotent
    block = page["blocks"][0]
    assert block["text"] == "ja voor altijd" and not block.get("ocr_unreliable")
    assert block["source_lines"][0]["ocr_text_raw"] == "© ja voor altijd"
    assert stats["checkbox_tokens_stripped"] == 1


def test_box_fused_with_a_word_is_stripped_only_with_lexical_evidence():
    pytest.importorskip("wordfreq")
    ir, page = _option_block("Onee")
    rasters = {1: _line_raster("empty", "nee")}
    verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters=rasters)
    verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters=rasters)
    block = page["blocks"][0]
    assert block["text"] == "nee" and not block.get("ocr_unreliable")  # never "ee"


def test_box_fused_with_a_non_word_makes_the_block_uncertain_not_translated():
    """Run18 DOC-004: a box fused with its short label was read as a foreign word and translated."""
    pytest.importorskip("wordfreq")
    ir, page = _option_block("ventana", language="spa")
    verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters={1: _line_raster("marked")})
    block = page["blocks"][0]
    assert block["text"] == "ventana"  # source kept as read, never rewritten
    assert block["ocr_unreliable"] is True
    assert block["ocr_unreliable_reason"] == "checkbox_glyph_fused"


def _two_options_raster() -> np.ndarray:
    image = Image.new("RGB", (800, 400), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(_BOLD, 40)
    for top in (204, 284):
        draw.rectangle((204, top, 242, top + 38), outline=(20, 20, 20), width=3)
        draw.text((262, top - 2), "ja voor", font=font, fill=(20, 20, 20))
    return np.asarray(image)


def test_two_lines_each_starting_on_a_box_become_two_option_blocks():
    lines = [
        {
            "id": "l0",
            "text": "© ja voor bepaald",
            "bbox": [50.0, 50.0, 150.0, 62.0],
            "confidence": 0.9,
        },
        {
            "id": "l1",
            "text": "© ja voor altijd",
            "bbox": [50.0, 70.0, 150.0, 82.0],
            "confidence": 0.9,
        },
    ]
    ir, page = _option_block("", lines=lines)
    stats = verify_lines(
        ir, "unused.pdf", reader=lambda _i: None, rasters={1: _two_options_raster()}
    )
    ids = [b["id"] for b in page["blocks"]]
    assert ids == ["p001-b0007-o1", "p001-b0007-o2"]
    assert [b["text"] for b in page["blocks"]] == ["ja voor bepaald", "ja voor altijd"]
    assert all(b["split_from"]["reason"] == "checkbox_options" for b in page["blocks"])
    assert stats["blocks_split_at_checkbox_options"] == 1
    assert len(ir["protected_visual_regions"]) == 2


def test_unchanged_block_touching_a_checkbox_is_untranslated_not_protected():
    """Run18 F15: a label returned unchanged was hidden as "protected"."""
    from app.documents.pipeline import _protected_for

    block = {"page": 1, "bbox": list(_LINE_PT)}
    checkbox = {
        "page": 1,
        "bbox": [51.0, 51.0, 60.5, 60.5],
        "subtype": "checkbox_glyph",
        "provenance": "automatic_candidate:line_verification",
    }
    annotation = {**checkbox, "subtype": "signature", "provenance": "user_annotation"}
    assert not _protected_for(block, [checkbox])
    assert _protected_for(block, [annotation])


# --- translation memory of the corpus launcher (attributable re-runs)


def _launcher():
    import importlib
    import sys
    from pathlib import Path

    tools = str(Path(__file__).resolve().parents[3] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    return importlib.import_module("interim_owner_corpus_run")


async def test_translation_memory_reuses_only_unchanged_blocks_fail_closed(tmp_path):
    import json

    launcher = _launcher()
    cache = tmp_path / "run-a" / "out" / "DOC-X"
    cache.mkdir(parents=True)
    blocks = [
        {
            "id": "b1",
            "text": "Hello",
            "language": "eng",
            "bbox": [0, 0, 10, 10],
            "ocr_unreliable": False,
        },
        {
            "id": "b2",
            "text": "World",
            "language": "eng",
            "bbox": [0, 20, 10, 30],
            "ocr_unreliable": False,
        },
        {
            "id": "b3",
            "text": "Again",
            "language": "eng",
            "bbox": [0, 40, 10, 50],
            "ocr_unreliable": False,
        },
    ]
    (cache / "analysis.json").write_text(json.dumps({"pages": [{"number": 1, "blocks": blocks}]}))
    (cache / "interim-service-result.json").write_text(
        json.dumps(
            {
                "translations": {"b1": "Bonjour", "b2": "Monde", "b3": "Encore"},
                "issues": [{"code": "UNCHANGED_TRANSLATION_RETRY", "block_id": "b1"}],
                "untranslated_blocks": [],
                "translation_telemetry": {"provider": "interim"},
            }
        )
    )
    current = json.loads((cache / "analysis.json").read_text())
    current["pages"][0]["blocks"][0]["bbox"] = [1, 1, 11, 11]  # geometry only: reused
    current["pages"][0]["blocks"][1]["text"] = "World!"  # text changed: new request
    current["pages"][0]["blocks"][2]["ocr_unreliable"] = True  # guard changed: new request
    seen: list[list[str]] = []

    async def fake_service(ir, options):
        ids = [str(b["id"]) for p in ir["pages"] for b in p["blocks"]]
        seen.append(ids)
        return {
            "translations": {i: f"new-{i}" for i in ids},
            "issues": [],
            "translation_telemetry": {"provider": "interim"},
        }

    original = launcher._REAL_TRANSLATE_BLOCKS
    launcher._REAL_TRANSLATE_BLOCKS = fake_service
    try:
        work = tmp_path / "run-b" / "out" / "DOC-X"
        work.mkdir(parents=True)
        merged = await launcher._caching_translate(work, cache)(current, {})
    finally:
        launcher._REAL_TRANSLATE_BLOCKS = original
    assert seen == [["b2", "b3"]]
    assert merged["translations"] == {"b1": "Bonjour", "b2": "new-b2", "b3": "new-b3"}
    assert [i["block_id"] for i in merged["issues"]] == ["b1"]
    memory = merged["translation_telemetry"]["translation_memory"]
    assert memory == {
        "cache_run": "run-a",
        "blocks_reused": 1,
        "blocks_processed_now": 2,
        "invalidated_by_current_guard": {},
    }


async def test_translation_memory_prunes_fully_cached_tables_but_keeps_unmapped(tmp_path):
    import json

    launcher = _launcher()
    cache = tmp_path / "run-a" / "out" / "DOC-X"
    cache.mkdir(parents=True)
    blocks = [
        {"id": "b1", "text": "Name", "language": "eng", "bbox": [0, 0, 10, 10]},
        {"id": "b2", "text": "Date", "language": "eng", "bbox": [20, 0, 30, 10]},
    ]
    tables = [
        {
            "id": "t-cached",
            "page": 1,
            "cells": [{"id": "c1", "block_ids": ["b1"]}, {"id": "c2", "block_ids": ["b2"]}],
        },
        {"id": "t-unmapped", "page": 1, "cells": [{"id": "c9", "text": "orphan"}]},
    ]
    ir = {"pages": [{"number": 1, "blocks": blocks}], "tables": tables}
    (cache / "analysis.json").write_text(json.dumps(ir))
    (cache / "interim-service-result.json").write_text(
        json.dumps(
            {
                "translations": {"b1": "Nom", "b2": "Date"},
                "issues": [
                    {"code": "UNCHANGED_TRANSLATION_RETRY", "block_ids": ["b2", "zz"], "blocks": 2}
                ],
                "translation_telemetry": {"provider": "interim"},
            }
        )
    )
    seen: list[list[str]] = []

    async def fake_service(reduced, options):
        seen.append([str(t["id"]) for t in reduced.get("tables", [])])
        return {"translations": {}, "issues": [], "translation_telemetry": {"provider": "interim"}}

    original = launcher._REAL_TRANSLATE_BLOCKS
    launcher._REAL_TRANSLATE_BLOCKS = fake_service
    try:
        work = tmp_path / "run-b" / "out" / "DOC-X"
        work.mkdir(parents=True)
        merged = await launcher._caching_translate(work, cache)(json.loads(json.dumps(ir)), {})
    finally:
        launcher._REAL_TRANSLATE_BLOCKS = original
    assert seen == [["t-unmapped"]]
    assert merged["issues"] == [
        {"code": "UNCHANGED_TRANSLATION_RETRY", "block_ids": ["b2"], "blocks": 1}
    ]
