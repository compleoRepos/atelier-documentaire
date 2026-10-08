"""Adaptateur PaddleOCR local.

L'adaptateur ne construit jamais PaddleOCR sans répertoires de modèles explicites.
Il est donc compatible avec une image privée pré-chargée et échoue fermement plutôt
que de déclencher le téléchargement implicite de poids.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from .tesseract import OCRResult, detect_script, normalize_languages


class PaddleAssetsError(RuntimeError):
    """Assets PaddleOCR absents, incomplets ou non locaux."""


class PaddleOCRLocal:
    def __init__(
        self, languages=None, assets: dict[str, str] | None = None, *, use_gpu: bool = False
    ):
        self.requested_languages = normalize_languages(languages)
        self.assets = {key: Path(value).expanduser() for key, value in (assets or {}).items()}
        self.use_gpu = bool(use_gpu)
        self._engine = None
        self._validate_assets()

    def _validate_assets(self) -> None:
        required = ("det_model_dir", "rec_model_dir")
        missing = [key for key in required if key not in self.assets]
        absent = [
            str(self.assets[key])
            for key in required
            if key in self.assets and not self.assets[key].is_dir()
        ]
        if missing or absent:
            raise PaddleAssetsError(
                "PaddleOCR local exige det_model_dir et rec_model_dir existants; "
                f"manquants={missing}, absents={absent}. Aucun autodownload n'est autorisé."
            )

    @property
    def backend(self) -> str:
        return "paddleocr-local"

    def _build_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover - dépendance optionnelle
            raise PaddleAssetsError("PaddleOCR n'est pas installé dans ce worker privé.") from exc
        signature = inspect.signature(PaddleOCR)
        options: dict[str, Any] = {
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            "device": "gpu:0" if self.use_gpu else "cpu",
            "det_model_dir": str(self.assets["det_model_dir"]),
            "rec_model_dir": str(self.assets["rec_model_dir"]),
        }
        if "cls_model_dir" in self.assets:
            options["cls_model_dir"] = str(self.assets["cls_model_dir"])
        if "lang" in signature.parameters and self.requested_languages:
            options["lang"] = self.requested_languages[0]
        # Only pass options understood by the installed PaddleOCR API.  Every model
        # directory remains explicit; filtering is for v2/v3 API compatibility.
        accepted = {key: value for key, value in options.items() if key in signature.parameters}
        self._engine = PaddleOCR(**accepted)
        return self._engine

    @staticmethod
    def _result_blocks(raw: Any) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        # PaddleOCR 3.x returns Result objects; tests and v2 wrappers often return
        # dictionaries/lists. Keep parsing conservative and provenance explicit.
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            payload = item.json if hasattr(item, "json") else item
            if callable(payload):
                payload = payload()
            if isinstance(payload, dict):
                payload = payload.get("res", payload)
                texts = payload.get("rec_texts", [])
                scores = payload.get("rec_scores", [])
                polys = payload.get("rec_polys", payload.get("dt_polys", []))
                for index, text in enumerate(texts):
                    polygon = polys[index] if index < len(polys) else []
                    points = [list(point) for point in polygon] if polygon is not None else []
                    xs = [point[0] for point in points if len(point) >= 2]
                    ys = [point[1] for point in points if len(point) >= 2]
                    bbox = [min(xs), min(ys), max(xs), max(ys)] if xs and ys else [0, 0, 0, 0]
                    confidence = float(scores[index]) if index < len(scores) else None
                    blocks.append(
                        {
                            "text": str(text),
                            "bbox": bbox,
                            "confidence": confidence,
                            "provenance": "ocr:paddle-local",
                        }
                    )
            elif isinstance(payload, list):
                # v2: [[polygon, (text, score)], ...]
                for entry in payload:
                    if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                        continue
                    polygon, recognised = entry[0], entry[1]
                    text = (
                        recognised[0] if isinstance(recognised, (list, tuple)) else str(recognised)
                    )
                    score = (
                        recognised[1]
                        if isinstance(recognised, (list, tuple)) and len(recognised) > 1
                        else None
                    )
                    points = [list(point) for point in polygon] if polygon else []
                    xs = [point[0] for point in points if len(point) >= 2]
                    ys = [point[1] for point in points if len(point) >= 2]
                    blocks.append(
                        {
                            "text": text,
                            "bbox": [min(xs), min(ys), max(xs), max(ys)]
                            if xs and ys
                            else [0, 0, 0, 0],
                            "confidence": float(score) if score is not None else None,
                            "provenance": "ocr:paddle-local",
                        }
                    )
        return sorted(blocks, key=lambda block: (block["bbox"][1], block["bbox"][0]))

    def image_to_blocks(self, image) -> OCRResult:
        engine = self._build_engine()
        if hasattr(engine, "predict"):
            raw = engine.predict(image)
        elif hasattr(engine, "ocr"):
            raw = engine.ocr(image, cls=False)
        else:  # pragma: no cover
            raise RuntimeError("API PaddleOCR locale inconnue: predict/ocr absent")
        blocks = self._result_blocks(raw)
        uncertainties = [
            {
                "code": "OCR_LOW_CONFIDENCE",
                "severity": "warning",
                "confidence": block["confidence"],
                "message": "Confiance PaddleOCR basse; aucune validation humaine.",
            }
            for block in blocks
            if isinstance(block.get("confidence"), (int, float)) and block["confidence"] < 0.70
        ]
        return OCRResult(
            blocks=blocks,
            text="\n".join(block["text"] for block in blocks),
            requested_languages=self.requested_languages,
            used_languages=self.requested_languages,
            warnings=uncertainties,
            script=detect_script("\n".join(block["text"] for block in blocks)),
            uncertainties=uncertainties,
            backend=self.backend,
        )
