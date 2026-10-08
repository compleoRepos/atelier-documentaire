"""Local, bounded preprocessing of processing copies, never original documents.

Confidence is only an OCR selection proxy, never CER/WER or human validation.
All geometry is invertible and protected regions are unauthenticated candidates.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

VERSION = "document-preprocessing-v2"
# Minimum coloured-ink fraction inside a stamp/logo candidate bbox (speckle filter).
STAMP_MIN_INK_DENSITY = 0.05
PROFILES = {"auto", "clean_scan", "noisy_scan", "old_document", "mobile_photo", "complex_document"}
MAX_PIXELS = 24_000_000


@dataclass
class ProcessingResult:
    image: Image.Image
    ocr: Any
    metadata: dict
    protected_visual_regions: list[dict]
    warnings: list[dict]


def map_bbox(bbox, matrix, width, height):
    """Map all four corners, not only the diagonal (rotation/perspective)."""
    x0, y0, x1, y1 = map(float, bbox)
    points = np.array([[x0, y0, 1], [x1, y0, 1], [x1, y1, 1], [x0, y1, 1]])
    mapped = points @ np.asarray(matrix, dtype=float).T
    if np.any(np.abs(mapped[:, 2]) < 1e-9):
        raise ValueError("Non-invertible coordinate mapping")
    mapped = mapped[:, :2] / mapped[:, 2:3]
    return [
        float(np.clip(mapped[:, 0].min(), 0, width)),
        float(np.clip(mapped[:, 1].min(), 0, height)),
        float(np.clip(mapped[:, 0].max(), 0, width)),
        float(np.clip(mapped[:, 1].max(), 0, height)),
    ]


def _gray(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def diagnose(rgb):
    gray = _gray(rgb)
    # Analyses run on a thumbnail; processing and coordinate maps retain full resolution.
    ratio = min(1.0, 1000 / max(gray.shape))
    small = cv2.resize(gray, None, fx=ratio, fy=ratio) if ratio < 1 else gray
    median = cv2.medianBlur(small, 3)
    residual = cv2.absdiff(small, median)
    tiles = [np.percentile(tile, 85) for tile in np.array_split(small, 6, axis=0)]
    background_spread = float(max(tiles) - min(tiles))
    foreground = small[small < 210]
    contrast = (
        float(np.percentile(small, 95) - np.percentile(foreground, 25)) if foreground.size else 0.0
    )
    return {
        "width": rgb.shape[1],
        "height": rgb.shape[0],
        "laplacian_variance": float(cv2.Laplacian(small, cv2.CV_64F).var()),
        "noise_fraction": float(np.mean(residual > 25)),
        "background_spread": background_spread,
        "contrast": contrast,
        "low_resolution": min(rgb.shape[:2]) < 1000,
        "resolution_action": "no_blind_upscale",
    }


def protected_candidates(rgb, page=1, supplied=None):
    """Conservative colour/contour candidates, not semantic authentication."""
    height, width = rgb.shape[:2]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    raw_colored = ((hsv[:, :, 1] > 65) & (hsv[:, :, 2] > 45)).astype(np.uint8) * 255
    kernel = max(3, min(15, int(min(width, height) / 150) | 1))
    colored = cv2.dilate(raw_colored, np.ones((kernel, kernel), np.uint8))
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(colored)
    # A stamp, logo or highlight has a physical size; JPEG chroma speckles on a
    # colour scan do not. Relative to the short side (A4: 210 mm), 1.2% ~ 2.5 mm
    # and 1.9% ~ 4 mm. Sparse speckle clusters are rejected by their ink density.
    short_side = min(width, height)
    min_side, min_long_side = short_side * 0.012, short_side * 0.019
    regions = []
    for x, y, w, h, area in stats[1:count]:
        if area < max(30, width * height * 0.00003):
            continue
        if min(w, h) < min_side or max(w, h) < min_long_side:
            continue
        if float(raw_colored[y : y + h, x : x + w].mean()) / 255 < STAMP_MIN_INK_DENSITY:
            continue
        regions.append(
            {
                "type": "protected_visual_region",
                "subtype": "stamp_or_logo_candidate",
                "page": page,
                "bbox": [int(x), int(y), int(x + w), int(y + h)],
                "candidate": True,
                "authenticated": False,
                "detector": "color_connected_components",
                "confidence": None,
            }
        )
    # Large dark contours may be monochrome stamps, logos, handwritten signatures,
    # tables or photos. False positives are deliberately preserved for human review.
    dark = cv2.threshold(_gray(rgb), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if (
            w > width * 0.045
            and h > height * 0.025
            and w * h < width * height * 0.35
            and (y > height * 0.60 or cv2.contourArea(contour) / (w * h) > 0.35)
        ):
            regions.append(
                {
                    "type": "protected_visual_region",
                    "subtype": "monochrome_visual_candidate",
                    "page": page,
                    "bbox": [x, y, x + w, y + h],
                    "candidate": True,
                    "authenticated": False,
                    "detector": "conservative_dark_contour",
                    "confidence": None,
                }
            )
    for region in supplied or []:
        if int(region.get("page", page)) != page:
            continue
        bbox = region.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            raise ValueError("Invalid protected bbox")
        if not all(math.isfinite(float(x)) for x in bbox):
            raise ValueError("Invalid protected coordinates")
        x0, y0, x1, y1 = map(float, bbox)
        if not 0 <= x0 < x1 <= width or not 0 <= y0 < y1 <= height:
            raise ValueError("Protected region outside source image")
        regions.append(
            {
                **region,
                "type": "protected_visual_region",
                "page": page,
                "bbox": list(bbox),
                "authenticated": False,
            }
        )
    # A hard bound protects pathological scans from contour explosion.
    if len(regions) > 128:
        regions = [
            {
                "type": "protected_visual_region",
                "subtype": "complex_visual_candidate",
                "page": page,
                "bbox": [0, 0, width, height],
                "candidate": True,
                "authenticated": False,
                "detector": "conservative_full_page",
            }
        ]
    return regions


def _mask(shape, regions):
    result = np.zeros(shape[:2], np.uint8)
    for region in regions:
        x0, y0, x1, y1 = region["bbox"]
        result[
            max(0, int(y0)) : min(shape[0], math.ceil(y1)),
            max(0, int(x0)) : min(shape[1], math.ceil(x1)),
        ] = 255
    return result


def _rotation(rgb, angle):
    h, w = rgb.shape[:2]
    affine = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
    c, s = abs(affine[0, 0]), abs(affine[0, 1])
    nw, nh = math.ceil(h * s + w * c), math.ceil(h * c + w * s)
    if nw * nh > MAX_PIXELS:
        raise ValueError("GEOMETRY_PIXEL_LIMIT")
    affine[0, 2] += nw / 2 - w / 2
    affine[1, 2] += nh / 2 - h / 2
    matrix = np.vstack([affine, [0, 0, 1]])
    return cv2.warpPerspective(rgb, matrix, (nw, nh), borderValue=(255, 255, 255)), matrix


def _skew(rgb):
    gray = _gray(rgb)
    scale = min(1.0, 1400 / max(gray.shape))
    small = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1 else gray
    edges = cv2.Canny(small, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 1800,
        threshold=40,
        minLineLength=max(30, small.shape[1] // 12),
        maxLineGap=12,
    )
    angles = []
    if lines is not None:
        for x0, y0, x1, y1 in lines[:, 0]:
            angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
            if -15 <= angle <= 15:
                angles.append(angle)
    if len(angles) < 4:
        return _projection_skew(small)
    angle = float(np.median(angles))
    confidence = float(np.mean(np.abs(np.array(angles) - angle) < 1.2))
    if confidence < 0.7:
        return _projection_skew(small)
    return angle, confidence


def _projection_skew(gray):
    scale = min(1.0, 700 / max(gray.shape))
    small = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1 else gray
    binary = cv2.threshold(small, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    if float(binary.mean()) < 0.001 or float(binary.mean()) > 0.45:
        return 0.0, 0.0
    h, w = binary.shape
    scores = []
    for angle in np.arange(-15, 15.01, 0.5):
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), float(angle), 1)
        rotated = cv2.warpAffine(binary, matrix, (w, h), flags=cv2.INTER_NEAREST)
        projection = rotated.sum(axis=1).astype(float)
        scores.append((float(np.square(np.diff(projection)).sum()), float(angle)))
    best_score, correction = max(scores)
    median = float(np.median([score for score, _ in scores]))
    baseline = next(score for score, angle in scores if angle == 0)
    # Require a material peak, not a confidence fabricated from the angle itself.
    confidence = min(1.0, max(0.0, (best_score - median) / max(1.0, best_score)))
    if best_score <= baseline * 1.12 or abs(correction) >= 15:
        return 0.0, confidence
    return correction, confidence


def _orientation(rgb):
    try:
        import pytesseract

        info = pytesseract.image_to_osd(
            Image.fromarray(rgb), output_type=pytesseract.Output.DICT, timeout=15
        )
        return int(info.get("rotate", 0)), float(info.get("orientation_conf", 0))
    except (OSError, RuntimeError, pytesseract.TesseractError):
        return 0, 0.0


def _ordered_quad(points):
    points = np.asarray(points, np.float32)
    total, diff = points.sum(axis=1), np.diff(points, axis=1).ravel()
    return np.array(
        [
            points[np.argmin(total)],
            points[np.argmin(diff)],
            points[np.argmax(total)],
            points[np.argmax(diff)],
        ],
        np.float32,
    )


def safe_perspective(rgb, regions):
    """Rectify a detected four-corner page only if no foreground/protection is lost.

    Ambiguous dark phone backgrounds are deliberately left for review.
    """
    h, w = rgb.shape[:2]
    edges = cv2.Canny(_gray(rgb), 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        perimeter = cv2.arcLength(contour, True)
        poly = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(poly) != 4 or not cv2.isContourConvex(poly) or cv2.contourArea(poly) < 0.45 * w * h:
            continue
        corners = _ordered_quad(poly[:, 0])
        polygon = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(polygon, corners.astype(np.int32), 255)
        polygon = cv2.dilate(polygon, np.ones((7, 7), np.uint8))
        foreground = np.any(rgb < 255, axis=2)
        if np.any(foreground & (polygon == 0)) or np.any(
            (_mask(rgb.shape, regions) > 0) & (polygon == 0)
        ):
            continue
        nw = math.ceil(
            max(np.linalg.norm(corners[1] - corners[0]), np.linalg.norm(corners[2] - corners[3]))
        )
        nh = math.ceil(
            max(np.linalg.norm(corners[3] - corners[0]), np.linalg.norm(corners[2] - corners[1]))
        )
        if nw < 30 or nh < 30 or nw * nh > MAX_PIXELS:
            continue
        dest = np.float32([[0, 0], [nw - 1, 0], [nw - 1, nh - 1], [0, nh - 1]])
        matrix = cv2.getPerspectiveTransform(corners, dest)
        if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-9:
            continue
        # Rectify the page, but retain the full source canvas around it. Even
        # document-border strokes and protections near a corner must not be cut.
        source_corners = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], dtype=float)
        mapped = source_corners @ matrix.T
        if np.any(mapped[:, 2] <= 1e-6):
            continue
        mapped = mapped[:, :2] / mapped[:, 2:3]
        lower = np.floor(mapped.min(axis=0))
        upper = np.ceil(mapped.max(axis=0))
        canvas_width, canvas_height = map(int, upper - lower)
        if canvas_width * canvas_height > MAX_PIXELS or min(canvas_width, canvas_height) < 1:
            continue
        translation = np.array([[1, 0, -lower[0]], [0, 1, -lower[1]], [0, 0, 1]], dtype=float)
        matrix = translation @ matrix
        return cv2.warpPerspective(
            rgb, matrix, (canvas_width, canvas_height), borderValue=(255, 255, 255)
        ), matrix
    return None


def safe_crop(rgb, regions):
    """Remove blank white margins only; all foreground and protections retained."""
    occupied = np.any(rgb < 255, axis=2).astype(np.uint8) * 255
    occupied |= _mask(rgb.shape, regions)
    points = cv2.findNonZero(occupied)
    if points is None:
        return None
    x, y, w, h = cv2.boundingRect(points)
    pad = max(12, int(min(rgb.shape[:2]) * 0.015))
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(rgb.shape[1], x + w + pad), min(rgb.shape[0], y + h + pad)
    if (x1 - x0) * (y1 - y0) > rgb.shape[0] * rgb.shape[1] * 0.92:
        return None
    matrix = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], dtype=float)
    return rgb[y0:y1, x0:x1].copy(), matrix


def _restore(candidate, source, source_mask, matrix):
    h, w = candidate.shape[:2]
    original = cv2.warpPerspective(source, matrix, (w, h), borderValue=(255, 255, 255))
    mask = cv2.warpPerspective(source_mask, matrix, (w, h), flags=cv2.INTER_NEAREST)
    candidate[mask > 0] = original[mask > 0]
    return candidate


def photometric(rgb, operation):
    gray = _gray(rgb)
    if operation == "median":
        return cv2.medianBlur(rgb, 3)
    if operation == "gaussian":
        return cv2.GaussianBlur(rgb, (3, 3), 0.5)
    if operation == "bilateral":
        return cv2.bilateralFilter(rgb, 5, 30, 30)
    if operation == "non_local_means":
        return cv2.fastNlMeansDenoisingColored(rgb, None, 3, 3, 5, 15)
    if operation == "morphological":
        value = cv2.morphologyEx(gray, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    elif operation == "background_normalization":
        # Smooth low-frequency illumination, never infer or generate new content.
        background = cv2.GaussianBlur(gray, (0, 0), max(8, min(gray.shape) / 50))
        value = cv2.divide(gray, np.maximum(background, 1), scale=245)
    elif operation == "clahe":
        value = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(gray)
    elif operation == "histogram_equalization":
        value = cv2.equalizeHist(gray)
    elif operation == "sharpen":
        blur = cv2.GaussianBlur(rgb, (0, 0), 0.8)
        return cv2.addWeighted(rgb, 1.25, blur, -0.25, 0)
    elif operation == "otsu":
        value = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    elif operation == "adaptive_gaussian":
        value = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
        )
    elif operation == "adaptive_mean":
        value = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 31, 12
        )
    else:
        raise ValueError(f"Unknown preprocessing operation: {operation}")
    return cv2.cvtColor(value, cv2.COLOR_GRAY2RGB)


def ocr_telemetry(result):
    blocks = getattr(result, "blocks", [])
    weighted = [
        (float(b["confidence"]), max(1, len(b.get("text", ""))))
        for b in blocks
        if isinstance(b.get("confidence"), (int, float)) and math.isfinite(b["confidence"])
    ]
    confidence = sum(c * n for c, n in weighted) / sum(n for _, n in weighted) if weighted else None
    return {
        "confidence": confidence,
        "characters": len(getattr(result, "text", "")),
        "blocks": len(blocks),
        "model": getattr(result, "backend", "unknown-local"),
        "version": _ocr_version(result),
        "languages": getattr(result, "used_languages", []),
    }


def _ocr_version(result):
    if getattr(result, "backend", "") == "tesseract":
        import pytesseract

        return str(pytesseract.get_tesseract_version()).split("\n")[0]
    return getattr(result, "version", None)


def preprocess_image(
    image,
    ocr,
    output_dir,
    *,
    page=1,
    profile="auto",
    protected_regions=None,
    before_result=None,
    orientation=True,
    max_variants=6,
):
    if profile not in PROFILES:
        raise ValueError("Unknown preprocessing profile")
    if not 1 <= int(max_variants) <= 12:
        raise ValueError("Variant budget must be 1..12")
    started = time.perf_counter()
    source = np.array(image.convert("RGB"), copy=True)
    if source.shape[0] * source.shape[1] > MAX_PIXELS:
        raise ValueError("PREPROCESSING_PIXEL_LIMIT")
    source_hash = hashlib.sha256(source.tobytes()).hexdigest()
    regions = protected_candidates(source, page, protected_regions)
    mask = _mask(source.shape, regions)
    diagnosis = diagnose(source)
    if profile == "auto":
        profile = (
            "complex_document"
            if regions
            else "old_document"
            if diagnosis["background_spread"] > 18
            else "noisy_scan"
            if diagnosis["noise_fraction"] > 0.015
            else "clean_scan"
        )
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    before = (
        before_result if before_result is not None else ocr.image_to_blocks(Image.fromarray(source))
    )
    initial = ocr_telemetry(before)
    variants = []
    warnings = []
    best = (source, np.eye(3), before, [], "original", initial)
    Image.fromarray(source).save(output / "original.png")
    variants.append({"name": "original", "operations": [], "ocr": initial, "eligible": True})
    proposals = []
    base, transform, geometry = source, np.eye(3), []
    rotation, rotation_conf = _orientation(source) if orientation else (0, 0.0)
    if rotation and rotation_conf >= 8:
        try:
            base, matrix = _rotation(base, -rotation)
            transform = matrix @ transform
            geometry.append(
                {
                    "operation": "orientation",
                    "degrees": -rotation,
                    "confidence": rotation_conf,
                    "confidence_unit": "tesseract_osd",
                }
            )
        except ValueError:
            warnings.append(
                {
                    "code": "GEOMETRY_PIXEL_LIMIT",
                    "severity": "warning",
                    "message": "Rotation ignorée: allocation excessive.",
                }
            )
    skew, skew_conf = _skew(base)
    if 0.4 <= abs(skew) <= 15 and skew_conf >= 0.7:
        try:
            base, matrix = _rotation(base, skew)
            transform = matrix @ transform
            geometry.append({"operation": "deskew", "degrees": skew, "confidence": skew_conf})
        except ValueError:
            warnings.append(
                {
                    "code": "GEOMETRY_PIXEL_LIMIT",
                    "severity": "warning",
                    "message": "Deskew ignoré: allocation excessive.",
                }
            )
    if geometry:
        proposals.append((base.copy(), transform.copy(), list(geometry)))
    if profile == "mobile_photo":
        mapped_regions = [
            {**r, "bbox": map_bbox(r["bbox"], transform, base.shape[1], base.shape[0])}
            for r in regions
        ]
        perspective = safe_perspective(base, mapped_regions)
        if perspective:
            base, matrix = perspective
            transform = matrix @ transform
            geometry.append({"operation": "perspective", "content_loss_guard": True})
            proposals.append((base.copy(), transform.copy(), list(geometry)))
        crop = safe_crop(
            base,
            [
                {**r, "bbox": map_bbox(r["bbox"], transform, base.shape[1], base.shape[0])}
                for r in regions
            ],
        )
        if crop:
            cropped, matrix = crop
            proposals.append(
                (
                    cropped,
                    matrix @ transform,
                    geometry + [{"operation": "blank_margin_crop", "content_loss_guard": True}],
                )
            )
    methods = []
    if diagnosis["noise_fraction"] > 0.015 or profile == "noisy_scan":
        methods += ["median", "bilateral", "non_local_means"]
    if diagnosis["background_spread"] > 18 or profile in {"old_document", "mobile_photo"}:
        methods += ["background_normalization"]
    if diagnosis["contrast"] < 140 or profile in {"old_document", "noisy_scan", "mobile_photo"}:
        methods += ["clahe"]
    if 1 < diagnosis["laplacian_variance"] < 70:
        methods += ["sharpen"]
    # Important graphics are never blindly binarized; original candidates restored anyway.
    if not regions and profile in {"old_document", "noisy_scan"}:
        methods += ["otsu", "adaptive_gaussian", "adaptive_mean"]
    for method in dict.fromkeys(methods):
        proposals.append(
            (photometric(base, method), transform.copy(), geometry + [{"operation": method}])
        )
    for index, (candidate, matrix, operations) in enumerate(proposals[: int(max_variants) - 1], 1):
        if candidate.shape[0] * candidate.shape[1] > MAX_PIXELS:
            continue
        candidate = _restore(candidate, source, mask, matrix)
        name = f"v{index:02d}"
        Image.fromarray(candidate).save(output / f"{name}.png")
        try:
            result = ocr.image_to_blocks(Image.fromarray(candidate))
            telemetry = ocr_telemetry(result)
        except (RuntimeError, ValueError) as exc:
            variants.append(
                {
                    "name": name,
                    "operations": operations,
                    "ocr": None,
                    "eligible": False,
                    "rejection": "OCR_FAILED",
                    "exception_class": type(exc).__name__,
                }
            )
            continue
        # Text loss guard is not a truth-grounded accuracy claim. It only rejects candidates.
        eligible = (
            telemetry["confidence"] is not None
            and telemetry["characters"] >= initial["characters"] * 0.95
        )
        score = best[5]["confidence"]
        if eligible and (score is None or telemetry["confidence"] > score + 0.003):
            best = candidate, matrix, result, operations, name, telemetry
        variants.append(
            {
                "name": name,
                "operations": operations,
                "ocr": telemetry,
                "eligible": eligible,
                "rejection": None if eligible else "OCR_TEXT_LOSS_OR_NO_CONFIDENCE",
                "transform_source_to_processing": matrix.tolist(),
            }
        )
    selected, matrix, result, operations, name, after = best
    processing_path = output / "selected.png"
    Image.fromarray(selected).save(processing_path)
    difference = (
        after["confidence"] - initial["confidence"]
        if after["confidence"] is not None and initial["confidence"] is not None
        else None
    )
    metadata = {
        "version": VERSION,
        "profile": profile,
        "selected_variant": name,
        "source_pixel_sha256": source_hash,
        "processing_pixel_sha256": hashlib.sha256(selected.tobytes()).hexdigest(),
        "source_size": [source.shape[1], source.shape[0]],
        "processing_size": [selected.shape[1], selected.shape[0]],
        "transform_source_to_processing": matrix.tolist(),
        "transform_processing_to_source": np.linalg.inv(matrix).tolist(),
        "processing_image_path": str(processing_path),
        "operations": operations,
        "diagnosis": diagnosis,
        "orientation": {
            "original_rotation": rotation,
            "confidence": rotation_conf,
            "corrected_rotation": 0
            if any(o["operation"] == "orientation" for o in operations)
            else rotation,
        },
        "deskew": {"detected_degrees": skew, "confidence": skew_conf},
        "ocr_before": initial,
        "ocr_after": after,
        "variants": variants,
        "PreprocessingQualityScore": {
            "confidence_before": initial["confidence"],
            "confidence_after": after["confidence"],
            "improvement": difference,
            "metric": "ocr_confidence_proxy",
            "cer": None,
            "wer": None,
            "validated": False,
        },
        "duration_seconds": time.perf_counter() - started,
        "protected_region_policy": "original_pixels_restored_after_photometric_processing; candidates_not_authenticated",
    }
    # Catch accidental mutation, including future in-place filter regressions.
    if hashlib.sha256(source.tobytes()).hexdigest() != source_hash:
        raise RuntimeError("PROCESSING_SOURCE_MUTATED")
    return ProcessingResult(Image.fromarray(selected), result, metadata, regions, warnings)
