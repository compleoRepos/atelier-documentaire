"""Measured source/candidate render fidelity.

This module is intentionally independent from :mod:`pipeline`.  It does not
turn reconstruction metadata into proof: source and candidate are rendered or
parsed independently, and every unavailable measurement is represented by
``None`` (or an explicit ``unavailable`` record).
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_W_TBL = _W + "tbl"
_W_TR = _W + "tr"
_W_TC = _W + "tc"
_W_T = _W + "t"
_W_R = _W + "r"
_W_P = _W + "p"
_W_GRID_SPAN = _W + "gridSpan"
_W_V_MERGE = _W + "vMerge"
_W_TBL_GRID = _W + "tblGrid"
_W_GRID_COL = _W + "gridCol"
_W_TBL_HEADER = _W + "tblHeader"
_W_VAL = _W + "val"
_W_TR_PR = _W + "trPr"
_W_TC_PR = _W + "tcPr"


def _finite(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _rect(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    out = [_finite(item) for item in value]
    if any(item is None for item in out):
        return None
    x0, y0, x1, y1 = out  # type: ignore[misc]
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def _area(box: list[float] | None) -> float:
    return max(0.0, (box[2] - box[0]) * (box[3] - box[1])) if box else 0.0


def _iou(left: list[float] | None, right: list[float] | None) -> float | None:
    if not left or not right:
        return None
    hit = [
        max(left[0], right[0]),
        max(left[1], right[1]),
        min(left[2], right[2]),
        min(left[3], right[3]),
    ]
    intersection = _area(hit) if hit[2] > hit[0] and hit[3] > hit[1] else 0.0
    union = _area(left) + _area(right) - intersection
    return intersection / union if union > 0 else None


def _normalise_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _int_attr(element: ET.Element | None, name: str, default: int = 1) -> int:
    if element is None:
        return default
    value = element.attrib.get(_W + name)
    try:
        return max(1, int(value)) if value is not None else default
    except (TypeError, ValueError):
        return default


def _element_text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(_W_T))


def _run_style(run: ET.Element) -> tuple[Any, ...]:
    props = run.find(_W + "rPr")
    if props is None:
        return (False, False, None, None, None, None)

    def has(name: str) -> bool:
        return props.find(_W + name) is not None

    def val(name: str) -> str | None:
        item = props.find(_W + name)
        return item.attrib.get(_W_VAL) if item is not None else None

    return (has("b"), has("i"), val("u"), val("color"), val("highlight"), val("rFonts"))


def _table_cells(table: ET.Element) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    order = 0
    rows = list(table.findall(_W_TR))
    for row_index, row in enumerate(rows):
        row_cells = list(row.findall(_W_TC))
        column = 0
        for cell in row_cells:
            tc_pr = cell.find(_W_TC_PR)
            grid_span = _int_attr(tc_pr.find(_W_GRID_SPAN) if tc_pr is not None else None, "val", 1)
            merge = tc_pr.find(_W_V_MERGE) if tc_pr is not None else None
            v_merge = None
            if merge is not None:
                v_merge = merge.attrib.get(_W_VAL, "continue")
            runs = []
            for paragraph in cell.findall(_W_P):
                for run in paragraph.iter(_W_R):
                    runs.append({"text": _element_text(run), "style": _run_style(run)})
            cells.append(
                {
                    "row": row_index,
                    "column": column,
                    "grid_span": grid_span,
                    "v_merge": v_merge,
                    "text": "\n".join(_element_text(p) for p in cell.findall(_W_P)),
                    "reading_order": order,
                    "runs": runs,
                }
            )
            order += 1
            column += grid_span
    return cells


def _body_order(root: ET.Element) -> list[str]:
    body = root.find(_W + "body")
    if body is None:
        return []
    return [
        "table" if child.tag == _W_TBL else "paragraph"
        for child in list(body)
        if child.tag in {_W_TBL, _W_P}
    ]


def parse_docx_structure(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Parse source and candidate DOCX packages independently.

    Text is retained for translation-aware diagnostics, while structural
    signatures deliberately exclude text.  Media hashes are package hashes,
    not claims about visual/semantic authenticity.
    """
    source = Path(path).expanduser().resolve()
    if source.suffix.casefold() != ".docx":
        return {
            "format": source.suffix.casefold().lstrip("."),
            "available": False,
            "reason": "not_docx",
        }
    with zipfile.ZipFile(source) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        tables = []
        for index, table in enumerate(root.iter(_W_TBL)):
            grid = table.find(_W_TBL_GRID)
            grid_columns = len(grid.findall(_W_GRID_COL)) if grid is not None else 0
            rows = list(table.findall(_W_TR))
            cells = _table_cells(table)
            columns = grid_columns or max(
                (cell["column"] + cell["grid_span"] for cell in cells), default=0
            )
            header_rows = []
            for row_index, row in enumerate(rows):
                tr_pr = row.find(_W_TR_PR)
                header_rows.append(
                    row_index
                    if tr_pr is not None and tr_pr.find(_W_TBL_HEADER) is not None
                    else None
                )
            tables.append(
                {
                    "index": index,
                    "rows": len(rows),
                    "columns": columns,
                    "grid": grid_columns,
                    "header_rows": [item for item in header_rows if item is not None],
                    "cells": cells,
                    "signature": {
                        "rows": len(rows),
                        "columns": columns,
                        "grid": grid_columns,
                        "header_rows": [item for item in header_rows if item is not None],
                        "cells": [
                            (
                                cell["row"],
                                cell["column"],
                                cell["grid_span"],
                                cell["v_merge"],
                                cell["reading_order"],
                            )
                            for cell in cells
                        ],
                    },
                }
            )
        media = {
            name: _sha256_bytes(archive.read(name))
            for name in sorted(archive.namelist())
            if name.startswith("word/media/") and not name.endswith("/")
        }
        runs = []
        for run in root.iter(_W_R):
            runs.append({"text": _element_text(run), "style": _run_style(run)})
    return {
        "format": "docx",
        "available": True,
        "path": str(source),
        "document_sha256": _sha256_file(source),
        "body_order": _body_order(root),
        "tables": tables,
        "media_hashes": media,
        "run_count": len(runs),
        "runs": runs,
        "header_rows": [row for table in tables for row in table["header_rows"]],
    }


def _same_sequence(left: list[Any], right: list[Any]) -> bool:
    return left == right


def compare_docx_structure(
    source: str | os.PathLike[str],
    candidate: str | os.PathLike[str],
    *,
    translations: dict[str, str] | None = None,
    source_ir: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return measured DOCX structure deltas; text translation is not a failure."""
    original = parse_docx_structure(source)
    target = parse_docx_structure(candidate)
    if not original.get("available") or not target.get("available"):
        return {
            "format": "docx",
            "available": False,
            "source": original,
            "candidate": target,
            "structure_metrics": {},
            "issues": [{"code": "DOCX_STRUCTURE_UNAVAILABLE", "severity": "warning"}],
        }
    issues: list[dict[str, Any]] = []
    source_tables = original["tables"]
    candidate_tables = target["tables"]
    table_equal = len(source_tables) == len(candidate_tables) and all(
        left["signature"] == right["signature"]
        for left, right in zip(source_tables, candidate_tables, strict=True)
    )
    if not table_equal:
        issues.append({"code": "DOCX_TABLE_STRUCTURE_CHANGED", "severity": "error"})
    merges_equal = len(source_tables) == len(candidate_tables) and all(
        [
            (cell["row"], cell["column"], cell["grid_span"], cell["v_merge"])
            for cell in left["cells"]
        ]
        == [
            (cell["row"], cell["column"], cell["grid_span"], cell["v_merge"])
            for cell in right["cells"]
        ]
        for left, right in zip(source_tables, candidate_tables, strict=True)
    )
    header_equal = len(source_tables) == len(candidate_tables) and all(
        left["header_rows"] == right["header_rows"]
        for left, right in zip(source_tables, candidate_tables, strict=True)
    )
    cell_order_equal = len(source_tables) == len(candidate_tables) and all(
        [cell["reading_order"] for cell in left["cells"]]
        == [cell["reading_order"] for cell in right["cells"]]
        for left, right in zip(source_tables, candidate_tables, strict=True)
    )
    media_equal = original["media_hashes"] == target["media_hashes"]
    if not media_equal:
        missing = sorted(set(original["media_hashes"]) - set(target["media_hashes"]))
        added = sorted(set(target["media_hashes"]) - set(original["media_hashes"]))
        issues.append(
            {
                "code": "DOCX_MEDIA_CHANGED",
                "severity": "critical",
                "missing": missing,
                "added": added,
            }
        )
        if missing:
            issues.append({"code": "DOCX_MEDIA_MISSING", "severity": "critical", "media": missing})
        if added:
            issues.append(
                {"code": "DOCX_MEDIA_ADDED_OUTSIDE_SOURCE", "severity": "critical", "media": added}
            )
    if original["body_order"] != target["body_order"]:
        issues.append({"code": "DOCX_READING_ORDER_CHANGED", "severity": "error"})
    # Exact formatting XML can be checked, but semantic style assignment after a
    # translated multi-run paragraph cannot.  Do not turn that uncertainty into 1.
    text_changed = any(
        a.get("text", "") != b.get("text", "")
        for a, b in zip(original["runs"], target["runs"], strict=False)
    )
    style_unknown = text_changed and (
        len(original["runs"]) != len(target["runs"])
        or any(
            a["style"] != b["style"] for a, b in zip(original["runs"], target["runs"], strict=False)
        )
    )
    styles = None if text_changed else float(original["runs"] == target["runs"])
    if style_unknown or text_changed:
        issues.append(
            {
                "code": "DOCX_STYLES_UNVERIFIED",
                "severity": "warning",
                "message": "Run-to-word semantic style assignment is not proven by package structure.",
            }
        )
    from .ooxml_integrity import compare_ooxml_integrity

    integrity = compare_ooxml_integrity(source, candidate)
    issues.extend(integrity["issues"])
    translated_cells = 0
    seen_target_cells = 0
    if translations and source_ir:
        source_table_cells = {
            (
                int(cell.get("source_ref", {}).get("table_index", -1)),
                int(cell.get("row", -1)),
                int(cell.get("column", -1)),
            ): cell
            for table in source_ir.get("tables", [])
            if isinstance(table, dict)
            for cell in table.get("cells", [])
            if isinstance(cell, dict)
        }
        target_table_cells = {
            (table_index, int(cell.get("row", -1)), int(cell.get("column", -1))): cell
            for table_index, table in enumerate(candidate_tables)
            for cell in table.get("cells", [])
        }
        for key, cell in source_table_cells.items():
            paragraph_ids = cell.get("paragraph_ids", [])
            expected_parts = [
                translations[str(item)] for item in paragraph_ids if str(item) in translations
            ]
            if not expected_parts:
                continue
            translated_cells += 1
            expected = _normalise_text(" ".join(expected_parts))
            actual = _normalise_text(target_table_cells.get(key, {}).get("text"))
            if actual == expected:
                seen_target_cells += 1
            else:
                issues.append(
                    {
                        "code": "DOCX_TABLE_CELL_TARGET_MISSING",
                        "severity": "critical",
                        "table_index": key[0],
                        "row": key[1],
                        "column": key[2],
                    }
                )
    cell_target_score = seen_target_cells / translated_cells if translated_cells else None
    metrics: dict[str, Any] = {
        "package_formatting": integrity,
        "tables": {"score": float(table_equal), "preserved": table_equal, "measured": True},
        "merges": {"score": float(merges_equal), "preserved": merges_equal, "measured": True},
        "header_rows": {"score": float(header_equal), "preserved": header_equal, "measured": True},
        "cells": {
            "score": float(table_equal and cell_order_equal),
            "preserved": table_equal and cell_order_equal,
            "measured": True,
        },
        "reading_order": {
            "score": float(original["body_order"] == target["body_order"]),
            "preserved": original["body_order"] == target["body_order"],
            "measured": True,
        },
        "images": {"score": float(media_equal), "preserved": media_equal, "measured": True},
        "cell_targets": {
            "score": cell_target_score,
            "preserved": cell_target_score == 1.0 if cell_target_score is not None else None,
            "measured": cell_target_score is not None,
            "translated_cells": translated_cells,
            "candidate_cells_seen": seen_target_cells,
        },
        "styles": {
            "score": styles,
            "preserved": styles == 1.0 if styles is not None else None,
            "measured": styles is not None,
        },
    }
    return {
        "format": "docx",
        "available": True,
        "source": original,
        "candidate": target,
        "structure_metrics": metrics,
        "issues": issues,
        "media_hashes_equal": media_equal,
        "styles_verified": styles is not None,
    }


def _convert_docx(path: Path, output: Path, timeout: float) -> Path:
    soffice = "/usr/bin/soffice"
    if not Path(soffice).is_file():
        raise RuntimeError("LibreOffice absent: pagination unavailable")
    output.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory(prefix="render-lo-profile-") as profile,
        tempfile.TemporaryDirectory(prefix="render-lo-home-") as home,
    ):
        env = os.environ.copy()
        env.update({"HOME": home, "SAL_USE_VCLPLUGIN": "svp", "LANG": "C.UTF-8"})
        command = [
            soffice,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={Path(profile).as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output),
            str(path),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=min(max(timeout, 1.0), 300.0),
            check=False,
            env=env,
        )
        if completed.returncode:
            raise RuntimeError(
                (completed.stderr or completed.stdout or "LibreOffice conversion failed").strip()[
                    -500:
                ]
            )
    result = output / f"{path.stem}.pdf"
    if not result.is_file() or result.stat().st_size == 0:
        raise RuntimeError("LibreOffice did not produce a PDF")
    return result


def _page_text_blocks(page: Any, number: int) -> list[dict[str, Any]]:
    data = page.get_text("dict")
    result = []
    index = 0
    for raw in data.get("blocks", []):
        if raw.get("type") != 0:
            continue
        lines = raw.get("lines", [])
        text = " ".join(
            "".join(span.get("text", "") for span in line.get("spans", [])) for line in lines
        ).strip()
        if not text:
            continue
        spans = [
            span for line in lines for span in line.get("spans", []) if span.get("text", "").strip()
        ]
        result.append(
            {
                "id": f"p{number:03d}-render-{index:04d}",
                "page": number,
                "text": text,
                "bbox": [float(value) for value in raw.get("bbox", [0, 0, 0, 0])],
                "font_size": sum(float(span.get("size", 0)) for span in spans) / len(spans)
                if spans
                else None,
                "font_sizes": [float(span.get("size", 0)) for span in spans],
            }
        )
        index += 1
    return result


def _render_pdf(
    pdf: Path, preview_dir: Path, prefix: str
) -> tuple[list[dict[str, Any]], list[Path]]:
    import fitz

    preview_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(str(pdf))
    pages: list[dict[str, Any]] = []
    previews: list[Path] = []
    for number, page in enumerate(document, 1):
        pix = page.get_pixmap(matrix=fitz.Matrix(120 / 72, 120 / 72), alpha=False)
        preview = preview_dir / f"{prefix}-{number:03d}.png"
        pix.save(str(preview))
        pages.append(
            {
                "number": number,
                "width": float(page.rect.width),
                "height": float(page.rect.height),
                "bbox": [0.0, 0.0, float(page.rect.width), float(page.rect.height)],
                "blocks": _page_text_blocks(page, number),
                "scanned": not bool(_page_text_blocks(page, number)),
            }
        )
        previews.append(preview)
    document.close()
    return pages, previews


def _render_image(
    path: Path, preview_dir: Path, prefix: str
) -> tuple[list[dict[str, Any]], list[Path]]:
    from PIL import Image

    preview_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(path).convert("RGB")
    preview = preview_dir / f"{prefix}-001.png"
    width, height = image.size
    image.resize((round(width * 120 / 72), round(height * 120 / 72))).save(preview)
    return (
        [
            {
                "number": 1,
                "width": float(width),
                "height": float(height),
                "bbox": [0.0, 0.0, float(width), float(height)],
                "blocks": [],
                "scanned": True,
            }
        ],
        [preview],
    )


def _prepare_render(path: Path, work: Path, prefix: str, timeout: float) -> dict[str, Any]:
    suffix = path.suffix.casefold()
    if suffix == ".docx":
        pdf = _convert_docx(path, work / f"{prefix}-libreoffice", timeout)
        pages, previews = _render_pdf(pdf, work / "previews", prefix)
        return {
            "path": path,
            "pdf": pdf,
            "pages": pages,
            "previews": previews,
            "format": "docx",
            "pagination": "libreoffice-pdf",
        }
    if suffix == ".pdf":
        pages, previews = _render_pdf(path, work / "previews", prefix)
        return {
            "path": path,
            "pdf": path,
            "pages": pages,
            "previews": previews,
            "format": "pdf",
            "pagination": "native-pdf",
        }
    if suffix in {".png", ".jpg", ".jpeg"}:
        pages, previews = _render_image(path, work / "previews", prefix)
        return {
            "path": path,
            "pdf": None,
            "pages": pages,
            "previews": previews,
            "format": suffix[1:],
            "pagination": "raster-image",
        }
    raise ValueError(f"Unsupported render format: {suffix}")


def _path_value(value: Any, candidate: bool = False) -> Path:
    if isinstance(value, (str, os.PathLike)):
        return Path(value).expanduser().resolve()
    if isinstance(value, dict):
        key = "candidate_pdf_path" if candidate else "source_path"
        fallback = "output_path" if candidate else "source_path"
        for item in (key, fallback, "path"):
            if value.get(item):
                return Path(value[item]).expanduser().resolve()
    raise ValueError("A source/candidate path is required")


def _source_blocks(
    source_ir: dict[str, Any] | None, source_pages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if isinstance(source_ir, dict):
        blocks = [
            block
            for page in source_ir.get("pages", [])
            if isinstance(page, dict)
            for block in page.get("blocks", [])
            if isinstance(block, dict)
        ]
        if blocks:
            return blocks
    return [block for page in source_pages for block in page.get("blocks", [])]


def _match_candidate(source_block, target_text, pages, used):
    wanted = _normalise_text(target_text) or _normalise_text(source_block.get("text"))
    if not wanted:
        return None
    candidates = [
        b
        for p in pages
        for b in p.get("blocks", [])
        if b.get("id") not in used and b.get("page") == source_block.get("page")
    ]
    matched = []
    for block in candidates:
        text = _normalise_text(block.get("text"))
        for span in re.finditer(r"(?<!\w)" + re.escape(wanted) + r"(?!\w)", text):
            start, end = span.span()
            overlaps = any(
                isinstance(t, tuple) and t[0] == str(block["id"]) and t[1] < end and start < t[2]
                for t in used
            )
            if not overlaps:
                matched.append(
                    {
                        **block,
                        "matched_text_range": [start, end],
                        "exact_text_match": text == wanted,
                    }
                )
    if not matched:
        return None
    exact = [b for b in matched if b["exact_text_match"]]
    return min(
        exact or matched,
        key=lambda b: (
            abs(b["bbox"][0] - source_block.get("bbox", [0, 0])[0])
            + abs(b["bbox"][1] - source_block.get("bbox", [0, 0])[1])
        ),
    )


def _geometry(
    source: dict[str, Any],
    candidate: dict[str, Any],
    source_ir: dict[str, Any] | None,
    translations: dict[str, str],
    verified_block_ids: set[str] | frozenset[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_pages = source["pages"]
    candidate_pages = candidate["pages"]
    issues: list[dict[str, Any]] = []
    page_pairs = min(len(source_pages), len(candidate_pages))
    dimension_values = []
    for index in range(page_pairs):
        left, right = source_pages[index], candidate_pages[index]
        width_left, width_right = float(left["width"]), float(right["width"])
        height_left, height_right = float(left["height"]), float(right["height"])
        dimension_values.append(
            float(abs(width_left - width_right) <= 0.01 and abs(height_left - height_right) <= 0.01)
        )
    dimensions = sum(dimension_values) / len(dimension_values) if dimension_values else None
    if len(source_pages) != len(candidate_pages):
        issues.append(
            {
                "code": "RENDER_PAGE_COUNT_CHANGED",
                "severity": "critical",
                "source": len(source_pages),
                "candidate": len(candidate_pages),
            }
        )
    source_blocks = _source_blocks(source_ir, source_pages)
    # F27: a block preserved on purpose as a protected visual element keeps its
    # source pixels; its (unapplied) translation is not "translated text".
    translated = [
        block
        for block in source_blocks
        if str(block.get("id")) in translations
        and translations.get(str(block.get("id"))) != block.get("text")
        and not block.get("protected")
    ]
    verified = {str(v) for v in (verified_block_ids or ())}
    # Sans remplacement, on compare les vrais blocs PDF des deux artefacts.
    # Un scan n'a pas de texte PDF natif : sa preuve est pixel, pas une disparition.
    translated_ids = {str(b.get("id")) for b in translated}
    scanned_pages = {p["number"] for p in source_pages if p.get("scanned")}
    compared = [
        block
        for block in source_blocks
        if block.get("page") not in scanned_pages or str(block.get("id")) in translated_ids
    ]
    if not compared:
        compared = [block for page in source_pages for block in page.get("blocks", [])]
    used: set = set()
    matches = []
    # F27: the contiguous match below requires the whole target inside ONE
    # extracted PDF text block. A target wrapped by the engine is often split by
    # the extractor; when the post-render proof (F26) found the target in the
    # exact frame used by the engine, the block is present, not missing.
    by_placement: set[str] = set()
    for block in compared:
        block_id = str(block.get("id", ""))
        target_text = str(translations.get(block_id, block.get("text", "")))
        match = _match_candidate(block, target_text, candidate_pages, used)
        if match is not None:
            used.add((str(match["id"]), *match["matched_text_range"]))
        elif block_id in verified:
            by_placement.add(block_id)
        matches.append((block, match, target_text))
    translated_count = len(translated)

    def _seen(block, match) -> bool:
        return match is not None or str(block.get("id")) in by_placement

    all_candidate_seen = sum(_seen(block, match) for block, match, _text in matches)
    translated_seen = sum(
        _seen(block, match)
        for block, match, _text in matches
        if str(block.get("id")) in translated_ids
    )
    candidate_seen = translated_seen if translated_count else all_candidate_seen
    missing = sum(not _seen(block, match) for block, match, _text in matches)
    if missing:
        issues.append(
            {"code": "RENDER_SOURCE_TEXT_MISSING", "severity": "critical", "count": missing}
        )
    if translated_count and translated_seen < translated_count:
        issues.append(
            {
                "code": "RENDER_TRANSLATED_TEXT_MISSING",
                "severity": "critical",
                "count": translated_count - translated_seen,
            }
        )
    ious = []
    displacements = []
    font_ratios = []
    containments = []
    anchor_scores = []
    clipping = 0
    for source_block, target_block, _target_text in matches:
        if target_block is None and str(source_block.get("id")) in by_placement:
            # Present and verified inside the engine frame (F26); no single
            # extracted block to compare geometrically.
            continue
        if target_block is None:
            ious.append(0.0)
            containments.append(0.0)
            anchor_scores.append(0.0)
            clipping += 1
            continue
        left = _rect(source_block.get("bbox"))
        right = _rect(target_block.get("bbox"))
        ious.append(_iou(left, right) if _iou(left, right) is not None else 0.0)
        if left and right:
            frame = [left[0] - 2, left[1] - 2, left[2] + 2, left[3] + 2]
            overlap = [
                max(frame[0], right[0]),
                max(frame[1], right[1]),
                min(frame[2], right[2]),
                min(frame[3], right[3]),
            ]
            intersection = (
                _area(overlap) if overlap[2] > overlap[0] and overlap[3] > overlap[1] else 0.0
            )
            containments.append(min(1.0, intersection / max(_area(right), 0.000001)))
            anchor_distance = abs(left[0] - right[0]) + abs(left[1] - right[1])
            anchor_scores.append(max(0.0, 1.0 - max(0, anchor_distance - 2) / 24))
            dx = abs((left[0] + left[2]) / 2 - (right[0] + right[2]) / 2)
            dy = abs((left[1] + left[3]) / 2 - (right[1] + right[3]) / 2)
            displacements.append(1.0 / (1.0 + (dx + dy) / 12.0))
        page = next(
            (item for item in candidate_pages if item["number"] == target_block.get("page")), None
        )
        if page and right:
            page_box = [0.0, 0.0, float(page["width"]), float(page["height"])]
            if translated_count and (
                right[0] < -0.01
                or right[1] < -0.01
                or right[2] > page_box[2] + 0.01
                or right[3] > page_box[3] + 0.01
            ):
                clipping += 1
        source_font = _finite(source_block.get("font_size"))
        target_font = _finite(target_block.get("font_size"))
        if source_font and target_font and source_font > 0:
            font_ratios.append(max(0.0, min(1.0, target_font / source_font)))
    if clipping:
        issues.append(
            {"code": "RENDER_TEXT_CLIPPED_OR_MISSING", "severity": "critical", "count": clipping}
        )
    values = {
        "dimensions": dimensions,
        "blocks": candidate_seen / translated_count
        if translated_count
        else (None if not compared else candidate_seen / len(compared)),
        "bbox_iou": sum(ious) / len(ious) if ious else None,
        "overlap": sum(ious) / len(ious) if ious else None,
        "frame_overlap": sum(containments) / len(containments) if containments else None,
        "anchor_stability": sum(anchor_scores) / len(anchor_scores) if anchor_scores else None,
        "displacement": sum(displacements) / len(displacements) if displacements else None,
        "clipping": 0.0 if clipping else (1.0 if matches else None),
        "font_size_reduction": sum(font_ratios) / len(font_ratios) if font_ratios else None,
        "matched_by_placement_verification": len(by_placement),
    }
    scored_keys = (
        "dimensions",
        "blocks",
        "frame_overlap",
        "anchor_stability",
        "clipping",
        "font_size_reduction",
    )
    available = [values[key] for key in scored_keys if values.get(key) is not None]
    metrics = {
        **values,
        "translation_aware": True,
        "score": sum(available) / len(available) if available else None,
        "translated_block_count": translated_count,
        "candidate_blocks_seen": candidate_seen,
        "missing_block_count": missing,
        "candidate_text_missing": translated_count - translated_seen
        if translated_count
        else missing,
        "clipped_block_count": clipping,
        "clipping_count": clipping,
        "measured": bool(available),
        "provenance": "actual_pdf_get_text_dict_geometry",
    }
    return metrics, issues


def _pixel_protected(
    source_previews: list[Path], candidate_previews: list[Path], regions: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from PIL import Image, ImageChops, ImageStat

    results = []
    issues = []
    for index, region in enumerate(regions):
        page = int(region.get("page", 1))
        bbox = _rect(region.get("bbox"))
        if (
            bbox is None
            or page < 1
            or page > len(source_previews)
            or page > len(candidate_previews)
        ):
            results.append(
                {
                    "id": region.get("id", f"region-{index}"),
                    "preserved": None,
                    "measured": False,
                    "authenticity_verified": False,
                }
            )
            issues.append(
                {
                    "code": "PROTECTED_REGION_UNMEASURABLE",
                    "severity": "warning",
                    "region": region.get("id", index),
                }
            )
            continue
        original = Image.open(source_previews[page - 1]).convert("RGB")
        target = Image.open(candidate_previews[page - 1]).convert("RGB")
        if original.size != target.size:
            results.append(
                {
                    "id": region.get("id", f"region-{index}"),
                    "preserved": False,
                    "measured": False,
                    "pixel_constant": False,
                    "authenticity_verified": False,
                }
            )
            issues.append(
                {
                    "code": "PROTECTED_REGION_PIXEL_DIMENSIONS_CHANGED",
                    "severity": "critical",
                    "page": page,
                }
            )
            continue
        scale_x, scale_y = (
            original.width
            / max(1.0, float(region.get("page_width", region.get("width", original.width)))),
            original.height
            / max(1.0, float(region.get("page_height", region.get("height", original.height)))),
        )
        width = float(region.get("page_width", original.width))
        height = float(region.get("page_height", original.height))
        if not (0 <= bbox[0] < bbox[2] <= width and 0 <= bbox[1] < bbox[3] <= height):
            results.append(
                {
                    "id": region.get("id", f"region-{index}"),
                    "preserved": None,
                    "measured": False,
                    "authenticity_verified": False,
                }
            )
            issues.append(
                {"code": "PROTECTED_REGION_OUTSIDE_PAGE", "severity": "critical", "page": page}
            )
            continue
        clip = tuple(
            int(round(value * (scale_x if index % 2 == 0 else scale_y)))
            for index, value in enumerate(bbox)
        )
        delta = ImageChops.difference(original.crop(clip), target.crop(clip))
        mean = sum(ImageStat.Stat(delta).mean) / 3.0 / 255.0
        preserved = mean == 0.0
        results.append(
            {
                "id": region.get("id", f"region-{index}"),
                "preserved": preserved,
                "measured": True,
                "pixel_constant": True,
                "mean_error": mean,
                "authenticity_verified": False,
            }
        )
        if not preserved:
            issues.append(
                {
                    "code": "PROTECTED_REGION_CHANGED",
                    "severity": "critical",
                    "region": region.get("id", index),
                }
            )
    return results, issues


def _raster_similarity(
    source_previews: list[Path],
    candidate_previews: list[Path],
    masks: list[dict[str, Any]],
    page_width: float,
    page_height: float,
    page_dimensions: list[dict[str, Any]] | None = None,
) -> tuple[float | None, dict[str, Any], list[dict[str, Any]]]:
    from PIL import Image, ImageChops, ImageDraw, ImageStat

    if not source_previews or len(source_previews) != len(candidate_previews):
        return (
            None,
            {"available": False, "pages_compared": 0},
            [{"code": "RASTER_PAGE_COVERAGE_MISSING", "severity": "warning"}],
        )
    scores = []
    issues = []
    for page_number, (source_path, candidate_path) in enumerate(
        zip(source_previews, candidate_previews, strict=True), 1
    ):
        original = Image.open(source_path).convert("RGB")
        target = Image.open(candidate_path).convert("RGB")
        if original.size != target.size:
            issues.append(
                {
                    "code": "RASTER_PIXEL_DIMENSIONS_CHANGED",
                    "severity": "critical",
                    "page": page_number,
                }
            )
            continue
        mask = Image.new("L", original.size, 0)
        draw = ImageDraw.Draw(mask)
        dimensions = (page_dimensions or [{}] * len(source_previews))[page_number - 1]
        current_width = float(dimensions.get("width", page_width))
        current_height = float(dimensions.get("height", page_height))
        for item in masks:
            if int(item.get("page", 1)) != page_number:
                continue
            box = _rect(item.get("bbox"))
            if box:
                draw.rectangle(
                    tuple(
                        round(
                            value
                            * (
                                original.width / max(current_width, 1.0)
                                if i % 2 == 0
                                else original.height / max(current_height, 1.0)
                            )
                        )
                        for i, value in enumerate(box)
                    ),
                    fill=255,
                )
        diff = ImageChops.difference(original, target).convert("L")
        inverted = ImageChops.invert(mask)
        stats = ImageStat.Stat(diff, mask=inverted)
        error = sum(stats.mean) / len(stats.mean) / 255.0 if sum(inverted.getdata()) else 1.0
        scores.append(max(0.0, min(1.0, 1.0 - error)))
    return (
        (sum(scores) / len(scores) if scores else None),
        {
            "available": bool(scores),
            "pages_compared": len(scores),
            "masked_text_excluded": bool(masks),
            "pixel_constant": not any(
                item.get("code") == "RASTER_PIXEL_DIMENSIONS_CHANGED" for item in issues
            ),
        },
        issues,
    )


def _mask_coverage_issues(
    masks: list[dict[str, Any]], pages: list[dict[str, Any]], limit: float = 0.35
) -> list[dict[str, Any]]:
    """Pages whose text masks cover more than ``limit`` of the page.

    F32 (run27): the coverage is the area of the UNION of the masks. Line masks
    and block masks overlap; their areas used to be summed, counting the same
    pixels up to twice (dense scanned letters reported 37-74 % for at most 28 %
    actually masked). The limit is unchanged."""
    from .geometry import union_area

    boxes_by_page: dict[int, list[list[float]]] = {}
    for mask in masks:
        box = _rect(mask.get("bbox"))
        if box:
            boxes_by_page.setdefault(int(mask.get("page", 1)), []).append(box)
    issues = []
    for page_number, boxes in boxes_by_page.items():
        mask_area = union_area(boxes)
        page = next((item for item in pages if item["number"] == page_number), None)
        page_area = float(page["width"]) * float(page["height"]) if page else 0.0
        if page_area and mask_area / page_area > limit:
            issues.append(
                {
                    "code": "RENDER_TEXT_MASK_TOO_LARGE",
                    "severity": "critical",
                    "page": page_number,
                    "coverage": mask_area / page_area,
                    "limit": limit,
                }
            )
    return issues


# RUN29 F49: structural rule check. A paper cover that erased a table rule
# was invisible to every metric (DOC-004 run29d: critical count went DOWN
# while a rule disappeared over ~120 pt). Values are in points; previews are
# rasterised at a known page size so they are converted per page.
_RULE_DARK_LEVEL = 160  # grey level under which a preview pixel is ink
_RULE_MIN_LENGTH_PT = 30.0  # a run at least this long on one pixel row/column
_RULE_MIN_COMPONENT_PT = 40.0  # a rule component at least this long
_RULE_GAP_CLOSE_PX = 1  # drop-outs of <= 2 px are closed before measuring
_RULE_THIN_OFFSET_PX = 3  # pixels above/below a thin rule are paper
_RULE_THIN_SHARE = 0.7
_RULE_OUTSIDE_MASK_PT = 4.0  # structural: the rule continues past the masks
_RULE_ERASED_PT = 8.0  # contiguous length erased under the masks


def _close_runs(rows: Any, radius: int) -> Any:
    """Binary closing along the last axis (fills holes of <= 2*radius px)."""
    import numpy as np

    if radius <= 0:
        return rows
    width = 2 * radius + 1
    padded = np.pad(rows, ((0, 0), (radius, radius)), constant_values=False)
    dilated = np.lib.stride_tricks.sliding_window_view(padded, width, axis=1).any(axis=-1)
    padded = np.pad(dilated, ((0, 0), (radius, radius)), constant_values=True)
    return np.lib.stride_tricks.sliding_window_view(padded, width, axis=1).all(axis=-1)


def _long_runs(rows: Any, min_length: int) -> Any:
    """Pixels belonging to a horizontal run of at least ``min_length``."""
    import numpy as np

    keep = np.zeros_like(rows, dtype=bool)
    edges = np.diff(np.pad(rows.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    for row in np.flatnonzero((edges == 1).any(axis=1)):
        starts = np.flatnonzero(edges[row] == 1)
        stops = np.flatnonzero(edges[row] == -1)
        for start, stop in zip(starts, stops, strict=True):
            if stop - start >= min_length:
                keep[row, start:stop] = True
    return keep


def _longest_true_run(values: Any) -> tuple[int, int]:
    """(length, start index) of the longest run of True values."""
    best = current = 0
    best_start = start = 0
    for index, value in enumerate(values):
        if value:
            if current == 0:
                start = index
            current += 1
            if current > best:
                best, best_start = current, start
        else:
            current = 0
    return best, best_start


def _erased_rules_one_axis(
    source: Any, target: Any, masked: Any, scale: float, cross_scale: float
) -> list[dict[str, Any]]:
    """Rules running along axis 1 of the arrays (rows = horizontal rules)."""
    import cv2
    import numpy as np

    closed = _close_runs(source, _RULE_GAP_CLOSE_PX)
    runs = _long_runs(closed, max(8, round(_RULE_MIN_LENGTH_PT * scale))) & source
    if not runs.any():
        return []
    # A skewed rule steps from one pixel row to the next: 8-connectivity on a
    # slightly grown map joins the steps into one component.
    grown = cv2.dilate(runs.astype(np.uint8), np.ones((3, 3), np.uint8))
    count, labels = cv2.connectedComponents(grown, connectivity=8)
    survived = cv2.dilate(target.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    offset = _RULE_THIN_OFFSET_PX
    height = source.shape[0]
    found: list[dict[str, Any]] = []
    for label in range(1, count):
        ys, xs = np.nonzero(runs & (labels == label))
        if xs.size == 0:
            continue
        span = int(xs.max() - xs.min() + 1)
        if span < _RULE_MIN_COMPONENT_PT * scale:
            continue
        above = source[np.clip(ys - offset, 0, height - 1), xs] & (ys - offset >= 0)
        below = source[np.clip(ys + offset, 0, height - 1), xs] & (ys + offset < height)
        if float(np.mean(~above & ~below)) < _RULE_THIN_SHARE:
            continue  # thick structure: a text row, a dark fill, a logo
        columns = np.arange(xs.min(), xs.max() + 1)
        inside = np.zeros(columns.size, dtype=bool)
        outside = np.zeros(columns.size, dtype=bool)
        kept = np.zeros(columns.size, dtype=bool)
        index = xs - xs.min()
        under = masked[ys, xs]
        np.logical_or.at(inside, index[under], True)
        np.logical_or.at(outside, index[~under], True)
        np.logical_or.at(kept, index[under & survived[ys, xs]], True)
        if outside.sum() < _RULE_OUTSIDE_MASK_PT * scale:
            continue  # an underline inside the text area, not a structural rule
        erased = inside & ~kept
        longest, first = _longest_true_run(erased)
        if longest < _RULE_ERASED_PT * scale:
            continue
        found.append(
            {
                "along": (float(xs.min() / scale), float((xs.max() + 1) / scale)),
                "across": (float(ys.min() / cross_scale), float((ys.max() + 1) / cross_scale)),
                "erased_along": (
                    float((xs.min() + first) / scale),
                    float((xs.min() + first + longest) / scale),
                ),
                "rule_pt": round(span / scale, 2),
                "erased_pt": round(longest / scale, 2),
                "erased_share": round(float(erased.sum()) / max(1, int(inside.sum())), 3),
            }
        )
    return found


def _erased_rule_issues(
    source_previews: list[Path],
    candidate_previews: list[Path],
    masks: list[dict[str, Any]],
    pages: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """RUN29 F49: table rules / frame lines of the original that are no longer
    drawn in the rendering where a text mask was painted.

    Only thin, long lines that ALSO continue outside the masks are considered
    (structure, not a text row or an underline). A rule redrawn or left intact
    passes; the check never repairs anything, it reports."""
    import numpy as np
    from PIL import Image, ImageDraw

    summary: dict[str, Any] = {"available": False, "pages_checked": 0, "erased_rules": 0}
    if not source_previews or len(source_previews) != len(candidate_previews):
        return summary, []
    issues: list[dict[str, Any]] = []
    for page_number, (source_path, candidate_path) in enumerate(
        zip(source_previews, candidate_previews, strict=True), 1
    ):
        page = next((item for item in pages if item.get("number") == page_number), None)
        original = Image.open(source_path).convert("L")
        rendered = Image.open(candidate_path).convert("L")
        if page is None or original.size != rendered.size:
            continue
        sx = original.width / max(float(page["width"]), 1.0)
        sy = original.height / max(float(page["height"]), 1.0)
        mask_image = Image.new("L", original.size, 0)
        draw = ImageDraw.Draw(mask_image)
        for item in masks:
            box = _rect(item.get("bbox"))
            if box and int(item.get("page", 1)) == page_number:
                draw.rectangle((box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy), fill=255)
        masked = np.asarray(mask_image) > 0
        if not masked.any():
            summary["pages_checked"] += 1
            continue
        source = np.asarray(original) < _RULE_DARK_LEVEL
        target = np.asarray(rendered) < _RULE_DARK_LEVEL
        summary["pages_checked"] += 1
        for orientation, found in (
            ("horizontal", _erased_rules_one_axis(source, target, masked, sx, sy)),
            ("vertical", _erased_rules_one_axis(source.T, target.T, masked.T, sy, sx)),
        ):
            for rule in found:
                (a0, a1), (c0, c1) = rule["along"], rule["across"]
                e0, e1 = rule["erased_along"]
                bbox = [a0, c0, a1, c1] if orientation == "horizontal" else [c0, a0, c1, a1]
                erased_bbox = [e0, c0, e1, c1] if orientation == "horizontal" else [c0, e0, c1, e1]
                issues.append(
                    {
                        "code": "RENDER_RULE_ERASED",
                        "severity": "critical",
                        "page": page_number,
                        "orientation": orientation,
                        "bbox": [round(value, 2) for value in bbox],
                        "erased_bbox": [round(value, 2) for value in erased_bbox],
                        "rule_pt": rule["rule_pt"],
                        "erased_pt": rule["erased_pt"],
                        "erased_share": rule["erased_share"],
                    }
                )
    summary["available"] = summary["pages_checked"] > 0
    summary["erased_rules"] = len(issues)
    return summary, issues


def measure_render_fidelity(
    source: Any,
    candidate: Any,
    *,
    source_ir: dict[str, Any] | None = None,
    translations: dict[str, str] | None = None,
    text_masks: list[dict[str, Any]] | None = None,
    protected_regions: list[dict[str, Any]] | None = None,
    work_dir: str | os.PathLike[str] | None = None,
    libreoffice_timeout: float = 90.0,
    verified_block_ids: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Render both artifacts and return scorer-compatible measured evidence."""
    source_path = _path_value(source, False)
    candidate_path = _path_value(candidate, True)
    work = (
        Path(work_dir).expanduser().resolve()
        if work_dir
        else Path(tempfile.mkdtemp(prefix="render-metrics-"))
    )
    work.mkdir(parents=True, exist_ok=True)
    warnings: list[dict[str, Any]] = []
    try:
        original = _prepare_render(source_path, work, "original", libreoffice_timeout)
        target = _prepare_render(candidate_path, work, "candidate", libreoffice_timeout)
    except Exception as exc:
        return {
            "source_path": str(source_path),
            "candidate_path": str(candidate_path),
            "format": source_path.suffix.casefold().lstrip("."),
            "source_page_count": None,
            "translated_page_count": None,
            "source_pages": [],
            "candidate_pages": [],
            "source_previews": [],
            "translated_previews": [],
            "geometry_metrics": None,
            "structure_metrics": None,
            "layout_score": None,
            "geometry_pure": None,
            "issues": [
                {"code": "RENDER_PROOF_UNAVAILABLE", "severity": "error", "message": str(exc)}
            ],
            "execution_status": "NOT_AVAILABLE_IN_ENVIRONMENT",
            "provenance": {
                "method": "actual_render_unavailable",
                "source": str(source_path),
                "candidate": str(candidate_path),
            },
        }
    translations = {str(key): str(value) for key, value in (translations or {}).items()}
    geometry, geometry_issues = _geometry(
        original, target, source_ir, translations, verified_block_ids
    )
    issues = warnings + geometry_issues
    structure: dict[str, Any] | None = None
    if source_path.suffix.casefold() == ".docx" and candidate_path.suffix.casefold() == ".docx":
        structure = compare_docx_structure(
            source_path,
            candidate_path,
            translations=translations,
            source_ir=source_ir,
        )
        issues.extend(structure.get("issues", []))
        structure_metrics = structure.get("structure_metrics")
    else:
        from .pdf_fidelity import compare_pdf_tables

        if original.get("pdf") and target.get("pdf"):
            pdf_structure = compare_pdf_tables(
                original["pdf"], target["pdf"], source_ir=source_ir, translations=translations
            )
            structure_metrics = pdf_structure["structure_metrics"]
            issues.extend(pdf_structure.get("issues", []))
        else:
            pdf_structure = {"available": False, "reason": "NOT_AVAILABLE_IN_ENVIRONMENT"}
            structure_metrics = {"tables": {"score": None, "preserved": None, "measured": False}}
        structure = {"available": False, "reason": "not_docx"}
    masks = []
    if source_ir:
        for block in _source_blocks(source_ir, original["pages"]):
            block_id = str(block.get("id", ""))
            if block_id in translations and translations[block_id] != block.get("text"):
                masks.append(
                    {
                        "page": block.get("page", 1),
                        "bbox": block.get("bbox", []),
                        "block_id": block_id,
                    }
                )
    if text_masks:
        masks.extend(item for item in text_masks if isinstance(item, dict))
    unique_masks = {(int(mask.get("page", 1)), tuple(mask.get("bbox", []))): mask for mask in masks}
    masks = list(unique_masks.values())
    mask_issues = _mask_coverage_issues(masks, original["pages"])
    issues.extend(mask_issues)
    page_width = float(original["pages"][0]["width"]) if original["pages"] else 1.0
    page_height = float(original["pages"][0]["height"]) if original["pages"] else 1.0
    raster_score, raster_coverage, raster_issues = _raster_similarity(
        original["previews"], target["previews"], masks, page_width, page_height, original["pages"]
    )
    if mask_issues:
        raster_score = None
    issues.extend(raster_issues)
    protected_results, protected_issues = _pixel_protected(
        original["previews"],
        target["previews"],
        [
            {
                **r,
                "page_width": original["pages"][int(r.get("page", 1)) - 1]["width"],
                "page_height": original["pages"][int(r.get("page", 1)) - 1]["height"],
            }
            if 1 <= int(r.get("page", 1)) <= len(original["pages"])
            else r
            for r in (protected_regions or [])
        ],
    )
    issues.extend(protected_issues)
    rule_integrity, rule_issues = _erased_rule_issues(
        original["previews"], target["previews"], masks, original["pages"]
    )
    issues.extend(rule_issues)
    measured_components = [
        value for value in [geometry.get("score"), raster_score] if value is not None
    ]
    layout_score = geometry.get("score") if geometry.get("measured") else None
    return {
        "format": source_path.suffix.casefold().lstrip("."),
        "source_path": str(source_path),
        "candidate_path": str(candidate_path),
        "source_pdf_path": str(original["pdf"]) if original.get("pdf") else None,
        "candidate_pdf_path": str(target["pdf"]) if target.get("pdf") else None,
        "source_page_count": len(original["pages"]),
        "translated_page_count": len(target["pages"]),
        "candidate_page_count": len(target["pages"]),
        "pages_preserved": len(original["pages"]) == len(target["pages"]),
        "source_pages": original["pages"],
        "original_pages": original["pages"],
        "candidate_pages": target["pages"],
        "translated_pages": target["pages"],
        "source_previews": [str(path) for path in original["previews"]],
        "original_previews": [str(path) for path in original["previews"]],
        "translated_previews": [str(path) for path in target["previews"]],
        "candidate_previews": [str(path) for path in target["previews"]],
        "geometry_metrics": geometry,
        "geometry_pure": geometry.get("score"),
        "layout_score": layout_score,
        "rule_integrity": rule_integrity,
        "structure_metrics": structure_metrics,
        "docx_structure": structure,
        "pdf_structure": pdf_structure if source_path.suffix.casefold() != ".docx" else None,
        "text_masks": masks,
        "protected_regions": list(protected_regions or []),
        "protected_region_results": protected_results,
        "raster_similarity": raster_score,
        "raster_coverage": raster_coverage,
        "visual_difference": None,
        "issues": issues,
        "provenance": {
            "method": "actual_render_pdf_get_text_dict_and_pixel_compare",
            "source_pdf": original.get("pagination"),
            "candidate_pdf": target.get("pagination"),
            "styles": "unknown_when_translated_multi_run",
            "signature_authenticity": "not_verified",
        },
        "measured_components": len(measured_components),
    }


def render_metrics(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility alias for callers using the noun form."""
    return measure_render_fidelity(*args, **kwargs)


def measure_render(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return measure_render_fidelity(*args, **kwargs)


def build_render_result(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return measure_render_fidelity(*args, **kwargs)


def measure_render_metrics(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return measure_render_fidelity(*args, **kwargs)


def render_pair(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return measure_render_fidelity(*args, **kwargs)


def extract_docx_structure(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return parse_docx_structure(*args, **kwargs)


def compare_structure(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return compare_docx_structure(*args, **kwargs)


def score_render(ir: dict[str, Any], source: Any, candidate: Any, **kwargs: Any) -> dict[str, Any]:
    """Convenience adapter: produce measured render evidence then call score_visual."""
    from app.ai.vision.scorer import score_visual

    result = measure_render_fidelity(source, candidate, source_ir=ir, **kwargs)
    score = score_visual(ir, result)
    result["visual_score"] = score
    return result


__all__ = [
    "build_render_result",
    "compare_docx_structure",
    "compare_structure",
    "extract_docx_structure",
    "measure_render",
    "measure_render_fidelity",
    "measure_render_metrics",
    "parse_docx_structure",
    "render_metrics",
    "render_pair",
    "score_render",
]
