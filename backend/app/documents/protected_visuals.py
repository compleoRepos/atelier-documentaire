"""Original-only visual protection. Candidates never assert identity/authenticity."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path


def _intersects(a, b):
    return bool(a and b and a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1])


def _area(box):
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1]) if box else 0.0


def _inter_area(a, b):
    if not _intersects(a, b):
        return 0.0
    return (min(a[2], b[2]) - max(a[0], b[0])) * (min(a[3], b[3]) - max(a[1], b[1]))


def is_user_region(region):
    """Human annotations stay strict: any contact protects the block."""
    provenance = str(region.get("provenance") or "")
    return provenance.startswith(("user", "human")) or bool(region.get("annotation"))


def carves_only(region):
    """Automatic check-box glyphs never protect their whole block: the text
    beside the box stays translatable, the renderer keeps the box pixels out
    of masks and text frames (run18: yes/no option labels of a form)."""
    return str(region.get("subtype")) == "checkbox_glyph" and not is_user_region(region)


def significant_overlap(block_box, region_box):
    """Overlap large enough to make the block part of the protected visual.

    Measured failure mode: a stamp touching the corner of a paragraph, or a
    form frame enclosing labels, protected whole text blocks. A block is now
    protected by an AUTOMATIC candidate only if the overlap covers 30 % of the
    block or half of the candidate; smaller contacts are recorded as
    ``near_protected_regions`` and avoided by the renderer instead.
    """
    inter = _inter_area(block_box, region_box)
    if inter <= 0:
        return False
    return inter >= 0.3 * max(_area(block_box), 1e-6) or inter >= 0.5 * max(_area(region_box), 1e-6)


_WORD4 = None


def _readable_line(block):
    import re

    global _WORD4
    if _WORD4 is None:
        _WORD4 = re.compile(r"[^\W\d_]{4,}", re.UNICODE)
    return float(block.get("confidence") or 0.0) >= 0.6 and bool(
        _WORD4.search(str(block.get("text") or ""))
    )


def _candidate_pixels(ir, page_number, box):
    """Original RGB pixels of a candidate (4x), or None when unavailable."""
    source = ir.get("source_path")
    if not source:
        return None
    try:
        from pathlib import Path

        import numpy as np

        path = Path(source)
        if path.suffix.lower() == ".pdf":
            import fitz

            with fitz.open(path) as doc:
                page = doc[int(page_number) - 1]
                pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(*box), alpha=False)
                return np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n
                )[:, :, :3]
        from PIL import Image, ImageSequence

        page = next(
            (p for p in ir.get("pages", []) if int(p.get("number", 0)) == int(page_number)), None
        )
        with Image.open(path) as image:
            frame = next(
                f for i, f in enumerate(ImageSequence.Iterator(image)) if i == int(page_number) - 1
            ).convert("RGB")
            scale = frame.width / float(page["width"])
            crop = frame.crop(tuple(int(round(v * scale)) for v in box))
            return np.asarray(crop)
    except Exception:  # noqa: BLE001 - unavailable evidence is reported as None
        return None


def multicolor_evidence(rgb):
    """Significant hues (30 degree bins) of saturated pixels and whether at
    least two of them are >= 60 degrees apart (logo pictogram), as opposed to
    one hue family (coloured title, marker highlight)."""
    import numpy as np

    if rgb is None or rgb.size == 0:
        return None
    c = np.asarray(rgb, dtype=np.float32) / 255.0
    high, low = c.max(axis=2), c.min(axis=2)
    chroma = high - low
    coloured = (chroma >= 0.25) & (high >= 0.25)
    if int(coloured.sum()) < 20:
        return {"hues": [], "multicolor": False}
    r, g, b = c[..., 0][coloured], c[..., 1][coloured], c[..., 2][coloured]
    m, d = high[coloured], chroma[coloured]
    hue = (
        np.where(m == r, ((g - b) / d) % 6, np.where(m == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    )
    hist = np.bincount((hue // 30).astype(int) % 12, minlength=12) / len(hue)
    hues = [i * 30 for i, share in enumerate(hist) if share >= 0.12]
    far = any(
        min(abs(a - b), 360 - abs(a - b)) >= 60 for i, a in enumerate(hues) for b in hues[i + 1 :]
    )
    return {"hues": hues, "multicolor": bool(far)}


def reclassify_text_candidates(ir):
    """Drop automatic raster candidates that are text structure, with a trace.

    * ``conservative_dark_contour`` frames enclosing >= 2 readable OCR lines and
      large enough to be layout (>= 4 % of the page or >= 35 % of its width)
      are form/section frames, not stamps.
    * ``color_connected_components`` contained in a readable OCR line (grown by
      0.3 line height) and no taller than 1.8 line heights are the coloured
      letters of that line (e.g. a coloured title), not a logo -- unless the
      original pixels show two hue families >= 60 degrees apart: a logo
      pictogram read by OCR as part of a line (measured on the final corpus:
      orange/green pictogram next to a company wordmark) stays protected.

    Human annotations and PDF-native visuals are never reclassified.
    """
    pages = {int(p["number"]): p for p in ir.get("pages", [])}
    kept, moved, warnings, vetoed = [], [], [], []
    for region in ir.get("protected_visual_regions") or []:
        page = pages.get(int(region.get("page", 0) or 0))
        box = region.get("bbox")
        if (
            page is None
            or not page.get("scanned")
            or str(region.get("provenance")) != "automatic_candidate:preprocessing"
            or not box
        ):
            kept.append(region)
            continue
        lines = [b for b in page.get("blocks", []) if b.get("bbox") and _readable_line(b)]
        detector = str(region.get("detector") or "")
        page_area = float(page.get("width", 0)) * float(page.get("height", 0)) or 1.0
        reason, members = None, []
        if detector == "conservative_dark_contour":
            members = [
                b for b in lines if _inter_area(b["bbox"], box) >= 0.8 * max(_area(b["bbox"]), 1e-6)
            ]
            large = _area(box) >= 0.04 * page_area or (box[2] - box[0]) >= 0.35 * float(
                page.get("width", 0)
            )
            if len(members) >= 2 and large:
                reason = "text_container_frame"
        elif detector == "color_connected_components":
            for line in lines:
                lb = line["bbox"]
                height = lb[3] - lb[1]
                grown = [
                    lb[0] - 0.3 * height,
                    lb[1] - 0.3 * height,
                    lb[2] + 0.3 * height,
                    lb[3] + 0.3 * height,
                ]
                if (box[3] - box[1]) <= 1.8 * height and _inter_area(box, grown) >= 0.7 * max(
                    _area(box), 1e-6
                ):
                    reason, members = "colored_text_glyphs", [line]
                    break
            if reason == "colored_text_glyphs":
                evidence = multicolor_evidence(_candidate_pixels(ir, region.get("page"), box))
                if evidence and evidence["multicolor"]:
                    region["reclassification_veto"] = {
                        "reason": "multicolor_logo",
                        "hues": evidence["hues"],
                    }
                    vetoed.append(
                        {
                            "page": int(region.get("page", 0)),
                            "bbox": [round(float(v), 3) for v in box],
                            "reason": "multicolor_logo",
                            "hues": evidence["hues"],
                        }
                    )
                    reason, members = None, []
        if reason is None:
            kept.append(region)
            continue
        moved.append(
            {
                "page": int(region.get("page", 0)),
                "bbox": [round(float(v), 3) for v in box],
                "detector": detector,
                "subtype": region.get("subtype"),
                "reason": reason,
                "line_ids": [str(b.get("id")) for b in members],
            }
        )
    by_page = {}
    for item in moved:
        by_page.setdefault(item["page"], []).append(item["reason"])
    for page_number, reasons in sorted(by_page.items()):
        warnings.append(
            {
                "code": "PROTECTED_CANDIDATE_RECLASSIFIED_TEXT",
                "message": "Candidats visuels automatiques reconnus comme structure de texte (cadre de formulaire ou lettres colorées); non protégés, tracés.",
                "severity": "info",
                "page": page_number,
                "count": len(reasons),
                "reasons": sorted(set(reasons)),
            }
        )
    ir["protected_visual_regions"] = kept
    ir["reclassified_visual_candidates"] = _merge_trace(
        ir.get("reclassified_visual_candidates"), moved
    )
    if vetoed:
        ir["reclassification_vetoes"] = _merge_trace(ir.get("reclassification_vetoes"), vetoed)
        warnings.append(
            {
                "code": "PROTECTED_CANDIDATE_MULTICOLOR_KEPT",
                "message": "Candidat coloré inclus dans une ligne OCR mais multicolore (pictogramme de logo): protection conservée.",
                "severity": "info",
                "count": len(vetoed),
            }
        )
    ir.setdefault("warnings", []).extend(warnings)
    return ir


def _merge_trace(existing: list[dict] | None, new: list[dict]) -> list[dict]:
    """Append trace entries once: re-applying protection on a reused analysis
    must not duplicate them (measured: a veto counted twice after reuse)."""

    def key(item: dict) -> tuple:
        bbox = tuple(round(float(v), 1) for v in (item.get("bbox") or []))
        return (item.get("page"), bbox, item.get("reason"), item.get("id"))

    out, seen = [], set()
    for item in list(existing or []) + list(new):
        k = key(item)
        if k not in seen:
            seen.add(k)
            out.append(item)
    return out


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
                "type": "protected_visual_region",
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
            infos = list(page.get_image_info(hashes=True, xrefs=True))
            # Scanners often store one page as many full-width (or full-height)
            # strips. Together they are the page background, not logos or
            # signatures; protecting them would forbid any text on the scan.
            strip_indexes: set[int] = set()
            if scanned:
                strips = [
                    (i, info)
                    for i, info in enumerate(infos)
                    if (info["bbox"][2] - info["bbox"][0]) >= page.rect.width * 0.9
                    or (info["bbox"][3] - info["bbox"][1]) >= page.rect.height * 0.9
                ]
                strip_area = sum(
                    max(0, b[2] - b[0]) * max(0, b[3] - b[1])
                    for b in (info["bbox"] for _, info in strips)
                )
                if len(strips) > 1 and strip_area >= area * 0.8:
                    strip_indexes = {i for i, _ in strips}
                # Scan mosaics are also stored as same-width strips stacked
                # vertically (or same-height tiles side by side) inside page
                # margins; together they cover most of the page.
                mosaics: dict[tuple[str, int, int], list[int]] = {}
                for i, info in enumerate(infos):
                    x0, y0, x1, y1 = info["bbox"]
                    mosaics.setdefault(("v", round(x0), round(x1)), []).append(i)
                    mosaics.setdefault(("h", round(y0), round(y1)), []).append(i)
                for members in mosaics.values():
                    covered = sum(
                        max(0, infos[i]["bbox"][2] - infos[i]["bbox"][0])
                        * max(0, infos[i]["bbox"][3] - infos[i]["bbox"][1])
                        for i in members
                    )
                    if len(members) > 1 and covered >= area * 0.4:
                        strip_indexes |= set(members)
                if strip_indexes:
                    warnings.append(
                        {
                            "code": "RASTER_GRAPHIC_ANNOTATION_REQUIRED",
                            "severity": "warning",
                            "page": number,
                            "background_strips": len(strip_indexes),
                        }
                    )
            for index, image in enumerate(infos):
                if index in strip_indexes:
                    continue
                bbox = list(image["bbox"])
                image_area = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
                if scanned and image_area >= area * 0.4:
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
            from .cover_layer import source_drawings

            for index, drawing in enumerate(source_drawings(page)):
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
    reclassify_text_candidates(ir)
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
        scanned = bool(page.get("scanned"))
        for block in page.get("blocks", []):
            hits = [
                region
                for region in regions
                if region["page"] == page["number"]
                and _intersects(block.get("bbox"), region["bbox"])
            ]
            protecting = [
                region
                for region in hits
                if not carves_only(region)
                and (
                    not scanned
                    or is_user_region(region)
                    or significant_overlap(block.get("bbox"), region["bbox"])
                )
            ]
            near = [region for region in hits if region not in protecting]
            # Recomputed from the final region list (strict on native PDFs and
            # for human annotations, significant overlap on scans).
            block["protected"] = bool(protecting)
            if protecting:
                block["protected_by"] = [str(region.get("id")) for region in protecting]
            else:
                block.pop("protected_by", None)
            if near:
                block["near_protected_regions"] = [str(region.get("id")) for region in near]
            else:
                block.pop("near_protected_regions", None)
    return ir
