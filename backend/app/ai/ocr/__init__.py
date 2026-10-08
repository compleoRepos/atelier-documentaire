"""Backends OCR locaux et sans téléchargement implicite."""

from .paddle_local import PaddleAssetsError, PaddleOCRLocal
from .tesseract import OCRResult, TesseractOCR, detect_script, normalize_languages, select_languages

__all__ = [
    "OCRResult",
    "TesseractOCR",
    "PaddleOCRLocal",
    "PaddleAssetsError",
    "detect_script",
    "normalize_languages",
    "select_languages",
]
