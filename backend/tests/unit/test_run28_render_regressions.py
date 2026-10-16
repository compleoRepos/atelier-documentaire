"""RUN28 render regressions F37/F38/F38b (synthetic rasters and invented texts
only; no document of the private corpus is used).

- F37: before refusing a scanned line (LAYOUT_OVERFLOW), the condensed variant
  of the same family is tried on the same validated frames with the same size
  floor; a text that fits in the regular font never uses it.
- F38: a slightly skewed scanned table rule (spread over several pixel rows)
  is recognised and kept out of the paper cover; a dense text row is not a rule.
- F38b: a cover whose sampling ring lies on table rules is filled with the
  paper colour, not with the rules' grey; a correct ring estimate is unchanged.
"""

from __future__ import annotations

import io

import fitz
import numpy as np
import pytest
from PIL import Image

from app.documents import pdf_fidelity as pf
from app.documents.pdf_fidelity import _plan_scan_block

CONDENSED_INSTALLED = pf._condensed_available({})
needs_condensed = pytest.mark.skipif(
    not CONDENSED_INSTALLED, reason="DejaVu Sans Condensed (fonts-dejavu-extra) not installed"
)


def _scan_doc(arr: np.ndarray) -> fitz.Document:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=arr.shape[1], height=arr.shape[0])
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc


# ---------------------------------------------------------------- F37 ------


def _line_block(block_id: str = "p001-b0100") -> dict:
    box = [60.0, 200.0, 200.0, 210.0]
    text = "Invented source line for a narrow form cell"
    return {
        "id": block_id,
        "page": 1,
        "text": text,
        "bbox": box,
        "confidence": 0.93,
        "role": "line",
        "line_count": 1,
        "line_heights": [10.0],
        "line_pitch": None,
        "source_lines": [{"id": f"{block_id}-l0", "text": text, "bbox": box, "confidence": 0.93}],
        "style": {"align": "left", "bold": False, "color": None, "highlight": False},
    }


OBSTACLES = [
    {"id": "below", "text": "Signature", "bbox": [60, 212, 300, 222], "source_lines": None},
    {"id": "right", "text": "Code", "bbox": [204, 199, 320, 211], "source_lines": None},
]


def _plan(target: str):
    buffer = io.BytesIO()
    Image.new("RGB", (595, 842), (250, 250, 248)).save(buffer, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    block = _line_block()
    return _plan_scan_block(
        block=block,
        target=target,
        page=doc[0],
        page_number=1,
        ir_blocks=[block, *OBSTACLES],
        protected_regions=[],
        body_size=9.0,
        body_right=532.0,
        source_bytes=doc.tobytes(),
        bound=None,
    )


def _target(n: int) -> str:
    """Invented French text of about ``2 * n`` characters (fine-grained)."""
    return ("mot clé " * 80)[: 2 * n].rstrip()


def test_f37_font_kwargs_select_the_condensed_variant_of_the_same_style():
    regular = pf._font_kwargs(8.0, {"bold": True}, 0)
    condensed = pf._font_kwargs(8.0, {"bold": True, "condensed": True}, 0)
    assert regular["fontname"] == "DejaVuSans-Bold"
    assert condensed["fontname"] == "DejaVuSansCondensed-Bold"
    assert condensed["fontsize"] == regular["fontsize"]  # same size, narrower glyphs


@needs_condensed
def test_f37_condensed_font_is_the_last_resort_before_overflow(monkeypatch):
    # Find the first length at which the regular font overflows.
    with monkeypatch.context() as m:
        m.setattr(pf, "_condensed_available", lambda style: False)
        first_overflow = None
        for n in range(4, 300):
            item, _issues, overflow = _plan(_target(n))
            if overflow:
                first_overflow = n
                break
        assert first_overflow is not None and first_overflow > 1
        # counter-proof: without the condensed variant the line is refused
        item, issues, overflow = _plan(_target(first_overflow))
        assert item is None and overflow
        assert any(i["code"] == "LAYOUT_OVERFLOW" for i in issues)

    # With the condensed variant: rendered, same floor, explicitly reported.
    item, issues, overflow = _plan(_target(first_overflow))
    assert item is not None and not overflow
    assert item["style"].get("condensed") is True
    base, _i, _o = _plan(_target(4))  # a short text keeps the measured size
    assert item["size"] >= base["size"] * pf._SCAN_MIN_FONT_RATIO - 1e-6
    assert any(i["code"] == "SCAN_CONDENSED_FONT" for i in issues)
    assert not any(i["code"] == "LAYOUT_OVERFLOW" for i in issues)

    # Non-regression: a text that fits in the regular font never uses it.
    item, issues, overflow = _plan(_target(first_overflow - 1))
    assert item is not None and not overflow
    assert not item["style"].get("condensed")
    assert not any(i["code"] == "SCAN_CONDENSED_FONT" for i in issues)


@needs_condensed
def test_f37_condensed_font_never_hides_a_real_overflow():
    item, issues, overflow = _plan(_target(299))
    assert item is None and overflow
    assert any(i["code"] == "LAYOUT_OVERFLOW" for i in issues)


# ---------------------------------------------------------------- F38 ------

COVER = [50.0, 99.5, 250.0, 112.0]


def _skewed_rule_raster(text_rows: bool = True) -> np.ndarray:
    """A scanned rule rising 2 px over its length (0.3 deg), then text stems."""
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    for x in range(40, 261):
        y = 100 + int(round(2 * (x - 40) / 220))
        arr[y, x] = 0
    if text_rows:
        for x in range(56, 246, 3):
            arr[105:111, x : x + 1] = 0
    return arr


def test_f38_skewed_rule_is_kept_out_of_the_cover():
    doc = _scan_doc(_skewed_rule_raster())
    clipped = pf._clip_cover_off_rules(doc[0], COVER)
    assert clipped is not None
    assert clipped[1] >= 102.0  # below every row of the rule
    assert clipped[1] <= 105.0  # never into the line's own glyphs
    assert clipped[0] == COVER[0] and clipped[2] == COVER[2] and clipped[3] == COVER[3]


def test_f38_counter_proof_single_row_test_misses_the_skewed_rule(monkeypatch):
    monkeypatch.setattr(pf, "_RULE_SKEW_ROWS", 0)
    doc = _scan_doc(_skewed_rule_raster())
    assert pf._clip_cover_off_rules(doc[0], COVER) is None


def test_f38_straight_rule_is_clipped_exactly_as_before():
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    arr[100, 40:261] = 0
    for x in range(56, 246, 3):
        arr[105:111, x : x + 1] = 0
    doc = _scan_doc(arr)
    clipped = pf._clip_cover_off_rules(doc[0], COVER)
    assert clipped is not None and 100.5 <= clipped[1] <= 102.0


def test_f38_dense_text_row_is_not_a_rule():
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    for x in range(42, 258, 2):  # dense stems with one-pixel gaps
        arr[99:111, x : x + 1] = 0
    doc = _scan_doc(arr)
    assert pf._clip_cover_off_rules(doc[0], COVER) is None


# --------------------------------------------------------------- F38b ------

BOX = [50.0, 100.5, 250.0, 111.5]


def _ruled_cell(paper=(255, 255, 255)) -> np.ndarray:
    arr = np.full((200, 300, 3), paper, dtype=np.uint8)
    arr[96:101, 30:271] = 0  # rule above the clipped cover (ring lies on it)
    arr[112:117, 30:271] = 0  # rule below
    for x in range(60, 240, 4):
        arr[103:110, x : x + 1] = 0
    return arr


def test_f38b_ring_on_rules_gives_the_paper_colour_not_grey():
    doc = _scan_doc(_ruled_cell())
    colour = pf._paper_color(doc[0], BOX)
    assert min(colour) >= 0.95


def test_f38b_counter_proof_ring_only_estimate_is_grey(monkeypatch):
    monkeypatch.setattr(pf, "_PAPER_RING_TOLERANCE", 1e9)
    doc = _scan_doc(_ruled_cell())
    assert min(pf._paper_color(doc[0], BOX)) < 0.8


def test_f38b_correct_ring_estimate_is_unchanged_on_tinted_paper(monkeypatch):
    arr = np.full((200, 300, 3), (238, 232, 214), dtype=np.uint8)
    for x in range(60, 240, 4):
        arr[103:110, x : x + 1] = 0
    doc = _scan_doc(arr)
    colour = pf._paper_color(doc[0], BOX)
    monkeypatch.setattr(pf, "_PAPER_RING_TOLERANCE", 1e9)
    legacy = pf._paper_color(doc[0], BOX)
    assert colour == legacy
    assert abs(colour[0] - 238 / 255) < 0.01 and abs(colour[2] - 214 / 255) < 0.01


# --- F40 -----------------------------------------------------------------------
# Invisible bidi controls (LRM/RLM, ALM, embeddings, isolates) are typography: a
# target that only drops such a mark is the source returned unchanged and must
# never be re-typeset over the original pixels (synthetic strings only).


def test_f40_bidi_marks_are_typography():
    from app.ai.translation.typography import typography_equivalent

    assert typography_equivalent("Qx", "Qx\u200f")
    assert typography_equivalent("\u202bQx Zv\u202c", "Qx Zv")
    assert typography_equivalent("\u2067Ab 7\u2069", "\u200eAb 7")
    assert typography_equivalent("\u061cAb", "Ab")


def test_f40_words_and_digits_are_never_neutralised():
    from app.ai.translation.typography import typography_equivalent

    assert not typography_equivalent("Qx", "Qy\u200f")
    assert not typography_equivalent("Ab 12", "Ab 13\u200e")
    assert not typography_equivalent("Ab 12", "\u200fAb 1 2")


def test_f40_pipeline_normaliser_restores_exact_source_and_reports_it():
    from app.documents.pipeline import _normalise_typography_only

    blocks = {"b1": "Qx\u200f", "b2": "Zorvat plen", "b3": "Ab 12\u200e", "b4": "   "}
    translations = {"b1": "Qx", "b2": "Texte traduit", "b3": "Ab 13", "b4": "x"}
    issues = _normalise_typography_only(blocks, translations)
    assert translations == {"b1": "Qx\u200f", "b2": "Texte traduit", "b3": "Ab 13", "b4": "x"}
    assert [(i["code"], i["block_id"], i["severity"]) for i in issues] == [
        ("TYPOGRAPHY_ONLY_TARGET_NORMALISED", "b1", "info")
    ]


def test_f40_bidi_only_change_is_not_counted_as_translated():
    from app.documents.block_status import classify_blocks

    ir = {
        "language": "ara",
        "languages": ["ara"],
        "pages": [{"number": 1, "blocks": [{"id": "b1", "text": "Qx\u200f", "language": "ara"}]}],
    }
    status = classify_blocks(ir, {"b1": "Qx"}, [])
    assert status["blocks"]["b1"]["status"] != "TRANSLATED"


def test_f40_translate_document_keeps_source_whatever_the_engine(tmp_path, monkeypatch):
    """End to end on a synthetic native PDF: an engine (or a translation memory)
    returning the source without its bidi mark must not produce a re-typeset
    'translation'; the exact source is kept and the normalisation is reported."""
    import asyncio

    from app.ai.translation import service
    from app.documents.pipeline import analyze_document, translate_document

    source = tmp_path / "source.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=200)
        page.insert_text((40, 80), "Qx", fontsize=12)
        doc.save(str(source))
    work = tmp_path / "work"
    ir = analyze_document(str(source), str(work), {})
    block = ir["pages"][0]["blocks"][0]
    block["text"] = block["text"] + "\u200f"
    block["language"] = "ara"

    def fake_translate_blocks(ir_, options):
        return {"translations": {block["id"]: block["text"].replace("\u200f", "")}, "issues": []}

    monkeypatch.setattr(service, "translate_blocks", fake_translate_blocks)
    tr = asyncio.run(translate_document(ir, str(work), {"engine": "offline"}))
    assert tr["translations"][block["id"]] == block["text"]
    assert any(
        i["code"] == "TYPOGRAPHY_ONLY_TARGET_NORMALISED" and i.get("block_id") == block["id"]
        for i in tr["issues"]
    )
    assert tr["block_status"]["blocks"][block["id"]]["status"] != "TRANSLATED"
