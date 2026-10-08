from pathlib import Path

from PIL import Image, ImageDraw

from app.ai.vision.scorer import score_visual


def render(**extra):
    value = {
        "source_page_count": 1,
        "translated_page_count": 1,
        "geometry_metrics": {"blocks": 1.0, "clipping": 1.0},
        "structure_metrics": {"tables": 1.0, "merges": 1.0, "reading_order": 1.0},
        "protected_region_results": [{"id": "signature", "preserved": True}],
    }
    value.update(extra)
    return value


def test_visual_score_uses_page_geometry_structure_and_protected_evidence():
    result = score_visual({"pages": [{"number": 1, "width": 100, "height": 100}]}, render())
    assert result["score"] == 1.0
    assert result["coverage"]["components_available"] >= 4
    assert result["provenance"]["preview_comparison"] is False


def test_missing_page_is_critical_and_not_hidden_by_other_metrics():
    result = score_visual(
        {"pages": [{"number": 1}, {"number": 2}]},
        render(source_page_count=2, translated_page_count=1),
    )
    assert result["score"] == 0.0
    assert any(issue["code"] == "VISUAL_PAGE_COUNT_CHANGED" for issue in result["issues"])


def test_protected_region_change_is_critical():
    result = score_visual(
        {"pages": [{"number": 1}]},
        render(protected_region_results=[{"id": "stamp", "preserved": False}]),
    )
    assert result["score"] == 0.0
    assert any(issue["code"] == "PROTECTED_REGION_CHANGED" for issue in result["issues"])


def test_masking_an_entire_page_is_rejected():
    result = score_visual(
        {"pages": [{"number": 1, "width": 100, "height": 100}]},
        render(text_masks=[{"page": 1, "bbox": [0, 0, 100, 100]}]),
    )
    assert any(issue["code"] == "VISUAL_MASK_TOO_LARGE" for issue in result["issues"])
    assert result["coverage"]["text_masks_bounded"] is False


def test_preview_comparison_is_real_and_masks_only_text_region(tmp_path: Path):
    source = tmp_path / "source.png"
    target = tmp_path / "target.png"
    original = Image.new("RGB", (100, 100), "white")
    candidate = original.copy()
    draw = ImageDraw.Draw(original)
    draw.rectangle((10, 10, 20, 20), fill="black")
    original.save(source)
    candidate.save(target)
    result = score_visual(
        {"pages": [{"number": 1, "width": 100, "height": 100}]},
        render(
            source_previews=[str(source)],
            translated_previews=[str(target)],
            text_masks=[{"page": 1, "bbox": [10, 10, 20, 20]}],
        ),
    )
    assert result["coverage"]["previews"]["available"] is True
    assert result["components"]["masked_preview_similarity"] == 1.0
