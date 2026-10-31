"""Client OCR Surya du produit.

Le produit n'importe jamais Surya : il appelle le service local
``services/ocr-surya`` (client officiel surya-ocr + serveur llama.cpp local).

Contrat de sortie identique aux autres moteurs (``OCRResult``) : des blocs
« ligne » ``{text, bbox, confidence}`` en pixels de l'image reçue, car la
segmentation du produit regroupe des LIGNES en paragraphes (hauteur de ligne,
interligne, taille de police).

Surya rend des BLOCS (paragraphes, tableaux) sans position par ligne. Le texte
de chaque bloc est exact (sortie du modèle) ; la position de chaque ligne est
ESTIMÉE par projection de l'encre dans le bloc, puis le texte est réparti sur
ces lignes sans jamais couper un mot. Cette estimation est signalée par un
avertissement explicite (``OCR_SURYA_LINE_GEOMETRY_ESTIMATED``).

Aucun repli silencieux : si le service est indisponible, l'analyse échoue
avec ``OCR_SURYA_UNAVAILABLE``. Tesseract n'est jamais appelé dans ce mode.
"""

from __future__ import annotations

import io
import statistics
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.ai.ocr.tesseract import OCRResult, detect_script

BACKEND = "surya"
GEOMETRY_VERSION = "surya-lines-v1"
LOW_CONFIDENCE = 0.70
DEFAULT_TIMEOUT_SECONDS = 900.0
RULE_ROW_SHARE = 0.85
INK_ROW_SHARE = 0.003
THIN_BAND_SHARE = 0.40


class SuryaOCRError(RuntimeError):
    """Erreur explicite du moteur Surya (aucun contenu documentaire dans le message)."""


@dataclass
class SuryaOCRResult(OCRResult):
    version: str = ""
    model: str = ""
    engine_seconds: float = 0.0
    geometry: str = GEOMETRY_VERSION


def validated_url(url: str | None, allowed_hosts: list[str]) -> str:
    """URL du service : schéma http(s), sans identifiants, hôte explicitement autorisé."""
    if not url:
        raise SuryaOCRError("OCR_SURYA_URL_REQUIRED")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SuryaOCRError("OCR_SURYA_URL_INVALID")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SuryaOCRError("OCR_SURYA_URL_INVALID")
    if parsed.hostname.lower() not in {h.lower() for h in allowed_hosts}:
        raise SuryaOCRError("OCR_SURYA_HOST_NOT_ALLOWED")
    return url.rstrip("/")


# --------------------------------------------------------------------------
# Géométrie : lignes estimées par projection de l'encre (déterministe, numpy).
# --------------------------------------------------------------------------


def _runs(mask) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def _ink_threshold(gray) -> float:
    """Seuil d'encre relatif au FOND (90e centile), robuste aux zones très encrées.

    La médiane devient noire dès que l'encre couvre plus de la moitié du recadrage
    (rangée dense, gras, aplat) : le seuil tomberait alors à 0 et plus rien ne serait
    vu comme de l'encre. Sur une page ordinaire, fond = médiane : comportement égal.
    """
    import numpy as np

    return min(170.0, float(np.percentile(gray, 90)) * 0.75)


def ink_bands(gray) -> list[list[int]]:
    """Bandes horizontales d'encre ``[x0, y0, x1, y1]`` (coordonnées du recadrage).

    Les filets horizontaux (lignes de tableau) sont ignorés ; les bandes très
    minces (accents, points diacritiques, signes suscrits) sont fusionnées avec
    la bande voisine la plus proche.
    """
    import numpy as np

    gray = np.asarray(gray, dtype=np.float32)
    if gray.ndim != 2 or gray.shape[0] < 2 or gray.shape[1] < 2:
        return []
    height, width = gray.shape
    ink = gray < _ink_threshold(gray)
    ink[ink.sum(axis=1) > RULE_ROW_SHARE * width] = False
    # Filets verticaux MINCES sur toute la hauteur (grille de tableau, barre de marge) :
    # exclus de la projection, sinon toutes les rangées fusionnent en une seule bande.
    vertical = np.zeros(width, dtype=bool)
    thin = max(4, int(0.01 * width))
    for a, b in _runs(ink.sum(axis=0) > RULE_ROW_SHARE * height):
        if b - a <= thin:
            vertical[a:b] = True
    projected = ink & ~vertical[None, :]
    rows = projected.sum(axis=1) >= max(1, int(INK_ROW_SHARE * width))
    bands = [[a, b] for a, b in _runs(rows)]
    if not bands:
        return []
    changed = True
    while changed and len(bands) > 1:
        changed = False
        median = statistics.median(b - a for a, b in bands)
        for i, (a, b) in enumerate(bands):
            if b - a >= THIN_BAND_SHARE * median:
                continue
            gap_up = a - bands[i - 1][1] if i > 0 else None
            gap_down = bands[i + 1][0] - b if i + 1 < len(bands) else None
            j = i - 1 if gap_down is None or (gap_up is not None and gap_up <= gap_down) else i + 1
            lo, hi = sorted((i, j))
            bands[lo : hi + 1] = [
                [min(bands[lo][0], bands[hi][0]), max(bands[lo][1], bands[hi][1])]
            ]
            changed = True
            break
    # Recadrage d'une seule ligne : un fût de glyphe peut couvrir toute la hauteur,
    # l'étendue horizontale garde alors toute l'encre.
    extent = projected if len(bands) > 1 else ink
    boxes = []
    for a, b in bands:
        cols = np.flatnonzero(extent[a:b].any(axis=0))
        if cols.size:
            boxes.append([int(cols[0]), int(a), int(cols[-1]) + 1, int(b)])
    return boxes


def _even_rows(box: list[float], count: int) -> list[list[float]]:
    x0, y0, x1, y1 = box
    step = (y1 - y0) / max(1, count)
    return [[x0, y0 + i * step, x1, y0 + (i + 1) * step] for i in range(count)]


def _split_words(words: list[str], widths: list[float]) -> list[str]:
    """Répartit des mots (jamais coupés) sur des lignes au prorata de leur largeur."""
    total_chars = sum(len(w) for w in words) + max(0, len(words) - 1)
    total_width = sum(widths) or 1.0
    targets, acc = [], 0.0
    for width in widths:
        acc += width
        targets.append(total_chars * acc / total_width)
    parts: list[list[str]] = [[] for _ in widths]
    position, line = 0.0, 0
    for word in words:
        middle = position + len(word) / 2.0
        while line < len(widths) - 1 and middle > targets[line]:
            line += 1
        parts[line].append(word)
        position += len(word) + 1
    return [" ".join(p) for p in parts]


def allocate_lines(
    lines: list[str], bands: list[list[float]], box: list[float]
) -> tuple[list[tuple[str, list[float]]], bool]:
    """Associe les lignes logiques Surya aux bandes d'encre. Retourne (lignes, estimée)."""
    lines = [line for line in lines if line.strip()]
    if not lines:
        return [], False
    if len(bands) == len(lines):
        return list(zip(lines, bands, strict=True)), False
    if len(bands) < len(lines):
        return list(zip(lines, _even_rows(box, len(lines)), strict=True)), True
    widths = [b[2] - b[0] for b in bands]
    chars = [len(line) for line in lines]
    per_px = sum(chars) / (sum(widths) or 1.0)
    out: list[tuple[str, list[float]]] = []
    index = 0
    for i, line in enumerate(lines):
        remaining_lines = len(lines) - i - 1
        if remaining_lines == 0:
            take = len(bands) - index
        else:
            take, capacity = 1, widths[index] * per_px
            while capacity < 0.9 * chars[i] and len(bands) - (index + take) > remaining_lines:
                capacity += widths[index + take] * per_px
                take += 1
        group = bands[index : index + take]
        index += take
        for text, band in zip(
            _split_words(line.split(), [b[2] - b[0] for b in group]), group, strict=True
        ):
            if text:
                out.append((text, band))
    return out, True


def _columns(gray_row, count: int, box: list[float]) -> list[list[float]]:
    """Colonnes d'une ligne de tableau : intervalles d'encre, sinon partage égal."""
    import numpy as np

    x0, y0, x1, y1 = box
    if count <= 1:
        return [box]
    gray_row = np.asarray(gray_row, dtype=np.float32)
    if gray_row.size:
        ink = gray_row < _ink_threshold(gray_row)
        # Filet vertical = tracé MINCE couvrant toute la hauteur de la rangée ; un aplat
        # ou un glyphe épais de même hauteur n'est jamais effacé (sinon partage égal à tort).
        full = ink.sum(axis=0) > RULE_ROW_SHARE * ink.shape[0]
        thin = max(4, int(0.01 * ink.shape[1]))
        for a, b in _runs(full):
            if b - a <= thin:
                ink[:, a:b] = False
        segments = [list(r) for r in _runs(ink.any(axis=0))]
        while len(segments) > count:
            gaps = [segments[k + 1][0] - segments[k][1] for k in range(len(segments) - 1)]
            k = gaps.index(min(gaps))
            segments[k : k + 2] = [[segments[k][0], segments[k + 1][1]]]
        if len(segments) == count:
            return [[x0 + a, y0, x0 + b, y1] for a, b in segments]
    step = (x1 - x0) / count
    return [[x0 + k * step, y0, x0 + (k + 1) * step, y1] for k in range(count)]


def page_to_line_blocks(page: dict, gray) -> tuple[list[dict], dict]:
    """Convertit la réponse pleine page Surya en blocs « ligne » du produit."""
    import numpy as np

    gray = np.asarray(gray, dtype=np.float32)
    height, width = gray.shape
    blocks: list[dict] = []
    stats = {
        "surya_blocks": 0,
        "estimated_lines": 0,
        "exact_band_lines": 0,
        "table_cells": 0,
        "errors": 0,
        "skipped": 0,
    }
    ordered = sorted(page.get("blocks") or [], key=lambda b: int(b.get("reading_order", 0)))
    for block in ordered:
        if block.get("skipped"):
            stats["skipped"] += 1
            continue
        if block.get("error"):
            stats["errors"] += 1
        x0, y0, x1, y1 = (float(v) for v in block.get("bbox") or (0, 0, 0, 0))
        x0, y0 = max(0.0, min(x0, width)), max(0.0, min(y0, height))
        x1, y1 = max(x0, min(x1, width)), max(y0, min(y1, height))
        if x1 - x0 < 1 or y1 - y0 < 1:
            continue
        box = [x0, y0, x1, y1]
        stats["surya_blocks"] += 1
        confidence = float(block.get("confidence") or 0.0)
        crop = gray[int(y0) : int(np.ceil(y1)), int(x0) : int(np.ceil(x1))]
        bands = [[x0 + b[0], y0 + b[1], x0 + b[2], y0 + b[3]] for b in ink_bands(crop)]
        if block.get("kind") == "table" and block.get("rows"):
            rows = [r for r in block["rows"] if any(c.strip() for c in r)]
            row_boxes = bands if len(bands) == len(rows) else _even_rows(box, len(rows))
            for cells, row_box in zip(rows, row_boxes, strict=True):
                ry0, ry1 = int(row_box[1]), int(np.ceil(row_box[3]))
                columns = _columns(
                    gray[ry0:ry1, int(x0) : int(np.ceil(x1))],
                    len(cells),
                    [x0, row_box[1], x1, row_box[3]],
                )
                for text, cell_box in zip(cells, columns, strict=True):
                    if text.strip():
                        blocks.append(
                            {"text": text.strip(), "bbox": cell_box, "confidence": confidence}
                        )
                        stats["table_cells"] += 1
            continue
        lines, estimated = allocate_lines(list(block.get("lines") or []), bands, box)
        for text, line_box in lines:
            blocks.append(
                {"text": text, "bbox": [float(v) for v in line_box], "confidence": confidence}
            )
        stats["estimated_lines" if estimated else "exact_band_lines"] += len(lines)
    return blocks, stats


# --------------------------------------------------------------------------
# Client HTTP
# --------------------------------------------------------------------------


def _png(image) -> bytes:
    from PIL import Image

    if not isinstance(image, Image.Image):
        import numpy as np

        image = Image.fromarray(np.asarray(image))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


class SuryaOCRClient:
    """Moteur OCR ``surya`` : même interface que ``TesseractOCR.image_to_blocks``."""

    backend = BACKEND
    # Réservé aux tests (httpx.MockTransport) ; jamais configuré en exploitation.
    transport_override: Any = None

    def __init__(
        self,
        base_url: str,
        *,
        allowed_hosts: list[str],
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Any = None,
    ) -> None:
        self.base_url = validated_url(base_url, allowed_hosts)
        self._token = token or None
        self._timeout = float(timeout)
        self._transport = transport if transport is not None else type(self).transport_override

    @classmethod
    def from_settings(cls, settings: Any = None) -> SuryaOCRClient:
        if settings is None:
            from app.core.settings import get_settings

            settings = get_settings()
        return cls(
            settings.surya_ocr_url,
            allowed_hosts=settings.surya_hosts,
            token=settings.surya_ocr_token,
            timeout=settings.surya_ocr_timeout_seconds,
        )

    @classmethod
    def from_options(cls, options: dict) -> SuryaOCRClient:
        # L'URL et le jeton viennent UNIQUEMENT des réglages serveur, jamais des
        # options de tâche (qui peuvent être journalisées ou persistées).
        return cls.from_settings()

    def adjust_options(self, options: dict) -> dict:
        """Une seule lecture Surya par page, sans détection d'orientation Tesseract.

        Le prétraitement multi-variantes relance l'OCR sur chaque variante
        (jusqu'à 6) : à 30-90 s par page avec Surya, ce coût est prohibitif et
        le critère de choix (confiance OCR) n'est pas discriminant pour Surya.
        """
        out = dict(options)
        out["preprocessing_max_variants"] = int(options.get("surya_preprocessing_max_variants", 1))
        out["preprocessing_orientation"] = False
        return out

    def _post(self, path: str, image) -> dict:
        import httpx

        headers = {"Content-Type": "image/png"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self._timeout, connect=5.0),
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.post(self.base_url + path, content=_png(image), headers=headers)
        except httpx.HTTPError as exc:
            raise SuryaOCRError("OCR_SURYA_UNAVAILABLE") from exc
        if response.status_code != 200:
            raise SuryaOCRError(f"OCR_SURYA_HTTP_{response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SuryaOCRError("OCR_SURYA_BAD_RESPONSE") from exc
        if not isinstance(payload, dict) or payload.get("engine") != "surya-ocr":
            raise SuryaOCRError("OCR_SURYA_BAD_RESPONSE")
        return payload

    def image_to_blocks(self, image) -> SuryaOCRResult:
        import numpy as np

        page = self._post("/v1/ocr/page", image)
        gray = np.asarray(image.convert("L") if hasattr(image, "convert") else image)
        if gray.ndim == 3:
            gray = gray.mean(axis=2)
        size = page.get("image_size") or [gray.shape[1], gray.shape[0]]
        if [int(size[0]), int(size[1])] != [gray.shape[1], gray.shape[0]]:
            raise SuryaOCRError("OCR_SURYA_SIZE_MISMATCH")
        blocks, stats = page_to_line_blocks(page, gray)
        text = "\n".join(b["text"] for b in blocks)
        warnings = [
            {
                "code": "OCR_ORIENTATION_NOT_CHECKED",
                "severity": "warning",
                "message": "Orientation non vérifiée par un détecteur dédié en mode Surya ; contrôler visuellement une page pivotée.",
            }
        ]
        if stats["estimated_lines"] or stats["table_cells"]:
            warnings.append(
                {
                    "code": "OCR_SURYA_LINE_GEOMETRY_ESTIMATED",
                    "severity": "info",
                    "message": "Texte Surya exact par bloc ; position des lignes ou cellules estimée par projection de l'encre.",
                    "estimated_lines": stats["estimated_lines"],
                    "table_cells": stats["table_cells"],
                }
            )
        if stats["errors"]:
            warnings.append(
                {
                    "code": "OCR_SURYA_BLOCK_ERROR",
                    "severity": "warning",
                    "message": "Bloc Surya en erreur ou tronqué ; relecture humaine requise.",
                    "blocks": stats["errors"],
                }
            )
        if not blocks:
            warnings.append(
                {
                    "code": "OCR_NO_TEXT",
                    "severity": "warning",
                    "message": "Aucun texte reconnu par Surya sur la page.",
                }
            )
        uncertainties = [
            {
                "code": "OCR_LOW_CONFIDENCE",
                "severity": "warning",
                "block_index": index,
                "confidence": block["confidence"],
                "message": "Confiance OCR basse; ce signal ne constitue pas une validation humaine.",
            }
            for index, block in enumerate(blocks)
            if block["confidence"] < LOW_CONFIDENCE
        ]
        return SuryaOCRResult(
            blocks=blocks,
            text=text,
            requested_languages=[],
            used_languages=[],
            warnings=warnings,
            script=detect_script(text),
            uncertainties=uncertainties,
            backend=BACKEND,
            version=str(page.get("engine_version") or ""),
            model=str(page.get("model") or ""),
            engine_seconds=float(page.get("seconds") or 0.0),
        )

    def line_reader(self, image) -> str | None:
        """Lecteur de double lecture : relit un recadrage ; None = non concluant."""
        try:
            payload = self._post("/v1/ocr/block", image)
        except SuryaOCRError:
            return None
        if payload.get("capped"):
            return None  # lecture tronquée : jamais comparée comme si elle était complète
        text = payload.get("text")
        return text if isinstance(text, str) else None

    @classmethod
    def line_verification_kwargs(cls) -> dict:
        """Double lecture par Surya ; reprise F25 (calibrée Tesseract) désactivée."""
        return {"reader": cls.from_settings().line_reader, "recovery": False}
