"""OCR line grouping into logical blocks (prompt final, priority 1).

Synthetic pages only: geometry mirrors the measurements taken on the corpus
(body line height ~9-10 pt, intra-paragraph gap < 0.75 H, paragraph gap > 1 H).
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.documents.segmentation import (
    VERSION,
    is_unreliable_ocr,
    line_style_evidence,
    segment_ir,
    segment_page,
)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _line(i, text, x0, y0, x1, h=10.0, conf=0.93, **extra):
    return {
        "id": f"p001-b{i:04d}",
        "page": 1,
        "kind": "text",
        "text": text,
        "bbox": [x0, y0, x1, y0 + h],
        "confidence": conf,
        "language": "eng",
        "reading_order": i,
        **extra,
    }


def _page(blocks):
    return {"number": 1, "width": 595.0, "height": 842.0, "scanned": True, "blocks": blocks}


def test_multiline_paragraph_is_one_block_with_traceable_lines():
    blocks = [
        _line(0, "Nora Dubois has been our permanent Office Coordinator since the", 60, 200, 530),
        _line(
            1, "services county from 4.11.2021 until today and she was in charge of", 60, 213, 532
        ),
        _line(2, "the daily planning.", 60, 226, 200),
    ]
    out, trace = segment_page(_page(blocks))
    assert len(out) == 1
    block = out[0]
    assert block["role"] == "paragraph" and block["line_count"] == 3
    assert block["id"] == "p001-b0000"  # first line id is kept: references stay valid
    assert [ln["id"] for ln in block["source_lines"]] == [b["id"] for b in blocks]
    assert block["text"].startswith("Nora Dubois") and block["text"].endswith("daily planning.")
    assert block["segmentation"] == {
        "version": VERSION,
        "merged": True,
        "member_ids": [b["id"] for b in blocks],
    }
    assert trace["merged_groups"] == 1 and trace["merged_lines"] == 3


def test_short_title_stays_separate_from_following_paragraph():
    blocks = [
        _line(0, "Employment certificate", 60, 180, 190, h=14.5),
        _line(1, "Nora Dubois has been our permanent Office Coordinator since the", 60, 205, 530),
        _line(2, "services county from 4.11.2021.", 60, 218, 260),
    ]
    out, _ = segment_page(_page(blocks))
    assert len(out) == 2
    title = next(b for b in out if b["id"] == "p001-b0000")
    assert title["line_count"] == 1 and title["text"] == "Employment certificate"


def test_signature_lines_keep_their_deliberate_line_break():
    blocks = [
        _line(0, "Nora Dubois has been our permanent Office Coordinator since the", 60, 200, 530),
        _line(
            1, "services county from 4.11.2021 until today and she was in charge of", 60, 213, 532
        ),
        _line(2, "Paul Exemple-Nom, Service Manager", 60, 300, 230),
        _line(3, "Exempla", 60, 312, 100),
    ]
    out, trace = segment_page(_page(blocks))
    ids = {b["id"] for b in out}
    assert {"p001-b0002", "p001-b0003"} <= ids  # name/title and company stay two lines
    assert trace["refusals"].get("short_line_break", 0) >= 1


def test_lines_in_different_table_cells_are_never_merged():
    blocks = [
        _line(0, "Salaire de base mensuel brut", 60, 400, 250),
        _line(1, "Indemnité de transport mensuelle", 60, 412, 260),
    ]
    tables = [
        {
            "id": "t1",
            "page": 1,
            "cells": [
                {
                    "id": "t1:r0:c0",
                    "row": 0,
                    "col": 0,
                    "bbox": [55, 398, 300, 411],
                    "block_ids": ["p001-b0000"],
                },
                {
                    "id": "t1:r1:c0",
                    "row": 1,
                    "col": 0,
                    "bbox": [55, 411, 300, 424],
                    "block_ids": ["p001-b0001"],
                },
            ],
        }
    ]
    out, trace = segment_page(_page(blocks), tables)
    assert len(out) == 2
    assert {b["table_cell_id"] for b in out} == {"t1:r0:c0", "t1:r1:c0"}
    assert all(b["role"] == "table_cell" for b in out)
    assert trace["refusals"].get("table_cell_boundary", 0) >= 1


def test_side_by_side_columns_are_not_merged():
    blocks = [
        _line(0, "Nom du salarié", 60, 500, 160),
        _line(1, "Date d'entrée", 320, 500, 410),
        _line(2, "Fonction occupée", 60, 513, 170),
        _line(3, "Type de contrat", 320, 513, 420),
    ]
    out, _ = segment_page(_page(blocks))
    for block in out:
        xs = {round(line["bbox"][0]) for line in block["source_lines"]}
        assert len(xs) == 1  # a group never spans the two columns


def test_protected_line_is_never_merged():
    blocks = [
        _line(
            0, "Le présent contrat est conclu pour une durée indéterminée et prend", 60, 600, 530
        ),
        _line(
            1,
            "effet à compter de la date de signature des deux parties concernées",
            60,
            613,
            530,
            protected=True,
        ),
    ]
    out, trace = segment_page(_page(blocks))
    assert len(out) == 2
    assert trace["refusals"].get("protected_line", 0) >= 1


def test_unreadable_ocr_noise_is_flagged_and_not_a_merge_partner():
    assert is_unreliable_ocr("© N ES", 0.21)
    assert not is_unreliable_ocr("Attestation", 0.21)  # a real word is kept
    assert not is_unreliable_ocr("© N ES", 0.9)
    blocks = [_line(0, "~ = ©", 60, 700, 90, conf=0.2)]
    out, _ = segment_page(_page(blocks))
    assert out[0]["ocr_unreliable"] is True


def _render_lines(lines, scale=4.0):
    """Draw lines at 288 dpi; return the RGB array and pt bboxes."""
    image = Image.new("RGB", (int(595 * scale), int(842 * scale)), "white")
    draw = ImageDraw.Draw(image)
    boxes = []
    for text, y_pt, bold in lines:
        font = ImageFont.truetype(FONT_BOLD if bold else FONT, int(9 * scale))
        x0, y0, x1, y1 = draw.textbbox((60 * scale, y_pt * scale), text, font=font)
        draw.text((60 * scale, y_pt * scale), text, font=font, fill=(20, 20, 20))
        boxes.append([x0 / scale, y0 / scale, x1 / scale, y1 / scale])
    return np.asarray(image), boxes


def test_bold_line_is_detected_from_raster_stroke_evidence():
    specs = [
        ("Conditions generales du contrat", 100, True),
        ("Le salarie exerce ses fonctions au siege social", 140, False),
        ("La remuneration est versee chaque fin de mois", 180, False),
        ("Les conges payes sont acquis selon la loi", 220, False),
    ]
    rgb, boxes = _render_lines(specs)
    blocks = []
    for i, ((text, _, _), box) in enumerate(zip(specs, boxes, strict=True)):
        block = _line(i, text, box[0], box[1], box[2], h=box[3] - box[1])
        evidence = line_style_evidence(rgb, [v * 4.0 for v in box], points_per_pixel=0.25)
        assert evidence is not None
        block["style_evidence"] = evidence
        blocks.append(block)
    out, _ = segment_page(_page(blocks))
    by_id = {b["id"]: b for b in out}
    assert by_id["p001-b0000"]["style"]["bold"] is True
    assert all(by_id[f"p001-b{i:04d}"]["style"]["bold"] is False for i in (1, 2, 3))


def test_segment_ir_remaps_table_references_to_the_group_id():
    blocks = [
        _line(0, "Nora Dubois has been our permanent Office Coordinator since the", 60, 200, 530),
        _line(1, "services county from 4.11.2021.", 60, 213, 260),
    ]
    ir = {
        "pages": [_page(blocks)],
        "tables": [
            {
                "id": "t9",
                "page": 1,
                "cells": [
                    {
                        "id": "t9:r0:c0",
                        "row": 0,
                        "col": 0,
                        "bbox": [10, 10, 585, 832],  # scan frame: excluded as a semantic cell
                        "block_ids": ["p001-b0000", "p001-b0001"],
                    }
                ],
            }
        ],
    }
    segment_ir(ir)
    assert [b["id"] for b in ir["pages"][0]["blocks"]] == ["p001-b0000"]
    assert ir["tables"][0]["cells"][0]["block_ids"] == ["p001-b0000", "p001-b0000"] or ir["tables"][
        0
    ]["cells"][0]["block_ids"] == ["p001-b0000"]
    assert ir["segmentation"]["version"] == VERSION
    assert ir["segmentation"]["input_lines"] == 2 and ir["segmentation"]["output_blocks"] == 1


def test_highlighted_line_keeps_highlight_and_ink_evidence():
    scale = 4.0
    image = Image.new("RGB", (int(595 * scale), int(842 * scale)), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, int(9 * scale))
    texts = [("Montant net a payer", 100, True), ("Periode du mois de mars", 140, False)]
    blocks = []
    for i, (text, y_pt, highlighted) in enumerate(texts):
        x0, y0, x1, y1 = draw.textbbox((60 * scale, y_pt * scale), text, font=font)
        if highlighted:
            draw.rectangle([x0 - 8, y0 - 6, x1 + 8, y1 + 6], fill=(255, 236, 110))
        draw.text((60 * scale, y_pt * scale), text, font=font, fill=(15, 15, 15))
        box = [x0 / scale, y0 / scale, x1 / scale, y1 / scale]
        block = _line(i, text, box[0], box[1], box[2], h=box[3] - box[1])
        block["style_evidence"] = line_style_evidence(
            np.asarray(image), [x0, y0, x1, y1], points_per_pixel=1 / scale
        )
        blocks.append(block)
    out, _ = segment_page(_page(blocks))
    by_id = {b["id"]: b for b in out}
    marked = by_id["p001-b0000"]["style"]
    assert marked["highlight"] is True and marked["background"][2] < 0.6
    assert marked["color"] is None  # black ink is not reported as a colour
    assert by_id["p001-b0001"]["style"]["highlight"] is False
