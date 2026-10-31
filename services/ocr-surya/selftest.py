"""Autotest du service ocr-surya, exécuté DANS l'image, sans réseau ni poids.

Usage CI : docker run --rm --network none --entrypoint /opt/surya/bin/python \
    <image> /opt/ocr-surya/selftest.py

Vérifie : import hors ligne du client Surya, conversion HTML -> lignes/tableau, garde
d'écoute en boucle locale, refus des images non PNG / trop grandes, et le protocole HTTP
réel (jeton, /health public, taille de corps, 404) avec un moteur OCR simulé.
Sortie 0 si tout passe ; aucune donnée documentaire n'est utilisée.
"""

from __future__ import annotations

import io
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ocr_surya_service as svc  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool) -> None:
    print(("OK   " if condition else "ÉCHEC ") + name)
    if not condition:
        FAILURES.append(name)


def _png(width: int, height: int) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


def _request(url: str, body: bytes | None = None, token: str | None = None):
    headers = {"Content-Type": "image/png"} if body is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=body, headers=headers, method="POST" if body is not None else "GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def main() -> int:
    # 1. Le client officiel s'importe sans réseau (aucun téléchargement à l'import).
    try:
        from surya.recognition import RecognitionPredictor  # noqa: F401

        check("import hors ligne de surya.recognition", True)
    except Exception as exc:  # noqa: BLE001
        check(f"import hors ligne de surya.recognition ({type(exc).__name__})", False)

    # 2. Conversion HTML -> structure.
    text = svc.html_to_structure("<p>Ligne <b>un</b></p><p>Ligne deux<br>Ligne trois</p>")
    check(
        "texte : lignes extraites dans l'ordre",
        text["lines"] == ["Ligne un", "Ligne deux", "Ligne trois"],
    )
    table = svc.html_to_structure(
        "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    )
    check(
        "tableau : lignes et cellules",
        table.get("kind") == "table" and table.get("rows") == [["A", "B"], ["1", "2"]],
    )

    # 3. Écoute : boucle locale acceptée, hors boucle refusée sans autorisation explicite.
    os.environ.pop("OCR_SURYA_ALLOW_NON_LOOPBACK", None)
    svc.check_bind("127.0.0.1")
    svc.check_bind("::1")
    try:
        svc.check_bind("0.0.0.0")
        refused = False
    except SystemExit:
        refused = True
    check("écoute 0.0.0.0 refusée sans OCR_SURYA_ALLOW_NON_LOOPBACK", refused)

    # 4. Images : non PNG et dépassement de pixels refusés.
    for label, body, expected in (
        ("non PNG refusé", b"GIF89a-not-a-png", "NOT_PNG"),
        ("limite de pixels", _png(80, 80), "PIXEL_LIMIT"),
    ):
        saved = svc.MAX_PIXELS
        svc.MAX_PIXELS = 1000 if expected == "PIXEL_LIMIT" else saved
        try:
            svc._decode_png(body)
            outcome = "accepted"
        except Exception as exc:  # noqa: BLE001
            outcome = str(exc)
        finally:
            svc.MAX_PIXELS = saved
        check(label, outcome == expected)

    # 5. Protocole HTTP réel avec moteur simulé et jeton.
    svc.TOKEN = "selftest-token"
    svc.ocr_page = lambda image: {"engine": "simulated", "blocks": [], "width": image.width}
    server = ThreadingHTTPServer(("127.0.0.1", 0), svc.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _request(base + "/health")
        check("/health public (sondes sans jeton)", status == 200 and payload.get("status") == "ok")
        status, _ = _request(base + "/v1/ocr/page", _png(32, 16))
        check("OCR sans jeton -> 401", status == 401)
        status, _ = _request(base + "/v1/ocr/page", _png(32, 16), token="mauvais")
        check("OCR mauvais jeton -> 401", status == 401)
        status, payload = _request(base + "/v1/ocr/page", _png(32, 16), token="selftest-token")
        check("OCR jeton valide -> 200", status == 200 and payload.get("width") == 32)
        status, payload = _request(base + "/v1/ocr/page", b"not a png", token="selftest-token")
        check("corps non PNG -> 422", status == 422 and payload.get("error") == "NOT_PNG")
        saved = svc.MAX_BODY_BYTES
        svc.MAX_BODY_BYTES = 10
        status, _ = _request(base + "/v1/ocr/page", _png(32, 16), token="selftest-token")
        svc.MAX_BODY_BYTES = saved
        check("corps trop grand -> 413", status == 413)
        status, _ = _request(base + "/v1/inconnu", _png(8, 8), token="selftest-token")
        check("route inconnue -> 404", status == 404)
    finally:
        server.shutdown()

    print(f"autotest ocr-surya : {'ÉCHEC ' + str(len(FAILURES)) if FAILURES else 'OK'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
