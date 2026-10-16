"""RUN28 route A — native XLSX / PPTX (synthetic packages only, no real data)."""

from __future__ import annotations

import asyncio
import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.documents.ooxml_office import (
    collect_office_content,
    edit_office_package,
    verify_office_candidate,
)
from app.documents.pipeline import analyze_document, reconstruct_document, translate_document
from app.infrastructure.validation import validate_upload

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
PR = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
P = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
T = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def _zip(path: Path, parts: dict[str, str], extra: dict[str, bytes] | None = None) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            archive.writestr(name, text.encode("utf-8"))
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path


def make_xlsx(path: Path, *, hidden: bool = False, extra: dict[str, bytes] | None = None) -> Path:
    state = ' state="hidden"' if hidden else ""
    parts = {
        "[Content_Types].xml": DECL
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>",
        "_rels/.rels": DECL
        + f'<Relationships {PR}><Relationship Id="rId1" Type="{T}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": DECL
        + f'<workbook {S} {R}><sheets><sheet name="Overview" sheetId="1" r:id="rId1"/>'
        f'<sheet name="Data" sheetId="2"{state} r:id="rId2"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": DECL
        + f'<Relationships {PR}><Relationship Id="rId1" Type="{T}/worksheet" Target="worksheets/sheet1.xml"/>'
        f'<Relationship Id="rId2" Type="{T}/worksheet" Target="worksheets/sheet2.xml"/>'
        f'<Relationship Id="rId3" Type="{T}/sharedStrings" Target="sharedStrings.xml"/></Relationships>',
        "xl/sharedStrings.xml": DECL + f'<sst {S} count="5" uniqueCount="4">'
        "<si><t>Garden budget</t></si>"
        "<si><r><rPr><b/></rPr><t>Harvest </t></r><r><t>season</t></r></si>"
        "<si><t>Orphan string never used</t></si>"
        "<si><t>Seed catalogue</t></si></sst>",
        "xl/worksheets/sheet1.xml": DECL + f"<worksheet {S}><sheetData>"
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><v>42</v></c>'
        '<c r="C1"><f>SUM(B1:B2)</f><v>84</v></c>'
        '<c r="D1" t="str"><f>"Total "&amp;B1</f><v>Total 42</v></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>Watering plan</t></is></c><c r="B2"><v>42</v></c></row>'
        '<row r="3"><c r="A3" t="s"><v>1</v></c></row>'
        "</sheetData></worksheet>",
        "xl/worksheets/sheet2.xml": DECL
        + f'<worksheet {S}><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c>'
        '<c r="B1" t="s"><v>3</v></c></row></sheetData></worksheet>',
        "xl/comments1.xml": DECL
        + f'<comments {S}><commentList><comment ref="A1"><text><t>Reviewer remark</t></text></comment></commentList></comments>',
    }
    return _zip(path, parts, extra)


def make_pptx(path: Path, *, extra: dict[str, bytes] | None = None) -> Path:
    body = "<a:bodyPr>{fit}</a:bodyPr><a:lstStyle/>"
    slide1 = (
        DECL + f"<p:sld {A} {P} {R}><p:cSld><p:spTree>"
        "<p:sp><p:txBody>"
        + body.format(fit="<a:noAutofit/>")
        + '<a:p><a:r><a:rPr lang="en-US"/><a:t>Picnic agenda</a:t></a:r></a:p>'
        "<a:p><a:r><a:t>Bring blankets</a:t></a:r><a:br/><a:r><a:t>Pack lemonade</a:t></a:r></a:p>"
        '<a:p><a:fld id="{00000000-0000-0000-0000-000000000001}" type="slidenum"><a:t>1</a:t></a:fld></a:p>'
        "</p:txBody></p:sp>"
        "<p:graphicFrame><a:graphic><a:graphicData><a:tbl><a:tr><a:tc><a:txBody>"
        + body.format(fit="")
        + "<a:p><a:r><a:t>Sandwich count</a:t></a:r></a:p></a:txBody></a:tc></a:tr></a:tbl>"
        "</a:graphicData></a:graphic></p:graphicFrame>"
        "</p:spTree></p:cSld></p:sld>"
    )
    slide2 = (
        DECL
        + f'<p:sld {A} {P} {R} show="0"><p:cSld><p:spTree><p:sp><p:txBody>'
        + body.format(fit="<a:normAutofit/>")
        + "<a:p><a:r><a:t>Spare slide</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    parts = {
        "[Content_Types].xml": DECL
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        '<Override PartName="/ppt/slides/slide2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        "</Types>",
        "_rels/.rels": DECL
        + f'<Relationships {PR}><Relationship Id="rId1" Type="{T}/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
        "ppt/presentation.xml": DECL
        + f'<p:presentation {P} {R}><p:sldIdLst><p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId3"/></p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": DECL
        + f'<Relationships {PR}><Relationship Id="rId2" Type="{T}/slide" Target="slides/slide1.xml"/>'
        f'<Relationship Id="rId3" Type="{T}/slide" Target="slides/slide2.xml"/></Relationships>',
        "ppt/slides/slide1.xml": slide1,
        "ppt/slides/slide2.xml": slide2,
        "ppt/notesSlides/notesSlide1.xml": DECL
        + f"<p:notes {A} {P}><p:cSld><p:spTree><p:sp><p:txBody><a:bodyPr/>"
        "<a:p><a:r><a:t>Speaker reminder</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>",
    }
    return _zip(path, parts, extra)


def _texts(path: Path) -> dict[str, str]:
    return {b["id"]: b["text"] for b in collect_office_content(path)["blocks"]}


def _reps(path: Path, targets: dict[str, str]) -> list[dict]:
    blocks = {b["id"]: b for b in collect_office_content(path)["blocks"]}
    return [
        {"id": i, "source_ref": blocks[i]["source_ref"], "target": t} for i, t in targets.items()
    ]


def _rewrite(path: Path, out: Path, part: str, old: bytes, new: bytes) -> Path:
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == part:
                assert old in data
                data = data.replace(old, new)
            dst.writestr(info, data)
    return out


# --- XLSX -----------------------------------------------------------------


def test_xlsx_collects_used_shared_and_inline_strings_only(tmp_path):
    content = collect_office_content(make_xlsx(tmp_path / "a.xlsx"))
    texts = {b["id"]: b["text"] for b in content["blocks"]}
    assert texts == {
        "x01-s00000": "Garden budget",
        "x01-cA2": "Watering plan",
        "x01-s00001": "Harvest season",
        "x02-s00003": "Seed catalogue",
    }
    shared = next(b for b in content["blocks"] if b["id"] == "x01-s00000")
    assert shared["source_ref"]["use_count"] == 2  # reused on both sheets
    inventory = content["inventory"]
    assert inventory["formulas"] == 2 and inventory["formula_text_cells"] == 1
    assert inventory["shared_strings_total"] == 4 and inventory["shared_strings_used"] == 3
    assert inventory["untranslated_text_parts"] == {"xl/comments1.xml": 1}
    assert [u["name"] for u in content["units"]] == ["Overview", "Data"]


def test_xlsx_edit_rewrites_text_only_and_verifies(tmp_path):
    source = make_xlsx(tmp_path / "a.xlsx")
    targets = {
        "x01-s00000": "Budget du jardin",
        "x01-cA2": "Plan d'arrosage",
        "x02-s00003": "  Catalogue des graines  ",
    }
    out = tmp_path / "candidate.xlsx"
    result = edit_office_package(source, out, _reps(source, targets))
    assert sorted(result["changed_blocks"]) == sorted(targets)
    assert result["rewritten_parts"] == ["xl/sharedStrings.xml", "xl/worksheets/sheet1.xml"]
    texts = _texts(out)
    assert texts["x01-s00000"] == "Budget du jardin" and texts["x01-s00001"] == "Harvest season"
    with zipfile.ZipFile(source) as a, zipfile.ZipFile(out) as b:
        assert a.namelist() == b.namelist()
        for name in a.namelist():
            if name not in result["rewritten_parts"]:
                assert a.read(name) == b.read(name), name  # byte for byte
        assert b'xml:space="preserve"' in b.read("xl/sharedStrings.xml")
        assert b"<f>SUM(B1:B2)</f>" in b.read("xl/worksheets/sheet1.xml")
    report = verify_office_candidate(source, out, targets)
    assert report["status"] == "VERIFIED", report
    assert report["formulas_identical"] and report["sheet_names_identical"]
    assert report["visual_proof"] == "NOT_AVAILABLE"


def test_xlsx_rich_text_merge_is_reported(tmp_path):
    source = make_xlsx(tmp_path / "a.xlsx")
    result = edit_office_package(
        source, tmp_path / "c.xlsx", _reps(source, {"x01-s00001": "Saison des récoltes"})
    )
    assert [i["code"] for i in result["issues"]] == ["OFFICE_RICH_TEXT_RUNS_MERGED"]
    assert _texts(tmp_path / "c.xlsx")["x01-s00001"] == "Saison des récoltes"


@pytest.mark.parametrize(
    ("part", "old", "new", "field"),
    [
        ("xl/worksheets/sheet1.xml", b"SUM(B1:B2)", b"SUM(B1:B9)", "formulas_identical"),
        ("xl/workbook.xml", b'name="Data"', b'name="Daten"', "sheet_names_identical"),
        ("xl/comments1.xml", b"Reviewer remark", b"Remarque", "parts_changed_beyond_text"),
    ],
)
def test_xlsx_verification_detects_changes_beyond_text(tmp_path, part, old, new, field):
    source = make_xlsx(tmp_path / "a.xlsx")
    targets = {"x01-s00000": "Budget du jardin"}
    good = tmp_path / "good.xlsx"
    edit_office_package(source, good, _reps(source, targets))
    bad = _rewrite(good, tmp_path / "bad.xlsx", part, old, new)
    report = verify_office_candidate(source, bad, targets)
    assert report["status"] == "FAILED"
    assert part in report["parts_changed_beyond_text"]
    if field != "parts_changed_beyond_text":
        assert report[field] is False


def test_xlsx_verification_detects_missing_and_unexpected_text(tmp_path):
    source = make_xlsx(tmp_path / "a.xlsx")
    out = tmp_path / "c.xlsx"
    edit_office_package(source, out, _reps(source, {"x01-s00000": "Budget du jardin"}))
    # An expected target that is absent, and a block changed without expectation.
    report = verify_office_candidate(source, out, {"x01-cA2": "Plan d'arrosage"})
    assert report["status"] == "FAILED"
    assert report["not_applied"] == ["x01-cA2"]
    assert report["unexpected_changes"] == ["x01-s00000"]


# --- PPTX -----------------------------------------------------------------


def test_pptx_collects_runs_segments_tables_and_skips_fields(tmp_path):
    content = collect_office_content(make_pptx(tmp_path / "a.pptx"))
    blocks = {b["id"]: b for b in content["blocks"]}
    assert {i: b["text"] for i, b in blocks.items()} == {
        "s01-p0000": "Picnic agenda",
        "s01-p0001-l0": "Bring blankets",
        "s01-p0001-l1": "Pack lemonade",
        "s01-p0003": "Sandwich count",
        "s02-p0000": "Spare slide",
    }
    assert blocks["s01-p0003"]["kind"] == "table_cell"
    assert blocks["s01-p0000"]["autofit"] == "none" and blocks["s02-p0000"]["autofit"] == "text"
    assert content["inventory"]["fields"] == 1 and content["inventory"]["hidden_units"] == 1
    assert content["inventory"]["untranslated_text_parts"] == {"ppt/notesSlides/notesSlide1.xml": 1}


def test_pptx_edit_keeps_fields_breaks_and_other_parts(tmp_path):
    source = make_pptx(tmp_path / "a.pptx")
    targets = {
        "s01-p0000": "Programme du pique-nique",
        "s01-p0001-l1": "Prévoir la limonade",
        "s01-p0003": "Nombre de sandwichs",
    }
    out = tmp_path / "c.pptx"
    result = edit_office_package(source, out, _reps(source, targets))
    assert result["issues"] == [] and result["rewritten_parts"] == ["ppt/slides/slide1.xml"]
    texts = _texts(out)
    assert (
        texts["s01-p0001-l0"] == "Bring blankets" and texts["s01-p0001-l1"] == "Prévoir la limonade"
    )
    with zipfile.ZipFile(out) as archive:
        slide = archive.read("ppt/slides/slide1.xml")
        assert slide.count(b"<a:br/>") == 1 and b'type="slidenum"><a:t>1</a:t>' in slide
        assert b"Speaker reminder" in archive.read("ppt/notesSlides/notesSlide1.xml")
    assert verify_office_candidate(source, out, targets)["status"] == "VERIFIED"


def test_pptx_verification_detects_field_change(tmp_path):
    source = make_pptx(tmp_path / "a.pptx")
    targets = {"s01-p0000": "Programme du pique-nique"}
    good = tmp_path / "good.pptx"
    edit_office_package(source, good, _reps(source, targets))
    bad = _rewrite(
        good, tmp_path / "bad.pptx", "ppt/slides/slide1.xml", b'type="slidenum"', b'type="datetime"'
    )
    report = verify_office_candidate(source, bad, targets)
    assert report["status"] == "FAILED" and report["parts_changed_beyond_text"] == [
        "ppt/slides/slide1.xml"
    ]


# --- pipeline -------------------------------------------------------------


@pytest.mark.parametrize("maker,suffix", [(make_xlsx, "xlsx"), (make_pptx, "pptx")])
def test_office_pipeline_end_to_end_offline(tmp_path, maker, suffix):
    source = maker(tmp_path / f"source.{suffix}")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    work = tmp_path / "work"
    ir = analyze_document(str(source), str(work), {"office_previews": False})
    assert ir["format"] == suffix and ir["versions"]["source_sha256"] == sha
    codes = {w["code"] for w in ir["warnings"]}
    assert {"OFFICE_VISUAL_PROOF_UNAVAILABLE", "OFFICE_TEXT_PARTS_NOT_TRANSLATED"} <= codes
    assert "OFFICE_HIDDEN_UNITS_PRESENT" in codes if suffix == "pptx" else True
    first = ir["pages"][0]["blocks"][0]
    memory = {first["text"]: "Traduction synthétique"}
    tr = asyncio.run(translate_document(ir, str(work), {"engine": "offline", "memory": memory}))
    candidate = Path(tr["versions"]["candidate"])
    assert candidate.name == f"candidate.{suffix}" and candidate.is_file()
    assert _texts(candidate)[first["id"]] == "Traduction synthétique"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == sha  # original untouched
    assert tr["native_verification"]["status"] == "VERIFIED"
    assert tr["native_verification"]["visual_proof"] == "NOT_AVAILABLE"
    status = tr["block_status"]["blocks"]
    assert status[first["id"]]["status"] == "TRANSLATED"
    # Blocks absent from the offline memory stay visible as failures.
    assert all(v["status"] == "FAILED" for k, v in status.items() if k != first["id"])
    assert {"VISUAL_EVIDENCE_MISSING", "UNTRANSLATED"} <= {i["code"] for i in tr["issues"]}


def test_office_reconstruct_reports_possible_pptx_overflow(tmp_path):
    source = make_pptx(tmp_path / "source.pptx")
    ir = analyze_document(str(source), str(tmp_path / "work"), {"office_previews": False})
    long = "Programme détaillé et complet du pique-nique annuel"
    render = reconstruct_document(
        ir,
        {"s01-p0000": long, "s02-p0000": long},
        str(tmp_path / "out" / "candidate.pptx"),
    )
    assert render["native_verification"]["status"] == "VERIFIED"
    overflow = [i["block_id"] for i in render["issues"] if i["code"] == "PPTX_TEXT_MAY_OVERFLOW"]
    assert overflow == ["s01-p0000"]  # s02 has normAutofit
    assert not [i for i in render["issues"] if i.get("severity") == "critical"]


def test_office_target_not_applied_is_failed_not_translated(tmp_path):
    from app.documents.block_status import classify_blocks

    source = make_xlsx(tmp_path / "source.xlsx")
    ir = analyze_document(str(source), str(tmp_path / "work"), {"office_previews": False})
    block = next(b for p in ir["pages"] for b in p["blocks"] if b["id"] == "x01-s00000")
    block["source_ref"] = {**block["source_ref"], "si": 99}  # corrupted mapping
    translations = {"x01-s00000": "Budget du jardin", "x01-cA2": "Plan d'arrosage"}
    render = reconstruct_document(ir, translations, str(tmp_path / "out" / "c.xlsx"))
    codes = {(i["code"], i.get("block_id")) for i in render["issues"]}
    assert ("OFFICE_TARGET_NOT_APPLIED", "x01-s00000") in codes
    assert "x01-s00000" not in render["changed_blocks"]
    status = classify_blocks(ir, translations, render["issues"])["blocks"]
    assert status["x01-s00000"]["status"] == "FAILED"
    assert status["x01-s00000"]["reason"] == "render_office_target_missing"
    assert status["x01-cA2"]["status"] == "TRANSLATED"


# --- upload validation ----------------------------------------------------


def test_upload_accepts_synthetic_xlsx_and_pptx(tmp_path):
    xlsx = make_xlsx(tmp_path / "a.xlsx").read_bytes()
    pptx = make_pptx(tmp_path / "a.pptx").read_bytes()
    assert validate_upload(xlsx, "a.xlsx", XLSX_MIME) == ("xlsx", XLSX_MIME)
    assert validate_upload(pptx, "a.pptx", PPTX_MIME) == ("pptx", PPTX_MIME)


@pytest.mark.parametrize(
    ("kind", "extra", "code"),
    [
        ("xlsx", {"xl/vbaProject.bin": b"\x00"}, "XLSX_MACRO"),
        ("xlsx", {"xl/externalLinks/externalLink1.xml": b"<x/>"}, "EXTERNAL_RELATION"),
        ("xlsx", {"xl/connections.xml": b"<x/>"}, "EXTERNAL_RELATION"),
        ("xlsx", {"xl/embeddings/oleObject1.bin": b"\x00"}, "EMBEDDED_OBJECT"),
        ("pptx", {"ppt/activeX/activeX1.xml": b"<x/>"}, "ACTIVE_CONTENT"),
        ("pptx", {"ppt/vbaProject.bin": b"\x00"}, "PPTX_MACRO"),
    ],
)
def test_upload_rejects_dangerous_office_content(tmp_path, kind, extra, code):
    maker = make_xlsx if kind == "xlsx" else make_pptx
    data = maker(tmp_path / f"a.{kind}", extra=extra).read_bytes()
    with pytest.raises(HTTPException) as caught:
        validate_upload(data, f"a.{kind}", XLSX_MIME if kind == "xlsx" else PPTX_MIME)
    assert code in str(caught.value.detail)


def test_upload_rejects_office_without_main_part():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    with pytest.raises(HTTPException) as caught:
        validate_upload(buffer.getvalue(), "a.xlsx", XLSX_MIME)
    assert "XLSX_INVALID" in str(caught.value.detail)
