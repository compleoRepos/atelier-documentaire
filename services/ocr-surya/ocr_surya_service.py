"""Service OCR local Surya (processus séparé du produit).

Ce service exécute le client OFFICIEL ``surya-ocr`` (Apache-2.0) relié à un
serveur d'inférence llama.cpp local qui sert les poids Surya OCR 2.5. Il tourne
dans son propre environnement Python (torch CPU, Pillow < 11 imposés par
surya-ocr) : le produit n'importe jamais Surya, il n'appelle que l'API HTTP
ci-dessous.

Garde-fous :
- écoute sur la boucle locale par défaut ; toute autre adresse exige
  ``OCR_SURYA_ALLOW_NON_LOOPBACK=1`` (réseau interne de conteneurs) ;
- jeton partagé optionnel (``OCR_SURYA_TOKEN``), comparé à temps constant ;
- PNG uniquement (signature + décodeur PNG seul), taille et pixels bornés ;
- aucune donnée documentaire journalisée : seulement tailles, durées, codes.

Points d'entrée :
- ``GET  /health``        état et versions ;
- ``POST /v1/ocr/page``   OCR pleine page (une requête modèle par page) ;
- ``POST /v1/ocr/block``  relecture d'un recadrage (double lecture, reprise).
"""

from __future__ import annotations

import hmac
import io
import ipaddress
import json
import logging
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVICE_VERSION = "1.0.0"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BODY_BYTES = int(os.environ.get("OCR_SURYA_MAX_BODY_BYTES", str(40 * 1024 * 1024)))
MAX_PIXELS = int(os.environ.get("OCR_SURYA_MAX_PIXELS", str(40_000_000)))
MAX_INFLIGHT = max(1, int(os.environ.get("OCR_SURYA_MAX_INFLIGHT", "1")))
MODEL_LABEL = os.environ.get("OCR_SURYA_MODEL_LABEL", "surya-ocr-2.5")
TOKEN = os.environ.get("OCR_SURYA_TOKEN") or None
BLOCK_MAX_TOKENS = int(os.environ.get("OCR_SURYA_BLOCK_MAX_TOKENS", "512"))

LOG = logging.getLogger("ocr_surya_service")
_GATE = threading.BoundedSemaphore(MAX_INFLIGHT)
_STATE: dict = {}

BLOCK_TAGS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "pre", "blockquote", "caption")


def _surya():
    """Charge paresseusement le client officiel (une seule fois)."""
    if "rec" not in _STATE:
        from importlib.metadata import version

        from surya.inference import SuryaInferenceManager
        from surya.recognition import RecognitionPredictor

        manager = SuryaInferenceManager()
        _STATE.update(
            manager=manager,
            rec=RecognitionPredictor(manager),
            version=version("surya-ocr"),
        )
    return _STATE


def html_to_structure(html: str) -> dict:
    """Texte exploitable d'un bloc HTML Surya : lignes logiques ou lignes de tableau."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    table = soup.find("table")
    if table is not None:
        rows = []
        for tr in table.find_all("tr"):
            cells = [
                " ".join(c.get_text(" ", strip=True).split()) for c in tr.find_all(["td", "th"])
            ]
            if any(cells):
                rows.append(cells)
        return {"kind": "table", "rows": rows, "lines": [" ".join(c for c in r if c) for r in rows]}
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(BLOCK_TAGS):
        tag.append("\n")
    lines = [" ".join(line.split()) for line in soup.get_text("").split("\n")]
    return {"kind": "text", "rows": [], "lines": [line for line in lines if line]}


def _bbox(polygon) -> list[float]:
    xs = [float(p[0]) for p in polygon]
    ys = [float(p[1]) for p in polygon]
    return [min(xs), min(ys), max(xs), max(ys)]


def _decode_png(body: bytes):
    from PIL import Image

    if not body.startswith(PNG_SIGNATURE):
        raise ValueError("NOT_PNG")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        image = Image.open(io.BytesIO(body), formats=["PNG"])
    except Image.DecompressionBombError as exc:  # > 2 x limite : refus natif de Pillow
        raise ValueError("PIXEL_LIMIT") from exc
    if image.width * image.height > MAX_PIXELS:
        raise ValueError("PIXEL_LIMIT")
    return image.convert("RGB")


def ocr_page(image) -> dict:
    state = _surya()
    started = time.perf_counter()
    page = state["rec"]([image], full_page=True)[0]
    blocks = []
    for order, block in enumerate(getattr(page, "blocks", []) or []):
        structure = html_to_structure(getattr(block, "html", "") or "")
        blocks.append(
            {
                "label": str(getattr(block, "label", "")),
                "raw_label": str(getattr(block, "raw_label", "") or ""),
                "bbox": [round(v, 2) for v in _bbox(block.polygon)],
                "reading_order": int(getattr(block, "reading_order", order) or order),
                "confidence": float(getattr(block, "confidence", 0.0) or 0.0),
                "skipped": bool(getattr(block, "skipped", False)),
                "error": bool(getattr(block, "error", False)),
                **structure,
            }
        )
    return {
        "engine": "surya-ocr",
        "engine_version": state["version"],
        "model": MODEL_LABEL,
        "service_version": SERVICE_VERSION,
        "image_size": [image.width, image.height],
        "seconds": round(time.perf_counter() - started, 3),
        "blocks": blocks,
    }


def ocr_block(image) -> dict:
    from surya.inference.parsers import clean_block_html
    from surya.inference.prompts import PROMPT_TYPE_BLOCK
    from surya.inference.schema import BatchInputItem

    state = _surya()
    started = time.perf_counter()
    item = BatchInputItem(image=image, prompt_type=PROMPT_TYPE_BLOCK, max_tokens=BLOCK_MAX_TOKENS)
    out = state["manager"].generate([item])[0]
    if getattr(out, "error", False):
        raise RuntimeError("BLOCK_GENERATION_ERROR")
    structure = html_to_structure(clean_block_html(out.raw or ""))
    prob = getattr(out, "mean_token_prob", None)
    return {
        "engine": "surya-ocr",
        "engine_version": state["version"],
        "model": MODEL_LABEL,
        "text": " ".join(structure["lines"]),
        "lines": structure["lines"],
        "confidence": float(prob) if prob is not None else None,
        "capped": getattr(out, "finish_reason", None) == "length",
        "seconds": round(time.perf_counter() - started, 3),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ocr-surya/" + SERVICE_VERSION
    sys_version = ""

    def log_message(self, fmt, *args):  # journal d'accès sans contenu ni requête brute
        return

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if TOKEN is None:
            return True
        supplied = self.headers.get("Authorization", "")
        return hmac.compare_digest(supplied.encode(), f"Bearer {TOKEN}".encode())

    def do_GET(self):  # noqa: N802 - API http.server
        if self.path != "/health":
            return self._send(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})
        # /health reste sans jeton : les sondes Docker/Compose/Kubernetes n'en portent pas ;
        # elle ne renvoie qu'un état et des versions, jamais de contenu documentaire.
        payload = {"status": "ok", "service_version": SERVICE_VERSION, "model": MODEL_LABEL}
        if "version" in _STATE:
            payload["engine_version"] = _STATE["version"]
        return self._send(HTTPStatus.OK, payload)

    def do_POST(self):  # noqa: N802 - API http.server
        route = {"/v1/ocr/page": ocr_page, "/v1/ocr/block": ocr_block}.get(self.path)
        if route is None:
            return self._send(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})
        if not self._authorized():
            return self._send(HTTPStatus.UNAUTHORIZED, {"error": "UNAUTHORIZED"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "BODY_SIZE"})
        body = self.rfile.read(length)
        started = time.perf_counter()
        try:
            image = _decode_png(body)
        except Exception as exc:  # noqa: BLE001 - toute image refusée est un 422 explicite
            code = str(exc) if str(exc) in {"NOT_PNG", "PIXEL_LIMIT"} else type(exc).__name__
            return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": code})
        with _GATE:
            try:
                payload = route(image)
            except Exception as exc:  # noqa: BLE001 - type seul, jamais le contenu
                LOG.warning("ocr_failed route=%s error=%s", self.path, type(exc).__name__)
                return self._send(
                    HTTPStatus.BAD_GATEWAY, {"error": "OCR_FAILED", "type": type(exc).__name__}
                )
        LOG.info(
            "ocr_ok route=%s pixels=%d blocks=%s seconds=%.2f",
            self.path,
            image.width * image.height,
            len(payload.get("blocks", [])) if "blocks" in payload else "-",
            time.perf_counter() - started,
        )
        return self._send(HTTPStatus.OK, payload)


def check_bind(host: str) -> None:
    """Refuse une écoute hors boucle locale sans autorisation explicite."""
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "localhost"
    if not loopback and os.environ.get("OCR_SURYA_ALLOW_NON_LOOPBACK") != "1":
        raise SystemExit(
            "Écoute hors boucle locale refusée (OCR_SURYA_ALLOW_NON_LOOPBACK=1 requis)"
        )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    host = os.environ.get("OCR_SURYA_BIND", "127.0.0.1")
    port = int(os.environ.get("OCR_SURYA_PORT", "8093"))
    check_bind(host)
    server = ThreadingHTTPServer((host, port), Handler)
    LOG.info("ocr-surya %s à l'écoute port=%d inflight=%d", SERVICE_VERSION, port, MAX_INFLIGHT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
