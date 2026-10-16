"""Private corpus benchmark: no external AI calls and no human references invented.

Full artifacts stay in ignored dataset/preprocessing and test-report directories.
Public summary contains document IDs, aggregate telemetry, null CER/WER only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ai.ocr.tesseract import TesseractOCR  # noqa: E402
from app.documents.pipeline import analyze_document  # noqa: E402
from app.documents.preprocessing import _rotation, preprocess_image  # noqa: E402


def degraded_versions(rgb):
    for angle in (5,10,90,180,270):
        yield f"rotation_{angle}", _rotation(rgb,angle)[0]
    yield "blur", cv2.GaussianBlur(rgb,(7,7),1.8)
    rng = np.random.default_rng(20261008)
    yield "noise", np.clip(rgb.astype(float)+rng.normal(0,12,rgb.shape),0,255).astype(np.uint8)
    yield "low_contrast", np.clip(rgb.astype(float)*.4+140,0,255).astype(np.uint8)
    ok,encoded = cv2.imencode(".jpg",cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,20])
    if ok:
        yield "jpeg", cv2.cvtColor(cv2.imdecode(encoded,cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
    shadow = np.linspace(.55,1,rgb.shape[1])[None,:,None]
    yield "shadow", (rgb*shadow).astype(np.uint8)
    h,w = rgb.shape[:2]
    matrix = cv2.getPerspectiveTransform(np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]]),
             np.float32([[w*.08,h*.08],[w*.90,0],[w-1,h*.92],[0,h-1]]))
    yield "perspective",cv2.warpPerspective(rgb,matrix,(w,h),borderValue=(255,255,255))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--degradations",action="store_true")
    parser.add_argument("--max-variants",type=int,default=6)
    args = parser.parse_args()
    root = args.root.resolve()
    private = root / "test-report/prompt-1"
    private.mkdir(parents=True,exist_ok=True)
    summary = {"schema":"preprocessing-benchmark/v1","documents":[],"degradations":[],
               "cer":None,"wer":None,"names_accuracy":None,"dates_accuracy":None,
               "numbers_accuracy":None,"references_accuracy":None,"human_references":0,
               "qwen_status":"NOT_AVAILABLE_IN_ENVIRONMENT","quality_validated":False}
    inputs = sorted((root/"dataset/input").glob("*.pdf"))
    started = time.perf_counter()
    for i,source in enumerate(inputs,1):
        document_id = f"DOC-{i:03d}"
        print(f"Analyse {document_id} ({i}/{len(inputs)}), elapsed={time.perf_counter()-started:.1f}s",flush=True)
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        work = root/"dataset/preprocessing"/document_id
        ir = analyze_document(str(source),str(work),{"ocr_languages":["ara","eng","fra","spa"],
                              "preprocessing_max_variants":args.max_variants})
        assert ir["versions"]["source_sha256"] == sha
        assert hashlib.sha256(source.read_bytes()).hexdigest() == sha
        row = {"id":document_id,"pages":len(ir["pages"]),"original_unchanged":True,
               "human_reference_status":"NOT_AVAILABLE_IN_ENVIRONMENT","ocr_pages":[]}
        for page in ir["pages"]:
            meta = page["preprocessing"]
            row["ocr_pages"].append({"page":page["number"],"profile":meta["profile"],
                "selected":meta["selected_variant"],"before":meta["ocr_before"],"after":meta["ocr_after"],
                "operations":meta["operations"],"protected_candidates":len(page["protected_visual_regions"]),
                "quality":meta["PreprocessingQualityScore"],"variants":len(meta["variants"])})
        summary["documents"].append(row)
        (private/"benchmark-summary.json").write_text(json.dumps(summary,indent=2))
    if args.degradations and inputs:
        doc = fitz.open(inputs[0])
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
        rgb = np.asarray(Image.frombytes("RGB",[pix.width,pix.height],pix.samples))
        doc.close()
        ocr = TesseractOCR(["ara","eng","fra","spa"])
        for name, degraded in degraded_versions(rgb):
            print(f"Dégradation {name}, elapsed={time.perf_counter()-started:.1f}s",flush=True)
            result = preprocess_image(Image.fromarray(degraded),ocr,root/"dataset/regression"/name,
                    profile="mobile_photo" if name=="perspective" else "auto",max_variants=args.max_variants)
            summary["degradations"].append({"case":name,"source":"DOC-001/page-1",
                "quality":result.metadata["PreprocessingQualityScore"],"selected":result.metadata["selected_variant"],
                "before":result.metadata["ocr_before"],"after":result.metadata["ocr_after"],
                "operations":result.metadata["operations"],"cer":None,"wer":None,"validated":False})
            (private/"benchmark-summary.json").write_text(json.dumps(summary,indent=2))
    summary["duration_seconds"] = time.perf_counter()-started
    summary["pages"] = sum(d["pages"] for d in summary["documents"])
    (private/"benchmark-summary.json").write_text(json.dumps(summary,indent=2))
    print(f"Terminé: {len(inputs)} documents, {summary['pages']} pages, {len(summary['degradations'])} dégradations",flush=True)


if __name__ == "__main__":
    main()
