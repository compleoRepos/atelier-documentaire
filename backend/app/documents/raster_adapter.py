"""Lossless raster ingestion adapter for existing PDF renderers (not a renderer).

Each TIFF frame is embedded as original RGB pixels in a processing PDF. Page
coordinates stay in source pixels; the immutable uploaded TIFF is never changed.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import fitz
from PIL import Image, ImageSequence


def raster_pdf_copy(source_path, output_path, *, max_pages=200, max_pixels=24_000_000):
    source, output = Path(source_path).resolve(), Path(output_path).resolve()
    if source == output:
        raise ValueError("Original cannot be overwritten")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    document = fitz.open()
    try:
        with Image.open(source) as image:
            if getattr(image,"n_frames",1) > max_pages:
                raise ValueError("PAGE_LIMIT")
            for frame in ImageSequence.Iterator(image):
                if frame.width*frame.height > max_pixels:
                    raise ValueError("PREPROCESSING_PIXEL_LIMIT")
                stream = io.BytesIO()
                frame.convert("RGB").save(stream,format="PNG")
                page = document.new_page(width=frame.width,height=frame.height)
                page.insert_image(page.rect,stream=stream.getvalue())
        document.save(output,deflate=True)
    finally:
        document.close()
    if hashlib.sha256(source.read_bytes()).hexdigest() != sha:
        raise RuntimeError("ORIGINAL_INTEGRITY_MISMATCH")
    return output
