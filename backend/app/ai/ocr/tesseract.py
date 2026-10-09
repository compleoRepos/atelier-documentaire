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


LINE_SPLIT_GAP_FACTOR = 2.0
LINE_SPLIT_TALL_WORD_FACTOR = 2.2


def split_line_at_gaps(
    item: dict[str, list[Any]],
    factor: float = LINE_SPLIT_GAP_FACTOR,
    tall_factor: float = LINE_SPLIT_TALL_WORD_FACTOR,
) -> list[dict[str, Any]]:
    """Split one Tesseract line where two consecutive words (left to right) are
    separated by a blank >= ``factor`` x the median word height.

    Measured on the authorised corpus: Tesseract groups texts of separate form
    cells, columns or zones into ONE line when they share a baseline (a ministry
    name and a header 265 pt apart, four form cells, a footer and its far-right
    "Page No:"). One line box then spans the blank: the size estimated from its
    width was 19.9 pt for 7 pt print and the translation was written across the
    cells. A normal space is ~0.3 x the word height and a justified one stays
    below 1 x, so 2 x only separates distinct zones. Each segment keeps its own
    box and mean confidence; its text keeps the OCR reading order (RTL safe).

    In lines of >= 3 words, a "word" >= ``tall_factor`` x the median word height
    is isolated as its own segment: it is a graphic read as a glyph (a crest
    fragment read as "2" made a 7 pt line box 22.5 pt tall: font 12.7 pt and a
    mask erasing the line above). Ascender/descender variation stays < 2 x.
    """
    words = [
        {
            "order": index,
            "text": item["text"][index],
            "left": item["left"][index],
            "top": item["top"][index],
            "right": item["right"][index],
            "bottom": item["bottom"][index],
            "confidence": item["confidence"][index],
        }
        for index in range(len(item["text"]))
    ]
    heights = sorted(max(1, w["bottom"] - w["top"]) for w in words)
    median = heights[len(heights) // 2]
    threshold = factor * median
    tall = (
        {w["order"] for w in words if (w["bottom"] - w["top"]) >= tall_factor * median}
        if len(words) >= 3
        else set()
    )
    by_x = sorted(words, key=lambda w: (w["left"], w["order"]))
    segments: list[list[dict[str, Any]]] = [[by_x[0]]]
    right = by_x[0]["right"]
    for previous, word in zip(by_x, by_x[1:], strict=False):
        isolate = word["order"] in tall or previous["order"] in tall
        if isolate or word["left"] - right >= threshold:
            segments.append([word])
        else:
            segments[-1].append(word)
        right = max(right, word["right"])
    out = []
    for segment in segments:
        ordered = sorted(segment, key=lambda w: w["order"])
        out.append(
            {
                "text": " ".join(w["text"] for w in ordered),
                "bbox": [
                    min(w["left"] for w in segment),
                    min(w["top"] for w in segment),
                    max(w["right"] for w in segment),
                    max(w["bottom"] for w in segment),
                ],
                "confidence": sum(w["confidence"] for w in segment) / len(segment),
            }
        )
    return out


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
        try:
            data = pytesseract.image_to_data(
                image,
                lang="+".join(used),
                config=config,
                output_type=Output.DICT,
                timeout=self.timeout,
            )
        except RuntimeError as exc:
            # pytesseract raises RuntimeError("Tesseract process timeout") when
            # the CPU is saturated. One bounded retry (2x, max 300 s) instead of
            # failing the whole document; any other error is re-raised as is.
            if "timeout" not in str(exc).lower() or self.timeout >= 300:
                raise
            retry_timeout = min(300.0, 2.0 * self.timeout)
            data = pytesseract.image_to_data(
                image,
                lang="+".join(used),
                config=config,
                output_type=Output.DICT,
                timeout=retry_timeout,
            )
            warnings = [
                *warnings,
                {
                    "code": "OCR_TIMEOUT_RETRIED",
                    "severity": "info",
                    "message": "OCR relancé une fois après dépassement du délai",
                    "timeout_s": self.timeout,
                    "retry_timeout_s": retry_timeout,
                },
            ]
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
        split_lines = 0
        for item in groups.values():
            segments = split_line_at_gaps(item)
            split_lines += len(segments) > 1
            for segment in segments:
                blocks.append({**segment, "provenance": "ocr:tesseract-local"})
        if split_lines:
            warnings = [
                *warnings,
                {
                    "code": "OCR_LINE_SPLIT_AT_GAP",
                    "severity": "info",
                    "message": "Lignes OCR découpées aux grands blancs (colonnes, cellules ou zones distinctes lues comme une seule ligne)",
                    "count": split_lines,
                },
            ]
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
