"""OCR local déterministe, sans téléchargement implicite ni appel réseau.

Le backend historique ``TesseractOCR`` reste disponible.  La sélection des langues
est faite à partir des langues demandées et des scripts observés, tandis que les
scores OCR restent des signaux de confiance et non une exactitude validée.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

AVAILABLE_DEFAULT = {"ara", "eng", "fra", "osd"}
LANG_ALIASES = {
    "en": "eng",
    "fr": "fra",
    "de": "deu",
    "it": "ita",
    "es": "spa",
    "nl": "nld",
    "ar": "ara",
    "deu": "deu",
    "eng": "eng",
    "fra": "fra",
    "ita": "ita",
    "nld": "nld",
    "spa": "spa",
    "ara": "ara",
}
LANGUAGE_SCRIPTS = {
    "ara": "arabic",
    "eng": "latin",
    "fra": "latin",
    "deu": "latin",
    "ita": "latin",
    "nld": "latin",
    "spa": "latin",
}


@dataclass
class OCRResult:
    blocks: list[dict[str, Any]]
    text: str
    requested_languages: list[str]
    used_languages: list[str]
    warnings: list[dict[str, Any]]
    script: str = "unknown"
    language_scores: dict[str, float] = field(default_factory=dict)
    uncertainties: list[dict[str, Any]] = field(default_factory=list)
    backend: str = "tesseract"


def normalize_languages(languages: Iterable[str] | str | None) -> list[str]:
    values = languages.split("+") if isinstance(languages, str) else (languages or [])
    result: list[str] = []
    for value in values:
        code = LANG_ALIASES.get(str(value).strip().casefold(), str(value).strip().casefold())
        if code and code not in result:
            result.append(code)
    return result


def detect_script(text: str) -> str:
    counts = Counter()
    for char in text or "":
        code = ord(char)
        if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F:
            counts["arabic"] += 1
        elif char.isalpha():
            counts["latin"] += 1
    if not counts:
        return "unknown"
    script, count = counts.most_common(1)[0]
    total = sum(counts.values())
    return script if count / total >= 0.45 else "mixed"


def select_languages(
    requested: Iterable[str] | str | None,
    available: Iterable[str],
    text: str = "",
) -> tuple[list[str], list[dict[str, Any]], str]:
    """Select local OCR languages, never installing or downloading a model.

    A caller-provided list is authoritative except for unavailable local traineddata.
    When no list is provided, script evidence narrows the local corpus where possible.
    """
    available_set = {str(x) for x in available}
    requested_codes = normalize_languages(requested)
    script = detect_script(text)
    warnings: list[dict[str, Any]] = []
    if requested_codes:
        candidates = requested_codes
    elif script == "arabic":
        candidates = ["ara"]
    elif script == "latin":
        candidates = ["eng", "fra", "deu", "ita", "nld", "spa"]
    else:
        candidates = ["ara", "deu", "eng", "fra", "ita", "nld", "spa"]
    used = [code for code in candidates if code in available_set and code != "osd"]
    missing = [code for code in candidates if code not in available_set and code != "osd"]
    if missing:
        warnings.append(
            {
                "code": "OCR_LANGUAGE_UNAVAILABLE",
                "severity": "warning",
                "message": f"Langues OCR locales absentes: {', '.join(missing)}; aucun téléchargement n'est effectué.",
                "requested": missing,
            }
        )
    if not used:
        fallback = [code for code in ("eng", "fra", "ara") if code in available_set]
        used = fallback
        if fallback:
            warnings.append(
                {
                    "code": "OCR_LANGUAGE_FALLBACK",
                    "severity": "warning",
                    "message": "Aucune langue demandée n'est disponible localement; repli explicite.",
                    "used": fallback,
                }
            )
    if not used:
        raise RuntimeError("Aucune langue Tesseract locale utilisable")
    return used, warnings, script


def _uncertainties(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    for block in blocks:
        confidence = block.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.70:
            issues.append(
                {
                    "code": "OCR_LOW_CONFIDENCE",
                    "severity": "warning",
                    "block_id": block.get("id"),
                    "confidence": float(confidence),
                    "message": "Confiance OCR basse; ce signal ne constitue pas une validation humaine.",
                }
            )
    return issues


class TesseractOCR:
    def __init__(self, languages: list[str] | str | None = None, psm: int = 3, timeout: float = 90):
        self.requested = normalize_languages(languages)
        self.psm = int(psm)
        if not 0 <= self.psm <= 13 or not 1 <= float(timeout) <= 300:
            raise ValueError("Configuration OCR hors limites")
        self.timeout = float(timeout)
        self._available = self.available_languages()

    @staticmethod
    def available_languages() -> set[str]:
        try:
            import pytesseract

            return set(pytesseract.get_languages(config=""))
        except Exception:
            return set()

    def resolve_languages(self, text: str = "") -> tuple[list[str], list[dict[str, Any]]]:
        used, warnings, _script = select_languages(self.requested, self._available, text)
        return used, warnings

    def image_to_blocks(self, image) -> OCRResult:
        import pytesseract
        from pytesseract import Output

        used, warnings, script = select_languages(self.requested, self._available)
        config = f"--psm {self.psm}"
        data = pytesseract.image_to_data(
            image, lang="+".join(used), config=config, output_type=Output.DICT, timeout=self.timeout
        )
        groups: dict[tuple[int, int, int], dict[str, Any]] = {}
        n = len(data.get("text", []))
        for i in range(n):
            raw = (data["text"][i] or "").strip()
            if not raw:
                continue
            try:
                confidence = max(0.0, min(1.0, float(data["conf"][i]) / 100.0))
            except (ValueError, TypeError):
                confidence = 0.0
            key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
            item = groups.setdefault(
                key,
                {"text": [], "left": [], "top": [], "right": [], "bottom": [], "confidence": []},
            )
            x, y, w, h = [int(data[k][i]) for k in ("left", "top", "width", "height")]
            item["text"].append(raw)
            item["left"].append(x)
            item["top"].append(y)
            item["right"].append(x + w)
            item["bottom"].append(y + h)
            item["confidence"].append(confidence)
        blocks = []
        for item in groups.values():
            blocks.append(
                {
                    "text": " ".join(item["text"]),
                    "bbox": [
                        min(item["left"]),
                        min(item["top"]),
                        max(item["right"]),
                        max(item["bottom"]),
                    ],
                    "confidence": sum(item["confidence"]) / len(item["confidence"]),
                    "provenance": "ocr:tesseract-local",
                }
            )
        blocks.sort(key=lambda block: (block["bbox"][1], block["bbox"][0]))
        uncertainties = _uncertainties(blocks)
        warnings.extend(uncertainties)
        return OCRResult(
            blocks=blocks,
            text="\n".join(block["text"] for block in blocks),
            requested_languages=self.requested or used,
            used_languages=used,
            warnings=warnings,
            script=detect_script("\n".join(block["text"] for block in blocks)) or script,
            language_scores={code: 1.0 / len(used) for code in used},
            uncertainties=uncertainties,
        )
