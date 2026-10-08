from __future__ import annotations

import copy
import hashlib
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from app.documents.docx_fidelity import (
    edit_docx_package,
    numeric_paragraph_path,
    paragraph_metadata,
    redistribute_text,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": W, "r": R}


def _p(xml: str):
    return etree.fromstring(xml.encode("utf-8"))


def _texts(element):
    return [node.text or "" for node in element.xpath(".//w:t", namespaces=NS)]


def test_paragraph_metadata_reports_structure_and_protected_field_result():
    paragraph = _p(
        f'''<w:p xmlns:w="{W}" xmlns:r="{R}">
          <w:pPr><w:pStyle w:val="BodyText"/></w:pPr>
          <w:hyperlink r:id="rId7"><w:r><w:rPr><w:b/></w:rPr><w:t>linked</w:t></w:r></w:hyperlink>
          <w:bookmarkStart w:id="2" w:name="mark"/><w:r><w:t> body</w:t><w:tab/><w:br/></w:r><w:bookmarkEnd w:id="2"/>
          <w:r><w:fldChar w:fldCharType="begin"/><w:instrText> PAGE </w:instrText><w:fldChar w:fldCharType="separate"/><w:t>4</w:t><w:fldChar w:fldCharType="end"/></w:r>
        </w:p>'''
    )
    metadata = paragraph_metadata(paragraph)
    assert metadata["text"] == "linked body4"
    assert metadata["runs"] and metadata["runs"][0]["style_xml"]
    assert metadata["properties"]["paragraph_style"] == "BodyText"
    assert metadata["hyperlinks"][0]["relationship_id"] == "rId7"
    assert metadata["bookmarks"][0]["name"] == "mark"
    assert metadata["tabs"] and metadata["breaks"]
    assert metadata["field_result_protected"] is True
    assert metadata["fields"][0]["result_text"] == "4"


def test_redistribution_preserves_runs_and_traces_word_boundary_without_semantics():
    paragraph = _p(
        f'''<w:p xmlns:w="{W}"><w:r><w:t>Alpha </w:t></w:r><w:r><w:t>beta</w:t></w:r></w:p>'''
    )
    before = copy.deepcopy(paragraph)
    result = redistribute_text(paragraph, "Premier mot")
    assert result["applied"] is True
    assert result["status"] == "APPLIED"
    assert result["node_count"] == 2
    assert result["trace"]["semantic_alignment"] is False
    assert all(segment["boundary"] == "word_boundary" for segment in result["trace"]["segments"])
    assert "".join(_texts(paragraph)) == "Premier mot"
    assert [node.tag for node in paragraph] == [node.tag for node in before]
    assert len(paragraph.xpath(".//w:r", namespaces=NS)) == 2
    assert paragraph.xpath(".//w:t", namespaces=NS)[1].text == "mot"


def test_multistyle_hyperlink_and_field_changes_require_review_without_mutation():
    multistyle = _p(
        f'''<w:p xmlns:w="{W}"><w:r><w:rPr><w:b/></w:rPr><w:t>One </w:t></w:r><w:r><w:rPr><w:i/></w:rPr><w:t>two</w:t></w:r></w:p>'''
    )
    original = etree.tostring(multistyle)
    result = redistribute_text(multistyle, "Un deux")
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["applied"]
    assert "".join(_texts(multistyle)) == "Un deux"
    assert len(multistyle.xpath(".//w:r", namespaces=NS)) == 2
    assert any(issue["code"] == "DOCX_MULTI_STYLE_BOUNDARY_AMBIGUOUS" for issue in result["issues"])

    hyperlink = _p(
        f'''<w:p xmlns:w="{W}" xmlns:r="{R}"><w:hyperlink r:id="rId1"><w:r><w:t>One two</w:t></w:r></w:hyperlink></w:p>'''
    )
    result = redistribute_text(hyperlink, "Un deux")
    assert result["status"] == "REVIEW_REQUIRED"
    assert any(issue["code"] == "DOCX_HYPERLINK_BOUNDARY_AMBIGUOUS" for issue in result["issues"])

    field = _p(
        f'''<w:p xmlns:w="{W}"><w:r><w:fldChar w:fldCharType="begin"/><w:instrText> PAGE </w:instrText><w:fldChar w:fldCharType="separate"/><w:t>4</w:t><w:fldChar w:fldCharType="end"/></w:r></w:p>'''
    )
    original = etree.tostring(field)
    result = redistribute_text(field, "5")
    assert result["status"] == "REVIEW_REQUIRED"
    assert etree.tostring(field) == original
    assert _texts(field) == ["4"]


def _document_xml() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}"><w:body>
  <w:p><w:r><w:t>Body source</w:t></w:r></w:p>
  <w:tbl><w:tr><w:tc><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Nested source</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p><w:r><w:t>Cell source</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
  <w:sectPr/>
</w:body></w:document>'''.encode()


def _package(path: Path) -> dict[str, bytes]:
    members = {
        "[Content_Types].xml": b"types that must remain byte-identical",
        "word/document.xml": _document_xml(),
        "word/media/image.bin": bytes(range(32)),
        "custom/data.bin": b"unmodified custom member",
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return members


def test_edit_package_uses_current_refs_keeps_unmodified_members_and_returns_trace(tmp_path):
    source = tmp_path / "source.docx"
    expected = _package(source)
    output = tmp_path / "candidate.docx"
    nested_path = [0, 1, 0, 0, 0, 0, 0, 0]
    # document/body/tbl/tr/tc/tbl/tr/tc/p: the explicit numeric path addresses
    # the nested table paragraph rather than flattening the table hierarchy.
    replacements = [
        {"id": "body", "source_ref": {"paragraph_index": 0}, "target": "Corps"},
        {
            "id": "nested",
            "source_ref": {"xml_part": "word/document.xml", "paragraph_path": nested_path},
            "target": "Imbrique",
        },
    ]
    result = edit_docx_package(source, output, replacements)
    assert result["status"] == "APPLIED"
    assert result["changed_blocks"] == 2
    assert len(result["redistribution_trace"]) == 2
    assert result["modified_parts"] == ["word/document.xml"]
    assert output.is_file()

    with zipfile.ZipFile(output) as archive:
        assert archive.read("[Content_Types].xml") == expected["[Content_Types].xml"]
        assert archive.read("word/media/image.bin") == expected["word/media/image.bin"]
        document = etree.fromstring(archive.read("word/document.xml"))
        assert _texts(document) == ["Corps", "Imbrique", "Cell source"]


def test_edit_package_rejects_same_path_and_no_change_copies_source_exactly(tmp_path):
    source = tmp_path / "source.docx"
    _package(source)
    with pytest.raises(ValueError):
        edit_docx_package(source, source, [])
    output = tmp_path / "copy.docx"
    result = edit_docx_package(source, output, [])
    assert result["status"] == "NO_CHANGE"
    assert (
        hashlib.sha256(output.read_bytes()).digest() == hashlib.sha256(source.read_bytes()).digest()
    )


def test_numeric_paragraph_path_is_deterministic():
    root = _p(
        f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>x</w:t></w:r></w:p></w:body></w:document>'
    )
    paragraph = root.xpath(".//w:p", namespaces=NS)[0]
    assert numeric_paragraph_path(root, paragraph) == [0, 0]


def test_nested_text_box_is_not_flattened_or_redistributed():
    paragraph = _p(
        f'<w:p xmlns:w="{W}"><w:r><w:t>Outer source</w:t><w:drawing><w:txbxContent><w:p><w:r><w:t>Inner source</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r></w:p>'
    )
    original = etree.tostring(paragraph)
    result = redistribute_text(paragraph, "Texte arbitraire")
    assert result["applied"] is False
    assert result["status"] == "REVIEW_REQUIRED"
    assert etree.tostring(paragraph) == original
    assert any(i["code"] == "DOCX_NESTED_TEXT_REQUIRES_REVIEW" for i in result["issues"])


def test_non_word_text_namespace_is_preserved_and_null_target_rejected():
    paragraph = _p(
        f'<w:p xmlns:w="{W}" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><w:r><w:t>Word source</w:t><w:drawing><a:t>Protected drawing</a:t></w:drawing></w:r></w:p>'
    )
    result = redistribute_text(paragraph, "Texte cible")
    assert result["applied"] is True
    assert (
        paragraph.xpath(
            ".//a:t", namespaces={"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        )[0].text
        == "Protected drawing"
    )
    with pytest.raises(ValueError):
        redistribute_text(paragraph, None)


def test_negative_numeric_ref_cannot_select_last_paragraph(tmp_path):
    source = tmp_path / "source.docx"
    _package(source)
    result = edit_docx_package(
        source,
        tmp_path / "candidate.docx",
        [
            {
                "id": "invalid",
                "source_ref": {"xml_part": "word/document.xml", "paragraph_path": [0, -1]},
                "target": "Invalid",
            }
        ],
    )
    assert result["changed_blocks"] == 0
    assert any(i["code"] == "DOCX_PARAGRAPH_REF_NOT_FOUND" for i in result["issues"])


def test_cross_paragraph_complex_field_result_is_protected(tmp_path):
    source = tmp_path / "field.docx"
    xml = f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:fldChar w:fldCharType="begin"/><w:instrText> TOC </w:instrText><w:fldChar w:fldCharType="separate"/></w:r></w:p><w:p><w:r><w:t>Protected result</w:t></w:r></w:p><w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:body></w:document>'
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("word/document.xml", xml.encode())
    candidate = tmp_path / "candidate.docx"
    result = edit_docx_package(
        source,
        candidate,
        [{"id": "field-result", "source_ref": {"paragraph_index": 1}, "target": "Modified result"}],
    )
    assert result["changed_blocks"] == 0
    assert any(i["code"] == "DOCX_FIELD_RESULT_PROTECTED" for i in result["issues"])
    with zipfile.ZipFile(candidate) as archive:
        assert archive.read("word/document.xml") == xml.encode()
