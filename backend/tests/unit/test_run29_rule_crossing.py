"""RUN29 F53 regression: translated text must not be drawn across a rule that
the paper cover leaves visible (synthetic rasters and invented text only; no
document of the private corpus is used, no text of it either).

F38/F48 clip a cover off a table rule so the rule survives, but the text frame
anchored on an inflated OCR box may still straddle that rule: the translation
is then printed struck through, which reads as deleted. F53 measures the lines
PyMuPDF really draws (scratch page) and refuses the placement (source kept,
critical anomaly) when a visible rule runs through the x-height body of a
line. A rule at the baseline (underline effect) stays allowed. The counter-
proof shows the RUN29-before-F53 behaviour when the check is switched off.
"""

from __future__ import annotations

import io

import fitz
import numpy as np
import pytest
from PIL import Image

from app.documents import pdf_fidelity as pf
from app.documents.block_status import VERSION
from app.documents.pdf_fidelity import _plan_scan_block

PAPER = (250, 250, 248)


def _page(rows: list[tuple[int, int, int, int]]) -> fitz.Page:
    """A scanned A4 page (1 px per point) with dark bands (y0, y1, x0, x1)."""
    arr = np.full((842, 595, 3), PAPER, dtype=np.uint8)
    for y0, y1, x0, x1 in rows:
        arr[y0:y1, x0:x1] = 0
    buffer = io.BytesIO()
    Image.fromarray(arr).save(buffer, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    return doc[0]


# ------------------------------------------------------ rule detection ------


def test_f53_a_thin_long_rule_is_found_with_its_extent():
    page = _page([(205, 206, 30, 400)])
    rules = pf._visible_rules_in(page, [60.0, 200.0, 200.0, 212.0], [])
    assert len(rules) == 1
    y, x0, x1 = rules[0]
    assert y == pytest.approx(205.5, abs=0.3)
    assert x0 == pytest.approx(60.0, abs=0.6) and x1 == pytest.approx(200.0, abs=0.6)


def test_f53_a_rule_under_a_cover_is_not_visible():
    page = _page([(205, 206, 30, 400)])
    cover = [55.0, 203.0, 205.0, 208.0]  # the cover paints over the rule
    assert pf._visible_rules_in(page, [60.0, 200.0, 200.0, 212.0], [cover]) == []


def test_f53_short_runs_and_thick_bands_are_not_rules():
    short = _page([(205, 206, 60, 70)])  # 10 pt: a glyph stroke, not a rule
    assert pf._visible_rules_in(short, [60.0, 200.0, 200.0, 212.0], []) == []
    thick = _page([(202, 208, 30, 400)])  # 6 pt: a graphic band, not a rule
    assert pf._visible_rules_in(thick, [60.0, 198.0, 200.0, 214.0], []) == []


def test_f53_drawn_lines_report_the_real_baseline():
    page = _page([])
    lines = pf._drawn_lines(page.rect, [60.0, 200.0, 300.0, 214.0], "mot clé inventé", 9.0, {}, 0)
    assert len(lines) == 1
    baseline, size, x0, x1 = lines[0]
    assert 200.0 < baseline < 214.0
    assert size == pytest.approx(9.0)
    assert x0 >= 59.5 and x1 > x0


def test_f53_rule_through_the_body_crosses_but_rule_at_the_baseline_does_not():
    rect, text, size = [60.0, 200.0, 300.0, 214.0], "mot clé inventé", 9.0
    (baseline, *_rest) = pf._drawn_lines(_page([]).rect, rect, text, size, {}, 0)[0]
    body = int(round(baseline - 0.3 * size))  # middle of the x-height
    through = _page([(body, body + 1, 30, 400)])
    hit = pf._text_crosses_visible_rule(through, rect, text, size, {}, 0, [])
    assert hit == pytest.approx(body + 0.5, abs=0.3)
    under = int(round(baseline))  # underline effect
    at_baseline = _page([(under, under + 1, 30, 400)])
    assert pf._text_crosses_visible_rule(at_baseline, rect, text, size, {}, 0, []) is None


def test_f53_a_rule_beside_the_drawn_text_does_not_cross():
    rect, text, size = [60.0, 200.0, 300.0, 214.0], "mot", 9.0
    (baseline, *_rest) = pf._drawn_lines(_page([]).rect, rect, text, size, {}, 0)[0]
    body = int(round(baseline - 0.3 * size))
    beside = _page([(body, body + 1, 150, 400)])  # starts far right of "mot"
    assert pf._text_crosses_visible_rule(beside, rect, text, size, {}, 0, []) is None


# ---------------------------------------------------- planner (F53) --------


def _block() -> dict:
    box = [60.0, 200.0, 200.0, 212.0]
    text = "Invented source line"
    return {
        "id": "p001-b0200",
        "page": 1,
        "text": text,
        "bbox": box,
        "confidence": 0.93,
        "role": "line",
        "line_count": 1,
        "line_heights": [10.0],
        "line_pitch": None,
        "source_lines": [{"id": "p001-b0200-l0", "text": text, "bbox": box, "confidence": 0.93}],
        "style": {"align": "left", "bold": False, "color": None, "highlight": False},
    }


def _plan(rule_row: int):
    # A table rule running through the OCR box and well beyond it, so F38/F48
    # clip the cover off it and the rule stays visible.
    page = _page([(rule_row, rule_row + 1, 20, 560)])
    block = _block()
    return _plan_scan_block(
        block=block,
        target="Ligne traduite inventée",
        page=page,
        page_number=1,
        ir_blocks=[block],
        protected_regions=[],
        body_size=9.0,
        body_right=532.0,
        source_bytes=page.parent.tobytes(),
        bound=None,
    )


def _codes(issues: list[dict]) -> list[str]:
    return [issue["code"] for issue in issues]


def test_f53_planner_refuses_the_frame_the_check_flags(monkeypatch):
    # Wiring: the check receives the frame, size, style and covers the planner
    # would draw with; a hit refuses the placement (source kept, critical).
    monkeypatch.setattr(pf, "_SCAN_CHECK_TEXT_OVER_RULES", False)
    placed, _issues, _overflow = _plan(400)  # rule far from the line
    assert placed is not None
    seen = []

    def flag(page, rect, text, size, style, align, covers):
        seen.append((list(rect), text, size, dict(style), align, [list(c) for c in covers]))
        return 205.0

    monkeypatch.setattr(pf, "_text_crosses_visible_rule", flag)
    monkeypatch.setattr(pf, "_SCAN_CHECK_TEXT_OVER_RULES", True)
    item, issues, overflow = _plan(400)
    assert item is None and overflow is False
    assert seen == [
        (
            placed["inner"],
            placed["text"],
            placed["size"],
            placed["style"],
            placed["align"],
            placed["source_rects"],
        )
    ]
    hits = [i for i in issues if i["code"] == "SCAN_TEXT_CROSSES_RULE"]
    assert len(hits) == 1 and hits[0]["severity"] == "critical"
    assert hits[0]["block_id"] == "p001-b0200" and hits[0]["rule_y"] == 205.0


def test_f53_counter_proof_switched_off_the_check_is_not_run(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("F53 check must not run when switched off")

    monkeypatch.setattr(pf, "_text_crosses_visible_rule", boom)
    monkeypatch.setattr(pf, "_SCAN_CHECK_TEXT_OVER_RULES", False)
    item, issues, _overflow = _plan(400)
    assert item is not None
    assert "SCAN_TEXT_CROSSES_RULE" not in _codes(issues)


def test_f53_planner_real_check_passes_a_line_with_a_distant_rule():
    item, issues, _overflow = _plan(400)
    assert item is not None
    assert "SCAN_TEXT_CROSSES_RULE" not in _codes(issues)


def test_f53_planner_without_any_rule_is_unchanged(monkeypatch):
    page = _page([])
    block = _block()
    kwargs = dict(
        block=block,
        target="Ligne traduite inventée",
        page=page,
        page_number=1,
        ir_blocks=[block],
        protected_regions=[],
        body_size=9.0,
        body_right=532.0,
        source_bytes=page.parent.tobytes(),
        bound=None,
    )
    on = _plan_scan_block(**kwargs)
    monkeypatch.setattr(pf, "_SCAN_CHECK_TEXT_OVER_RULES", False)
    off = _plan_scan_block(**kwargs)
    assert on[0] is not None and off[0] is not None
    assert on[0]["inner"] == off[0]["inner"] and on[0]["size"] == off[0]["size"]
    assert _codes(on[1]) == _codes(off[1])


def test_f53_status_mapping_and_version():
    from app.documents.block_status import _RENDER_FAILURES

    assert VERSION.startswith("block-status-6")
    assert _RENDER_FAILURES["SCAN_TEXT_CROSSES_RULE"] == "render_text_crosses_rule"
