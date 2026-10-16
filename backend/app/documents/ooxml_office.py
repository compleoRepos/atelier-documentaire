"""RUN28 route A — native XLSX / PPTX translation at OOXML package level.

Only text nodes are rewritten:

* XLSX: shared strings (``xl/sharedStrings.xml``) that are referenced by at
  least one cell, and inline strings (``<c t="inlineStr">``).  Formulas
  (``<f>``), cached values, formula-result cells (``t="str"``), sheet names,
  defined names, styles, number formats, comments, charts, drawings and every
  other package part are kept byte for byte.
* PPTX: text runs of the slide paragraphs (``a:p``), including tables and
  groups.  Fields (``a:fld``: slide number, date) and line breaks are never
  rewritten.  Notes, layouts, masters, charts and SmartArt are kept byte for
  byte and reported as not translated.

No visual proof is produced here: :func:`verify_office_candidate` checks that
each expected target is present in the candidate, that no other text changed
and that the package, with the edited text nodes blanked, is canonically
identical to the source (formulas, sheet names, styles, relationships...).
"""

from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

VERSION = "ooxml-office-1"
S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
MAIN_PART = {"xlsx": "xl/workbook.xml", "pptx": "ppt/presentation.xml"}
_CELL = re.compile(r"^([A-Z]{1,3})(\d{1,7})$")
# Parts whose text is kept as is (byte for byte) and only inventoried.
_UNTRANSLATED = {
    "xlsx": (
        r"^xl/comments[^/]*\.xml$",
        r"^xl/threadedComments/",
        r"^xl/drawings/",
        r"^xl/charts/",
    ),
    "pptx": (r"^ppt/notesSlides/", r"^ppt/charts/", r"^ppt/diagrams/"),
}
# Parts this path may rewrite (only their text nodes).
_REWRITABLE = {
    "xlsx": r"^xl/(sharedStrings\.xml|worksheets/[^/]+\.xml)$",
    "pptx": r"^ppt/slides/slide\d+\.xml$",
}


def _q(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def _parse(data: bytes) -> Any:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    return etree.fromstring(data, parser)


def _serialize(root: Any, original: bytes) -> bytes:
    head = original[:256].lstrip()
    if not head.startswith(b"<?xml"):
        return etree.tostring(root, encoding="UTF-8")
    match = re.search(rb'standalone\s*=\s*"(yes|no)"', head)
    standalone = None if match is None else match.group(1) == b"yes"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=standalone)


def _rels(archive: zipfile.ZipFile, part: str) -> dict[str, tuple[str, str]]:
    folder, name = posixpath.split(part)
    rels_name = posixpath.join(folder, "_rels", name + ".rels")
    if rels_name not in archive.namelist():
        return {}
    out: dict[str, tuple[str, str]] = {}
    for rel in _parse(archive.read(rels_name)).iter(_q(PR_NS, "Relationship")):
        if (rel.get("TargetMode") or "").casefold() == "external":
            continue
        target = rel.get("Target") or ""
        path = (
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath(posixpath.join(folder, target))
        )
        out[rel.get("Id") or ""] = (path, rel.get("Type") or "")
    return out


def _cell_position(ref: str | None) -> tuple[int, int]:
    match = _CELL.match(ref or "")
    if not match:
        return (10**8, 10**8)
    column = 0
    for char in match.group(1):
        column = column * 26 + (ord(char) - 64)
    return (int(match.group(2)), column)


def _text_nodes(container: Any) -> list[Any]:
    """``t`` nodes of a shared/inline string, phonetic runs excluded."""
    return [
        node
        for node in container.iter(_q(S_NS, "t"))
        if node.getparent() is not None and node.getparent().tag != _q(S_NS, "rPh")
    ]


def _xlsx_units(archive: zipfile.ZipFile) -> list[dict]:
    workbook = _parse(archive.read(MAIN_PART["xlsx"]))
    rels = _rels(archive, MAIN_PART["xlsx"])
    units = []
    for index, sheet in enumerate(workbook.iter(_q(S_NS, "sheet")), 1):
        part = rels.get(sheet.get(_q(R_NS, "id")) or "", (None, ""))[0]
        units.append(
            {
                "number": index,
                "name": sheet.get("name") or "",
                "part": part,
                "hidden": (sheet.get("state") or "visible") != "visible",
            }
        )
    return units


def _collect_xlsx(archive: zipfile.ZipFile) -> dict:
    names = set(archive.namelist())
    units = _xlsx_units(archive)
    sst_part = next(
        (
            path
            for path, kind in _rels(archive, MAIN_PART["xlsx"]).values()
            if kind.endswith("/sharedStrings")
        ),
        "xl/sharedStrings.xml",
    )
    shared: list[str] = []
    if sst_part in names:
        root = _parse(archive.read(sst_part))
        shared = [
            "".join(node.text or "" for node in _text_nodes(si))
            for si in root.findall(_q(S_NS, "si"))
        ]
    uses: dict[int, list[tuple[int, str]]] = {}
    blocks: list[dict] = []
    formulas: list[tuple[str, str, str]] = []
    formula_text_cells = 0
    header_footer = False
    for unit in units:
        part = unit["part"]
        if not part or part not in names:
            continue
        root = _parse(archive.read(part))
        for cell in root.iter(_q(S_NS, "c")):
            ref = cell.get("r") or ""
            formula = cell.find(_q(S_NS, "f"))
            if formula is not None:
                formulas.append((part, ref, etree.tostring(formula, method="c14n").decode()))
            kind = cell.get("t")
            if kind == "s":
                value = cell.find(_q(S_NS, "v"))
                try:
                    index = int((value.text or "").strip()) if value is not None else -1
                except ValueError:
                    continue
                uses.setdefault(index, []).append((unit["number"], ref))
            elif kind == "inlineStr":
                inline = cell.find(_q(S_NS, "is"))
                text = (
                    "".join(n.text or "" for n in _text_nodes(inline)) if inline is not None else ""
                )
                if text.strip():
                    blocks.append(
                        {
                            "id": f"x{unit['number']:02d}-c{ref}",
                            "page": unit["number"],
                            "text": text,
                            "kind": "cell",
                            "position": _cell_position(ref),
                            "source_ref": {"part": part, "type": "inline", "cell": ref},
                        }
                    )
            elif kind == "str":
                formula_text_cells += 1
        header = root.find(_q(S_NS, "headerFooter"))
        if header is not None and "".join(header.itertext()).strip():
            header_footer = True
    for index in sorted(uses):
        if index < 0 or index >= len(shared) or not shared[index].strip():
            continue
        first_sheet, first_ref = min(uses[index], key=lambda u: (u[0], _cell_position(u[1])))
        blocks.append(
            {
                "id": f"x{first_sheet:02d}-s{index:05d}",
                "page": first_sheet,
                "text": shared[index],
                "kind": "cell",
                "position": _cell_position(first_ref),
                "source_ref": {
                    "part": sst_part,
                    "type": "shared",
                    "si": index,
                    "use_count": len(uses[index]),
                    "cells": [f"{s}!{r}" for s, r in uses[index][:5]],
                },
            }
        )
    blocks.sort(key=lambda b: (b["page"], b["position"], b["id"]))
    return {
        "kind": "xlsx",
        "units": units,
        "blocks": blocks,
        "inventory": {
            "formulas": len(formulas),
            "formula_digest": hashlib.sha256(repr(sorted(formulas)).encode()).hexdigest(),
            "formula_text_cells": formula_text_cells,
            "shared_strings_total": len(shared),
            "shared_strings_used": sum(1 for i in uses if 0 <= i < len(shared)),
            "header_footer_text": header_footer,
            "hidden_units": sum(1 for u in units if u["hidden"]),
            "sheet_names_digest": hashlib.sha256(
                "\x1f".join(u["name"] for u in units).encode()
            ).hexdigest(),
            "untranslated_text_parts": _untranslated(archive, "xlsx"),
        },
    }


def _segments(paragraph: Any) -> list[list[Any]]:
    """Runs (``a:r``) of a paragraph, split on line breaks; fields excluded."""
    segments: list[list[Any]] = [[]]
    for child in paragraph:
        if child.tag == _q(A_NS, "br"):
            segments.append([])
        elif child.tag == _q(A_NS, "r"):
            segments[-1].append(child)
    return segments


def _run_text(run: Any) -> str:
    node = run.find(_q(A_NS, "t"))
    return "" if node is None else node.text or ""


def _autofit(paragraph: Any) -> str | None:
    body = next(
        (a for a in paragraph.iterancestors() if etree.QName(a).localname == "txBody"), None
    )
    props = body.find(_q(A_NS, "bodyPr")) if body is not None else None
    if props is None:
        return None
    for child in props:
        local = etree.QName(child).localname
        if local in {"normAutofit", "spAutoFit", "noAutofit"}:
            return {"normAutofit": "text", "spAutoFit": "shape", "noAutofit": "none"}[local]
    return None


def _pptx_units(archive: zipfile.ZipFile) -> list[dict]:
    presentation = _parse(archive.read(MAIN_PART["pptx"]))
    rels = _rels(archive, MAIN_PART["pptx"])
    listing = presentation.find(_q(P_NS, "sldIdLst"))
    units = []
    for index, slide in enumerate(listing if listing is not None else [], 1):
        part = rels.get(slide.get(_q(R_NS, "id")) or "", (None, ""))[0]
        units.append({"number": index, "name": f"slide-{index}", "part": part, "hidden": False})
    return units


def _collect_pptx(archive: zipfile.ZipFile) -> dict:
    names = set(archive.namelist())
    units = _pptx_units(archive)
    blocks: list[dict] = []
    fields = 0
    for unit in units:
        part = unit["part"]
        if not part or part not in names:
            continue
        root = _parse(archive.read(part))
        unit["hidden"] = root.get("show") == "0"
        for p_index, paragraph in enumerate(root.iter(_q(A_NS, "p"))):
            fields += len(paragraph.findall(_q(A_NS, "fld")))
            segments = _segments(paragraph)
            in_table = any(etree.QName(a).localname == "tbl" for a in paragraph.iterancestors())
            for s_index, runs in enumerate(segments):
                text = "".join(_run_text(run) for run in runs)
                if not text.strip():
                    continue
                suffix = f"-l{s_index}" if len(segments) > 1 else ""
                blocks.append(
                    {
                        "id": f"s{unit['number']:02d}-p{p_index:04d}{suffix}",
                        "page": unit["number"],
                        "text": text,
                        "kind": "table_cell" if in_table else "paragraph",
                        "position": (p_index, s_index),
                        "autofit": _autofit(paragraph),
                        "source_ref": {
                            "part": part,
                            "type": "paragraph",
                            "p": p_index,
                            "segment": s_index,
                        },
                    }
                )
    return {
        "kind": "pptx",
        "units": units,
        "blocks": blocks,
        "inventory": {
            "fields": fields,
            "hidden_units": sum(1 for u in units if u["hidden"]),
            "untranslated_text_parts": _untranslated(archive, "pptx"),
        },
    }


def _untranslated(archive: zipfile.ZipFile, kind: str) -> dict[str, int]:
    """Number of non-empty text nodes in parts this path never rewrites."""
    out: dict[str, int] = {}
    for name in archive.namelist():
        if not name.endswith(".xml") or not any(re.search(p, name) for p in _UNTRANSLATED[kind]):
            continue
        try:
            root = _parse(archive.read(name))
        except etree.XMLSyntaxError:
            out[name] = -1
            continue
        count = sum(
            1
            for node in root.iter()
            if isinstance(node.tag, str)
            and etree.QName(node).localname == "t"
            and (node.text or "").strip()
        )
        if count:
            out[name] = count
    return out


def office_kind(path: str | Path) -> str:
    kind = Path(path).suffix.lower().lstrip(".")
    if kind not in MAIN_PART:
        raise ValueError(f"Format OOXML non pris en charge: {kind}")
    return kind


def collect_office_content(path: str | Path) -> dict:
    kind = office_kind(path)
    with zipfile.ZipFile(path) as archive:
        if MAIN_PART[kind] not in archive.namelist():
            raise ValueError(f"{kind.upper()} incomplet")
        return _collect_xlsx(archive) if kind == "xlsx" else _collect_pptx(archive)


def _style_key(node: Any) -> str:
    return "" if node is None else etree.tostring(node, method="c14n").decode()


def _write_runs(text_nodes: list[Any], styles: list[str], target: str) -> bool:
    """Put ``target`` in the first text node, empty the others.

    Returns True when runs carrying different formatting were merged (the
    first run's formatting then applies to the whole text)."""
    first = text_nodes[0]
    first.text = target
    if target != target.strip() or "\n" in target or "  " in target:
        first.set(XML_SPACE, "preserve")
    for node in text_nodes[1:]:
        node.text = ""
    return len(set(styles)) > 1


def _apply_xlsx(root: Any, replacements: list[dict], issues: list[dict]) -> list[str]:
    applied: list[str] = []
    shared = root.findall(_q(S_NS, "si"))
    cells = {c.get("r"): c for c in root.iter(_q(S_NS, "c")) if c.get("t") == "inlineStr"}
    for rep in replacements:
        ref = rep["source_ref"]
        if ref.get("type") == "shared":
            index = ref.get("si", -1)
            container = shared[index] if 0 <= index < len(shared) else None
        else:
            cell = cells.get(ref.get("cell"))
            container = cell.find(_q(S_NS, "is")) if cell is not None else None
        nodes = _text_nodes(container) if container is not None else []
        if not nodes:
            issues.append(_issue("OFFICE_TEXT_NODE_NOT_FOUND", "error", rep["id"]))
            continue
        styles = [
            _style_key(n.getparent().find(_q(S_NS, "rPr")))
            if n.getparent().tag == _q(S_NS, "r")
            else ""
            for n in nodes
        ]
        if _write_runs(nodes, styles, rep["target"]):
            issues.append(_issue("OFFICE_RICH_TEXT_RUNS_MERGED", "warning", rep["id"]))
        applied.append(rep["id"])
    return applied


def _apply_pptx(root: Any, replacements: list[dict], issues: list[dict]) -> list[str]:
    applied: list[str] = []
    paragraphs = list(root.iter(_q(A_NS, "p")))
    for rep in replacements:
        ref = rep["source_ref"]
        p_index, s_index = ref.get("p", -1), ref.get("segment", 0)
        runs: list[Any] = []
        if 0 <= p_index < len(paragraphs):
            segments = _segments(paragraphs[p_index])
            runs = segments[s_index] if 0 <= s_index < len(segments) else []
        nodes = [run.find(_q(A_NS, "t")) for run in runs]
        if not runs or any(node is None for node in nodes):
            issues.append(_issue("OFFICE_TEXT_NODE_NOT_FOUND", "error", rep["id"]))
            continue
        styles = [_style_key(run.find(_q(A_NS, "rPr"))) for run in runs]
        if _write_runs(nodes, styles, rep["target"]):
            issues.append(_issue("OFFICE_RICH_TEXT_RUNS_MERGED", "warning", rep["id"]))
        applied.append(rep["id"])
    return applied


def _issue(code: str, severity: str, block_id: str | None = None, **extra: Any) -> dict:
    messages = {
        "OFFICE_TEXT_NODE_NOT_FOUND": "Nœud texte introuvable : traduction non appliquée.",
        "OFFICE_RICH_TEXT_RUNS_MERGED": "Texte enrichi : la mise en forme du premier segment s'applique à toute la traduction.",
    }
    issue = {"code": code, "severity": severity, "message": messages.get(code, code), **extra}
    if block_id is not None:
        issue["block_id"] = block_id
    return issue


def edit_office_package(source: str | Path, out: str | Path, replacements: list[dict]) -> dict:
    """Write ``out``: source package with only the replaced text nodes changed."""
    kind = office_kind(source)
    by_part: dict[str, list[dict]] = {}
    for rep in replacements:
        by_part.setdefault(rep["source_ref"]["part"], []).append(rep)
    issues: list[dict] = []
    changed: list[str] = []
    rewritten: dict[str, bytes] = {}
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        for part, reps in sorted(by_part.items()):
            if part not in names:
                issues.extend(_issue("OFFICE_TEXT_NODE_NOT_FOUND", "error", r["id"]) for r in reps)
                continue
            original = archive.read(part)
            root = _parse(original)
            apply = _apply_xlsx if kind == "xlsx" else _apply_pptx
            done = apply(root, reps, issues)
            if done:
                changed.extend(done)
                rewritten[part] = _serialize(root, original)
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w") as target:
            for info in archive.infolist():
                target.writestr(info, rewritten.get(info.filename, archive.read(info.filename)))
    return {"changed_blocks": changed, "issues": issues, "rewritten_parts": sorted(rewritten)}


def _blanked_snapshot(path: str | Path, kind: str) -> dict[str, str]:
    """Canonical hash of every part, text nodes blanked in rewritable parts only.

    Notes, comments, charts and every other part keep their text in the hash:
    any change there is reported as a change beyond text."""
    text_tag = _q(S_NS, "t") if kind == "xlsx" else _q(A_NS, "t")
    rewritable = _REWRITABLE[kind]
    records: dict[str, str] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            data = archive.read(name)
            if name.endswith(".xml") or name.endswith(".rels"):
                try:
                    root = _parse(data)
                except etree.XMLSyntaxError:
                    records[name] = "INVALID_XML"
                    continue
                if re.search(rewritable, name):
                    for node in root.iter(text_tag):
                        node.text = ""
                        node.attrib.pop(XML_SPACE, None)
                data = etree.tostring(root, method="c14n")
            records[name] = hashlib.sha256(data).hexdigest()
    return records


def verify_office_candidate(
    source: str | Path, candidate: str | Path, expected: dict[str, str]
) -> dict:
    """Independent native check of a candidate package.

    ``expected`` maps block id -> target for every block that had to change.
    """
    kind = office_kind(source)
    src = collect_office_content(source)
    cand = collect_office_content(candidate)
    cand_text = {b["id"]: b["text"] for b in cand["blocks"]}
    not_applied = sorted(i for i, t in expected.items() if cand_text.get(i) != t)
    unexpected = sorted(
        b["id"]
        for b in src["blocks"]
        if b["id"] not in expected and cand_text.get(b["id"]) != b["text"]
    )
    before, after = _blanked_snapshot(source, kind), _blanked_snapshot(candidate, kind)
    beyond_text = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    formulas_ok = (
        kind != "xlsx" or src["inventory"]["formula_digest"] == cand["inventory"]["formula_digest"]
    )
    names_ok = (
        kind != "xlsx"
        or src["inventory"]["sheet_names_digest"] == cand["inventory"]["sheet_names_digest"]
    )
    units_ok = len(src["units"]) == len(cand["units"])
    ok = (
        not not_applied
        and not unexpected
        and not beyond_text
        and formulas_ok
        and names_ok
        and units_ok
    )
    return {
        "version": VERSION,
        "kind": kind,
        "status": "VERIFIED" if ok else "FAILED",
        "expected_targets": len(expected),
        "applied": len(expected) - len(not_applied),
        "not_applied": not_applied,
        "unexpected_changes": unexpected,
        "parts_total": len(before),
        "parts_changed_beyond_text": beyond_text,
        "formulas": src["inventory"].get("formulas"),
        "formulas_identical": formulas_ok,
        "sheet_names_identical": names_ok,
        "units_identical": units_ok,
        "visual_proof": "NOT_AVAILABLE",
    }
