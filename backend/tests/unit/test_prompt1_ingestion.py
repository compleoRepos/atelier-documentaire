from __future__ import annotations

import hashlib
import io

import fitz
import pytest
from fastapi import HTTPException
from PIL import Image

from app.ai.ocr.tesseract import TesseractOCR
from app.documents.pipeline import analyze_document
from app.documents.preprocessing import _rotation, preprocess_image
from app.infrastructure.validation import validate_upload


def _fixture():
    document = fitz.open()
    page = document.new_page(width=500,height=450)
    for i in range(18):
        page.insert_text((25,30+i*22),f"Document reference line {i} - quality control report",fontsize=12)
    pix = page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
    image = Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
    document.close()
    return image


def test_real_tesseract_before_after_uses_original_coordinates(tmp_path):
    source = tmp_path/"source.png"
    _fixture().save(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    ir = analyze_document(str(source),str(tmp_path/"work"),{"ocr_languages":["eng"],"preprocessing_max_variants":3})
    assert hashlib.sha256(source.read_bytes()).hexdigest() == sha
    page = ir["pages"][0]
    meta = page["preprocessing"]
    assert meta["ocr_before"]["model"] == "tesseract"
    assert meta["ocr_before"]["blocks"] > 10
    assert meta["ocr_after"]["confidence"] >= meta["ocr_before"]["confidence"]
    assert (tmp_path/"work/previews/enhanced-001.png").exists()
    for block in page["blocks"]:
        assert 0 <= block["bbox"][0] < block["bbox"][2] <= page["width"]
        assert 0 <= block["bbox"][1] < block["bbox"][3] <= page["height"]


@pytest.mark.parametrize("angle",[90,180,270,5,10])
def test_real_orientation_and_deskew_probes_do_not_claim_validated_cer(angle,tmp_path):
    import numpy as np
    image,matrix = _rotation(np.asarray(_fixture()),angle)
    result = preprocess_image(Image.fromarray(image),TesseractOCR(["eng"]),tmp_path,max_variants=3)
    before = result.metadata["ocr_before"]["confidence"]
    after = result.metadata["ocr_after"]["confidence"]
    assert after is not None
    if before is not None:
        assert after >= before
    assert result.metadata["PreprocessingQualityScore"]["validated"] is False
    assert result.metadata["PreprocessingQualityScore"]["cer"] is None
    # OCR improvement is a probe, not a universally guaranteed OCR recovery.
    assert abs(__import__("numpy").linalg.det(matrix)) > .99


def test_tiff_all_frames_and_page_limit_are_validated(tmp_path):
    output = io.BytesIO()
    image = _fixture()
    image.save(output,format="TIFF",save_all=True,append_images=[image])
    data = output.getvalue()
    assert validate_upload(data,"source.tiff","image/tiff",2) == ("tiff","image/tiff")
    with pytest.raises(HTTPException) as error:
        validate_upload(data,"source.tiff","image/tiff",1)
    assert error.value.detail["code"] == "PAGE_LIMIT"
    with pytest.raises(HTTPException) as error:
        validate_upload(data,"source.png","image/png")
    assert error.value.detail["code"] == "MAGIC_MISMATCH"
    path = tmp_path/"source.tiff"
    path.write_bytes(data)
    ir = analyze_document(str(path),str(tmp_path/"work"),{"ocr_languages":["eng"],"preprocessing_max_variants":1,"preprocessing_orientation":False})
    assert len(ir["pages"]) == 2
    assert ir["versions"]["source_sha256"] == hashlib.sha256(data).hexdigest()
