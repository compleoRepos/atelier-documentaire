"""Final corpus audit regressions (synthetic data only).

Measured on the final run of the authorised corpus, after form frames were no
longer protected as a whole on scans:
* one OCR line spanning three form cells, and digit boxes (box rules read as extra
  digits), were rewritten as one line: values left their cells;
* two table rows were merged into one paragraph;
* a footer line made of identifiers only (RIB/ICE) was rewritten and the two
  logo marks OCR had read as letters were erased;
* low-confidence OCR lines swollen by a rotated stamp produced a giant font.
"""

from __future__ import annotations

import httpx
import numpy as np
import pytest
from test_interim_owner_authorization import SHA, options
from test_line_verification_final import _response

from app.ai.translation.service import translate_blocks
from app.documents.line_verification import (
    form_structure_evidence,
    horizontal_rule_between,
    identifier_only,
    ruling_glyphs,
    verify_lines,
    vertical_rules_crossing,
)
from app.documents.pdf_fidelity import _scan_font_size


def _page(rules_v=(), rules_h=()):
    rgb = np.full((600, 2400, 3), 250, dtype=np.uint8)
    rgb[210:240, 220:300] = 20  # glyph strokes, inside the line box only
    rgb[210:240, 900:910] = 20  # a tall glyph ("l") stays inside the line box
    for x, y0, y1 in rules_v:
        rgb[y0:y1, x : x + 3] = 15
    for y, x0, x1 in rules_h:
        rgb[y : y + 3, x0:x1] = 15
    return rgb


LINE_PX = [200.0, 205.0, 1600.0, 245.0]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("| Certificate NVQ or HND", True),
        ("Date of Return (where needed) _| N/A", True),
        ("PAÍS 7] 2] 4]| CIUDAD 047262228 01", True),
        ("CIUDAD [o]s [o] PAÍS 724", True),
        ("Company | Street 2 | PO 46", True),
        ("Then | think the contract is clear", False),  # single bar = misread "I"
        ("The employee works full time.", False),
        ("", False),
    ],
)
def test_ruling_glyphs_only_at_structural_positions(text, expected):
    assert ruling_glyphs(text) is expected


def test_vertical_rule_crossing_a_line_is_detected_but_glyph_strokes_are_not():
    assert vertical_rules_crossing(_page(), LINE_PX) == 0
    crossing = _page(rules_v=[(800, 120, 330)])  # cell border well above and below
    assert vertical_rules_crossing(crossing, LINE_PX) == 1
    inside = _page(rules_v=[(800, 207, 243)])  # stroke confined to the line box
    assert vertical_rules_crossing(inside, LINE_PX) == 0


def test_horizontal_rule_between_two_lines_is_detected():
    upper, lower = [200.0, 205.0, 1600.0, 245.0], [200.0, 285.0, 1600.0, 325.0]
    assert horizontal_rule_between(_page(), upper, lower) is False
    ruled = _page(rules_h=[(262, 150, 1700)])
    assert horizontal_rule_between(ruled, upper, lower) is True


def test_form_structure_evidence_reasons():
    lines = [
        {"text": "Hello Sample Qualification", "bbox": [50, 51.25, 400, 61.25]},
        {"text": "Period Covered (where needed)", "bbox": [50, 71.25, 400, 81.25]},
    ]
    ruled = _page(rules_h=[(262, 150, 1700)])
    assert form_structure_evidence(ruled, lines, 4.0) == ["horizontal_rule_between_lines"]
    assert form_structure_evidence(_page(), lines, 4.0) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("B RIB : 011122233344455566677788 — ICE : 000111222333444 B", True),
        ("t: +44 (0)20 7946 0501", True),
        ("10/12/2021", True),
        ("ZZ9 9ZZ", False),  # no 3-digit group: sent, the model keeps it
        ("1. DEFINITIONS", False),  # upper-case heading = words, not acronyms
        ("12. NOTICE OF TERMINATION OF EMPLOYMENT 2024", False),
        ("Tel: +44 (0) 20 7946 0716", False),
        ("Licence for Sample", False),  # no digits
        ("الهاتف 055-000 11 22", False),  # Arabic word: translatable
        ("Start date 10/12/2021", False),
    ],
)
def test_identifier_only_lines(text, expected):
    assert identifier_only(text) is expected


def test_verify_lines_marks_structure_risk_and_identifier_only_with_counts():
    ruled_block = {
        "id": "p001-b0000",
        "text": "Hello Sample Qualification Period Covered (where needed)",
        "style": {},
        "source_lines": [
            {"id": "l0", "text": "Hello Sample Qualification", "bbox": [50, 51.25, 400, 61.25]},
            {"id": "l1", "text": "Period Covered (where needed)", "bbox": [50, 71.25, 400, 81.25]},
        ],
    }
    footer = {
        "id": "p001-b0001",
        "text": "RIB : 011122233344455566677788",
        "style": {},
        "source_lines": [
            {"id": "l2", "text": "RIB : 011122233344455566677788", "bbox": [50, 120, 400, 130]}
        ],
    }
    clean = {
        "id": "p001-b0002",
        "text": "The employee works full time.",
        "style": {},
        "source_lines": [
            {"id": "l3", "text": "The employee works full time.", "bbox": [50, 140, 400, 150]}
        ],
    }
    ir = {"pages": [{"number": 1, "scanned": True, "blocks": [ruled_block, footer, clean]}]}
    stats = verify_lines(
        ir, "unused.pdf", reader=lambda _i: None, rasters={1: _page(rules_h=[(262, 150, 1700)])}
    )
    assert ruled_block["form_structure_risk"]["reasons"] == ["horizontal_rule_between_lines"]
    assert footer.get("identifier_only") is True
    assert "form_structure_risk" not in clean and "identifier_only" not in clean
    assert stats["blocks_form_structure_risk"] == 1 and stats["blocks_identifier_only"] == 1
    # idempotent: a second pass on a clean raster removes stale flags
    verify_lines(ir, "unused.pdf", reader=lambda _i: None, rasters={1: _page()})
    assert "form_structure_risk" not in ruled_block


@pytest.mark.asyncio
async def test_structural_and_identifier_blocks_are_never_sent_nor_rewritten(tmp_path):
    seen = []

    def handler(request):
        import json

        blocks = json.loads(json.loads(request.content)["messages"][1]["content"])["blocks"]
        seen.extend(b["id"] for b in blocks)
        return _response([(b["id"], f"Traduction {b['id']}.") for b in blocks])

    ir = {
        "language": "es",
        "domain": "HR",
        "versions": {"source_sha256": SHA},
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {
                        "id": "b1",
                        "text": "ANA PRUEBA LOPEZ 00000000T APODERADO",
                        "language": "spa",
                        "form_structure_risk": {
                            "reasons": ["vertical_rule_crosses_line"],
                            "lines": 1,
                        },
                    },
                    {
                        "id": "b2",
                        "text": "RIB : 011122233344455566677788",
                        "language": "fra",
                        "identifier_only": True,
                    },
                    {"id": "b3", "text": "El trabajador presta servicios.", "language": "spa"},
                ],
            }
        ],
    }
    result = await translate_blocks(ir, options(tmp_path, httpx.MockTransport(handler)))
    assert seen == ["b3"]
    assert result["translations"]["b1"] == "ANA PRUEBA LOPEZ 00000000T APODERADO"
    form = [i for i in result["issues"] if i["code"] == "FORM_STRUCTURE_PRESERVED"]
    assert (
        form
        and form[0]["severity"] == "warning"
        and form[0]["reasons"] == ["vertical_rule_crosses_line"]
    )


@pytest.mark.asyncio
async def test_identifier_only_non_french_block_is_kept_with_info_issue(tmp_path):
    seen = []

    def handler(request):
        import json

        blocks = json.loads(json.loads(request.content)["messages"][1]["content"])["blocks"]
        seen.extend(b["id"] for b in blocks)
        return _response([(b["id"], f"Traduction {b['id']}.") for b in blocks])

    ir = {
        "language": "en",
        "domain": "HR",
        "versions": {"source_sha256": SHA},
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {"id": "b1", "text": "ZZ9 9ZZ", "language": "eng", "identifier_only": True},
                    {"id": "b2", "text": "The employee works full time.", "language": "eng"},
                ],
            }
        ],
    }
    result = await translate_blocks(ir, options(tmp_path, httpx.MockTransport(handler)))
    assert seen == ["b2"]
    assert result["translations"]["b1"] == "ZZ9 9ZZ"
    kept = [i for i in result["issues"] if i["code"] == "IDENTIFIER_ONLY_KEPT"]
    assert kept and kept[0]["severity"] == "info" and kept[0]["block_id"] == "b1"


def _sized(height, confidence, role="line"):
    return {
        "text": "Dear Sam Taylor",
        "role": role,
        "confidence": confidence,
        "bbox": [100, 256, 496, 256 + height],
        "line_heights": [height],
        "source_lines": [
            {
                "text": "Dear Sam Taylor",
                "bbox": [100, 256, 496, 256 + height],
                "confidence": confidence,
            }
        ],
    }


def test_low_confidence_swollen_line_gets_body_size_but_confident_heading_keeps_its_own():
    swollen = _scan_font_size(_sized(22.5, 0.74, role="heading"), 8.4)
    assert swollen == pytest.approx(8.4)
    title = _scan_font_size(_sized(16.0, 0.93, role="heading"), 8.4)
    assert title > 1.25 * 8.4
