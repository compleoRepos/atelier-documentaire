"""RUN28 regression tests (synthetic data only, no corpus text).

F35 — reference lines. RUN27 MV-01: an address line and a line of legal
identifiers of a French letterhead were detected as a foreign language, sent
"FR->FR" to the model and re-rendered from a faulty OCR reading: an
identifier changed in the final PDF. Such lines are now recognised before
sending (strong anchors only) and keep their original pixels, with an explicit
status; a first, broader rule was rejected because it captured translatable
headings, page numbers, dates and compound words (cases pinned below).
"""

from __future__ import annotations

import httpx
import pytest
from test_interim_owner_authorization import options
from test_interim_unchanged_retry import _handler, _ir

from app.documents import language_evidence as le
from app.documents.block_status import classify_blocks

pytestmark = pytest.mark.skipif(not le.available(), reason="wordfreq lexicon not installed")

LANGS = ["fra", "eng", "spa", "deu", "nld"]


@pytest.mark.parametrize(
    "text",
    [
        "RC: 98765 — Patente : 11223344 — CNSS: 5566778 — IF: 99887766",
        "RIB: 123450000099900000777 — ICE : 000999888000011",
        "Résidence Atrium K3 Rue Ibnou Khaldoun",
        "Nordwind Logistik Deutschland GmbH",
        "Blue Harbor Trading Ltd",
        "ACME IBERIA SERVICIOS S. L.",
    ],
)
def test_reference_lines_are_recognised_before_sending(text):
    result = le.reference_line(text, "spa", LANGS, "pre_send")
    assert result is not None and result["rule"] == "reference_line"
    assert result["version"] == le.REFERENCE_VERSION


@pytest.mark.parametrize(
    "text",
    [
        "1. EMPLOYMENT",  # numbered heading: translate
        "Página 2 de 7",  # page number: translate
        "Date: 3 March 2021",  # date with a month name: translate
        "Fietsenstallingsreglement",  # Dutch compound word rare in the lexicon
        "zonnige middagen buiten",  # lowercase phrase
        "P.O. Box 12",  # "Box" is a translatable word
        "Telefon +49 30 1234567",  # translatable label
        "TERMS AS AGREED 2024",  # "AS" is not a final legal form here
        "salaire de base 2500",  # lowercase phrase with a number
        "شركة النور SARL",  # non-Latin: a decision is needed, translate
        "Bank Statement",  # translatable title
    ],
)
def test_translatable_lines_are_never_taken_for_reference_lines(text):
    assert le.reference_line(text, "eng", LANGS, "pre_send") is None


def test_conservative_refusal_a_name_common_in_a_foreign_language_is_translated():
    """Documented limitation: "Sina" is common in German, so the address is
    not recognised and is translated as before (safe default, no omission)."""
    assert le.reference_line("Résidence Atrium K3 Rue Ibnou Sina", "spa", LANGS) is None


def test_returned_unchanged_level_is_broader_but_never_used_before_sending():
    for text, rule in [
        ("www.example-shop.de", "returned_unchanged_reference"),
        ("SW1A 2AA", "returned_unchanged_reference"),
        ("Zbigniew Kowalczyk", "returned_unchanged_proper_name"),
    ]:
        assert le.reference_line(text, "eng", LANGS, "pre_send") is None
        assert le.reference_line(text, "eng", LANGS, "returned_unchanged")["rule"] == rule
    assert le.reference_line("Bank Statement", "eng", LANGS, "returned_unchanged") is None
    assert le.reference_line("x", "eng", LANGS, "unknown_mode") is None


def test_without_lexicon_nothing_is_preserved(monkeypatch):
    monkeypatch.setattr(le, "_lexicon", lambda: None)
    assert le.reference_line("Nordwind Logistik Deutschland GmbH", "deu", LANGS) is None


def test_analysis_flags_reference_lines_idempotently_and_never_french_blocks():
    ir = {
        "languages": LANGS,
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {
                        "id": "r1",
                        "text": "Résidence Atrium K3 Rue Ibnou Khaldoun",
                        "language": "spa",
                    },
                    {"id": "t1", "text": "1. EMPLOYMENT", "language": "eng"},
                    {"id": "f1", "text": "Société Nordwind GmbH", "language": "fra"},
                    {"id": "p1", "text": "Blue Harbor Trading Ltd", "protected": True},
                ],
            }
        ],
    }
    for _ in range(2):  # idempotent
        stats = le.refine_block_languages(ir)
        flagged = [b["id"] for b in ir["pages"][0]["blocks"] if b.get("reference_line")]
        assert flagged == ["r1"] and stats["reference_lines"] == 1
    ir["pages"][0]["blocks"][0]["text"] = "Employment contract"
    le.refine_block_languages(ir)
    assert "reference_line" not in ir["pages"][0]["blocks"][0]


@pytest.mark.asyncio
async def test_reference_line_is_not_sent_and_keeps_its_source_with_explicit_trace(tmp_path):
    seen: list[dict] = []
    reference = le.reference_line("Résidence Atrium K3 Rue Ibnou Khaldoun", "spa", LANGS)
    blocks = [
        {"id": "r1", "text": "Résidence Atrium K3 Rue Ibnou Khaldoun", "language": "spa"},
        {"id": "w1", "text": "Employment certificate", "language": "eng"},
    ]
    blocks[0]["reference_line"] = reference
    result = await translate_blocks_mock(blocks, seen, tmp_path)
    assert seen and all(request["ids"] == ["w1"] for request in seen)
    assert result["translations"]["r1"] == "Résidence Atrium K3 Rue Ibnou Khaldoun"
    kept = [i for i in result["issues"] if i["code"] == "REFERENCE_LINE_KEPT"]
    assert [i["block_id"] for i in kept] == ["r1"] and kept[0]["severity"] == "info"
    provenance = result["translation_telemetry"]["block_provenance"]["blocks"]
    assert provenance["r1"] == {"origin": "NOT_SENT"}
    assert provenance["w1"]["origin"] == "MODEL_CALL"


async def translate_blocks_mock(blocks, seen, tmp_path):
    from app.ai.translation.service import translate_blocks

    return await translate_blocks(
        _ir(blocks), options(tmp_path, httpx.MockTransport(_handler(seen, translate_on_retry=True)))
    )


def _status(block, target, issues=None):
    ir = {"languages": LANGS, "pages": [{"number": 1, "blocks": [block]}]}
    return classify_blocks(ir, {block["id"]: target}, issues or [])["blocks"][block["id"]]


def test_block_status_reports_reference_lines_explicitly():
    text = "Résidence Atrium K3 Rue Ibnou Khaldoun"
    flagged = {"id": "r1", "text": text, "language": "spa", "reference_line": {"rule": "x"}}
    assert (_status(flagged, text)["status"], _status(flagged, text)["reason"]) == (
        "PRESERVED_INTENTIONALLY",
        "reference_line",
    )
    # an unreliable OCR reading stays uncertain, even on a reference line
    uncertain = {**flagged, "ocr_unreliable": True}
    assert _status(uncertain, text)["status"] == "UNCERTAIN"
    # returned verbatim by the model: kept rightly only for a reference line
    url = {"id": "u1", "text": "www.example-shop.de", "language": "eng"}
    assert _status(url, "www.example-shop.de")["reason"] == "reference_returned_unchanged"
    title = {"id": "t1", "text": "Bank Statement", "language": "eng"}
    assert _status(title, "Bank Statement") == {
        "page": 1,
        "status": "FAILED",
        "reason": "model_returned_source",
        "chars": len("Bank Statement"),
    }


def test_translation_memory_never_reapplies_a_cached_target_to_a_reference_line():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
    from interim_owner_corpus_run import _hit_invalidation

    block = {
        "id": "r1",
        "text": "Résidence Atrium K3 Rue Ibnou Khaldoun",
        "reference_line": {"rule": "reference_line"},
    }
    assert _hit_invalidation(block, "Résidence Atrium K3 Rue Ibnou Khaldoun", set()) == (
        "not_sent_by_current_service"
    )
    plain = {"id": "w1", "text": "Employment certificate"}
    assert _hit_invalidation(plain, "Attestation d'emploi", set()) is None


# --------------------------------------------------------------------------
# F39 — incomplete translations. DOC-008 (run27b): a bilingual footer came
# back as "French + German copied verbatim" and counted as translated. One
# targeted retry; a block still partial keeps its source, explicitly.
# Invented German sentence (no corpus text).

DE_SOURCE = "Bescheinigung der Mitgliedschaft — Mitglied des Vereins seit dem letzten Jahr beim Amt"
DE_PARTIAL = "Attestation d'adhésion — Mitglied des Vereins seit dem letzten Jahr beim Amt"
DE_FULL = "Attestation d'adhésion — adhérent du cercle depuis l'an dernier auprès du service"


def test_partial_copy_of_a_foreign_segment_is_detected():
    assert le.copied_source_words(DE_SOURCE, DE_PARTIAL, LANGS, "deu") >= le.PARTIAL_MIN_FOREIGN
    assert le.partial_source_copy(DE_SOURCE, DE_PARTIAL, LANGS, "deu")
    assert not le.partial_source_copy(DE_SOURCE, DE_FULL, LANGS, "deu")
    # a block returned whole and unchanged is the unchanged-retry's business
    assert not le.partial_source_copy(DE_SOURCE, DE_SOURCE, LANGS, "deu")


@pytest.mark.parametrize(
    ("source", "target", "language"),
    [
        # proper names kept on purpose (capitalised, non-German source)
        (
            "Blue Harbor Trading Limited, Harbour Road 12, Bristol, a Northwind Group company",
            "Blue Harbor Trading Limited, Harbour Road 12, Bristol, une société du groupe Northwind",
            "eng",
        ),
        # an official title in capitals kept in the original language
        (
            "según el CONVENIO COLECTIVO ESTATAL DE SEGURIDAD PRIVADA vigente",
            "selon le CONVENIO COLECTIVO ESTATAL DE SEGURIDAD PRIVADA en vigueur",
            "spa",
        ),
        # shared words only (French too) are not evidence
        ("Total des frais de transport", "Total des frais de transport inclus", "eng"),
    ],
)
def test_names_titles_and_shared_words_are_not_partial_translations(source, target, language):
    assert not le.partial_source_copy(source, target, LANGS, language)


def test_without_lexicon_no_partial_decision(monkeypatch):
    monkeypatch.setattr(le, "available", lambda: False)
    assert le.copied_source_words(DE_SOURCE, DE_PARTIAL, LANGS, "deu") is None
    assert not le.partial_source_copy(DE_SOURCE, DE_PARTIAL, LANGS, "deu")


def _partial_handler(seen, fix_on_retry: bool):
    import json as _json

    def handler(request):
        body = _json.loads(request.content)
        system = body["messages"][0]["content"]
        blocks = _json.loads(body["messages"][1]["content"])["blocks"]
        retry = "left part of the source text untranslated" in system
        seen.append({"ids": [b["id"] for b in blocks], "partial_retry": retry})
        out = []
        for b in blocks:
            if b["id"] == "g1":
                out.append((b["id"], DE_FULL if retry and fix_on_retry else DE_PARTIAL))
            else:
                out.append((b["id"], "Certificat de travail"))
        from test_interim_unchanged_retry import _response

        return _response(out)

    return handler


GERMAN_BLOCKS = [
    {"id": "g1", "text": DE_SOURCE, "language": "deu"},
    {"id": "w1", "text": "Employment certificate", "language": "eng"},
]


async def _run_partial(tmp_path, fix_on_retry):
    from app.ai.translation.service import translate_blocks

    seen: list[dict] = []
    result = await translate_blocks(
        _ir([dict(b) for b in GERMAN_BLOCKS]),
        options(tmp_path, httpx.MockTransport(_partial_handler(seen, fix_on_retry))),
    )
    return seen, result


@pytest.mark.asyncio
async def test_partial_translation_is_retried_once_and_applied_when_fixed(tmp_path):
    seen, result = await _run_partial(tmp_path, fix_on_retry=True)
    assert [s["partial_retry"] for s in seen] == [False, True]
    assert seen[1]["ids"] == ["g1"]  # only the partial block, not its neighbour
    assert result["translations"]["g1"] == DE_FULL
    assert result["translations"]["w1"] == "Certificat de travail"
    codes = [i["code"] for i in result["issues"]]
    assert "PARTIAL_TRANSLATION_RETRY" in codes
    assert "PARTIAL_TRANSLATION_SOURCE_COPIED" not in codes
    assert "g1" not in (result.get("untranslated_blocks") or [])
    provenance = result["translation_telemetry"]["block_provenance"]["blocks"]
    assert provenance["g1"]["origin"] == "MODEL_CALL" and provenance["g1"]["outcome"] == "CHANGED"


@pytest.mark.asyncio
async def test_partial_translation_still_partial_keeps_the_source_for_review(tmp_path):
    seen, result = await _run_partial(tmp_path, fix_on_retry=False)
    assert [s["partial_retry"] for s in seen] == [False, True]  # bounded: one retry only
    assert result["translations"]["g1"] == DE_SOURCE  # never the partial text
    refused = [i for i in result["issues"] if i["code"] == "PARTIAL_TRANSLATION_SOURCE_COPIED"]
    assert [i["block_id"] for i in refused] == ["g1"] and refused[0]["severity"] == "error"
    assert "g1" in result["untranslated_blocks"]
    assert result["translations"]["w1"] == "Certificat de travail"
    block = dict(GERMAN_BLOCKS[0])
    status = _status(block, result["translations"]["g1"], result["issues"])
    assert (status["status"], status["reason"]) == ("FAILED", "partial_translation")


def test_translation_memory_resends_a_cached_partial_target():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
    from interim_owner_corpus_run import _hit_invalidation

    block = {"id": "g1", "text": DE_SOURCE, "language": "deu"}
    assert _hit_invalidation(block, DE_PARTIAL, set()) == "partial_source_copy"
    assert _hit_invalidation(block, DE_FULL, set()) is None
    assert (
        _hit_invalidation(block, DE_SOURCE, {"PARTIAL_TRANSLATION_SOURCE_COPIED"})
        == "previous_guard_rejection"
    )
