"""Independent render measurement (tools/recette/render_outcome.py), method v2.1.

Synthetic PDF only (no corpus data). The search zone of a block must not depend
on the direction in which a renderer grows its frame: a translation fully written
to the LEFT of its source box (right-aligned / RTL cell, run18 F5) and one
overflowing to the RIGHT are both WRITTEN, while a really truncated one stays
PARTIAL and a missing one ABSENT.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import fitz


def _render_outcome():
    tools = str(Path(__file__).resolve().parents[3] / "tools" / "recette")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    return importlib.import_module("render_outcome")


def _pdf(tmp_path: Path, items: list[tuple[float, float, str]]) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for x, y, text in items:
        page.insert_text((x, y), text, fontsize=9, fontname="helv")
    path = tmp_path / "candidate.pdf"
    doc.save(path)
    doc.close()
    return path


def test_zone_is_symmetric_around_the_source_box():
    ro = _render_outcome()
    x0, y0, x1, y1 = ro._zone((200.0, 100.0, 300.0, 112.0), 1)
    assert 200.0 - x0 == x1 - 300.0 > 50.0
    assert y0 < 100.0 and y1 > 112.0


def test_left_growth_and_right_overflow_are_both_written(tmp_path):
    ro = _render_outcome()
    target = "Accepted before the courts"  # ~105 pt for a 70 pt box
    # A: right-anchored on its box end (x1 = 300) -> grows left of x0 = 230.
    # B: starts at its box start (x0 = 330) -> overflows right of x1 = 400.
    # C: truncated (only 1 of 4 target tokens printed).
    # D: nothing printed.
    pdf = _pdf(
        tmp_path,
        [
            (300 - fitz.get_text_length(target, fontname="helv", fontsize=9), 110, target),
            (330, 210, target),
            (230, 310, "Accepted"),
        ],
    )
    pages = [
        {
            "number": 1,
            "scanned": False,
            "blocks": [
                {"id": "A", "bbox": [230, 101, 300, 112], "line_count": 1, "text": "src a"},
                {"id": "B", "bbox": [330, 201, 400, 212], "line_count": 1, "text": "src b"},
                {"id": "C", "bbox": [230, 301, 300, 312], "line_count": 1, "text": "src c"},
                {"id": "D", "bbox": [230, 501, 300, 512], "line_count": 1, "text": "src d"},
            ],
        }
    ]
    translations = {"A": target, "B": target, "C": target, "D": target}
    out = ro.measure_candidate(pdf, pages, translations, lambda s, t: bool(t) and s != t)
    blocks = out["blocks"] if "blocks" in out else out["per_block"]
    assert blocks["A"]["status"] == "WRITTEN"
    assert blocks["B"]["status"] == "WRITTEN"
    assert blocks["C"]["status"] == "PARTIAL"
    assert blocks["D"]["status"] == "ABSENT"
