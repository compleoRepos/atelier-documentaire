"""Chunk budget is measured on what is actually sent (id/text/language).

Regression (final corpus run, DOC-004/DOC-007): grouped OCR blocks carry
rendering metadata (source_lines, style evidence, geometry). Counting it made a
62-cell table look like 38 522 tokens instead of 2 676 and blocked it without
any request. A genuinely oversized unit must still be reported as overflow.
"""

from __future__ import annotations

from app.ai.context.builder import ContextPackBuilder


class _CharTokenizer:
    def encode(self, value, add_special_tokens=False):
        return list(range(len(str(value)) // 4 + 1))


def _heavy_block(index: int, text: str) -> dict:
    lines = [
        {
            "id": f"p001-b{index:04d}-l{n}",
            "text": text,
            "bbox": [60.0, 100.0 + n * 12, 530.0, 110.0 + n * 12],
            "confidence": 0.91,
            "style_evidence": {"stroke_px": 2.1, "ink_rgb": [0.1, 0.1, 0.1]}
            | {f"k{i}": i for i in range(60)},
        }
        for n in range(6)
    ]
    return {
        "id": f"p001-b{index:04d}",
        "page": 1,
        "text": text,
        "bbox": [60, 100, 530, 180],
        "source_lines": lines,
    }


def _ir(blocks):
    return {
        "pages": [{"number": 1, "blocks": blocks}],
        "tables": [{"page": 1, "block_ids": [b["id"] for b in blocks]}],
    }


def test_rendering_metadata_does_not_count_against_the_budget():
    blocks = [_heavy_block(i, "Nom de l'employeur") for i in range(62)]
    builder = ContextPackBuilder(tokenizer=_CharTokenizer(), max_tokens=2000)
    unit = builder.units(_ir(blocks))[0]
    assert builder.count_tokens(builder._unit_json(unit)) > 2000  # what was counted before
    chunks = builder.build_chunks(_ir(blocks))
    assert len(chunks) == 1 and chunks[0]["overflow"] is False
    assert len(chunks[0]["blocks"]) == 62
    assert chunks[0]["blocks"][0]["source_lines"]  # metadata still available downstream


def test_genuinely_oversized_table_is_still_atomic_overflow():
    blocks = [_heavy_block(i, "mot " * 400) for i in range(10)]
    builder = ContextPackBuilder(tokenizer=_CharTokenizer(), max_tokens=2000)
    chunks = builder.build_chunks(_ir(blocks))
    assert len(chunks) == 1 and chunks[0]["overflow"] is True
