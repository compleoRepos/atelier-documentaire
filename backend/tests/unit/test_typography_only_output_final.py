"""D27: a typography-only variant of the source is not a translation.

Observed on the real corpus (run16): for non-French blocks the model returned
the source with only French typographic spacing (no-break space before ":",
space inserted before ";"). The strict comparison saw a translation, no
UNTRANSLATED issue was raised and the same foreign text was re-written over
the original. Synthetic data, MockTransport only, no network.
"""

from __future__ import annotations

import json

import httpx
import pytest
from test_interim_owner_authorization import options
from test_interim_unchanged_retry import _ir, _response

from app.ai.translation.service import translate_blocks
from app.ai.translation.typography import typography_equivalent
from app.documents.pipeline import evaluate_document

GERMAN = "Telefon : Kundenservice Nordstadt 42"


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("Telefon\u00a0: Kundenservice Nordstadt 42", True),  # no-break space
        ("Telefon\u202f: Kundenservice Nordstadt 42", True),  # narrow no-break space
        ("Telefon: Kundenservice  Nordstadt 42", True),  # spacing only
        ("TELEFON : KUNDENSERVICE NORDSTADT 42", True),  # case only
        ("Téléphone : service client Nordstadt 42", False),  # real translation
        ("Telefon : Kundenservice Nordstadt 43", False),  # digit changed
    ],
)
def test_typography_key_ignores_typography_only(variant, expected):
    assert typography_equivalent(GERMAN, variant) is expected


def test_quote_dash_and_semicolon_spacing_variants():
    assert typography_equivalent("Ort; 01/02/2025", "Ort ; 01/02/2025")
    assert typography_equivalent("\u201cGmbH\u201d \u2013 Abteilung", '"GmbH" - Abteilung')
    assert not typography_equivalent("Ort; 01/02/2025", "Lieu ; 01/02/2025")


def _handler(seen, translate_on_retry):
    def handler(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        sent = json.loads(body["messages"][1]["content"])["blocks"]
        retry = "returned unchanged by a previous request" in system
        seen.append({"ids": [b["id"] for b in sent], "retry": retry})
        if retry and translate_on_retry:
            # Translate the text actually sent, so protected-entity markers survive.
            return _response(
                [
                    (
                        b["id"],
                        b["text"]
                        .replace("Telefon", "Téléphone")
                        .replace("Kundenservice", "service client"),
                    )
                    for b in sent
                ]
            )
        return _response([(b["id"], b["text"].replace(" :", "\u00a0:")) for b in sent])

    return handler


BLOCK = {"id": "g1", "text": GERMAN, "language": "deu"}


@pytest.mark.asyncio
async def test_typography_only_answer_keeps_source_and_triggers_one_retry(tmp_path):
    seen: list[dict] = []
    result = await translate_blocks(
        _ir([dict(BLOCK)]),
        options(tmp_path, httpx.MockTransport(_handler(seen, translate_on_retry=False))),
    )
    assert [s["retry"] for s in seen] == [False, True]  # seen as unchanged -> one retry
    assert result["translations"]["g1"] == GERMAN  # exact source, never the variant
    codes = [i["code"] for i in result["issues"]]
    assert "TYPOGRAPHY_ONLY_OUTPUT_DISCARDED" in codes
    assert "UNCHANGED_TRANSLATION_RETRY" in codes


@pytest.mark.asyncio
async def test_real_translation_on_retry_is_applied(tmp_path):
    seen: list[dict] = []
    result = await translate_blocks(
        _ir([dict(BLOCK)]),
        options(tmp_path, httpx.MockTransport(_handler(seen, translate_on_retry=True))),
    )
    assert result["translations"]["g1"] == "Téléphone : service client Nordstadt 42"


def test_pipeline_flags_typography_only_variant_as_untranslated():
    ir = {
        "language": "deu",
        "pages": [
            {"number": 1, "blocks": [{"id": "g1", "text": GERMAN, "page": 1, "language": "deu"}]}
        ],
    }
    result = evaluate_document(ir, {"g1": GERMAN.replace(" :", "\u00a0:")})
    flagged = [i for i in result["issues"] if i["code"] == "UNTRANSLATED"]
    assert flagged and flagged[0]["block_id"] == "g1"
    assert result["status"] == "REVIEW_REQUIRED"
