from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from app.documents.docx_analysis import collect_docx_content
from app.documents.docx_fidelity import edit_docx_package

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": W, "r": R}


def _make_hyperlink_doc(path: Path) -> None:
    doc = Document()
    paragraph = doc.add_paragraph()
    rid = doc.part.relate_to("https://example.test/source", RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "Source link"
    run.append(text)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)
    doc.save(path)


def test_hyperlink_text_is_translated_in_place_and_relationship_is_kept(tmp_path):
    source = tmp_path / "source.docx"
    candidate = tmp_path / "candidate.docx"
    _make_hyperlink_doc(source)
    blocks, _, _ = collect_docx_content(
        source,
        lambda text, bid, order, ref: {"id": bid, "text": text, "source_ref": ref},
    )
    block = blocks[0]

    result = edit_docx_package(
        source,
        candidate,
        [{"id": block["id"], "source_ref": block["source_ref"], "target": "Lien traduit"}],
    )

    assert result["changed_count"] == 1
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(candidate) as after:
        source_xml = etree.fromstring(before.read("word/document.xml"))
        candidate_xml = etree.fromstring(after.read("word/document.xml"))
        assert (
            candidate_xml.xpath("string(.//w:hyperlink/w:r/w:t)", namespaces=NS) == "Lien traduit"
        )
        assert candidate_xml.xpath("string(.//w:hyperlink/@r:id)", namespaces=NS) == "rId9"
        assert after.read("word/_rels/document.xml.rels") == before.read(
            "word/_rels/document.xml.rels"
        )
        assert source_xml.xpath("string(.//w:hyperlink/w:r/w:t)", namespaces=NS) == "Source link"
