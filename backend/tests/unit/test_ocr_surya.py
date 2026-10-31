"""OCR Surya (défaut produit) : client, géométrie de lignes, réglages et pipeline.

Aucun test n'appelle un vrai modèle : le service est simulé par
``httpx.MockTransport``. La recette sur le vrai service local est séparée.
"""

from __future__ import annotations

import io
import json

import httpx
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.ai.ocr import surya_client as sc

LINES = [
    "DOCUMENT SYNTHETIQUE DE TEST",
    "Montant net 1 234,56 EUR",
    "IBAN FR76 3000 6000 0112 3456 7890 189",
]


def _page_image(lines=LINES, size=(900, 360)):
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for i, text in enumerate(lines):
        draw.text((40, 60 + i * 80), text, fill="black", font_size=28)
    return image


def _ink_box(image):
    gray = np.asarray(image.convert("L"))
    ys, xs = np.nonzero(gray < 128)
    return [float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)]


def _payload(image, blocks):
    return {
        "engine": "surya-ocr",
        "engine_version": "0.0-test",
        "model": "surya-ocr-test",
        "image_size": [image.width, image.height],
        "seconds": 0.01,
        "blocks": blocks,
    }


class FakeService:
    """Service OCR simulé : renvoie le texte connu, calcule la boîte depuis l'encre reçue."""

    def __init__(self, lines=LINES, block_text="FR76 3000 6000 0112 3456 7890 189", capped=False):
        self.lines, self.block_text, self.capped = lines, block_text, capped
        self.calls: list[str] = []
        self.headers: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.path)
        self.headers.append(dict(request.headers))
        image = Image.open(io.BytesIO(request.content))
        if request.url.path == "/v1/ocr/block":
            return httpx.Response(
                200,
                json={
                    "engine": "surya-ocr",
                    "text": self.block_text,
                    "capped": self.capped,
                    "confidence": 0.99,
                },
            )
        block = {
            "label": "Text",
            "bbox": _ink_box(image),
            "reading_order": 0,
            "confidence": 0.97,
            "skipped": False,
            "error": False,
            "kind": "text",
            "rows": [],
            "lines": list(self.lines),
        }
        return httpx.Response(200, json=_payload(image, [block]))


def _client(handler, **kw):
    return sc.SuryaOCRClient(
        "http://127.0.0.1:8092",
        allowed_hosts=["127.0.0.1"],
        transport=httpx.MockTransport(handler),
        **kw,
    )


# --------------------------------------------------------------------------- URL


@pytest.mark.parametrize(
    "url,code",
    [
        (None, "OCR_SURYA_URL_REQUIRED"),
        ("ftp://127.0.0.1/x", "OCR_SURYA_URL_INVALID"),
        ("http://u:p@127.0.0.1:8092", "OCR_SURYA_URL_INVALID"),
        ("http://127.0.0.1:8092/?k=v", "OCR_SURYA_URL_INVALID"),
        ("http://ocr.example:8092", "OCR_SURYA_HOST_NOT_ALLOWED"),
    ],
)
def test_url_refused(url, code):
    with pytest.raises(sc.SuryaOCRError, match=code):
        sc.validated_url(url, ["127.0.0.1"])


def test_url_allowed_trailing_slash_removed():
    assert sc.validated_url("http://127.0.0.1:8092/", ["127.0.0.1"]) == "http://127.0.0.1:8092"


# --------------------------------------------------------------------- Géométrie


def test_ink_bands_lines_rule_and_diacritic():
    gray = np.full((200, 400), 255, dtype=np.uint8)
    gray[20:40, 10:300] = 0  # ligne 1
    gray[14:16, 50:60] = 0  # accent isolé au-dessus de la ligne 1 (bande mince)
    gray[70:90, 10:250] = 0  # ligne 2
    gray[110:112, :] = 0  # filet horizontal pleine largeur (ignoré)
    gray[140:160, 30:200] = 0  # ligne 3
    bands = sc.ink_bands(gray)
    assert len(bands) == 3
    assert bands[0][1] == 14 and bands[0][3] == 40  # accent fusionné avec sa ligne
    assert [b[0] for b in bands] == [10, 10, 30]


def test_ink_bands_ignore_thin_vertical_rules():
    gray = np.full((200, 400), 255, dtype=np.uint8)
    for y in (20, 80, 140):
        gray[y : y + 20, 20:180] = 0
        gray[y : y + 20, 220:380] = 0
    gray[:, 2:4] = 0  # filet vertical gauche (grille)
    gray[:, 199:201] = 0  # filet vertical central
    bands = sc.ink_bands(gray)
    assert [(b[1], b[3]) for b in bands] == [(20, 40), (80, 100), (140, 160)]
    assert bands[0][0] == 20 and bands[0][2] == 380  # filets exclus de l'étendue


def test_ink_bands_single_line_keeps_full_height_stems():
    gray = np.full((30, 200), 255, dtype=np.uint8)
    gray[:, 5:7] = 0  # fût de glyphe pleine hauteur en début de ligne
    gray[8:30, 10:190] = 0
    bands = sc.ink_bands(gray)
    assert len(bands) == 1 and bands[0][0] == 5


def test_allocate_exact_when_counts_match():
    bands = [[0, 0, 100, 10], [0, 20, 80, 30]]
    lines, estimated = sc.allocate_lines(["a b", "c"], bands, [0, 0, 100, 30])
    assert not estimated and [t for t, _ in lines] == ["a b", "c"] and lines[1][1] == bands[1]


def test_allocate_wrapped_paragraph_never_cuts_words():
    text = "Le salarié perçoit une rémunération mensuelle brute de trois mille euros versée chaque mois"
    bands = [[0, 0, 300, 10], [0, 15, 300, 25], [0, 30, 120, 40]]
    lines, estimated = sc.allocate_lines([text], bands, [0, 0, 300, 40])
    assert estimated and len(lines) == 3
    assert (
        " ".join(t for t, _ in lines).split() == text.split()
    )  # aucun mot perdu, coupé ou réordonné
    assert all(t.strip() for t, _ in lines)


def test_allocate_fewer_bands_splits_box_evenly():
    lines, estimated = sc.allocate_lines(["a", "b", "c"], [[0, 0, 10, 10]], [0, 0, 90, 30])
    assert estimated and [round(b[1]) for _, b in lines] == [0, 10, 20]


def test_table_block_produces_cells():
    gray = np.full((100, 300), 255, dtype=np.uint8)
    for y in (10, 60):
        gray[y : y + 20, 10:80] = 0
        gray[y : y + 20, 180:260] = 0
    gray[:, 130:132] = 0  # filet vertical de grille entre les deux colonnes
    page = {
        "blocks": [
            {
                "bbox": [0, 0, 300, 100],
                "kind": "table",
                "rows": [["Nom", "Montant"], ["Ligne A", "4 321"]],
                "lines": [],
                "confidence": 0.9,
            }
        ]
    }
    blocks, stats = sc.page_to_line_blocks(page, gray)
    assert [b["text"] for b in blocks] == ["Nom", "Montant", "Ligne A", "4 321"]
    assert stats["table_cells"] == 4
    assert blocks[0]["bbox"][2] <= 100 and blocks[1]["bbox"][0] >= 150  # colonnes à l'encre


def test_skipped_and_error_blocks():
    gray = np.full((50, 50), 255, dtype=np.uint8)
    page = {
        "blocks": [
            {"bbox": [0, 0, 50, 50], "skipped": True, "lines": ["x"]},
            {"bbox": [0, 0, 50, 50], "error": True, "lines": ["texte partiel"], "confidence": 0.2},
        ]
    }
    blocks, stats = sc.page_to_line_blocks(page, gray)
    assert (
        stats["skipped"] == 1
        and stats["errors"] == 1
        and [b["text"] for b in blocks] == ["texte partiel"]
    )


# ------------------------------------------------------------------------ Client


def test_image_to_blocks_contract_and_warnings():
    service = FakeService()
    result = _client(service, token="t0k").image_to_blocks(_page_image())
    assert (
        result.backend == "surya" and result.used_languages == [] and result.version == "0.0-test"
    )
    assert [b["text"] for b in result.blocks] == LINES
    assert all(len(b["bbox"]) == 4 and b["confidence"] == 0.97 for b in result.blocks)
    codes = {w["code"] for w in result.warnings}
    assert "OCR_ORIENTATION_NOT_CHECKED" in codes
    assert service.headers[0]["authorization"] == "Bearer t0k"
    assert service.headers[0]["content-type"] == "image/png"


def test_low_confidence_reported_as_uncertainty():
    class Low(FakeService):
        def __call__(self, request):
            response = super().__call__(request)
            data = json.loads(response.content)
            data["blocks"][0]["confidence"] = 0.4
            return httpx.Response(200, json=data)

    result = _client(Low()).image_to_blocks(_page_image())
    assert result.uncertainties and all(
        u["code"] == "OCR_LOW_CONFIDENCE" for u in result.uncertainties
    )


@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.Response(502, json={"error": "OCR_FAILED"}), "OCR_SURYA_HTTP_502"),
        (httpx.Response(200, content=b"not json"), "OCR_SURYA_BAD_RESPONSE"),
        (httpx.Response(200, json={"engine": "other"}), "OCR_SURYA_BAD_RESPONSE"),
    ],
)
def test_service_errors_fail_closed(response, code):
    with pytest.raises(sc.SuryaOCRError, match=code):
        _client(lambda request: response).image_to_blocks(_page_image())


def test_unreachable_service_fails_closed():
    def boom(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(sc.SuryaOCRError, match="OCR_SURYA_UNAVAILABLE"):
        _client(boom).image_to_blocks(_page_image())


def test_size_mismatch_refused():
    def handler(request):
        return httpx.Response(
            200, json={**_payload(Image.new("RGB", (10, 10)), []), "engine": "surya-ocr"}
        )

    with pytest.raises(sc.SuryaOCRError, match="OCR_SURYA_SIZE_MISMATCH"):
        _client(handler).image_to_blocks(_page_image())


def test_line_reader_inconclusive_cases():
    assert _client(FakeService(block_text="X")).line_reader(_page_image(["X"], (60, 40))) == "X"
    assert _client(FakeService(capped=True)).line_reader(_page_image(["X"], (60, 40))) is None

    def down(request):
        raise httpx.ConnectError("refused")

    assert _client(down).line_reader(_page_image(["X"], (60, 40))) is None


def test_adjust_options_single_read_without_orientation():
    out = _client(FakeService()).adjust_options({"preprocessing_max_variants": 6, "x": 1})
    assert (
        out["preprocessing_max_variants"] == 1
        and out["preprocessing_orientation"] is False
        and out["x"] == 1
    )


# ----------------------------------------------------------------------- Réglages


def _settings(**kw):
    from app.core.settings import Settings

    return Settings(**kw)


def test_default_backend_is_surya_and_hosts_parsed():
    s = _settings(ocr_backend="surya", surya_ocr_url="http://127.0.0.1:8092")
    assert s.ocr_backend == "surya" and "127.0.0.1" in s.surya_hosts


@pytest.mark.parametrize(
    "kw,fragment",
    [
        ({"surya_ocr_url": "http://ocr.example:8092"}, "ALLOWED_HOSTS"),
        ({"surya_ocr_url": "http://u:p@127.0.0.1:8092"}, "identifiants"),
    ],
)
def test_settings_refuse_bad_url(kw, fragment):
    with pytest.raises(ValueError, match=fragment):
        _settings(ocr_backend="surya", **kw)


PROD = {
    "environment": "production",
    "engine": "private",
    "storage_backend": "s3",
    "execution_mode": "celery",
    "database_url": "postgresql+psycopg://app@db.internal/app",
    "auto_create_schema": False,
    "jwt_secret": "s" * 64,
    "auth_mode": "cookie",
    "cookie_secure": True,
    "av_scan_enabled": True,
    "metrics_token": "m" * 32,
    "private_ai_base_url": "https://llm.internal/v1",
    "s3_endpoint_url": "https://s3.internal",
    "private_ai_model": "modele-prive",
    "private_ai_model_version": "1",
    "tokenizer_path": "/opt/tokenizer",
    "private_ai_allowed_hosts": "llm.internal",
    "allowed_origins": "https://atelier.example",
    "ocr_backend": "surya",
    "surya_ocr_url": "https://ocr.internal",
    "surya_ocr_allowed_hosts": "ocr.internal",
    "surya_weights_license_acknowledged": True,
}


def test_production_valid_with_surya_requirements():
    s = _settings(**PROD)
    assert s.ocr_backend == "surya" and s.surya_weights_license_acknowledged


@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"surya_ocr_url": None}, "TRANSLATOR_SURYA_OCR_URL requis"),
        ({"surya_weights_license_acknowledged": False}, "licence des poids Surya"),
        ({"surya_ocr_url": "http://ocr.internal"}, "HTTPS requis"),
    ],
)
def test_production_refuses_missing_surya_requirement(override, fragment):
    with pytest.raises(ValueError, match=fragment):
        _settings(**{**PROD, **override})


def test_production_tesseract_needs_no_surya_settings():
    s = _settings(
        **{
            **PROD,
            "ocr_backend": "tesseract",
            "surya_ocr_url": None,
            "surya_weights_license_acknowledged": False,
        }
    )
    assert s.ocr_backend == "tesseract"


# ------------------------------------------------------------------------ Pipeline


_TESSERACT_ENTRY_POINTS = (
    "image_to_data",
    "image_to_string",
    "image_to_osd",
    "image_to_boxes",
    "get_languages",
    "get_tesseract_version",
    "run_and_get_output",
)


@pytest.fixture
def poisoned_tesseract(monkeypatch):
    pytesseract = pytest.importorskip("pytesseract")
    calls: list[str] = []
    for name in _TESSERACT_ENTRY_POINTS:
        for module in (pytesseract, pytesseract.pytesseract):
            if hasattr(module, name):

                def fake(*args, _name=name, **kwargs):
                    calls.append(_name)
                    raise RuntimeError("TESSERACT_FORBIDDEN_IN_SURYA_MODE")

                monkeypatch.setattr(module, name, fake)
    return calls


@pytest.fixture
def surya_env(monkeypatch):
    from app.core.settings import get_settings

    monkeypatch.setenv("TRANSLATOR_OCR_BACKEND", "surya")
    monkeypatch.setenv("TRANSLATOR_SURYA_OCR_URL", "http://127.0.0.1:8092")
    get_settings.cache_clear()
    service = FakeService()
    monkeypatch.setattr(sc.SuryaOCRClient, "transport_override", httpx.MockTransport(service))
    yield service
    get_settings.cache_clear()


def test_pipeline_default_is_surya_without_any_tesseract_call(
    tmp_path, surya_env, poisoned_tesseract
):
    from app.documents.pipeline import analyze_document

    image = tmp_path / "scan.png"
    _page_image().save(image)
    ir = analyze_document(
        str(image), str(tmp_path / "work")
    )  # aucun moteur imposé : défaut configuré
    blocks = [b for p in ir["pages"] for b in p["blocks"]]
    assert blocks and all(str(b.get("provenance", "")).startswith("ocr:surya") for b in blocks)
    text = " ".join(b.get("text", "") for b in blocks)
    for line in LINES:
        assert all(word in text for word in line.split())
    assert (
        surya_env.calls.count("/v1/ocr/page") == 1
    )  # une seule lecture par page (pas de variantes)
    assert poisoned_tesseract == [], (
        f"Tesseract appelé en mode Surya : {sorted(set(poisoned_tesseract))}"
    )
    codes = {w.get("code") for w in ir.get("warnings", [])}
    assert "OCR_ORIENTATION_NOT_CHECKED" in codes
    verification = ir.get("line_verification") or {}
    assert verification.get("status") != "NOT_EXECUTED"
    assert verification.get("ocr_recovery_disabled_blocks", 0) >= 1


def test_pipeline_explicit_tesseract_unchanged_kwargs():
    from app.documents.pipeline import _line_verification_kwargs

    ir = {"pages": [{"blocks": [{"provenance": "ocr:tesseract"}, {"provenance": "native"}]}]}
    assert _line_verification_kwargs(ir) == {}


def test_unknown_backend_still_refused():
    from app.documents.pipeline import _make_ocr

    with pytest.raises(ValueError, match="inconnu"):
        _make_ocr({"ocr_backend": "cloud-ocr"})


def test_unreachable_service_fails_document_without_fallback(tmp_path, monkeypatch):
    """Service injoignable : l'analyse échoue explicitement, Tesseract n'est jamais appelé."""
    from PIL import Image, ImageDraw

    from app.ai.ocr import surya_client as sc
    from app.core.settings import get_settings
    from app.documents import pipeline

    monkeypatch.setenv("TRANSLATOR_OCR_BACKEND", "surya")
    monkeypatch.setenv("TRANSLATOR_SURYA_OCR_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()
    calls = []
    import pytesseract

    for name in ("image_to_data", "image_to_string", "image_to_osd"):
        monkeypatch.setattr(pytesseract, name, lambda *a, _n=name, **k: calls.append(_n))
    image = Image.new("RGB", (900, 600), "white")
    ImageDraw.Draw(image).text((80, 80), "Synthetic unreachable engine page", fill="black")
    source = tmp_path / "scan.png"
    image.save(source)
    try:
        with pytest.raises(sc.SuryaOCRError, match="OCR_SURYA_UNAVAILABLE"):
            pipeline.analyze_document(str(source), str(tmp_path), {})
    finally:
        get_settings.cache_clear()
    assert calls == []
