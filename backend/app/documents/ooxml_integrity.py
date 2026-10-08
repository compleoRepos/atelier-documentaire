"""Independent package invariants; XML formatting equality != semantic alignment."""

from __future__ import annotations

import hashlib
import zipfile

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def package_snapshot(path):
    records = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            data = archive.read(name)
            if name.startswith("word/") and name.endswith(".xml"):
                parser = etree.XMLParser(resolve_entities=False, no_network=True)
                root = etree.fromstring(data, parser)
                for node in root.iter(W + "t"):
                    node.text = ""
                    node.attrib.pop(SPACE, None)
                data = etree.tostring(root, method="c14n")
            records[name] = hashlib.sha256(data).hexdigest()
    return records


def compare_ooxml_integrity(source, candidate):
    left, right = package_snapshot(source), package_snapshot(candidate)
    missing = sorted(left.keys() - right.keys())
    added = sorted(right.keys() - left.keys())
    changed = sorted(name for name in left.keys() & right.keys() if left[name] != right[name])
    preserved = not (missing or added or changed)
    return {
        "preserved": preserved,
        "score": float(preserved),
        "measured": True,
        "provenance": "independent_ooxml_c14n_excluding_w_t_and_xml_space",
        "missing_parts": missing,
        "added_parts": added,
        "changed_parts": changed,
        "source_part_count": len(left),
        "candidate_part_count": len(right),
        "semantic_style_alignment_validated": False,
        "issues": []
        if preserved
        else [
            {
                "code": "OOXML_NON_TEXT_STRUCTURE_CHANGED",
                "severity": "critical",
                "parts": missing + added + changed,
            }
        ],
    }
