"""Original-only visual protection. Candidates never assert identity/authenticity."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path


def _intersects(a, b):
    return bool(a and b and a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1])


def normalize_regions(regions, pages, source_id):
    """Fail closed on invalid annotations rather than silently dropping them."""
    dimensions = {int(p["number"]): (float(p["width"]), float(p["height"])) for p in pages}
    out = []
    for index, item in enumerate(regions or []):
        page = int(item.get("page", 1))
        box = list(map(float, item.get("bbox", [])))
        if page not in dimensions or len(box) != 4 or not all(math.isfinite(x) for x in box):
            raise ValueError("Invalid protected visual page/bbox")
        width, height = dimensions[page]
        if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
            raise ValueError("Protected visual bbox outside original coordinates")
        out.append(
            {
                **item,
                "id": item.get("id", f"protected-{index:04d}"),
                "type": "protected_visual",
                "page": page,
                "bbox": box,
                "source_id": item.get("source_id") or source_id,
                "editable": False,
                "subtype": item.get("subtype", "graphic_candidate"),
                "provenance": item.get("provenance", "user_annotation_unvalidated"),
                "authenticity_verified": False,
                "coordinates_kind": "original",
            }
        )
    return out


def is_table_geometry(drawing, tables):
    """Only axis-aligned edges or exact cell/table rectangles may be table art."""
    boxes = [cell.get("bbox") for t in tables for cell in t.get("cells", [])] + [
        t.get("bbox") for t in tables
    ]
    boxes = [b for b in boxes if b]
    items = drawing.get("items", [])
    if not items or float(drawing.get("width") or 0) > 3:
        return False
    for item in items:
        if item[0] == "re":
            rect = list(item[1])
            if not any(
                all(abs(x - y) <= 2 for x, y in zip(rect, box, strict=True)) for box in boxes
            ):
                return False
        elif item[0] == "l":
            a, b = item[1], item[2]
            if abs(a.y - b.y) <= 0.5:
                if not any(
                    (abs(a.y - box[1]) <= 2 or abs(a.y - box[3]) <= 2)
                    and min(a.x, b.x) >= box[0] - 2
                    and max(a.x, b.x) <= box[2] + 2
                    for box in boxes
                ):
                    return False
            elif abs(a.x - b.x) <= 0.5:
                if not any(
                    (abs(a.x - box[0]) <= 2 or abs(a.x - box[2]) <= 2)
                    and min(a.y, b.y) >= box[1] - 2
                    and max(a.y, b.y) <= box[3] + 2
                    for box in boxes
                ):
                    return False
            else:
                return False
        else:
            return False
    return True


def detect_pdf_visuals(source, pages, tables):
    """Protect embedded non-background images, widgets and non-table vectors.

    A full-page raster is not falsely labelled a signature. Scans require user
    annotation for embedded signatures; that coverage gap is explicit.
    """
    import fitz

    source_id = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    regions = []
    warnings = []
    measured_pages = []
    with fitz.open(str(source)) as document:
        for number, page in enumerate(document, 1):
            measured_pages.append(
                {
                    "number": number,
                    "width": float(page.rect.width),
                    "height": float(page.rect.height),
                }
            )
            if not any(t.get("page") == number for t in tables):
                from .layout import detect_layout

                tables = list(tables) + detect_layout(
                    page=page,
                    blocks=[],
                    page_number=number,
                    width=page.rect.width,
                    height=page.rect.height,
                ).get("tables", [])
            area = page.rect.width * page.rect.height
            table_boxes = [t.get("bbox") for t in tables if t.get("page") == number]
            scanned = next(
                (p.get("scanned", False) for p in pages if p.get("number") == number), False
            )
            for index, image in enumerate(page.get_image_info(hashes=True, xrefs=True)):
                bbox = list(image["bbox"])
                image_area = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
                if scanned and image_area >= area * 0.8:
                    warnings.append(
                        {
                            "code": "RASTER_GRAPHIC_ANNOTATION_REQUIRED",
                            "severity": "warning",
                            "page": number,
                        }
                    )
                    continue
                regions.append(
                    {
                        "id": f"p{number:03d}-image-{index:03d}",
                        "page": number,
                        "bbox": bbox,
                        "subtype": "image_candidate",
                        "provenance": "pdf_embedded_image_original",
                        "source_id": f"{source_id}:image:{image.get('xref', index)}",
                    }
                )
            for index, widget in enumerate(page.widgets() or []):
                regions.append(
                    {
                        "id": f"p{number:03d}-widget-{index:03d}",
                        "page": number,
                        "bbox": list(widget.rect),
                        "subtype": "form_widget_candidate",
                        "provenance": "pdf_widget_original",
                    }
                )
            for index, drawing in enumerate(page.get_drawings()):
                bbox = list(drawing["rect"])
                if bbox[2] - bbox[0] <= 1 or bbox[3] - bbox[1] <= 1:
                    continue
                # Ruled table geometry is retained by the renderer, not used to
                # block translation of all cells. Other graphic identity is unknown.
                page_tables = [t for t in tables if t.get("page") == number]
                if any(_intersects(bbox, box) for box in table_boxes) and is_table_geometry(
                    drawing, page_tables
                ):
                    continue
                regions.append(
                    {
                        "id": f"p{number:03d}-vector-{index:03d}",
                        "page": number,
                        "bbox": bbox,
                        "subtype": "vector_graphic_candidate",
                        "provenance": "pdf_vector_original",
                    }
                )
    visible = []
    dimensions = {p["number"]: (p["width"], p["height"]) for p in measured_pages}
    for region in regions:
        width, height = dimensions[region["page"]]
        raw = region["bbox"]
        clipped = [max(0.0, raw[0]), max(0.0, raw[1]), min(width, raw[2]), min(height, raw[3])]
        if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
            continue
        if clipped != raw:
            region = {
                **region,
                "source_object_bbox": raw,
                "bbox": clipped,
                "clip_provenance": "original_visible_page_intersection",
            }
            warnings.append(
                {
                    "code": "PROTECTED_VISUAL_CLIPPED_TO_PAGE",
                    "severity": "warning",
                    "page": region["page"],
                }
            )
        visible.append(region)
    return normalize_regions(visible, measured_pages, source_id), warnings


def protect_ir(ir, annotations=None):
    """Compatible augmentation, always based on original source coordinates."""
    source = Path(ir["source_path"])
    source_id = hashlib.sha256(source.read_bytes()).hexdigest()
    if ir.get("format") == "pdf":
        detected, warnings = detect_pdf_visuals(source, ir["pages"], ir.get("tables", []))
    else:
        detected, warnings = [], []
    existing = list(ir.get("protected_visual_regions") or [])
    normalized = normalize_regions(
        existing + detected + list(annotations or []), ir["pages"], source_id
    )
    seen = set()
    regions = []
    for region in normalized:
        key = (region["page"], tuple(region["bbox"]), region["source_id"])
        if key not in seen:
            seen.add(key)
            regions.append(region)
    ir["protected_visual_regions"] = regions
    ir.setdefault("versions", {})["source_sha256"] = source_id
    ir.setdefault("warnings", []).extend(warnings)
    for page in ir["pages"]:
        for block in page.get("blocks", []):
            if any(
                region["page"] == page["number"] and _intersects(block.get("bbox"), region["bbox"])
                for region in regions
            ):
                block["protected"] = True
    return ir
