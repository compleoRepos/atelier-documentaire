from __future__ import annotations

from types import SimpleNamespace

import fitz
import numpy as np
import pytest
from PIL import Image

from app.api.routes import _stage_projection
from app.documents.pipeline import _tables
from app.documents.preprocessing import _orientation, _rotation


def test_raster_tables_and_cells_remain_in_pdf_points():
    rgb = np.full((400,600,3),255,np.uint8)
    for x in [40,300,560]:
        rgb[40:361,x:x+2] = 0
    for y in [40,200,360]:
        rgb[y:y+2,40:562] = 0
    doc = fitz.open()
    page = doc.new_page(width=300,height=200)
    blocks = [{"id":"one","bbox":[25,25,90,50],"text":"one"}]
    tables,_layout = _tables(page,1,blocks,Image.fromarray(rgb))
    assert tables
    for table in tables:
        assert table["bbox"][2] <= 300
        assert table["bbox"][3] <= 200
        assert any("one" in cell["block_ids"] for cell in table["cells"])
        for cell in table["cells"]:
            assert cell["bbox"][2] <= 300
            assert cell["bbox"][3] <= 200
    doc.close()


def test_orientation_failure_preserves_source_instead_of_raising(monkeypatch):
    import pytesseract
    def failure(*args,**kwargs):
        raise OSError("missing local binary")
    monkeypatch.setattr(pytesseract,"image_to_osd",failure)
    assert _orientation(np.full((100,100,3),255,np.uint8)) == (0,0.0)


def test_geometry_budget_precedes_warp_allocation(monkeypatch):
    import app.documents.preprocessing as module
    monkeypatch.setattr(module,"MAX_PIXELS",10000)
    def unexpected(*args,**kwargs):
        raise AssertionError("warp must not be allocated")
    monkeypatch.setattr(module.cv2,"warpPerspective",unexpected)
    with pytest.raises(ValueError,match="GEOMETRY_PIXEL_LIMIT"):
        _rotation(np.zeros((100,100,3),np.uint8),45)


def test_native_document_does_not_falsely_claim_ocr_execution():
    doc = SimpleNamespace(status="ANALYZED",analysis_json={"pages":[{"number":1,"scanned":False,"blocks":[{"id":"one"}]}]},
                          translation_json=None,issues_json=[],quality_json=None,review_version=None)
    stages = {item["id"]:item for item in _stage_projection(doc)}
    assert stages["ocr"]["state"] == "not_applicable"
    assert stages["preprocessing"]["state"] == "not_applicable"
    assert stages["translation"]["state"] == "pending"


def test_tiff_adapter_preserves_every_frame_pixel_and_original_hash(tmp_path):
    import hashlib

    from app.documents.raster_adapter import raster_pdf_copy
    original = tmp_path/"source.tiff"
    frames = [Image.new("RGB",(40,30),color) for color in ["red","blue"]]
    frames[0].save(original,save_all=True,append_images=frames[1:])
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    output = raster_pdf_copy(original,tmp_path/"copy.pdf")
    with fitz.open(output) as doc:
        assert len(doc) == 2
        for number,frame in enumerate(frames):
            pix = doc[number].get_pixmap(alpha=False)
            assert pix.samples == frame.tobytes()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == sha
    with pytest.raises(ValueError,match="overwritten"):
        raster_pdf_copy(original,original)


@pytest.mark.asyncio
async def test_private_failure_never_substitutes_offline_memory(tmp_path,monkeypatch):
    import app.ai.translation.service as service
    import app.documents.pipeline as pipeline
    source = tmp_path/"source.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300,height=200)
    page.insert_text((20,50),"Source English sentence")
    doc.save(source)
    doc.close()
    ir = pipeline.analyze_document(str(source),str(tmp_path/"work"))
    async def failure(*args,**kwargs):
        raise ValueError("private tokenizer unavailable")
    monkeypatch.setattr(service,"translate_blocks",failure)
    result = await pipeline.translate_document(ir,str(tmp_path/"work"),{"engine":"private", "memory":{"Source English sentence":"Traduction non privée"}})
    assert "Traduction non privée" not in result["translations"].values()
    assert any(x["code"] == "TRANSLATION_SERVICE_ERROR" for x in result["issues"])
    assert result["quality"]["status"] == "REVIEW_REQUIRED"
