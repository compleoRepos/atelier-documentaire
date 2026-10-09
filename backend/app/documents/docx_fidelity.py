"""Conservative, package-preserving DOCX text fidelity helpers.

The module deliberately does not use :mod:`python-docx` to save a document.  A
DOCX is an OPC/ZIP package and a normal ``Document.save`` may rewrite or drop
parts which are unrelated to a text replacement.  The functions here edit only
``w:t`` values in the selected XML part and copy every other package member.

No function in this module makes a semantic alignment claim: redistribution is
only a proportional, word-boundary heuristic and ambiguous structures are
returned as ``REVIEW_REQUIRED`` instead of being silently flattened.
"""

from __future__ import annotations

import copy
import posixpath
import re
import shutil
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:  # lxml is installed with python-docx in the normal backend environment.
    from lxml import etree as _XML
except Exception:  # pragma: no cover - stdlib fallback is intentionally supported.
    _XML = ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS, "r": R_NS, "pr": PR_NS}


def _q(name: str, namespace: str = W_NS) -> str:
    return name if name.startswith("{") else f"{{{namespace}}}{name}"


def _local(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _is(element: Any, name: str) -> bool:
    return getattr(element, "tag", "") == _q(name)


def _children(element: Any) -> list[Any]:
    return list(element) if element is not None else []


def _iter(element: Any, name: str | None = None) -> Iterable[Any]:
    if element is None:
        return ()
    if name is None:
        return element.iter()
    return (node for node in element.iter() if _is(node, name))


def _attr(element: Any, name: str, namespace: str = W_NS) -> str | None:
    if element is None:
        return None
    return element.get(name if name.startswith("{") else _q(name, namespace))


def _text(node: Any) -> str:
    return node.text or ""


def _serialize(node: Any) -> str:
    if _XML is ET:
        return ET.tostring(node, encoding="unicode")
    return _XML.tostring(node, encoding="unicode", with_tail=False)


def _serialize_bytes(root: Any, original: bytes) -> bytes:
    """Serialize a modified part while retaining the original XML declaration style."""
    has_declaration = original.lstrip().startswith(b"<?xml")
    encoding = "UTF-8"
    if _XML is ET:
        ET.register_namespace("w", W_NS)
        ET.register_namespace("r", R_NS)
        ET.register_namespace("xml", XML_NS)
        data = ET.tostring(root, encoding=encoding, xml_declaration=has_declaration)
    else:
        standalone = None
        match = re.search(rb"standalone\s*=\s*['\"](yes|no)['\"]", original[:200])
        if match:
            standalone = match.group(1).decode("ascii") == "yes"
        data = _XML.tostring(
            root,
            encoding=encoding,
            xml_declaration=has_declaration,
            standalone=standalone,
        )
    return data


def _parse_xml(data: bytes) -> Any:
    if _XML is ET:
        return ET.fromstring(data)
    parser = _XML.XMLParser(remove_blank_text=False, resolve_entities=False, no_network=True)
    return _XML.fromstring(data, parser=parser)


def _parent_map(root: Any) -> dict[Any, Any]:
    return {child: parent for parent in root.iter() for child in parent}


def _path_from_root(root: Any, node: Any) -> list[int]:
    parents = _parent_map(root)
    path: list[int] = []
    current = node
    while current is not root:
        parent = parents.get(current)
        if parent is None:
            raise ValueError("element is not below root")
        path.append(_children(parent).index(current))
        current = parent
    return list(reversed(path))


def numeric_paragraph_path(root: Any, paragraph: Any) -> list[int]:
    """Return a deterministic child-index path from an XML part root to ``w:p``.

    The path is JSON-friendly and intentionally does not rely on namespace
    prefixes.  It can be supplied back as ``source_ref["paragraph_path"]``.
    """
    if not _is(paragraph, "p"):
        raise ValueError("paragraph_path requires a w:p element")
    return _path_from_root(root, paragraph)


def _parse_numeric_path(value: Any) -> list[int] | None:
    if isinstance(value, (list, tuple)):
        try:
            if any(
                isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in value
            ):
                return None
            return list(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if re.fullmatch(r"/?\d+(?:[/.]\d+)*", raw):
            return [int(part) for part in re.split(r"[/.]", raw.strip("/."))]
    return None


def _find_numeric_path(root: Any, value: Any) -> Any | None:
    path = _parse_numeric_path(value)
    if path is not None:
        current = root
        try:
            for index in path:
                current = _children(current)[index]
            return current
        except (IndexError, TypeError):
            return None
    # Also accept a deterministic XPath written with numeric predicates, for
    # example /w:document[1]/w:body[1]/w:tbl[1]/w:tr[1]/w:tc[1]/w:p[1].
    if not isinstance(value, str):
        return None
    tokens = [token for token in value.split("/") if token]
    current = root
    for token in tokens:
        match = re.fullmatch(r"(?:[^\[]+)?\[(\d+)\]", token)
        if not match:
            return None
        ordinal = int(match.group(1))
        name_match = re.match(r"([^\[]+)", token)
        wanted = name_match.group(1).split(":")[-1] if name_match else None
        candidates = [
            child for child in _children(current) if wanted is None or _local(child.tag) == wanted
        ]
        if ordinal < 1 or ordinal > len(candidates):
            return None
        current = candidates[ordinal - 1]
    return current


def _node_path(root: Any, node: Any) -> str:
    return "/".join(str(index) for index in _path_from_root(root, node))


def _run_style_xml(run: Any) -> str:
    rpr = next((child for child in _children(run) if _is(child, "rPr")), None)
    return _serialize(rpr) if rpr is not None else ""


def _style_signature(run: Any) -> str:
    return _run_style_xml(run)


def _field_inventory(element: Any, root: Any | None = None) -> tuple[list[dict], set[Any]]:
    """Return fields and the w:t nodes which must not be edited."""
    root = element if root is None else root
    protected: set[Any] = set()
    fields: list[dict] = []

    for simple in _iter(element, "fldSimple"):
        result_nodes = [node for node in _iter(simple, "t")]
        protected.update(node for node in _iter(simple))
        fields.append(
            {
                "kind": "simple",
                "instruction": _attr(simple, "instr"),
                "result_text": "".join(_text(node) for node in result_nodes),
                "result_nodes": [_node_path(root, node) for node in result_nodes],
                "protected": True,
            }
        )

    # Complex fields are tracked in document order.  The result between
    # separate/end is protected, as are the instruction and field markers.
    stack: list[dict] = []
    for node in element.iter():
        if _is(node, "fldChar"):
            kind = _attr(node, "fldCharType") or ""
            if kind == "begin":
                field = {
                    "kind": "complex",
                    "instruction": "",
                    "result_text": "",
                    "result_nodes": [],
                    "protected": True,
                    "_separated": False,
                }
                fields.append(field)
                stack.append(field)
                protected.add(node)
            elif kind == "separate":
                if stack:
                    stack[-1]["_separated"] = True
                protected.add(node)
            elif kind == "end":
                if stack:
                    stack.pop()
                protected.add(node)
        elif _is(node, "instrText"):
            if stack:
                stack[-1]["instruction"] += _text(node)
            protected.add(node)
        elif _is(node, "t") and stack:
            protected.add(node)
            if stack[-1].get("_separated"):
                stack[-1]["result_text"] += _text(node)
                stack[-1]["result_nodes"].append(_node_path(root, node))

    for field in fields:
        field.pop("_separated", None)
    return fields, protected


def paragraph_metadata(element: Any) -> dict:
    """Describe paragraph structure without modifying it.

    ``element`` is normally a ``w:p`` XML element.  The result intentionally
    includes XML snapshots of styles/properties so callers can audit whether a
    replacement crossed a formatting or structural boundary.  Field results
    are explicitly marked protected.
    """
    if not _is(element, "p"):
        raise ValueError("paragraph_metadata expects a w:p element")
    fields, field_protected = _field_inventory(element, element)
    runs: list[dict] = []
    for index, run in enumerate(_iter(element, "r")):
        text_nodes = [node for node in _iter(run, "t")]
        runs.append(
            {
                "index": index,
                "path": _node_path(element, run),
                "text": "".join(_text(node) for node in text_nodes),
                "text_nodes": [_node_path(element, node) for node in text_nodes],
                "style_xml": _run_style_xml(run),
                "style_signature": _style_signature(run),
                "properties_xml": _run_style_xml(run),
                "protected": any(node in field_protected for node in text_nodes),
            }
        )
    hyperlinks = []
    for hyperlink in _iter(element, "hyperlink"):
        hyperlinks.append(
            {
                "path": _node_path(element, hyperlink),
                "relationship_id": _attr(hyperlink, "id", R_NS),
                "anchor": _attr(hyperlink, "anchor"),
                "text": "".join(_text(node) for node in _iter(hyperlink, "t")),
            }
        )
    bookmarks = [
        {
            "kind": _local(node.tag),
            "id": _attr(node, "id"),
            "name": _attr(node, "name"),
            "path": _node_path(element, node),
        }
        for node in element.iter()
        if _is(node, "bookmarkStart") or _is(node, "bookmarkEnd")
    ]
    tabs = [{"path": _node_path(element, node)} for node in _iter(element, "tab")]
    breaks = [
        {"path": _node_path(element, node), "kind": _local(node.tag), "type": _attr(node, "type")}
        for node in element.iter()
        if _is(node, "br") or _is(node, "cr")
    ]
    ppr = next((child for child in _children(element) if _is(child, "pPr")), None)
    properties = {
        "paragraph_xml": _serialize(ppr) if ppr is not None else "",
        "paragraph_style": _attr(next((child for child in _iter(ppr, "pStyle")), None), "val")
        if ppr is not None
        else None,
        "run_properties_xml": [run["properties_xml"] for run in runs],
    }
    text_nodes = [node for node in _iter(element, "t")]
    text = "".join(_text(node) for node in text_nodes)
    style_xml = [run["style_xml"] for run in runs]
    return {
        "text": text,
        "runs": runs,
        "style_xml": style_xml,
        "styles": style_xml,
        "hyperlinks": hyperlinks,
        "bookmarks": bookmarks,
        "fields": fields,
        "field_result_protected": bool(fields),
        "tabs": tabs,
        "breaks": breaks,
        "properties": properties,
        "paragraph_properties_xml": properties["paragraph_xml"],
        "text_nodes": [_node_path(element, node) for node in text_nodes],
    }


def _word_boundaries(target: str) -> list[int]:
    """Return safe split points at whitespace/word boundaries."""
    if not target:
        return [0]
    points = {0, len(target)}
    for index in range(1, len(target)):
        left, right = target[index - 1], target[index]
        if left.isspace() != right.isspace():
            points.add(index)
    return sorted(points)


def _proportional_splits(
    target: str, weights: Sequence[int]
) -> tuple[list[str], list[dict]] | None:
    count = len(weights)
    if count == 1:
        return [target], [{"target_span": [0, len(target)], "boundary": "single_node"}]
    boundaries = _word_boundaries(target)
    if len(boundaries) < count + 1:
        return None
    total = max(1, sum(weights))
    selected = [0]
    trace: list[dict] = []
    for index in range(1, count):
        desired = len(target) * sum(weights[:index]) / total
        candidates = [point for point in boundaries if selected[-1] < point < len(target)]
        if len(candidates) < count - index:
            return None
        point = min(
            candidates, key=lambda candidate: (abs(candidate - desired), candidate > desired)
        )
        selected.append(point)
        boundaries.remove(point)
    selected.append(len(target))
    pieces = [target[start:end] for start, end in zip(selected, selected[1:], strict=False)]
    for index, (start, end) in enumerate(zip(selected, selected[1:], strict=False)):
        trace.append(
            {
                "target_span": [start, end],
                "boundary": "word_boundary"
                if start in _word_boundaries(target)
                else "proportional",
                "piece_index": index,
            }
        )
    return pieces, trace


def _issue(code: str, message: str, severity: str = "warning", **extra: Any) -> dict:
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    return issue


def redistribute_text(element: Any, target: str, *, allow_single_hyperlink: bool = False) -> dict:
    """Safely redistribute ``target`` over existing ``w:t`` nodes.

    Only node text (and, when needed, ``xml:space=preserve``) is changed.  Runs,
    hyperlinks, bookmarks, fields, tabs, breaks, properties, tails, and all
    other XML nodes remain in place.  Ambiguous structures are not edited.
    """
    if not _is(element, "p"):
        raise ValueError("redistribute_text expects a w:p element")
    if not isinstance(target, str):
        raise ValueError("DOCX target must be text, not null/object")
    metadata = paragraph_metadata(element)
    original = metadata["text"]
    all_nodes = [node for node in _iter(element, "t")]
    fields, field_protected = _field_inventory(element, element)
    trace_base = {
        "semantic_alignment": False,
        "source_text": original,
        "target_text": target,
        "node_count": len(all_nodes),
    }
    if target == original:
        return {
            "applied": False,
            "node_count": len(all_nodes),
            "trace": {**trace_base, "segments": []},
            "status": "NO_CHANGE",
            "issues": [],
        }
    issues: list[dict] = []
    if any(node is not element and _is(node, "p") for node in element.iter()):
        issues.append(
            _issue(
                "DOCX_NESTED_TEXT_REQUIRES_REVIEW",
                "Nested text box/paragraph boundaries cannot be proportionally rewritten.",
                "error",
            )
        )
    if fields:
        issues.append(
            _issue(
                "DOCX_FIELD_RESULT_PROTECTED",
                "Simple/complex field code or result detected; a changed field result is not rewritten.",
                "error",
            )
        )
    if metadata["hyperlinks"] and not allow_single_hyperlink:
        issues.append(
            _issue(
                "DOCX_HYPERLINK_BOUNDARY_AMBIGUOUS",
                "Hyperlink boundaries are ambiguous for proportional redistribution.",
                "error",
            )
        )
    elif metadata["hyperlinks"]:
        hyperlink_nodes = list(_iter(element, "hyperlink"))
        hyperlink_text_nodes = {
            node for hyperlink in hyperlink_nodes for node in _iter(hyperlink, "t")
        }
        # A paragraph containing only one hyperlink has an unambiguous writable
        # boundary: redistribute inside its existing runs and retain r:id.
        # Mixed hyperlink/non-hyperlink paragraphs still require review because
        # proportional splitting could silently move link text across the edge.
        if len(hyperlink_nodes) != 1 or any(
            node not in hyperlink_text_nodes for node in all_nodes if node not in field_protected
        ):
            issues.append(
                _issue(
                    "DOCX_HYPERLINK_BOUNDARY_AMBIGUOUS",
                    "Hyperlink boundaries are ambiguous for proportional redistribution.",
                    "error",
                )
            )
    if metadata["bookmarks"]:
        issues.append(
            _issue(
                "DOCX_BOOKMARK_BOUNDARY_AMBIGUOUS",
                "Bookmark boundaries are ambiguous for proportional redistribution.",
                "error",
            )
        )
    if metadata["tabs"] or metadata["breaks"]:
        issues.append(
            _issue(
                "DOCX_LAYOUT_MARKER_AMBIGUOUS",
                "Tabs/breaks are preserved but make a changed paragraph layout ambiguous.",
                "error",
            )
        )
    writable = [node for node in all_nodes if node not in field_protected]
    if not writable:
        issues.append(
            _issue("DOCX_TEXT_NODE_MISSING", "No unprotected w:t node is available.", "error")
        )
    styles = set()
    parents = _parent_map(element)
    for node in writable:
        parent = parents.get(node)
        while parent is not None and not _is(parent, "r"):
            parent = parents.get(parent)
        styles.add(_style_signature(parent) if parent is not None else "")
    if len(styles) > 1:
        issues.append(
            _issue(
                "DOCX_MULTI_STYLE_BOUNDARY_AMBIGUOUS",
                "Translation crosses multiple run styles; no silent style assignment is claimed.",
                "warning",
            )
        )
    if any(issue["severity"] == "error" for issue in issues):
        return {
            "applied": False,
            "node_count": len(all_nodes),
            "trace": trace_base,
            "status": "REVIEW_REQUIRED",
            "issues": issues,
        }

    nonempty = [node for node in writable if _text(node)]
    if not nonempty:
        return {
            "applied": False,
            "node_count": len(all_nodes),
            "trace": trace_base,
            "status": "REVIEW_REQUIRED",
            "issues": [_issue("DOCX_TEXT_NODE_MISSING", "All w:t nodes are empty.", "error")],
        }
    weights = [max(1, len(_text(node))) for node in nonempty]
    split = _proportional_splits(target, weights)
    if split is None:
        return {
            "applied": False,
            "node_count": len(all_nodes),
            "trace": trace_base,
            "status": "REVIEW_REQUIRED",
            "issues": [
                _issue(
                    "DOCX_WORD_BOUNDARY_UNAVAILABLE",
                    "Target cannot be distributed over the existing nodes at word boundaries.",
                    "error",
                )
            ],
        }
    pieces, segment_trace = split
    # Keep separator whitespace with the source run that owned it when possible.
    # This is lexical whitespace ownership, never a semantic word alignment.
    for i in range(len(pieces) - 1):
        if _text(nonempty[i])[-1:].isspace():
            prefix = pieces[i + 1][: len(pieces[i + 1]) - len(pieces[i + 1].lstrip())]
            if prefix:
                pieces[i] += prefix
                pieces[i + 1] = pieces[i + 1][len(prefix) :]
                segment_trace[i]["target_span"][1] += len(prefix)
                segment_trace[i + 1]["target_span"][0] += len(prefix)
    # Commit only after every ambiguity check succeeds.
    source_cursor = 0
    segments = []
    for _index, (node, piece, trace) in enumerate(
        zip(nonempty, pieces, segment_trace, strict=False)
    ):
        source_piece = _text(node)
        node.text = piece
        if piece[:1].isspace() or piece[-1:].isspace():
            node.set(f"{{{XML_NS}}}space", "preserve")
        trace = {
            **trace,
            "node_index": all_nodes.index(node),
            "source_span": [source_cursor, source_cursor + len(source_piece)],
            "source_text": source_piece,
            "target_text": piece,
            "semantic_alignment": False,
        }
        source_cursor += len(source_piece)
        segments.append(trace)
    return {
        "applied": True,
        "node_count": len(all_nodes),
        "trace": {**trace_base, "segments": segments},
        "status": "REVIEW_REQUIRED" if issues else "APPLIED",
        "issues": issues
        + [
            _issue(
                "DOCX_PROPORTIONAL_REDISTRIBUTION",
                "Text was distributed proportionally at word boundaries; no semantic alignment is asserted.",
                "info",
            )
        ],
    }


def _part_name(value: str) -> str:
    value = str(value).replace("\\", "/").lstrip("/")
    return posixpath.normpath(value)


def _relationship_targets(document_data: bytes, rels_data: bytes) -> dict[str, str]:
    try:
        root = _parse_xml(rels_data)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for rel in root.iter():
        if _local(rel.tag) != "Relationship":
            continue
        rid = rel.get("Id")
        target = rel.get("Target")
        rel_type = rel.get("Type", "")
        if not rid or not target:
            continue
        if rel_type.rsplit("/", 1)[-1] not in {"header", "footer"}:
            continue
        base = "word/"
        target = (
            _part_name(posixpath.join(base, target))
            if not target.startswith("/")
            else _part_name(target)
        )
        out[rid] = target
    return out


def _section_properties(document_root: Any) -> list[Any]:
    body = next((node for node in _children(document_root) if _is(node, "body")), None)
    if body is None:
        return []
    props: list[Any] = []
    for child in _children(body):
        if _is(child, "p"):
            ppr = next((node for node in _children(child) if _is(node, "pPr")), None)
            sect = (
                next((node for node in _children(ppr) if _is(node, "sectPr")), None)
                if ppr is not None
                else None
            )
            if sect is not None:
                props.append(sect)
    final = next((node for node in _children(body) if _is(node, "sectPr")), None)
    if final is not None:
        props.append(final)
    return props


def _header_footer_part(
    document_root: Any, rels_data: bytes, source_ref: Mapping[str, Any]
) -> str | None:
    kind = source_ref.get("header_footer")
    if isinstance(kind, Mapping):
        section_value = kind.get(
            "section", kind.get("section_index", source_ref.get("section_index", 0))
        )
        kind = kind.get("kind", kind.get("type"))
    else:
        section_value = source_ref.get("section_index", source_ref.get("section", 0))
    if kind not in {"header", "footer"}:
        return None
    sections = _section_properties(document_root)
    try:
        section_index = int(section_value)
    except (TypeError, ValueError):
        return None
    if section_index < 0 or section_index >= len(sections):
        return None
    wanted = next(
        (node for node in _children(sections[section_index]) if _is(node, f"{kind}Reference")), None
    )
    if wanted is None:
        return None
    rid = _attr(wanted, "id", R_NS)
    return _relationship_targets(b"", rels_data).get(rid) if rid else None


def _body_paragraph(root: Any, ref: Mapping[str, Any]) -> Any | None:
    body = next((node for node in _children(root) if _is(node, "body")), None)
    if body is None:
        return None
    try:
        index = int(ref["paragraph_index"])
    except (KeyError, TypeError, ValueError):
        return None
    paragraphs = [node for node in _children(body) if _is(node, "p")]
    return paragraphs[index] if 0 <= index < len(paragraphs) else None


def _table_paragraph(root: Any, ref: Mapping[str, Any]) -> Any | None:
    body = next((node for node in _children(root) if _is(node, "body")), None)
    if body is None:
        return None
    try:
        table_index = int(ref["table_index"])
        row_index = int(ref["row_index"])
        cell_index = int(ref["cell_index"])
        paragraph_index = int(ref.get("cell_paragraph_index", 0))
    except (KeyError, TypeError, ValueError):
        return None
    tables = [node for node in _children(body) if _is(node, "tbl")]
    if not (0 <= table_index < len(tables)):
        return None
    rows = [node for node in _children(tables[table_index]) if _is(node, "tr")]
    if not (0 <= row_index < len(rows)):
        return None
    cells = [node for node in _children(rows[row_index]) if _is(node, "tc")]
    if not (0 <= cell_index < len(cells)):
        return None
    paragraphs = [node for node in _children(cells[cell_index]) if _is(node, "p")]
    return paragraphs[paragraph_index] if 0 <= paragraph_index < len(paragraphs) else None


def _resolve_paragraph(root: Any, source_ref: Mapping[str, Any]) -> Any | None:
    path = source_ref.get("paragraph_path")
    if path is not None:
        node = _find_numeric_path(root, path)
        return node if node is not None and _is(node, "p") else None
    if "table_index" in source_ref:
        return _table_paragraph(root, source_ref)
    return _body_paragraph(root, source_ref)


def _resolve_header_paragraph(root: Any, source_ref: Mapping[str, Any]) -> Any | None:
    if source_ref.get("paragraph_path") is not None:
        node = _find_numeric_path(root, source_ref["paragraph_path"])
        return node if node is not None and _is(node, "p") else None
    try:
        index = int(source_ref.get("paragraph_index", 0))
    except (TypeError, ValueError):
        return None
    paragraphs = [node for node in _children(root) if _is(node, "p")]
    return paragraphs[index] if 0 <= index < len(paragraphs) else None


def _write_package(source: Path, output: Path, modified: Mapping[str, bytes]) -> None:
    if not modified:
        shutil.copyfile(source, output)
        return
    with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(output, "w") as candidate:
        for info in original.infolist():
            data = modified.get(info.filename, original.read(info))
            cloned = copy.copy(info)
            candidate.writestr(cloned, data)


def _paragraph_in_complex_field(root, paragraph):
    """Word field ranges can cross paragraph boundaries (e.g. TOC)."""
    depth = 0
    paragraphs = list(root.iter(_q("p")))
    for current in paragraphs:
        inside = depth > 0
        for node in current.iter():
            if not _is(node, "fldChar"):
                continue
            kind = _attr(node, "fldCharType")
            if kind == "begin":
                depth += 1
                inside = True
            elif kind == "end":
                inside = inside or depth > 0
                depth = max(0, depth - 1)
        if current is paragraph:
            return inside
    return False


def edit_docx_package(
    source: str | Path, out: str | Path, replacements: Sequence[Mapping[str, Any]]
) -> dict:
    """Edit selected paragraphs in a DOCX package without a python-docx save.

    ``source_ref`` supports the pipeline's body/table/header/footer indexes and
    additionally ``xml_part`` plus a numeric ``paragraph_path`` (a list such
    as ``[0, 1, 0, 2]`` or ``"0/1/0/2"``) for nested tables and arbitrary
    header/footer parts.  ``xml_part`` is relative to the package root.
    """
    source_path = Path(source).expanduser().resolve()
    output_path = Path(out).expanduser().resolve()
    if source_path == output_path or (output_path.exists() and source_path.samefile(output_path)):
        raise ValueError("source and out must be different paths")
    if not source_path.is_file():
        raise FileNotFoundError(source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    replacements = list(replacements or [])
    results: list[dict] = []
    issues: list[dict] = []
    modified: dict[str, bytes] = {}
    roots: dict[str, Any] = {}
    originals: dict[str, bytes] = {}

    with zipfile.ZipFile(source_path, "r") as package:
        names = set(package.namelist())
        for replacement in replacements:
            rid = replacement.get("id")
            ref = replacement.get("source_ref") or {}
            if not isinstance(ref, Mapping):
                result = {
                    "id": rid,
                    "applied": False,
                    "status": "REVIEW_REQUIRED",
                    "issues": [
                        _issue("DOCX_SOURCE_REF_INVALID", "source_ref must be an object.", "error")
                    ],
                }
                results.append(result)
                continue
            part = _part_name(ref.get("xml_part", "word/document.xml"))
            if "header_footer" in ref and "xml_part" not in ref:
                if "word/document.xml" not in roots:
                    originals["word/document.xml"] = package.read("word/document.xml")
                    roots["word/document.xml"] = _parse_xml(originals["word/document.xml"])
                rels_name = "word/_rels/document.xml.rels"
                rels_data = package.read(rels_name) if rels_name in names else b""
                resolved = _header_footer_part(roots["word/document.xml"], rels_data, ref)
                if resolved:
                    part = resolved
            if part not in names:
                result = {
                    "id": rid,
                    "applied": False,
                    "status": "REVIEW_REQUIRED",
                    "issues": [
                        _issue("DOCX_XML_PART_NOT_FOUND", f"XML part not found: {part}", "error")
                    ],
                }
                results.append(result)
                continue
            if part not in roots:
                originals[part] = package.read(part)
                try:
                    roots[part] = _parse_xml(originals[part])
                except Exception as exc:
                    result = {
                        "id": rid,
                        "applied": False,
                        "status": "REVIEW_REQUIRED",
                        "issues": [_issue("DOCX_XML_PARSE_FAILED", str(exc), "error")],
                    }
                    results.append(result)
                    continue
            root = roots[part]
            paragraph = (
                _resolve_header_paragraph(root, ref)
                if ref.get("header_footer")
                or part.startswith("word/header")
                or part.startswith("word/footer")
                else _resolve_paragraph(root, ref)
            )
            if paragraph is None:
                result = {
                    "id": rid,
                    "applied": False,
                    "status": "REVIEW_REQUIRED",
                    "issues": [
                        _issue(
                            "DOCX_PARAGRAPH_REF_NOT_FOUND",
                            "source_ref does not resolve to a w:p in the current XML part.",
                            "error",
                        )
                    ],
                }
                results.append(result)
                continue
            try:
                target = replacement.get("target", "")
                if (
                    _paragraph_in_complex_field(root, paragraph)
                    and target != paragraph_metadata(paragraph)["text"]
                ):
                    result = {
                        "applied": False,
                        "node_count": 0,
                        "trace": {},
                        "status": "REVIEW_REQUIRED",
                        "issues": [
                            _issue(
                                "DOCX_FIELD_RESULT_PROTECTED",
                                "Field range crosses paragraph boundary; original result protected.",
                                "error",
                            )
                        ],
                    }
                else:
                    result = redistribute_text(paragraph, target, allow_single_hyperlink=True)
            except Exception as exc:
                result = {
                    "applied": False,
                    "node_count": 0,
                    "trace": {},
                    "status": "REVIEW_REQUIRED",
                    "issues": [_issue("DOCX_REPLACEMENT_ERROR", str(exc), "error")],
                }
            result = {"id": rid, **result, "xml_part": part}
            results.append(result)

    for part, root in roots.items():
        if part in originals:
            candidate_data = _serialize_bytes(root, originals[part])
            if (
                any(result.get("applied") and result.get("xml_part") == part for result in results)
                and candidate_data != originals[part]
            ):
                modified[part] = candidate_data
    _write_package(source_path, output_path, modified)
    changed = sum(1 for result in results if result.get("applied"))
    issues.extend(issue for result in results for issue in result.get("issues", []))
    status = (
        "REVIEW_REQUIRED"
        if any(issue.get("severity") == "error" for issue in issues)
        or any(result.get("status") == "REVIEW_REQUIRED" for result in results)
        else ("APPLIED" if changed else "NO_CHANGE")
    )
    return {
        "output_path": str(output_path),
        "status": status,
        "applied": changed > 0,
        "changed_count": changed,
        # Stable integration names used by the analysis/reconstruction layer.
        "changed_blocks": changed,
        "redistribution_trace": [
            {
                "id": result.get("id"),
                "xml_part": result.get("xml_part"),
                "trace": result.get("trace", {}),
                "status": result.get("status"),
            }
            for result in results
        ],
        "modified_parts": sorted(modified),
        "replacements": results,
        "issues": issues,
        "package_members_preserved": True,
    }


__all__ = [
    "edit_docx_package",
    "numeric_paragraph_path",
    "paragraph_metadata",
    "redistribute_text",
]
