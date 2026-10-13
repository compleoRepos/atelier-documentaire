"""Non-French blocks returned verbatim by the model get ONE bounded retry.

Observed on the real corpus (DOC-001, identical request replayed): the model
returned English blocks unchanged. MockTransport only, no network.
"""

from __future__ import annotations

import json
import re

import httpx
import pytest
from test_interim_owner_authorization import SHA, options

from app.ai.translation.service import translate_blocks

# RUN27 F29: the guard refuses any digit absent from the source, so the fake
# translation must not copy the digits of the block id ("b1" -> "b-un").
_DIGIT_WORDS = ("zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf")


def _spelled(block_id: str) -> str:
    return re.sub(r"\d", lambda m: "-" + _DIGIT_WORDS[int(m.group())], block_id)


def _ir(blocks):
    return {
        "language": "en",
        "domain": "HR",
        "versions": {"source_sha256": SHA},
        "pages": [{"number": 1, "blocks": blocks}],
    }


def _response(pairs):
    content = json.dumps({"translations": [{"id": i, "text": t} for i, t in pairs]})
    return httpx.Response(
        200,
        json={
            "model": "gpt-5-mini",
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 10,
                "total_tokens": 130,
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
        },
    )


def _handler(seen, translate_on_retry: bool):
    def handler(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        blocks = json.loads(body["messages"][1]["content"])["blocks"]
        retry = "returned unchanged by a previous request" in system
        seen.append({"ids": [b["id"] for b in blocks], "retry": retry})
        if retry and translate_on_retry:
            return _response([(b["id"], f"Traduction {_spelled(b['id'])}.") for b in blocks])
        return _response([(b["id"], b["text"]) for b in blocks])  # verbatim echo

    return handler


ENGLISH = [
    {"id": "b1", "text": "Employment certificate", "language": "eng"},
    {"id": "b2", "text": "Nora has been employed as an assistant.", "language": "eng"},
]


@pytest.mark.asyncio
async def test_verbatim_non_french_blocks_are_retried_once_and_applied(tmp_path):
    seen: list[dict] = []
    result = await translate_blocks(
        _ir([dict(b) for b in ENGLISH]),
        options(tmp_path, httpx.MockTransport(_handler(seen, translate_on_retry=True))),
    )
    assert [s["retry"] for s in seen] == [False, True]
    assert seen[1]["ids"] == ["b1", "b2"]
    assert result["translations"] == {"b1": "Traduction b-un.", "b2": "Traduction b-deux."}
    retry = [i for i in result["issues"] if i["code"] == "UNCHANGED_TRANSLATION_RETRY"]
    assert retry and retry[0]["severity"] == "info" and retry[0]["blocks"] == 2
    assert not result["untranslated_blocks"]


@pytest.mark.asyncio
async def test_retry_is_bounded_and_verbatim_output_is_not_hidden(tmp_path):
    seen: list[dict] = []
    result = await translate_blocks(
        _ir([dict(b) for b in ENGLISH]),
        options(tmp_path, httpx.MockTransport(_handler(seen, translate_on_retry=False))),
    )
    assert len(seen) == 2  # exactly one retry, never a loop
    # Still verbatim: kept as source, so the pipeline's UNTRANSLATED check fires.
    assert result["translations"]["b1"] == "Employment certificate"
    assert result["translations"]["b2"] == ENGLISH[1]["text"]


@pytest.mark.asyncio
async def test_unknown_language_and_short_identifiers_are_not_retried(tmp_path):
    seen: list[dict] = []
    blocks = [
        {"id": "u1", "text": "Esimerkkilän kirjastopalvelu", "language": "unknown"},
        {"id": "c1", "text": "PL 46", "language": "eng"},
        {"id": "c2", "text": "Exempla", "language": "eng"},
    ]
    result = await translate_blocks(
        _ir(blocks), options(tmp_path, httpx.MockTransport(_handler(seen, translate_on_retry=True)))
    )
    assert len(seen) == 1
    assert not [i for i in result["issues"] if i["code"] == "UNCHANGED_TRANSLATION_RETRY"]


@pytest.mark.asyncio
async def test_entity_guard_rejection_is_not_retried_as_unchanged(tmp_path):
    """D26: an answer rejected by the entity guard is restored to the source;
    it must not be mistaken for a verbatim echo and re-sent (a second answer
    would bypass the guard decision while the critical issue stays recorded)."""
    seen: list[dict] = []
    blocks = [
        {"id": "n1", "text": "Monthly gross salary 1250 euros.", "language": "eng"},
        {"id": "e1", "text": "Employment certificate", "language": "eng"},
    ]

    def handler(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        sent = json.loads(body["messages"][1]["content"])["blocks"]
        retry = "returned unchanged by a previous request" in system
        seen.append({"ids": [b["id"] for b in sent], "retry": retry})
        out = []
        for b in sent:
            if b["id"] == "n1":
                out.append((b["id"], "Salaire mensuel brut 1350 euros."))  # number altered
            elif retry:
                out.append((b["id"], "Attestation d'emploi"))
            else:
                out.append((b["id"], b["text"]))  # verbatim echo
        return _response(out)

    result = await translate_blocks(_ir(blocks), options(tmp_path, httpx.MockTransport(handler)))
    assert [s["retry"] for s in seen] == [False, True]
    assert seen[1]["ids"] == ["e1"]  # only the verbatim echo is retried
    assert result["translations"]["n1"] == blocks[0]["text"]  # source kept
    assert result["translations"]["e1"] == "Attestation d'emploi"
    codes = [(i["code"], i.get("block_id")) for i in result["issues"]]
    assert ("PROTECTED_ENTITY_CHANGED", "n1") in codes
    assert "n1" in result["untranslated_blocks"]
