"""Evidence-based visual regression scoring.

The scorer never treats a raw pixel difference as a quality score.  It combines
page integrity, geometry, structure and protected-region evidence, while
allowing text replacement masks only when their finite area is bounded.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _mean(values: list[float]) -> float | None:
    return _clamp(sum(values) / len(values)) if values else None


def _metric_value(item: Any, names: tuple[str, ...]) -> float | None:
    if isinstance(item, (int, float)):
        return _number(item)
    if isinstance(item, dict):
        for name in names:
            result = _number(item.get(name))
            if result is not None:
                return _clamp(result)
    return None


def _source_pages(ir: dict[str, Any], render: dict[str, Any]) -> list[dict[str, Any]]:
    pages = ir.get("pages")
    if isinstance(pages, list):
        return [p for p in pages if isinstance(p, dict)]
    pages = render.get("source_pages", render.get("original_pages", []))
    return [p for p in pages if isinstance(p, dict)] if isinstance(pages, list) else []


def _candidate_pages(render: dict[str, Any]) -> list[dict[str, Any]]:
    pages = render.get("translated_pages", render.get("candidate_pages", []))
    return [p for p in pages if isinstance(p, dict)] if isinstance(pages, list) else []


def _bbox_area(bbox: Any) -> float | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    nums = [_number(x) for x in bbox]
    if any(x is None for x in nums):
        return None
    x0, y0, x1, y1 = nums  # type: ignore[misc]
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _page_area(page: dict[str, Any]) -> float | None:
    width = _number(page.get("width"))
    height = _number(page.get("height"))
    if width and height and width > 0 and height > 0:
        return width * height
    return _bbox_area(page.get("bbox"))


def _validate_masks(
    ir: dict[str, Any], render: dict[str, Any], limit: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float | None]:
    masks = render.get("text_masks", render.get("masks", []))
    if masks is None:
        return [], [], None
    if not isinstance(masks, list):
        return [], [{"code": "VISUAL_MASKS_INVALID", "severity": "critical"}], None
    issues: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    # F32 (run27): coverage = area of the UNION of the page masks (overlapping
    # masks used to be summed, double counting the same pixels).
    from app.documents.geometry import union_area

    page_boxes: dict[int, list[Any]] = {}
    for index, mask in enumerate(masks):
        if not isinstance(mask, dict) or _bbox_area(mask.get("bbox")) is None:
            issues.append({"code": "VISUAL_MASK_INVALID", "severity": "critical", "index": index})
            continue
        page = int(mask.get("page", 1))
        page_boxes.setdefault(page, []).append(mask["bbox"])
        valid.append(mask)
    page_areas = {page: union_area(boxes) for page, boxes in page_boxes.items()}
    total = sum(page_areas.values())
    for page, area in page_areas.items():
        dimensions = next(
            (p for p in _source_pages(ir, render) if int(p.get("number", 1)) == page), None
        )
        page_area = _page_area(dimensions or {}) if dimensions else None
        if page_area and area / page_area > limit:
            issues.append(
                {
                    "code": "VISUAL_MASK_TOO_LARGE",
                    "severity": "critical",
                    "page": page,
                    "coverage": area / page_area,
                    "limit": limit,
                }
            )
    return valid, issues, (total if valid else 0.0)


def _image_similarity(
    render: dict[str, Any], masks: list[dict[str, Any]]
) -> tuple[float | None, list[dict[str, Any]], dict[str, Any]]:
    """Compare previews outside finite text masks, when paths are supplied."""
    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError:
        return None, [{"code": "VISUAL_IMAGE_DEPENDENCY_MISSING", "severity": "warning"}], {}
    source = render.get("source_previews", render.get("original_previews", []))
    target = render.get("translated_previews", render.get("candidate_previews", []))
    if (
        not isinstance(source, list)
        or not isinstance(target, list)
        or not source
        or len(source) != len(target)
    ):
        return None, [], {"available": False}
    scores: list[float] = []
    issues: list[dict[str, Any]] = []
    for page_number, (source_path, target_path) in enumerate(zip(source, target, strict=True), 1):
        try:
            original = Image.open(Path(str(source_path))).convert("RGB")
            candidate = Image.open(Path(str(target_path))).convert("RGB")
            if candidate.size != original.size:
                candidate = candidate.resize(original.size)
                issues.append(
                    {"code": "VISUAL_PAGE_RESIZED", "severity": "warning", "page": page_number}
                )
            diff = ImageChops.difference(original, candidate).convert("L")
            mask = Image.new("L", original.size, 0)
            from PIL import ImageDraw

            draw = ImageDraw.Draw(mask)
            for item in masks:
                if int(item.get("page", 1)) != page_number:
                    continue
                bbox = item.get("bbox")
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    scale_x = original.width / max(
                        1.0, float(render.get("page_width", original.width))
                    )
                    scale_y = original.height / max(
                        1.0, float(render.get("page_height", original.height))
                    )
                    draw.rectangle(
                        tuple(
                            float(x) * (scale_x if i % 2 == 0 else scale_y)
                            for i, x in enumerate(bbox)
                        ),
                        fill=255,
                    )
            # A mask is an exclusion region, not a way to make the page pass.
            inverted = ImageChops.invert(mask)
            stats = ImageStat.Stat(diff, mask=inverted)
            mean_error = (sum(stats.mean) / len(stats.mean)) / 255.0
            scores.append(_clamp(1.0 - mean_error))
            extrema = diff.getextrema()
            if extrema and extrema[1] == 0:
                scores[-1] = 1.0
        except (OSError, ValueError, TypeError) as exc:
            issues.append(
                {
                    "code": "VISUAL_PREVIEW_UNREADABLE",
                    "severity": "error",
                    "page": page_number,
                    "message": str(exc),
                }
            )
    return (
        _mean(scores),
        issues,
        {
            "available": bool(scores),
            "pages_compared": len(scores),
            "masked_text_excluded": bool(masks),
        },
    )


def _page_integrity(
    ir: dict[str, Any], render: dict[str, Any]
) -> tuple[float | None, list[dict[str, Any]], dict[str, Any]]:
    source = _source_pages(ir, render)
    target = _candidate_pages(render)
    source_count = render.get("source_page_count", len(source) or None)
    target_count = render.get(
        "translated_page_count", render.get("candidate_page_count", len(target) or None)
    )
    if source_count is None or target_count is None:
        return (
            None,
            [{"code": "VISUAL_PAGE_COVERAGE_MISSING", "severity": "warning"}],
            {"pages": None},
        )
    source_count, target_count = int(source_count), int(target_count)
    if source_count <= 0:
        return None, [{"code": "VISUAL_SOURCE_HAS_NO_PAGES", "severity": "critical"}], {"pages": 0}
    issues: list[dict[str, Any]] = []
    score = (
        1.0
        if source_count == target_count
        else _clamp(1.0 - abs(source_count - target_count) / source_count)
    )
    if source_count != target_count:
        issues.append(
            {
                "code": "VISUAL_PAGE_COUNT_CHANGED",
                "severity": "critical",
                "source": source_count,
                "target": target_count,
            }
        )
    blank_pages = render.get("blank_pages", [])
    if blank_pages:
        issues.append(
            {"code": "VISUAL_BLANK_PAGE", "severity": "critical", "pages": list(blank_pages)}
        )
        score = min(score, 0.0)
    disappeared = render.get("disappeared_regions", render.get("missing_regions", []))
    if disappeared:
        issues.append(
            {"code": "VISUAL_REGION_DISAPPEARED", "severity": "critical", "regions": disappeared}
        )
        score = min(score, 0.0)
    return score, issues, {"source_pages": source_count, "candidate_pages": target_count}


def _protected_integrity(
    render: dict[str, Any],
) -> tuple[float | None, list[dict[str, Any]], dict[str, Any]]:
    results = render.get("protected_region_results", render.get("protected_regions_checked"))
    if results is None:
        return (
            None,
            [{"code": "PROTECTED_REGION_COVERAGE_MISSING", "severity": "warning"}],
            {"checked": 0},
        )
    if not isinstance(results, list) or not results:
        return (
            None,
            [{"code": "PROTECTED_REGION_COVERAGE_MISSING", "severity": "warning"}],
            {"checked": 0},
        )
    failures = [
        item for item in results if isinstance(item, dict) and item.get("preserved") is not True
    ]
    issues = [
        {"code": "PROTECTED_REGION_CHANGED", "severity": "critical", "region": item}
        for item in failures
    ]
    return (0.0 if failures else 1.0), issues, {"checked": len(results), "failed": len(failures)}


def _structure_score(
    render: dict[str, Any],
) -> tuple[float | None, list[dict[str, Any]], dict[str, Any]]:
    metrics = render.get("structure_metrics", render.get("structure"))
    if not isinstance(metrics, dict):
        return None, [{"code": "VISUAL_STRUCTURE_COVERAGE_MISSING", "severity": "warning"}], {}
    values: list[float] = []
    issues: list[dict[str, Any]] = []
    for key in ("tables", "merges", "reading_order", "cells", "images", "signatures", "stamps"):
        if key not in metrics:
            continue
        raw = metrics[key]
        value = _metric_value(raw, ("score", "preserved", "similarity", "match"))
        if value is not None:
            values.append(value)
            if value < 1.0:
                issues.append(
                    {
                        "code": "VISUAL_STRUCTURE_CHANGED",
                        "severity": "error",
                        "component": key,
                        "score": value,
                    }
                )
    return _mean(values), issues, {"components": len(values)}


def _geometry_score(
    render: dict[str, Any],
    minimum: float = 0.9,
) -> tuple[float | None, list[dict[str, Any]], dict[str, Any]]:
    metrics = render.get("geometry_metrics", render.get("geometry"))
    if not isinstance(metrics, dict):
        return None, [{"code": "VISUAL_GEOMETRY_COVERAGE_MISSING", "severity": "warning"}], {}
    values: list[float] = []
    keys = (
        (
            "blocks",
            "frame_overlap",
            "anchor_stability",
            "font_size_reduction",
            "clipping",
            "dimensions",
        )
        if metrics.get("translation_aware")
        else ("blocks", "bbox_iou", "displacement", "overlap", "clipping", "dimensions")
    )
    for key in keys:
        if key not in metrics:
            continue
        value = _metric_value(metrics[key], ("score", "similarity", "preserved", "iou"))
        if value is not None:
            values.append(value)
    score = _mean(values)
    issues = (
        []
        if score is None or score >= minimum
        else [{"code": "VISUAL_GEOMETRY_REGRESSION", "severity": "error", "score": score}]
    )
    return score, issues, {"components": len(values)}


def score_visual(
    ir: dict[str, Any],
    render_result: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a bounded visual score plus method, provenance and coverage."""
    render = render_result or {}
    options = options or {}
    mask_limit = (
        _number(options.get("max_text_mask_fraction", render.get("max_text_mask_fraction", 0.35)))
        or 0.35
    )
    masks, mask_issues, _ = _validate_masks(ir, render, mask_limit)
    components: dict[str, float | None] = {}
    issues: list[dict[str, Any]] = list(mask_issues)
    page_score, page_issues, page_coverage = _page_integrity(ir, render)
    components["page_integrity"] = page_score
    issues.extend(page_issues)
    protected_score, protected_issues, protected_coverage = _protected_integrity(render)
    components["protected_regions"] = protected_score
    issues.extend(protected_issues)
    geometry_minimum = (options.get("quality_thresholds") or {}).get("layout_score", 0.9)
    geometry_score, geometry_issues, geometry_coverage = _geometry_score(render, geometry_minimum)
    components["geometry"] = geometry_score
    issues.extend(geometry_issues)
    structure_score, structure_issues, structure_coverage = _structure_score(render)
    components["structure"] = structure_score
    issues.extend(structure_issues)
    image_score, image_issues, image_coverage = _image_similarity(render, masks)
    components["masked_preview_similarity"] = image_score
    issues.extend(image_issues)
    available = [value for value in components.values() if value is not None]
    score = (
        _mean(available)
        if available and not any(issue.get("severity") == "critical" for issue in issues)
        else (
            0.0
            if any(issue.get("severity") == "critical" for issue in issues) and available
            else None
        )
    )
    coverage = {
        "components_available": len(available),
        "components_required": len(components),
        "component_names": [key for key, value in components.items() if value is not None],
        "pages": page_coverage,
        "protected_regions": protected_coverage,
        "geometry": geometry_coverage,
        "structure": structure_coverage,
        "previews": image_coverage,
        "text_masks_bounded": not any(
            issue.get("code") == "VISUAL_MASK_TOO_LARGE" for issue in issues
        ),
    }
    return {
        "score": score,
        "components": components,
        "issues": issues,
        "provenance": {
            "method": "page_integrity+protected_regions+geometry+structure+masked_preview_similarity",
            "preview_comparison": image_score is not None,
            "text_replacement_masks_are_excluded_only_in_bounded_regions": True,
            "source": render.get("provenance", "render_result"),
        },
        "coverage": coverage,
    }


class VisualScorer:
    """Small extensible adapter for callers that prefer an object interface."""

    def __init__(self, options: dict[str, Any] | None = None) -> None:
        self.options = options or {}

    def score(
        self, ir: dict[str, Any], render_result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return score_visual(ir, render_result, self.options)


__all__ = ["VisualScorer", "score_visual"]
