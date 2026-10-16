"""Measured fidelity summary; unavailable/uncalibrated components never pass."""

from __future__ import annotations

import json
from pathlib import Path


def fidelity_scores(render, evaluation):
    metrics = render.get("structure_metrics") or {}
    values = [
        item["score"]
        for item in metrics.values()
        if isinstance(item, dict) and item.get("measured") and item.get("score") is not None
    ]
    structure = min(values) if values else None
    table = metrics.get("tables", {}).get("score")
    text = (render.get("geometry_metrics") or {}).get("blocks")
    entity = (evaluation.get("quality_contract") or {}).get("entity_score")
    visual = evaluation.get("visual_score")
    if isinstance(visual, dict):
        visual = visual.get("score")
    scores = {
        "STRUCTURE_SCORE": structure,
        "LAYOUT_SCORE": render.get("layout_score"),
        "TEXT_SCORE": text,
        "ENTITY_SCORE": entity,
        "TABLE_SCORE": table,
        "VISUAL_SCORE": visual,
        "GLOBAL_SCORE": None,
    }
    return {
        "scores": scores,
        "status": "REVIEW_REQUIRED",
        "global_score_reason": "Human linguistic/style validation and calibrated thresholds required",
        "score_scope": "Technical evidence, not bank acceptance or translation correctness",
        "measured": {key: value is not None for key, value in scores.items()},
    }


def write_visual_artifacts(work, render, evaluation):
    """Private artifacts only: actual renders/diffs and proof JSON."""
    from PIL import Image, ImageChops

    work = Path(work)
    originals = render.get("source_previews") or render.get("source_preview_paths") or []
    candidates = render.get("candidate_previews") or render.get("candidate_preview_paths") or []
    artifact_dir = work / "fidelity-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    for index, (source, candidate) in enumerate(zip(originals, candidates, strict=False), 1):
        page_dir = artifact_dir / f"page-{index:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            before = image.convert("RGB")
        with Image.open(candidate) as image:
            after = image.convert("RGB")
        before.save(page_dir / "original.png")
        after.save(page_dir / "translated.png")
        if before.size == after.size:
            ImageChops.difference(before, after).save(page_dir / "diff.png")
        else:
            canvas = Image.new(
                "RGB", (max(before.width, after.width), max(before.height, after.height)), "black"
            )
            target = canvas.copy()
            canvas.paste(before)
            target.paste(after)
            ImageChops.difference(canvas, target).save(page_dir / "diff.png")
        pages.append(
            {
                "page": index,
                "original": str(page_dir / "original.png"),
                "translated": str(page_dir / "translated.png"),
                "diff": str(page_dir / "diff.png"),
                "dimensions_equal": before.size == after.size,
            }
        )
    summary = fidelity_scores(render, evaluation)
    summary.update(
        {
            "pages": pages,
            "source_page_count": render.get("source_page_count"),
            "candidate_page_count": render.get("candidate_page_count"),
            "renderer_version": render.get("renderer_version"),
            "issues": evaluation.get("issues", []),
        }
    )
    (artifact_dir / "metrics.json").write_text(
        json.dumps(render, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (artifact_dir / "result.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
