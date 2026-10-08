"""Hierarchical OOXML ingestion, including nested tables and shared header parts."""

from __future__ import annotations

import hashlib
import zipfile

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _xml(node):
    return etree.tostring(node, encoding="unicode") if node is not None else None


def collect_docx_content(path, make_block):
    from .docx_fidelity import paragraph_metadata

    blocks, tables, sections, media = [], [], [], []
    order = 0
    with zipfile.ZipFile(path) as archive:
        parts = ["word/document.xml"] + sorted(
            name
            for name in archive.namelist()
            if name.startswith(
                ("word/header", "word/footer", "word/footnotes", "word/endnotes", "word/comments")
            )
            and name.endswith(".xml")
        )
        for part in parts:
            root = etree.fromstring(
                archive.read(part), etree.XMLParser(resolve_entities=False, no_network=True)
            )
            table_indices = {t: i for i, t in enumerate(root.iter(W + "tbl"))}
            # lxml proxies are stable while retained in this mapping.
            paths = {}

            def index_paths(element, current, paths=paths):
                paths[element] = current
                for index, child in enumerate(element):
                    index_paths(child, current + [index])

            index_paths(root, [])

            def add_paragraph(element, parent_id, base_ref=None, part=part, paths=paths, root=root):
                nonlocal order
                text = "".join(node.text or "" for node in element.iter(W + "t"))
                bid = f"docx-{len(blocks):05d}"
                if text.strip():
                    base_ref = base_ref or {}
                    if (
                        part == "word/document.xml"
                        and "table_index" in base_ref
                        and len(paths[element]) == 5
                    ):
                        bid = f"p001-cell-{base_ref['table_index']:03d}-{base_ref['row_index']:03d}-{base_ref['cell_index']:03d}-par-{base_ref['cell_paragraph_index']:03d}"
                    elif part == "word/document.xml" and len(paths[element]) == 2:
                        body = root.find(W + "body")
                        bid = f"p001-par-{body.findall(W + 'p').index(element):04d}"
                    ref = {**base_ref, "xml_part": part, "paragraph_path": paths[element]}
                    block = make_block(text, bid, order, ref)
                    block.update(
                        {
                            "parent_id": parent_id,
                            "order": order,
                            "type": "paragraph",
                            "source_language": block.get("language"),
                            "target_language": "fra",
                            "translation_status": "pending",
                            **paragraph_metadata(element),
                        }
                    )
                    blocks.append(block)
                    order += 1
                    return bid
                return None

            def walk_table(element, parent_id, part=part, paths=paths, table_indices=table_indices):
                ti = table_indices[element]
                tid = f"{part}-table-{ti:04d}"
                grid = element.find(W + "tblGrid")
                row_elements = element.findall(W + "tr")
                record = {
                    "id": tid,
                    "page": 1,
                    "parent_id": parent_id,
                    "xml_part": part,
                    "rows": len(row_elements),
                    "columns": len(grid) if grid is not None else 0,
                    "grid_widths": [int(c.get(W + "w", 0)) for c in grid]
                    if grid is not None
                    else [],
                    "style_xml": _xml(element.find(W + "tblPr")),
                    "cells": [],
                    "row_records": [],
                    "coordinates_kind": "logical",
                    "provenance": "docx:original_ooxml",
                }
                tables.append(record)
                active = {}
                for ri, row in enumerate(row_elements):
                    row_id = f"{tid}-row-{ri:03d}"
                    row_pr = row.find(W + "trPr")
                    before = row_pr.find(W + "gridBefore") if row_pr is not None else None
                    column = int(before.get(W + "val", 0)) if before is not None else 0
                    row_rec = {
                        "id": row_id,
                        "parent_id": tid,
                        "row": ri,
                        "cell_ids": [],
                        "style_xml": _xml(row_pr),
                    }
                    record["row_records"].append(row_rec)
                    for _ci, cell in enumerate(row.findall(W + "tc")):
                        props = cell.find(W + "tcPr")
                        span_node = props.find(W + "gridSpan") if props is not None else None
                        span = int(span_node.get(W + "val", 1)) if span_node is not None else 1
                        merge = props.find(W + "vMerge") if props is not None else None
                        merge_state = (
                            merge.get(W + "val", "continue") if merge is not None else None
                        )
                        cid = f"{row_id}-cell-{column:03d}"
                        anchor = active.get(column) if merge_state == "continue" else None
                        if anchor:
                            anchor["row_span"] += 1
                        cell_rec = {
                            "id": cid,
                            "parent_id": row_id,
                            "row": ri,
                            "column": column,
                            "row_span": 1,
                            "column_span": span,
                            "grid_span": span,
                            "v_merge": merge_state,
                            "merge_parent_id": anchor["id"] if anchor else None,
                            "style_xml": _xml(props),
                            "paragraph_ids": [],
                            "table_ids": [],
                            "text": "",
                            "source_ref": {
                                "table_index": ti,
                                "row_index": ri,
                                "cell_index": column,
                                "xml_part": part,
                                "cell_path": paths[cell],
                            },
                        }
                        if merge_state == "restart":
                            active[column] = cell_rec
                        elif merge_state is None:
                            active.pop(column, None)
                        record["cells"].append(cell_rec)
                        row_rec["cell_ids"].append(cid)
                        pi = 0
                        for child in cell:
                            if child.tag == W + "p":
                                bid = add_paragraph(
                                    child,
                                    cid,
                                    {**cell_rec["source_ref"], "cell_paragraph_index": pi},
                                )
                                if bid:
                                    cell_rec["paragraph_ids"].append(bid)
                                pi += 1
                            elif child.tag == W + "tbl":
                                nested = walk_table(child, cid)
                                cell_rec["table_ids"].append(nested)
                        cell_rec["block_ids"] = list(cell_rec["paragraph_ids"])
                        cell_rec["text"] = "\n".join(
                            next(b["text"] for b in blocks if b["id"] == bid)
                            for bid in cell_rec["paragraph_ids"]
                        )
                        column += span
                    record["columns"] = max(record["columns"], column)
                return tid

            container = root.find(W + "body") if part == "word/document.xml" else root

            def walk_container(current, parent_id):
                for child in current:
                    if child.tag == W + "p":
                        add_paragraph(child, parent_id)
                    elif child.tag == W + "tbl":
                        walk_table(child, parent_id)
                    else:
                        walk_container(child, parent_id)

            walk_container(container, part)
            # Any paragraph behind an unusual table wrapper is still surfaced,
            # never silently omitted. Numeric XML refs preserve its container.
            mapped_paths = {
                tuple(b["source_ref"]["paragraph_path"])
                for b in blocks
                if b["source_ref"]["xml_part"] == part
            }
            for paragraph in root.iter(W + "p"):
                if tuple(paths[paragraph]) not in mapped_paths and not any(
                    ancestor.tag == W + "p" for ancestor in paragraph.iterancestors()
                ):
                    add_paragraph(paragraph, part)
            sections.extend(
                {"xml_part": part, "properties_xml": _xml(node)} for node in root.iter(W + "sectPr")
            )
        for name in archive.namelist():
            if name.startswith("word/media/") and not name.endswith("/"):
                media.append(
                    {
                        "id": name,
                        "type": "protected_visual",
                        "subtype": "embedded_image_candidate",
                        "source_id": hashlib.sha256(archive.read(name)).hexdigest(),
                        "editable": False,
                        "provenance": "docx_original_package_media",
                        "bbox": None,
                        "authenticity_verified": False,
                    }
                )
    return blocks, tables, {"sections": sections, "images": media}
